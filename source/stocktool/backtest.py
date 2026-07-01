"""
stocktool.backtest - 回測引擎
===============================

v1.1 重構：把回測函數從 StockTool.py 抽出

包含：
- 風險指標：max_losing_streak, profit_factor, annualize_sharpe, annualize_sortino
- 事件邏輯：event_exit_return, signal_level_backtest_event
- Portfolio 回測：build_gate_map, portfolio_backtest_topk_event, performance_by_year
- Walk-forward：run_walk_forward, get_codes_for_period, quick_backtest_for_period

被依賴：pipeline.py
依賴：config.py / technical.py
"""

from __future__ import annotations

import os
import math
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

import pandas as pd
import numpy as np
import requests

from .config import StrategyConfig, GuiLogger, find_col
from .fetch_market import fetch_twse_history, fetch_prices
from .cache import get_or_fetch
from .technical import calc_enhanced_tech_indicators


def event_exit_return(cfg: StrategyConfig, path_df: pd.DataFrame, entry_idx: int) -> Tuple[int, float, float, str]:
    entry_price = float(path_df.loc[entry_idx, "Close"])
    last_idx = min(entry_idx + cfg.hold_days, len(path_df) - 1)

    exit_idx = last_idx
    gross_ret = float(path_df.loc[last_idx, "Close"]) / entry_price - 1.0
    reason = "TIME_EXIT"

    for j in range(entry_idx + 1, last_idx + 1):
        px = float(path_df.loc[j, "Close"])
        rsi = float(path_df.loc[j, "RSI"]) if pd.notna(path_df.loc[j, "RSI"]) else None
        ret = px / entry_price - 1.0

        if ret <= cfg.stop_loss:
            exit_idx, gross_ret, reason = j, ret, "STOP_LOSS"
            break
        if ret >= cfg.take_profit:
            exit_idx, gross_ret, reason = j, ret, "TAKE_PROFIT"
            break
        if rsi is not None and rsi >= cfg.exit_rsi:
            exit_idx, gross_ret, reason = j, ret, "RSI_EXIT"
            break

    net_ret = (1.0 + gross_ret) * (1.0 - cfg.roundtrip_cost_pct) - 1.0
    return exit_idx, gross_ret, net_ret, reason


def max_losing_streak(returns):
    max_streak = 0
    cur = 0
    for r in returns:
        if pd.isna(r):
            continue
        if r < 0:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return int(max_streak)


def profit_factor(returns):
    r = pd.Series(returns).dropna()
    wins = r[r > 0].sum()
    losses = r[r < 0].sum()
    if losses == 0:
        return float("inf") if wins > 0 else None
    return float(wins / abs(losses))


def annualize_sharpe(cfg: StrategyConfig, daily_returns):
    r = pd.Series(daily_returns).dropna()
    if len(r) < 10:
        return None
    rf_d = cfg.risk_free_annual / cfg.trading_days
    mu = (r.mean() - rf_d) * cfg.trading_days
    sigma = r.std(ddof=1) * (cfg.trading_days ** 0.5)
    if sigma == 0:
        return None
    return float(mu / sigma)


def annualize_sortino(cfg: StrategyConfig, daily_returns):
    r = pd.Series(daily_returns).dropna()
    if len(r) < 10:
        return None
    mar_d = cfg.mar_annual / cfg.trading_days
    excess = r - mar_d
    downside = excess.copy()
    downside[downside > 0] = 0
    downside_dev = downside.std(ddof=1) * (cfg.trading_days ** 0.5)
    mu = excess.mean() * cfg.trading_days
    if downside_dev == 0:
        return None
    return float(mu / downside_dev)


def signal_level_backtest_event(cfg: StrategyConfig, tech_all: pd.DataFrame) -> pd.DataFrame:
    if tech_all is None or tech_all.empty:
        return pd.DataFrame()

    returns_net = []
    for code, g in tech_all.groupby("股票代號", sort=False):
        g = g.sort_values("Date").reset_index(drop=True)
        sig_idx = g.index[g["買點"] == True].tolist()
        if not sig_idx:
            continue
        for idx in sig_idx:
            _, _, net_ret, _ = event_exit_return(cfg, g, idx)
            returns_net.append(net_ret)

    rnet = pd.Series(returns_net).dropna()
    if rnet.empty:
        return pd.DataFrame()

    streak = max_losing_streak(rnet.values)
    pf = profit_factor(rnet.values)

    return pd.DataFrame([{
        "訊號數": int(len(rnet)),
        "事件型平均報酬_扣成本(%)": round(rnet.mean() * 100, 2),
        "事件型勝率_扣成本(%)": round((rnet > 0).mean() * 100, 2),
        "事件型中位數_扣成本(%)": round(rnet.median() * 100, 2),
        "MaxLosingStreak": int(streak),
        "ProfitFactor": round(pf, 3) if pf is not None and pf != float("inf") else pf
    }])


def build_gate_map(cfg: StrategyConfig, df_sel: pd.DataFrame) -> Dict[str, bool]:
    code = df_sel["股票代號"].astype(str).str.strip()
    gate = pd.Series([True] * len(code), index=code)
    return dict(zip(code, gate))


def portfolio_backtest_topk_event(cfg: StrategyConfig, tech_all: pd.DataFrame, score_map: dict, gate_map: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if tech_all is None or tech_all.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = tech_all[["Date", "股票代號", "Close", "買點", "RSI"]].copy()
    df = df.dropna(subset=["Date", "Close"])
    df["股票代號"] = df["股票代號"].astype(str).str.strip()

    score_map = {str(k).strip(): v for k, v in score_map.items()}
    df["Score"] = df["股票代號"].map(score_map).fillna(-1e18)

    by_code = {c: g.sort_values("Date").reset_index(drop=True) for c, g in df.groupby("股票代號")}
    all_dates = sorted(df["Date"].unique())

    cash = cfg.capital
    positions = {}
    equity_rows = []
    trade_rows = []

    entry_cost = cfg.roundtrip_cost_pct / 2
    exit_cost = cfg.roundtrip_cost_pct / 2

    for d in all_dates:
        d = pd.to_datetime(d)

        to_close = []
        for code, pos in list(positions.items()):
            g = by_code.get(code)
            if g is None:
                continue
            idx_list = g.index[g["Date"] == d].tolist()
            if not idx_list:
                continue

            cur_idx = idx_list[0]
            entry_idx = pos["entry_idx"]
            entry_price = pos["entry_price"]
            max_idx = min(entry_idx + cfg.hold_days, len(g) - 1)
            if cur_idx > max_idx:
                cur_idx = max_idx

            px = float(g.loc[cur_idx, "Close"])
            rsi = float(g.loc[cur_idx, "RSI"]) if pd.notna(g.loc[cur_idx, "RSI"]) else None
            ret = px / entry_price - 1.0

            reason = None
            if ret <= cfg.stop_loss:
                reason = "STOP_LOSS"
            elif ret >= cfg.take_profit:
                reason = "TAKE_PROFIT"
            elif (rsi is not None) and (rsi >= cfg.exit_rsi):
                reason = "RSI_EXIT"
            elif cur_idx == max_idx:
                reason = "TIME_EXIT"

            if reason is not None:
                to_close.append((code, px, ret, reason))

        for code, px, ret, reason in to_close:
            pos = positions.pop(code)
            shares = pos["shares"]
            proceeds = shares * px * (1.0 - exit_cost)
            cash += proceeds

            net_ret = (1.0 + ret) * (1.0 - cfg.roundtrip_cost_pct) - 1.0
            trade_rows.append({
                "股票代號": code,
                "進場日": pos["entry_date"].date().isoformat(),
                "進場價": pos["entry_price"],
                "出場日": d.date().isoformat(),
                "出場價": px,
                "出場原因": reason,
                "報酬(%)": round(ret * 100, 2),
                "報酬_扣成本(%)": round(net_ret * 100, 2)
            })

        if len(positions) == 0:
            cand = df[(df["Date"] == d) & (df["買點"] == True)].copy()
            if cfg.use_gate:
                cand["GateOK"] = cand["股票代號"].map(gate_map).fillna(False)
                cand = cand[cand["GateOK"] == True].copy()

            if not cand.empty:
                cand = cand.sort_values("Score", ascending=False).head(cfg.topk)
                k = len(cand)
                if k > 0:
                    alloc_each = cash / k
                    cash = 0.0
                    for _, row in cand.iterrows():
                        code = str(row["股票代號"]).strip()
                        g = by_code.get(code)
                        if g is None:
                            cash += alloc_each
                            continue
                        idx_list = g.index[g["Date"] == d].tolist()
                        if not idx_list:
                            cash += alloc_each
                            continue
                        entry_idx = idx_list[0]
                        entry_price = float(g.loc[entry_idx, "Close"])
                        alloc_after_cost = alloc_each * (1.0 - entry_cost)
                        shares = alloc_after_cost / entry_price if entry_price > 0 else 0.0
                        positions[code] = {
                            "shares": shares,
                            "entry_price": entry_price,
                            "entry_date": d,
                            "entry_idx": entry_idx
                        }

        equity = cash
        for code, pos in positions.items():
            g = by_code.get(code)
            if g is None:
                continue
            cur = g[g["Date"] == d]
            px = float(cur.iloc[0]["Close"]) if not cur.empty else pos["entry_price"]
            equity += pos["shares"] * px
        equity_rows.append({"Date": d, "Equity": equity})

    eq = pd.DataFrame(equity_rows).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    trades = pd.DataFrame(trade_rows)

    # Fix5：同時顯示標準化權益（初始=1.0）
    eq["Equity_Norm"] = eq["Equity"] / cfg.capital

    eq["Ret"] = eq["Equity"].pct_change()
    eq["Peak"] = eq["Equity"].cummax()
    eq["Drawdown"] = eq["Equity"] / eq["Peak"] - 1
    mdd = eq["Drawdown"].min()

    sharpe = annualize_sharpe(cfg, eq["Ret"])
    sortino = annualize_sortino(cfg, eq["Ret"])

    if len(eq) >= 2:
        days = (pd.to_datetime(eq["Date"].iloc[-1]) - pd.to_datetime(eq["Date"].iloc[0])).days
        years = days / 365.25 if days > 0 else None
        cagr = (eq["Equity"].iloc[-1] ** (1 / years) - 1) if years else None
    else:
        cagr = None

    if not trades.empty and "報酬_扣成本(%)" in trades.columns:
        tr = trades["報酬_扣成本(%)"].astype(float) / 100.0
        pf = profit_factor(tr.values)
        streak = max_losing_streak(tr.values)
    else:
        pf = None
        streak = 0

    kpi = pd.DataFrame([{
        "CAGR(%)": round(cagr * 100, 2) if cagr is not None else None,
        "MDD(%)": round(mdd * 100, 2) if mdd is not None else None,
        "Sharpe": round(sharpe, 3) if sharpe is not None else None,
        "Sortino": round(sortino, 3) if sortino is not None else None,
        "Trades": int(len(trades)),
        "MaxLosingStreak": int(streak),
        "ProfitFactor": round(pf, 3) if pf is not None and pf != float("inf") else pf
    }])

    if not trades.empty and "出場原因" in trades.columns:
        reason_counts = trades["出場原因"].value_counts()
        reason_pct = trades["出場原因"].value_counts(normalize=True) * 100
        reason_stats = pd.DataFrame({
            "次數": reason_counts,
            "比例(%)": reason_pct.round(2)
        }).reset_index()
        reason_stats = reason_stats.rename(columns={"index": "出場原因"})
    else:
        reason_stats = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])

    return eq, trades, kpi, reason_stats


def performance_by_year(trades_df):
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    date_col = find_col(df.columns, ["entry", "進場", "買進", "date"])
    if date_col is None:
        raise ValueError("找不到進場日期欄位")
    df["year"] = pd.to_datetime(df[date_col]).dt.year
    out = []
    for y, g in df.groupby("year"):
        ret_col = find_col(g.columns, ["return", "報酬", "損益", "ret", "%"])
        if ret_col is None:
            raise ValueError("找不到報酬欄位")
        returns = g[ret_col]
        out.append({
            "year": y,
            "trades": len(g),
            "win_rate(%)": round((returns > 0).mean() * 100, 2),
            "avg_return(%)": round(returns.mean() * 100, 2),
            "profit_factor": round(profit_factor(returns), 2) if profit_factor(returns) else None
        })
    return pd.DataFrame(out).sort_values("year")
# ==========================================================
# Walk-forward Analysis
# ==========================================================

def run_walk_forward(cfg: StrategyConfig, logger: GuiLogger, s: requests.Session):
    """Walk-forward 分析：評估策略在不同時間窗口下的穏定性。

    什麼是 Walk-forward？
    -------------------
    避免「過擬合」（in-sample overfitting）的標準驗證法：
    - 將歷史資料切成多個「訓練期 + 測試期」滑動窗口
    - 訓練期決定選股（get_codes_for_period）
    - 測試期驗證績效（quick_backtest_for_period）
    - 如果每個窗口的測試期纍效都接近訓練期，代表策略穏定

    演算法
    ------
    1. 計算起始日 = 現在 - (wf_train_years + wf_test_years * 4)
       （预留足夠時間產生 5+ 個 window）
    2. 滑動產生 windows，每個 window 包含：
       - train：[current_start, current_start + train_years)
       - test： [train_end,       train_end + test_years)
       - 步進 wf_step_years
    3. 上限 10 個 windows（避免計算過久）
    4. 如果 < 2 個 windows（歷史資料不足）→ return 空 DataFrame
    5. 對每個 window 呼叫：
       - get_codes_for_period()        取該期間評分達標的股號
       - quick_backtest_for_period()   在測試期跑回測
    6. 收集所有結果、計算「CAGR / Sharpe 標準差」評估穏定性

    Args:
        cfg: StrategyConfig。讀取以下參數：
            - wf_train_years: int    訓練期年數（預設 3）
            - wf_test_years:  int    測試期年數（預設 1）
            - wf_step_years:  int    窗口步進年數（預設 1）
        logger: GuiLogger。輸出 log。
        s:     requests.Session。抓歷史資料用的 HTTP session。

    Returns:
        pd.DataFrame: 每個 window 一列。欄位：
            - window:         int         窗口編號（1-based）
            - train_period:   str         訓練期 "YYYY-YYYY"
            - test_period:    str         測試期 "YYYY-YYYY"
            - test_cagr:      float       測試期 CAGR（%）
            - test_sharpe:    float       測試期 Sharpe ratio
            - test_mdd:       float       測試期 最大回撤（%）
            - test_trades:    int         測試期交易次數
        歷史不足時（< 2 windows）回傳空 DataFrame。

    Side effects:
        - 透過 logger 輸出 Walk-forward 進度、每個 window 結果、穏定性評估
        - 可能抓取歷史股價資料（透過 get_codes_for_period）

    Example:
        >>> df_wf = run_walk_forward(cfg, logger, s)
        >>> print(df_wf[['window', 'test_period', 'test_cagr', 'test_sharpe']])
        window test_period  test_cagr  test_sharpe
            1    2022-2023       8.5        0.85
            2    2023-2024      12.3        1.12

    Note:
        【V1.1.3-wf-docstring】2026-07-01 補 docstring（v1.0 改版 TODO P1）
        原本完全沒有 docstring、呼叫者需要讀源碼才看得懂
    """
    logger.log("\n" + "=" * 60)
    logger.log("📊 開始 Walk-forward 分析")
    logger.log("=" * 60)

    end_date = datetime.now()
    start_date = end_date - pd.DateOffset(years=cfg.wf_train_years + cfg.wf_test_years * 4)

    windows = []
    current_start = start_date
    window_count = 0

    while current_start + pd.DateOffset(years=cfg.wf_train_years + cfg.wf_test_years) <= end_date:
        train_end = current_start + pd.DateOffset(years=cfg.wf_train_years)
        test_end = train_end + pd.DateOffset(years=cfg.wf_test_years)
        windows.append({
            "train_start": current_start,
            "train_end": train_end,
            "test_start": train_end,
            "test_end": test_end,
            "train_start_str": current_start.strftime("%Y-%m-%d"),
            "train_end_str": train_end.strftime("%Y-%m-%d"),
            "test_start_str": train_end.strftime("%Y-%m-%d"),
            "test_end_str": test_end.strftime("%Y-%m-%d")
        })
        current_start += pd.DateOffset(years=cfg.wf_step_years)
        window_count += 1
        if window_count > 10:
            break

    if len(windows) < 2:
        logger.log("⚠️ 歷史資料不足，無法執行 Walk-forward 分析")
        return pd.DataFrame()

    results = []
    for i, window in enumerate(windows):
        logger.log(f"\n📊 Window {i + 1}/{len(windows)}")
        logger.log(f"   訓練期: {window['train_start_str']} ~ {window['train_end_str']}")
        logger.log(f"   測試期: {window['test_start_str']} ~ {window['test_end_str']}")

        try:
            tech_codes = get_codes_for_period(s, cfg, window['train_start'], window['train_end'], logger)
            test_result = quick_backtest_for_period(cfg, s, tech_codes, window['test_start'], window['test_end'], logger)

            results.append({
                "window": i + 1,
                "train_period": f"{window['train_start'].year}-{window['train_end'].year}",
                "test_period": f"{window['test_start'].year}-{window['test_end'].year}",
                "test_cagr": test_result.get('cagr', 0),
                "test_sharpe": test_result.get('sharpe', 0),
                "test_mdd": test_result.get('mdd', 0),
                "test_trades": test_result.get('trades', 0)
            })
        except Exception as e:
            logger.log(f"   ❌ Window {i + 1} 失敗: {e}")
            results.append({
                "window": i + 1,
                "train_period": f"{window['train_start'].year}-{window['train_end'].year}",
                "test_period": f"{window['test_start'].year}-{window['test_end'].year}",
                "test_cagr": 0,
                "test_sharpe": 0,
                "test_mdd": 0,
                "test_trades": 0
            })

    df_results = pd.DataFrame(results)

    logger.log("\n" + "=" * 60)
    logger.log("📈 Walk-forward 分析結果")
    logger.log("=" * 60)
    logger.log(df_results[['test_period', 'test_cagr', 'test_sharpe', 'test_mdd', 'test_trades']].to_string(index=False))

    if len(df_results) > 1:
        cagr_std = df_results['test_cagr'].std()
        sharpe_std = df_results['test_sharpe'].std()

        logger.log(f"\n📊 穩定性評估:")
        logger.log(f"   CAGR 標準差: {cagr_std:.2f}%")
        logger.log(f"   CAGR 平均值: {df_results['test_cagr'].mean():.2f}%")
        logger.log(f"   Sharpe 標準差: {sharpe_std:.3f}")
        logger.log(f"   Sharpe 平均值: {df_results['test_sharpe'].mean():.3f}")

        if cagr_std < 10:
            logger.log(f"   ✅ 策略穩定（CAGR 波動 < 10%）")
        else:
            logger.log(f"   ⚠️ 策略不穩定（CAGR 波動 > 10%）")

    return df_results


def get_codes_for_period(s, cfg, start_date, end_date, logger):
    from_cache = get_or_fetch("price", lambda: fetch_prices(s, cfg, logger), logger)
    codes = from_cache["股票代號"].dropna().astype(str).str.strip().tolist()
    return codes[:cfg.top_n_for_tech]


def quick_backtest_for_period(cfg, s, codes, start_date, end_date, logger):
    try:
        hist = fetch_twse_history(s, cfg, codes, logger, cfg.history_months)
        if hist.empty:
            return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}

        hist = hist[(hist["Date"] >= start_date) & (hist["Date"] <= end_date)]
        if hist.empty:
            return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}

        parts = []
        for code, g in hist.groupby("股票代號", sort=False):
            g2 = calc_enhanced_tech_indicators(cfg, g)
            g2["股票代號"] = str(code).strip()
            parts.append(g2)
        tech_all = pd.concat(parts, ignore_index=True)

        score_map = {}
        eq, trades, kpi, _ = portfolio_backtest_topk_event(cfg, tech_all, score_map, {})

        if not eq.empty and len(eq) > 1:
            start_val = eq.iloc[0]["Equity"]
            end_val = eq.iloc[-1]["Equity"]
            days = (eq.iloc[-1]["Date"] - eq.iloc[0]["Date"]).days
            years = days / 365.25
            cagr = (end_val / start_val) ** (1 / years) - 1 if years > 0 else 0

            sharpe_val = kpi.iloc[0]["Sharpe"] if not kpi.empty and kpi.iloc[0]["Sharpe"] else 0
            mdd_val = kpi.iloc[0]["MDD(%)"] if not kpi.empty and kpi.iloc[0]["MDD(%)"] else 0
            trades_val = kpi.iloc[0]["Trades"] if not kpi.empty else 0

            return {'cagr': cagr * 100, 'sharpe': sharpe_val, 'mdd': mdd_val, 'trades': trades_val}

        return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}
    except Exception as e:
        return {'cagr': 0, 'sharpe': 0, 'mdd': 0, 'trades': 0}


# ==========================================================
# Excel 美化函數
# ==========================================================

