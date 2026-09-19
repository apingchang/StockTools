"""
stocktool.paper_catchup - 模擬買賣的「補跑到今天」邏輯
=====================================================

【V1.2.0-paper-trading】

設計：
- 從 last_run_date + 1 開始、逐個交易日推進到 today
- 每個交易日呼叫 evaluate_portfolio_one_day 或 evaluate_ai_portfolio_one_day
- 抓真實歷史收盤價（從既有 export_excel cache 或 fetch_market）

被依賴：StockTool.py / tab_paper.py
依賴：paper_trading.py / paper_engine.py / fetch_market.py / export_excel.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import pandas as pd

from . import paper_trading as pt
from . import paper_engine as pe


# ==========================================================
# 工具：產生交易日清單（簡化版：跳過週末、其餘當交易日）
# ==========================================================

def _list_trade_dates(start_date: str, end_date: str) -> List[str]:
    """從 start 到 end 的所有日期（簡化版、跳過週末）
    TODO 之後接 TWSE 行事曆、排除國定假日 / 半日市
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if end < start:
        return []
    out = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 週一到週五
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


# ==========================================================
# 抓歷史收盤價（簡化版：從既有 cache 讀）
# ==========================================================

def _get_historical_prices(
    session,
    cfg,
    codes: List[str],
    trade_date: str,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Dict]:
    """
    從 cache/history 抓 trade_date 的收盤價

    回傳 {code: {price, name, ...}}
    若該日無資料 → 該檔不出現在 dict 中
    """
    out: Dict[str, Dict] = {}
    if not codes:
        return out

    from .export_excel import get_history_file
    from .cache import load_cache

    # 2026-08-20 bug fix：cache 實際放的是 cfg.history_months (預設 60)
    # 之前寫死 12 → *_12m.xlsx 不存在 → 整個 stock_data 空 → 28 天全部 skip
    # 修法：依序嘗試 cfg.history_months / 60 / 12 (相容舊 cache)
    months_to_try = []
    if cfg is not None and hasattr(cfg, 'history_months') and cfg.history_months:
        months_to_try.append(int(cfg.history_months))
    for m in (60, 12):
        if m not in months_to_try:
            months_to_try.append(m)

    import os as _os
    from .export_excel import get_stock_history  # 2026-08-20: 過舊 cache auto-refresh

    for code in codes:
        try:
            fp = None
            used_months = None
            for m in months_to_try:
                cand = get_history_file(code, m)
                if _os.path.exists(cand):
                    fp = cand
                    used_months = m
                    break

            df = None
            cache_max_str = ""
            if fp is not None:
                df, _, _ = load_cache(fp)
                if df is not None and not df.empty and "Date" in df.columns:
                    try:
                        cache_max_str = pd.to_datetime(df["Date"]).max().strftime("%Y-%m-%d")
                    except Exception:
                        cache_max_str = ""

            # === 2026-08-20 新增：cache 過舊時 auto-refresh ===
            # 條件：fp 不存在 OR cache_max < trade_date
            # 沒 session 就 graceful skip (test / PyCharm 開發模式也支援)
            need_refresh = (
                fp is None or  # 完全沒 cache
                (cache_max_str and cache_max_str < trade_date)  # cache 過舊
            )
            if need_refresh:
                if session is None:
                    # 沒 session → graceful skip
                    if logger:
                        logger.warning(
                            f"[catchup] {code} cache 過舊 (max={cache_max_str}) "
                            f"且無 session、跳過 {trade_date}"
                        )
                    continue
                # 決定 refresh 用幾幾個月 (used_months from existing cache, else cfg, else default 60)
                refresh_months = used_months
                if refresh_months is None:
                    if cfg is not None and hasattr(cfg, "history_months") and cfg.history_months:
                        refresh_months = int(cfg.history_months)
                    else:
                        refresh_months = 60
                try:
                    # get_stock_history: load → update_stock_history (or init if no cache) → save_cache → return df
                    df = get_stock_history(session, cfg, code, logger, refresh_months)
                except Exception as e:
                    if logger:
                        logger.warning(f"[catchup] {code} refresh 失敗: {e}")
                    continue

            if df is None or df.empty:
                continue
            # 找對應日期
            date_col = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)
            if not date_col:
                continue
            df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
            row = df[df[date_col] == trade_date]
            if row.empty:
                continue
            r = row.iloc[0]
            close_col = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
            price = float(r.get(close_col) or 0) if close_col else 0.0
            if price <= 0:
                continue

            # 技術指標（以 trade_date 及之前的歷史日 K 計算）
            rsi = None
            ma20_slope = None
            sub_df = df[df[date_col] <= trade_date].sort_values(date_col)
            if len(sub_df) >= 20:
                ma20_curr = float(sub_df[close_col].tail(20).mean())
                prev_len = min(25, len(sub_df))
                ma20_prev = float(sub_df[close_col].iloc[-prev_len:-5].mean()) if prev_len > 5 else ma20_curr
                ma20_slope = round(ma20_curr - ma20_prev, 4)
            if len(sub_df) >= 15:
                delta = sub_df[close_col].diff()
                gain = float(delta.clip(lower=0).tail(14).mean())
                loss = float((-delta.clip(upper=0)).tail(14).mean())
                if loss == 0 or pd.isna(loss):
                    rsi = 100.0 if gain > 0 else 50.0
                else:
                    rs = gain / loss
                    rsi = round(100.0 - (100.0 / (1.0 + rs)), 1)

            stock_name = pt.get_stock_name(code) or str(r.get("Name", code))
            out[code] = {
                "code": code,
                "name": stock_name,
                "price": price,
                "rsi": rsi,
                "ma20_slope": ma20_slope,
            }
        except Exception as e:
            if logger:
                logger.warning(f"[catchup] {code} @ {trade_date} 抓取失敗: {e}")

    # 注入基本面數據（EPS、動態 PE、股利、動態殖利率、營收 YoY）
    eps_db = getattr(cfg, "eps_history_db", None) if cfg else None
    out = enrich_stock_fundamentals(out, trade_date, eps_db=eps_db)

    return out


_REVENUE_CACHE: Optional[Dict[str, float]] = None


def _get_revenue_yoy_map() -> Dict[str, float]:
    global _REVENUE_CACHE
    if _REVENUE_CACHE is not None:
        return _REVENUE_CACHE

    import os as _os
    candidates = [
        "cache/revenue.xlsx",
        "source/cache/revenue.xlsx",
        _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "cache", "revenue.xlsx"),
        _os.path.expanduser("~/.local/share/stocktool/cache/revenue.xlsx"),
        "dist/cache/revenue.xlsx",
    ]
    res: Dict[str, float] = {}
    for p in candidates:
        if _os.path.exists(p):
            try:
                df = pd.read_excel(p)
                code_col = None
                yoy_col = None
                for c in df.columns:
                    sc = str(c).strip()
                    if sc in ("股票代號", "code", "stock_id"):
                        code_col = c
                    if "營收YoY" in sc or "累計營收YoY" in sc:
                        yoy_col = c
                if code_col and yoy_col:
                    for _, r in df.iterrows():
                        raw_c = str(r[code_col]).strip()
                        if raw_c.endswith(".0"):
                            raw_c = raw_c[:-2]
                        val = r[yoy_col]
                        if pd.notna(val):
                            try:
                                res[raw_c] = float(val)
                            except Exception:
                                pass
                    if res:
                        _REVENUE_CACHE = res
                        return res
            except Exception:
                continue
    _REVENUE_CACHE = res
    return res


def enrich_stock_fundamentals(
    stock_data: Dict[str, Dict[str, Any]],
    as_of_date: str,
    eps_db: Optional[str] = None,
    div_db: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    為 stock_data 注入歷史公開之 EPS、動態本益比 (PE)、股利與動態殖利率 (Yield %)、營收 YoY (%)。
    若欄位原本已存在且有效，則保留。
    """
    if not stock_data or not as_of_date:
        return stock_data

    from .database import _query_latest_eps_for_date, _query_latest_div_for_date

    codes = list(stock_data.keys())
    eps_map = _query_latest_eps_for_date(eps_db, codes, as_of_date)
    div_map = _query_latest_div_for_date(div_db, codes, as_of_date)
    rev_map = _get_revenue_yoy_map()

    for code, info in stock_data.items():
        price = float(info.get("price") or 0.0)

        # 1. EPS & PE
        if info.get("eps") is None and code in eps_map:
            eps_info = eps_map[code]
            info["eps"] = eps_info.get("eps")
            ann_eps = eps_info.get("annualized_eps")
            if info.get("pe") is None and ann_eps and ann_eps > 0 and price > 0:
                info["pe"] = round(price / ann_eps, 2)
        elif info.get("pe") is None and info.get("eps") and float(info["eps"]) > 0 and price > 0:
            info["pe"] = round(price / float(info["eps"]), 2)

        # 2. 股利 & 殖利率
        if info.get("yield_pct") is None and code in div_map:
            d_info = div_map[code]
            cash = d_info.get("cash", 0.0)
            cash_yld = d_info.get("cash_yield_pct", 0.0)
            if cash > 0 and price > 0:
                info["yield_pct"] = round((cash / price) * 100, 2)
            elif cash_yld > 0:
                info["yield_pct"] = cash_yld

        # 3. 營收 YoY
        if info.get("rev_yoy") is None and code in rev_map:
            info["rev_yoy"] = rev_map[code]

    return stock_data


# ==========================================================
# 主流程：補跑到今天
# ==========================================================

@dataclass
class CatchUpResult:
    portfolio_id: int
    portfolio_name: str
    start_date: str
    end_date: str
    trade_dates: List[str]
    total_buys: int
    total_sells: int
    skipped_dates: List[str]
    errors: List[str]


def catch_up_portfolio(
    db_path: str,
    portfolio_id: int,
    end_date: Optional[str] = None,
    session=None,
    cfg=None,
    logger: Optional[logging.Logger] = None,
) -> CatchUpResult:
    """
    對一個組合、從 last_run_date 補跑到 end_date（預設今天）
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    def log(msg: str):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    p = pt.get_portfolio(db_path, portfolio_id)
    if not p:
        raise ValueError(f"portfolio {portfolio_id} 不存在")

    # 起點
    start = p.last_run_date or p.started_at
    if start and " " in start:
        start = start.split(" ")[0]
    if not start:
        # 沒跑過 → 從今天往前 5 天開始（給一點暖身）
        start_dt = datetime.now() - timedelta(days=5)
        start = start_dt.strftime("%Y-%m-%d")
    else:
        # 從 last_run_date 隔天開始
        start_dt = datetime.strptime(start, "%Y-%m-%d") + timedelta(days=1)
        start = start_dt.strftime("%Y-%m-%d")

    log(f"[catchup] {p.name}（{start} → {end_date}）")

    # 若起點已超過 end_date、不做事
    if start > end_date:
        log(f"[catchup] 起點 {start} 已 >= 結束 {end_date}、無需補跑")
        return CatchUpResult(portfolio_id, p.name, start, end_date, [], 0, 0, [], [])

    dates = _list_trade_dates(start, end_date)
    log(f"[catchup] 共 {len(dates)} 個交易日")

    total_buys = 0
    total_sells = 0
    skipped_dates: List[str] = []
    errors: List[str] = []

    for d in dates:
        try:
            # 抓所有需要看的股票（股票池 + 持股）
            holdings = pt.list_holdings(db_path, portfolio_id)
            all_codes = list(set((p.stock_pool or []) + [h.stock_code for h in holdings]))

            if not all_codes:
                skipped_dates.append(d)
                continue

            stock_data = _get_historical_prices(session, cfg, all_codes, d, logger=logger)

            if not stock_data:
                skipped_dates.append(d)
                continue

            # 觸發引擎
            if p.strategy_mode == "ai_meta":
                regime = pe.detect_market_regime(None)
                result = pe.evaluate_ai_portfolio_one_day(
                    db_path, portfolio_id, d, stock_data, regime, logger=logger
                )
            else:
                result = pe.evaluate_portfolio_one_day(
                    db_path, portfolio_id, d, stock_data, logger=logger
                )

            total_buys += len(result.buy_actions)
            total_sells += len(result.sell_actions)
            pt.update_portfolio_last_run(db_path, portfolio_id, d)

            if result.buy_actions or result.sell_actions:
                log(f"  📅 {d}: BUY {len(result.buy_actions)}, SELL {len(result.sell_actions)}")

        except Exception as e:
            errors.append(f"{d}: {e}")
            log(f"  ❌ {d}: {e}")

    log(f"[catchup] 完成：BUY {total_buys} / SELL {total_sells} / 跳過 {len(skipped_dates)} / 錯誤 {len(errors)}")

    return CatchUpResult(
        portfolio_id=portfolio_id,
        portfolio_name=p.name,
        start_date=start,
        end_date=end_date,
        trade_dates=dates,
        total_buys=total_buys,
        total_sells=total_sells,
        skipped_dates=skipped_dates,
        errors=errors,
    )


def catch_up_all_active(
    db_path: str,
    end_date: Optional[str] = None,
    session=None,
    cfg=None,
    logger: Optional[logging.Logger] = None,
) -> List[CatchUpResult]:
    """對所有 active 組合跑 catch_up_portfolio"""
    results = []
    for p in pt.list_portfolios(db_path, status="active"):
        try:
            r = catch_up_portfolio(db_path, p.id, end_date, session, cfg, logger)
            results.append(r)
        except Exception as e:
            if logger:
                logger.error(f"[catchup] {p.name} 失敗: {e}")
    return results