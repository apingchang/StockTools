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

    for code in codes:
        try:
            # 12 個月歷史足夠抓到半年內任何一天
            fp = get_history_file(code, 12)
            import os
            if not os.path.exists(fp):
                continue
            df, _, _ = load_cache(fp)
            if df is None or df.empty:
                continue
            # 找對應日期
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
                row = df[df["Date"] == trade_date]
            elif "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                row = df[df["date"] == trade_date]
            else:
                continue
            if row.empty:
                continue
            r = row.iloc[0]
            price = float(r.get("Close") or r.get("close") or 0)
            if price <= 0:
                continue
            out[code] = {
                "code": code,
                "name": str(r.get("Name", code)),
                "price": price,
            }
        except Exception as e:
            if logger:
                logger.warning(f"[catchup] {code} @ {trade_date} 抓取失敗: {e}")

    return out


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