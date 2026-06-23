"""
stocktool.technical - 技術指標計算
=====================================

v1.1 重構：把技術指標從 StockTool.py 抽出

被依賴：pipeline.py / backtest.py
依賴：config.py
"""

from __future__ import annotations

import os
import math
from typing import List, Tuple, Optional

import pandas as pd
import numpy as np

from .config import StrategyConfig, GuiLogger


def calc_enhanced_tech_indicators(cfg: StrategyConfig, df_hist: pd.DataFrame) -> pd.DataFrame:
    df_hist = df_hist.sort_values("Date").copy()
    if cfg.tech_months is not None:
        cutoff_date = datetime.today() - pd.DateOffset(months=cfg.tech_months)
        df_hist = df_hist[df_hist["Date"] >= cutoff_date]

    df_hist["MA5"] = df_hist["Close"].rolling(5).mean()
    df_hist["MA20"] = df_hist["Close"].rolling(20).mean()
    df_hist["VolMA20"] = df_hist["Volume"].rolling(20).mean()

    delta = df_hist["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df_hist["RSI"] = 100 - (100 / (1 + rs))

    ema12 = df_hist["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df_hist["Close"].ewm(span=26, adjust=False).mean()
    df_hist["MACD"] = ema12 - ema26
    df_hist["MACD_signal"] = df_hist["MACD"].ewm(span=9, adjust=False).mean()
    df_hist["MACD_hist"] = df_hist["MACD"] - df_hist["MACD_signal"]

    oversold = df_hist["RSI"] < cfg.rsi_oversold
    oversold_recent = oversold.rolling(cfg.oversold_lookback).max().shift(1).fillna(0).astype(bool)

    recover_level = cfg.rsi_aggressive if cfg.use_aggressive_signal else cfg.rsi_recover
    rsi_cross_up = (df_hist["RSI"] >= recover_level) & (df_hist["RSI"].shift(1) < recover_level)
    macd_hist_turn = (df_hist["MACD_hist"] > 0) & (df_hist["MACD_hist"].shift(1) <= 0)
    turn_strong = rsi_cross_up | macd_hist_turn

    ma20_slope = df_hist["MA20"] - df_hist["MA20"].shift(cfg.ma_slope_days)
    trend_ok = (df_hist["Close"] >= df_hist["MA20"] * (1 - cfg.ma20_tolerance)) & (ma20_slope > 0)
    volume_ok = (df_hist["Volume"] >= df_hist["VolMA20"] * 1.5)

    daily_buy = oversold_recent & turn_strong
    if cfg.require_trend_filter:
        daily_buy = daily_buy & trend_ok
    if cfg.require_volume_filter:
        daily_buy = daily_buy & volume_ok

    if cfg.use_mtf_confirmation:
        df_hist["Weekly_MA20"] = df_hist["MA20"].rolling(5).mean()
        weekly_trend = df_hist["MA20"] > df_hist["Weekly_MA20"]
        df_hist["Monthly_MA20"] = df_hist["MA20"].rolling(20).mean()
        monthly_trend = df_hist["MA20"] > df_hist["Monthly_MA20"]
        df_hist["確認層級"] = daily_buy.astype(int) + weekly_trend.astype(int) + monthly_trend.astype(int)
        mtf_buy = daily_buy & (weekly_trend | monthly_trend)
    else:
        mtf_buy = daily_buy
        df_hist["確認層級"] = daily_buy.astype(int)

    if cfg.use_divergence_detection:
        price_high = df_hist["Close"].rolling(20).max()
        rsi_high = df_hist["RSI"].rolling(20).max()
        bearish_divergence = (df_hist["Close"] == price_high) & (df_hist["RSI"] < rsi_high.shift(1))
        price_low = df_hist["Close"].rolling(20).min()
        rsi_low = df_hist["RSI"].rolling(20).min()
        bullish_divergence = (df_hist["Close"] == price_low) & (df_hist["RSI"] > rsi_low.shift(1))
        df_hist["熊市背離"] = bearish_divergence
        df_hist["牛市背離"] = bullish_divergence
        mtf_buy = mtf_buy & (~bearish_divergence)
    else:
        df_hist["熊市背離"] = False
        df_hist["牛市背離"] = False

    volume_surge = df_hist["Volume"] >= df_hist["VolMA20"] * cfg.volume_surge_multiplier
    df_hist["成交量爆發"] = volume_surge

    df_hist["買點"] = mtf_buy
    df_hist["買點_基礎"] = daily_buy
    df_hist["訊號型態"] = "三段式_B_強化版"
    df_hist["Ret_1D_past(%)"] = df_hist["Close"].pct_change(1) * 100
    df_hist["Ret_5D_past(%)"] = df_hist["Close"].pct_change(5) * 100

    return df_hist
# ==========================================================
# Excel Stock List Loader
# ==========================================================



# ==========================================================
# run_tech：批次跑技術指標
# ==========================================================

def run_tech(cfg: StrategyConfig, session, codes: List[str], logger: GuiLogger, history_months: int):
    """【V0.9.5-etf-history】批次抓歷史日 K + 算技術指標

    Returns:
        tech_all: 所有股票的完整技術指標 DataFrame
        tech_today: 每檔股票「最新一天」的技術指標
        buy_today: 標記為買點的最新一天資料
    """
    # 【v1.1 重構】用 lazy lookup 避免 import-time binding
    from .fetch_market import fetch_twse_history

    hist = fetch_twse_history(session, cfg, codes, logger, history_months)
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_enhanced_tech_indicators(cfg, g)
        g2["股票代號"] = str(code).strip()
        parts.append(g2)

    tech_all = pd.concat(parts, ignore_index=True)
    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()

    return tech_all, tech_today, buy_today
