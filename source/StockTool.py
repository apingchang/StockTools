"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                               StockTool.py                                   ║
║                          台灣股市量化選股系統 v0.9.3                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
V0.9.3
【版本資訊】
Version: v0.9.3-HOTFIX
最後更新: 2026-06-08 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: tkinter, pandas, requests, openpyxl, numpy, itertools

════════════════════════════════════════════════════════════════════════════════
【v0.9.3 緊急修正內容】2026-06-08
════════════════════════════════════════════════════════════════════════════════

【問題描述】
- EPSYoY_raw 欄位完全為空，導致 EPSYoY_顯示(%) 全部為 0
- Score 欄位計算異常，出現 -1e+18 負無限大值
- PE 欄位出現 inf 無限值未正確處理
- 簡易評分門檻過濾邏輯錯誤，導致所有個股被排除
- Top10 選股結果全部為 ETF 而非正常個股

【修正內容】
1. 修正 fetch_eps_latest() 函數
   - 改用「去年同期 EPS 差值」計算 EPS YoY
   - 新增無限值處理 (inf/-inf → pd.NA)

2. 修正 calculate_simple_score() 函數
   - 新增 PE 和 EPSYoY_raw 的無限值處理
   - 修正門檻過濾邏輯（改用 -998 判斷閾值啟用狀態）
   - 未通過門檻的 Score 改為 pd.NA 而非 -1e+18

3. 修正 calculate_multi_factor_score() 函數
   - 新增營收YoY和EPSYoY的無限值處理

4. 確認 DEFAULT_CONFIG 中門檻預設值正確
   - simple_min_rev_yoy: -999.0
   - simple_min_eps_yoy: -999.0
   - simple_min_eps: -999.0
   - simple_max_pe: 999.0

════════════════════════════════════════════════════════════════════════════════
【修正後執行步驟】
════════════════════════════════════════════════════════════════════════════════

1. 儲存本檔案
2. 刪除 cache/ 目錄（強制重新下載資料）
3. 重新執行 python StockTool.py
4. 確認 GUI 中簡易評分門檻皆為 -999 / 999
5. 按下「執行策略」驗證結果

════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import io
import os
import json
import time
import queue
import threading
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional, List
from itertools import product

import pandas as pd
import numpy as np
import requests

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

# V0.9.4 買賣記錄模組
from portfolio import PortfolioDB, Transaction, DEFAULT_PORTFOLIO_DB

warnings.filterwarnings("ignore")

# ==========================================================
# 0) Config 檔案路徑與預設設定
# ==========================================================

CONFIG_FILE = "stocktool_config.json"

DEFAULT_CONFIG = {
    "top_n_for_tech": 60,
    "tech_months": 24,
    "history_months": 60,
    "timeout": 30,
    "verify_ssl": False,
    "use_excel_stock_list": False,
    "excel_stock_file": "stock_list.xlsx",
    "use_enhanced_score": True,
    "use_top10_backtest": False,
    "excel_force_buy": False,
    "factor_weight_mom1": 0.15,
    "factor_weight_mom3": 0.15,
    "factor_weight_mom6": 0.20,
    "factor_weight_rev": 0.25,
    "factor_weight_eps": 0.25,
    "simple_score_weight_rev": 35.0,
    "simple_score_weight_eps": 35.0,
    "simple_score_weight_div": 20.0,
    "simple_score_weight_pe": -5.0,
    "simple_min_rev_yoy": -999.0,
    "simple_min_eps_yoy": -999.0,
    "simple_min_eps": -999.0,
    "simple_max_pe": 999.0,
    "use_mtf_confirmation": True,
    "use_divergence_detection": True,
    "volume_surge_multiplier": 2.0,
    "wf_enabled": False,
    "wf_train_years": 2,
    "wf_test_years": 1,
    "wf_step_years": 1,
    "twse_retries": 3,
    "twse_backoff": 0.8,
    "twse_sleep": 0.12,
    "topk": 7,
    "hold_days": 10,
    "roundtrip_cost_pct": 0.004,
    "stop_loss": -0.03,
    "take_profit": 0.08,
    "exit_rsi": 70,
    "use_gate": False,
    "min_rev_yoy": 0.0,
    "min_eps_yoy": 0.0,
    "allow_eps_yoy_nan": True,
    "risk_free_annual": 0.0,
    "mar_annual": 0.0,
    "trading_days": 252,
    "rsi_oversold": 40,
    "oversold_lookback": 10,
    "rsi_recover": 40,
    "rsi_aggressive": 45,
    "use_aggressive_signal": True,
    "require_trend_filter": True,
    "ma_slope_days": 3,
    "ma20_tolerance": 0.01,
    "require_volume_filter": True,
    "strong_revenue_yoy": 10.0,
    "strong_pe_max": 30.0,
    "strong_price_min": 10.0,
    "out_file_prefix": "選股報表"
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved_config)
            return config
        except Exception as e:
            print(f"載入設定檔失敗: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"儲存設定檔失敗: {e}")
        return False


# ==========================================================
# StrategyConfig
# ==========================================================

HISTORY_DIR = "cache/history"


@dataclass
class StrategyConfig:
    top_n_for_tech: int = 60
    tech_months: int = 24
    history_months: int = 60
    timeout: int = 30
    verify_ssl: bool = False
    use_excel_stock_list: bool = False
    excel_stock_file: str = "stock_list.xlsx"
    use_enhanced_score: bool = True
    use_top10_backtest: bool = False
    excel_force_buy: bool = False      # Excel 清單強制買點模式
    factor_weight_mom1: float = 0.15
    factor_weight_mom3: float = 0.15
    factor_weight_mom6: float = 0.20
    factor_weight_rev: float = 0.25
    factor_weight_eps: float = 0.25
    simple_score_weight_rev: float = 35.0
    simple_score_weight_eps: float = 35.0
    simple_score_weight_div: float = 20.0
    simple_score_weight_pe: float = -5.0
    simple_min_rev_yoy: float = -999.0
    simple_min_eps_yoy: float = -999.0
    simple_min_eps: float = -999.0
    simple_max_pe: float = 999.0
    use_mtf_confirmation: bool = True
    use_divergence_detection: bool = True
    volume_surge_multiplier: float = 2.0
    wf_enabled: bool = False
    wf_train_years: int = 2
    wf_test_years: int = 1
    wf_step_years: int = 1
    twse_retries: int = 3
    twse_backoff: float = 0.8
    twse_sleep: float = 0.12
    topk: int = 7
    hold_days: int = 10
    roundtrip_cost_pct: float = 0.004
    stop_loss: float = -0.03
    take_profit: float = 0.08
    exit_rsi: int = 70
    use_gate: bool = False
    min_rev_yoy: float = 0.0
    min_eps_yoy: float = 0.0
    allow_eps_yoy_nan: bool = True
    risk_free_annual: float = 0.0
    mar_annual: float = 0.0
    trading_days: int = 252
    rsi_oversold: int = 45
    oversold_lookback: int = 10
    rsi_recover: int = 40
    rsi_aggressive: int = 45
    use_aggressive_signal: bool = True
    require_trend_filter: bool = True
    ma_slope_days: int = 3
    ma20_tolerance: float = 0.01
    require_volume_filter: bool = True
    strong_revenue_yoy: float = 10.0
    strong_pe_max: float = 30.0
    strong_price_min: float = 10.0
    out_file_prefix: str = "選股報表"

    def to_dict(self) -> dict:
        return asdict(self)

    def update_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# ==========================================================
# Logger
# ==========================================================

class GuiLogger:
    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.q.put(f"[{ts}] {msg}")
# ==========================================================
# Session
# ==========================================================

def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.9.3-GUI",
        "Accept": "application/json,text/plain,*/*"
    })
    return s


# ==========================================================
# Utility functions
# ==========================================================

def find_col(cols, keywords):
    for c in cols:
        s = str(c)
        for k in keywords:
            if k in s:
                return c
    return None


def get_cache_file(name):
    return f"cache/{name}.xlsx"


def save_cache(file_path, df):
    os.makedirs("cache", exist_ok=True)
    today = datetime.today().strftime("%Y-%m-%d")
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": [today]})
        meta.to_excel(writer, sheet_name="meta", index=False)


def load_cache(file_path):
    df = pd.read_excel(file_path, sheet_name="data", engine="openpyxl")
    meta = pd.read_excel(file_path, sheet_name="meta", engine="openpyxl")
    return df, meta.loc[0, "last_update"]


def get_or_fetch(name: str, fetch_func, logger: GuiLogger):
    file_path = get_cache_file(name)
    today = datetime.today().strftime("%Y-%m-%d")
    if not os.path.exists(file_path):
        logger.log(f"📥 [{name}] 無快取 → 下載資料")
        df = fetch_func()
        save_cache(file_path, df)
        return df
    df, last_update = load_cache(file_path)
    if last_update == today:
        logger.log(f"✅ [{name}] 使用快取資料")
        return df
    logger.log(f"♻️ [{name}] 資料過期 → 重新下載")
    df = fetch_func()
    save_cache(file_path, df)
    return df


def to_num_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("+", "", regex=False)
         .str.strip(),
        errors="coerce"
    )


def month_starts_back(n_months: int) -> List[str]:
    today = date.today()
    y, m = today.year, today.month
    out = []
    for i in range(n_months):
        mm = m - i
        yy = y
        while mm <= 0:
            yy -= 1
            mm += 12
        out.append(f"{yy}{mm:02d}01")
    return out


def roc_to_ad(roc_str: str):
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


def format_for_output(df: pd.DataFrame, sort_by_code: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "股票代號" in df.columns:
        df["股票代號"] = df["股票代號"].astype(str).str.strip()
    if "股票代號" in df.columns and "公司名稱_來源" in df.columns:
        cols = ["股票代號", "公司名稱_來源"] + [c for c in df.columns if c not in ["股票代號", "公司名稱_來源"]]
        df = df[cols]
    if sort_by_code and "股票代號" in df.columns:
        df["股票代號_sort"] = df["股票代號"].astype(str).str.extract(r'(\d+)').astype(int)
        df = df.sort_values("股票代號_sort", ascending=True).drop(columns=["股票代號_sort"])
    return df.reset_index(drop=True)


def ensure_str_column(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip()
    return df
# ==========================================================
# 多因子評分函數
# ==========================================================

def calculate_multi_factor_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    # ✅ 新增：處理異常值
    df["營收YoY(%)"] = df["營收YoY(%)"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_顯示(%)"] = df["EPSYoY_顯示(%)"].replace([float("inf"), -float("inf")], pd.NA)

    if "Close" in df.columns:
        df["mom_1m"] = df.groupby("股票代號")["Close"].pct_change(21) * 100
        df["mom_3m"] = df.groupby("股票代號")["Close"].pct_change(63) * 100
        df["mom_6m"] = df.groupby("股票代號")["Close"].pct_change(126) * 100
    else:
        df["mom_1m"] = 0
        df["mom_3m"] = 0
        df["mom_6m"] = 0

    factors = ['mom_1m', 'mom_3m', 'mom_6m', '營收YoY(%)', 'EPSYoY_顯示(%)']
    for f in factors:
        if f in df.columns:
            mean_val = df[f].mean()
            std_val = df[f].std()
            if std_val > 0:
                df[f"{f}_zscore"] = (df[f] - mean_val) / std_val
            else:
                df[f"{f}_zscore"] = 0

    df["Score"] = (df["mom_1m_zscore"].fillna(0) * cfg.factor_weight_mom1 +
                   df["mom_3m_zscore"].fillna(0) * cfg.factor_weight_mom3 +
                   df["mom_6m_zscore"].fillna(0) * cfg.factor_weight_mom6 +
                   df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev +
                   df["EPSYoY_顯示(%)_zscore"].fillna(0) * cfg.factor_weight_eps)
    df["Score"] = df["Score"].round(2)
    df["評分_動能1M"] = df["mom_1m_zscore"].fillna(0).round(2)
    df["評分_動能3M"] = df["mom_3m_zscore"].fillna(0).round(2)
    df["評分_動能6M"] = df["mom_6m_zscore"].fillna(0).round(2)
    df["評分_成長"] = (df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev * 4).round(2)
    return df


def calculate_enhanced_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    return calculate_multi_factor_score(df, cfg)


def calculate_simple_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    df["PE"] = df["PE"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_raw"] = df["EPSYoY_raw"].replace([float("inf"), -float("inf")], pd.NA)

    # ========== DEBUG: 簡易評分診斷 ==========
    print("\n" + "=" * 60)
    print("🔍 [DEBUG] calculate_simple_score 診斷")
    print("=" * 60)

    print(f"\n📊 原始資料筆數: {len(df)}")
    print(f"📊 有營收YoY資料的筆數: {df['營收YoY(%)'].notna().sum()}")
    print(f"📊 有EPS本期資料的筆數: {df['EPS本期'].notna().sum()}")
    print(f"📊 有EPSYoY_raw資料的筆數: {df['EPSYoY_raw'].notna().sum()}")
    print(f"📊 有PE資料的筆數: {df['PE'].notna().sum()}")

    print(f"\n⚙️ 目前門檻設定:")
    print(f"   simple_min_rev_yoy = {cfg.simple_min_rev_yoy}")
    print(f"   simple_min_eps_yoy = {cfg.simple_min_eps_yoy}")
    print(f"   simple_min_eps = {cfg.simple_min_eps}")
    print(f"   simple_max_pe = {cfg.simple_max_pe}")
    # ========== DEBUG 結束 ==========

    mask = pd.Series([True] * len(df))

    if cfg.simple_min_rev_yoy > -998:
        rev_ok = df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy
        mask = mask & rev_ok

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_ok = (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy
        mask = mask & eps_yoy_ok

    if cfg.simple_min_eps > -998:
        eps_ok = df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps
        mask = mask & eps_ok

    if cfg.simple_max_pe < 998:
        pe_ok = df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe
        mask = mask & pe_ok

    # ========== DEBUG: 門檻通過數量 ==========
    print(f"\n✅ 各門檻通過數量:")
    if cfg.simple_min_rev_yoy > -998:
        rev_pass = (df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy).sum()
        print(f"   營收門檻 (>= {cfg.simple_min_rev_yoy}%): {rev_pass} 檔")
    else:
        print(f"   營收門檻: 未啟用")

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_pass = (
                    (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy).sum()
        print(f"   EPS YoY 門檻 (>= {cfg.simple_min_eps_yoy}%): {eps_yoy_pass} 檔")
    else:
        print(f"   EPS YoY 門檻: 未啟用")

    if cfg.simple_min_eps > -998:
        eps_pass = (df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps).sum()
        print(f"   EPS 門檻 (>= {cfg.simple_min_eps}元): {eps_pass} 檔")
    else:
        print(f"   EPS 門檻: 未啟用")

    if cfg.simple_max_pe < 998:
        pe_pass = (df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe).sum()
        print(f"   PE 門檻 (<= {cfg.simple_max_pe}倍): {pe_pass} 檔")
    else:
        print(f"   PE 門檻: 未啟用")

    print(f"\n🎯 最終通過所有門檻的股票數量: {mask.sum()} 檔")

    if mask.sum() == 0 and len(df) > 0:
        print(f"\n⚠️ 前5筆未通過股票的診斷:")
        failed_df = df[~mask].head(5)
        for idx, row in failed_df.iterrows():
            code = row.get("股票代號", "N/A")
            name = str(row.get("公司名稱_來源", "N/A"))[:20]
            rev = row.get("營收YoY(%)", "N/A")
            eps_yoy_raw = row.get("EPSYoY_raw", "N/A")
            eps = row.get("EPS本期", "N/A")
            pe = row.get("PE", "N/A")
            print(f"   {code} {name} | 營收:{rev}% | EPS YoY:{eps_yoy_raw} | EPS:{eps} | PE:{pe}")
    # ========== DEBUG 結束 ==========

    rev_score = df["營收YoY(%)"].fillna(0)
    eps_score = (df["EPSYoY_raw"].fillna(0) * 100)
    div_score = df["殖利率(估)"].fillna(0) * 100
    pe_score = df["PE"].fillna(0)

    w_rev = cfg.simple_score_weight_rev
    w_eps = cfg.simple_score_weight_eps
    w_div = cfg.simple_score_weight_div
    w_pe = cfg.simple_score_weight_pe

    df["Score_raw"] = (rev_score * (w_rev / 100) +
                       eps_score * (w_eps / 100) +
                       div_score * (w_div / 100) +
                       pe_score * (w_pe / 100))

    df["Score"] = df["Score_raw"].where(mask, pd.NA)
    df["通過門檻"] = mask

    print("\n" + "=" * 60 + " DEBUG 結束 " + "=" * 60 + "\n")

    return df


# ==========================================================
# 強化版技術指標
# ==========================================================

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

def load_stock_list_from_excel(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到 Excel: {file_path}")
    df = pd.read_excel(file_path)
    col = find_col(df.columns, ["股票", "code"])
    if col is None:
        raise ValueError("Excel 必須包含 '股票代號' 或 'code' 欄位")
    return df[col].astype(str).str.strip().tolist()


# ==========================================================
# History Cache System
# ==========================================================

def get_history_file(stock_id, history_months):
    return f"{HISTORY_DIR}/{stock_id}_{history_months}m.xlsx"


def init_stock_history(session, cfg, stock_id, history_months):
    months = month_starts_back(history_months)
    frames = []
    for m in months:
        df = fetch_twse_stock_day_month(session, cfg, stock_id, m)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames)
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def update_stock_history(session, cfg, stock_id, df_old):
    today_month = datetime.today().strftime("%Y%m01")
    df_new = fetch_twse_stock_day_month(session, cfg, stock_id, today_month)
    if df_new is None or df_new.empty:
        return df_old
    df_all = pd.concat([df_old, df_new])
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def get_stock_history(session, cfg, stock_id, logger, history_months):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    file_path = get_history_file(stock_id, history_months)
    if not os.path.exists(file_path):
        logger.log(f"📥 [{stock_id}] 初始化 {history_months} 個月歷史資料")
        df = init_stock_history(session, cfg, stock_id, history_months)
        save_cache(file_path, df)
        return df
    df_old, _ = load_cache(file_path)
    logger.log(f"🔄 [{stock_id}] 更新當月資料")
    df_new = update_stock_history(session, cfg, stock_id, df_old)
    save_cache(file_path, df_new)
    return df_new


def fetch_csv_requests(session: requests.Session, url: str, cfg: StrategyConfig,
                       encodings=("utf-8-sig", "utf-8")) -> pd.DataFrame:
    r = session.get(url, timeout=cfg.timeout, verify=cfg.verify_ssl)
    r.raise_for_status()
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception:
            continue
    raise RuntimeError(f"讀取失敗：{url}")


# ==========================================================
# Data fetchers
# ==========================================================

def fetch_prices(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

    try:
        twse_response = session.get(twse_url, timeout=cfg.timeout)
        twse_response.raise_for_status()
        twse = pd.DataFrame(twse_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上市股價失敗：{e}")
        twse = pd.DataFrame()

    try:
        tpex_response = session.get(tpex_url, timeout=cfg.timeout)
        tpex_response.raise_for_status()
        tpex = pd.DataFrame(tpex_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上櫃股價失敗：{e}")
        tpex = pd.DataFrame()

    if twse.empty and tpex.empty:
        print("❌ 無法讀取任何股價資料")
        return pd.DataFrame()

    twse = twse.rename(columns={
        find_col(twse.columns, ["證券代號", "Code"]): "股票代號",
        find_col(twse.columns, ["證券名稱", "Name"]): "公司名稱_來源",
        find_col(twse.columns, ["收盤價", "ClosingPrice"]): "股價",
        find_col(twse.columns, ["漲跌價差", "Change"]): "漲跌",
    })

    tpex = tpex.rename(columns={
        find_col(tpex.columns, ["SecuritiesCompanyCode", "股票代號", "Code"]): "股票代號",
        find_col(tpex.columns, ["CompanyName", "公司名稱", "Name"]): "公司名稱_來源",
        find_col(tpex.columns, ["Close", "收盤", "ClosingPrice"]): "股價",
        find_col(tpex.columns, ["Change", "漲跌"]): "漲跌",
    })

    price = pd.concat([twse[["股票代號", "公司名稱_來源", "股價", "漲跌"]],
                       tpex[["股票代號", "公司名稱_來源", "股價", "漲跌"]]], ignore_index=True)
    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    price = price.drop_duplicates("股票代號").reset_index(drop=True)
    return price


def fetch_revenue_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv"]
    rev = pd.concat([fetch_csv_requests(session, u, cfg) for u in urls], ignore_index=True)

    code_col = find_col(rev.columns, ["公司代號"])
    ym_col = find_col(rev.columns, ["資料年月"])
    rev_col = find_col(rev.columns, ["營業收入-當月營收", "當月營收"])
    yoy_col = find_col(rev.columns, ["累計營業收入-前期比較增減", "前期比較增減"])
    yoy2_col = find_col(rev.columns, ["營業收入-去年同月增減", "去年同月增減"])

    if code_col is None or ym_col is None or rev_col is None:
        raise RuntimeError(f"營收欄位無法識別：{rev.columns}")

    rename_map = {code_col: "股票代號", ym_col: "年月", rev_col: "當月營收"}
    if yoy_col:
        rename_map[yoy_col] = "累計年增(%)"
    if yoy2_col:
        rename_map[yoy2_col] = "當月年增(%)"

    rev = rev.rename(columns=rename_map)
    rev["股票代號"] = rev["股票代號"].astype(str).str.strip()
    rev["年月"] = pd.to_numeric(rev["年月"], errors="coerce")

    latest_month = rev["年月"].max()
    rev = rev[rev["年月"] == latest_month].copy()

    rev["當月營收(億元)"] = to_num_series(rev["當月營收"]) / 1e8
    if "累計年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["累計年增(%)"])
    elif "當月年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["當月年增(%)"])
    else:
        rev["營收YoY(%)"] = 0.0

    return rev[["股票代號", "年月", "當月營收(億元)", "營收YoY(%)"]].drop_duplicates("股票代號").reset_index(drop=True)


def fetch_eps_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv"]

    eps_list = []
    for url in urls:
        try:
            df = fetch_csv_requests(session, url, cfg)
            eps_list.append(df)
        except Exception as e:
            print(f"⚠️ 讀取 {url} 失敗：{e}")

    if not eps_list:
        return pd.DataFrame()

    eps = pd.concat(eps_list, ignore_index=True)

    code_col = find_col(eps.columns, ["公司代號", "證券代號"])
    year_col = find_col(eps.columns, ["年度", "西元年度"])
    q_col = find_col(eps.columns, ["季別", "季度"])
    eps_col = find_col(eps.columns, ["基本每股盈餘(元)", "基本每股盈餘", "每股盈餘"])

    if None in [code_col, year_col, q_col, eps_col]:
        print(f"❌ 找不到必要欄位")
        return pd.DataFrame()

    eps = eps.rename(columns={
        code_col: "股票代號",
        year_col: "年度",
        q_col: "季別",
        eps_col: "EPS"
    })

    eps["股票代號"] = eps["股票代號"].astype(str).str.strip()
    eps["年度"] = pd.to_numeric(eps["年度"], errors="coerce")
    eps["季別"] = pd.to_numeric(eps["季別"], errors="coerce")
    eps["EPS"] = pd.to_numeric(eps["EPS"], errors="coerce")

    latest_year = eps["年度"].max()
    latest_q = eps.loc[eps["年度"] == latest_year, "季別"].max()

    cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS本期"})
    prev = eps[(eps["年度"] == latest_year - 1) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS去年"})

    # ========== DEBUG: 查看所有年度資料 ==========
    print("\n" + "=" * 60)
    print("🔍 [DEBUG] EPS 年度資料分布")
    print("=" * 60)

    # 顯示所有年度
    years = eps["年度"].dropna().unique()
    years.sort()
    print(f"📊 資料中的年度: {years}")

    # 顯示每個年度的季別
    for year in years:
        quarters = eps[eps["年度"] == year]["季別"].dropna().unique()
        quarters.sort()
        print(f"   {int(year)}年: Q{quarters}")

    # 顯示資料筆數統計
    print(f"\n📊 各年度季別資料筆數:")
    year_q_counts = eps.groupby(["年度", "季別"]).size()
    for (year, q), count in year_q_counts.items():
        print(f"   {int(year)}年 Q{int(q)}: {count} 筆")

    # 顯示前幾筆原始資料範例
    print(f"\n📋 原始資料範例 (前5筆):")
    for idx in range(min(5, len(eps))):
        row = eps.iloc[idx]
        print(f"   {row['年度']}年 Q{row['季別']} | {row['股票代號']} | EPS: {row['EPS']}")

    print("=" * 60 + "\n")
    # ========== DEBUG 結束 ==========

    out = cur.merge(prev, on="股票代號", how="left")

    def safe_yoy(row):
        if pd.isna(row["EPS去年"]) or row["EPS去年"] == 0:
            return pd.NA
        return (row["EPS本期"] - row["EPS去年"]) / abs(row["EPS去年"])

    out["EPSYoY_raw"] = out.apply(safe_yoy, axis=1)
    out["EPSYoY_顯示(%)"] = out["EPSYoY_raw"].apply(
        lambda x: round(x * 100, 2) if pd.notna(x) else pd.NA
    )
    out["EPS季別"] = f"{int(latest_year)}Q{int(latest_q)}"

    # ========== DEBUG 訊息 ==========
    print(f"\n📊 EPS 資料筆數: {len(out)}")
    print(f"📊 有 EPS YoY 資料的筆數: {out['EPSYoY_raw'].notna().sum()}")

    sample = out[out['EPSYoY_raw'].notna()].head(5)
    if len(sample) > 0:
        print(f"\n📋 EPS YoY 範例:")
        for _, row in sample.iterrows():
            print(f"   {row['股票代號']} | 本期EPS: {row['EPS本期']} | YoY: {row['EPSYoY_顯示(%)']}%")
    else:
        print(f"\n⚠️ 沒有找到任何有 YoY 資料的股票！")
    # ========== DEBUG 結束 ==========

    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates(
        "股票代號").reset_index(drop=True)


# ==========================================================
# TWSE STOCK_DAY fetch
# ==========================================================

def safe_parse_json(r):
    text = (r.text or "").strip()
    if not text or text.startswith("<"):
        return None
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return r.json()
    except Exception:
        return None


def fetch_twse_stock_day_month(session: requests.Session, cfg: StrategyConfig, stock_no: str, yyyymm01: str) -> pd.DataFrame:
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}

    for attempt in range(1, cfg.twse_retries + 1):
        try:
            r = session.get(url, params=params, timeout=cfg.timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")

            js = safe_parse_json(r)
            if js is None or js.get("stat") != "OK" or "data" not in js:
                return pd.DataFrame()

            fields = js.get("fields", [])
            data = js.get("data", [])
            if not fields or not data:
                return pd.DataFrame()

            dfm = pd.DataFrame(data, columns=fields)

            date_col = find_col(dfm.columns, ["日期"])
            vol_col = find_col(dfm.columns, ["成交股數"])
            close_col = find_col(dfm.columns, ["收盤價"])
            if date_col is None or close_col is None:
                return pd.DataFrame()

            rename_map = {date_col: "Date_roc", close_col: "Close"}
            if vol_col:
                rename_map[vol_col] = "Volume"
            dfm = dfm.rename(columns=rename_map)

            dfm["Date"] = pd.to_datetime(dfm["Date_roc"].apply(roc_to_ad))
            dfm["股票代號"] = str(stock_no).strip()
            dfm["Close"] = to_num_series(dfm["Close"])
            if "Volume" in dfm.columns:
                dfm["Volume"] = to_num_series(dfm["Volume"])
            else:
                dfm["Volume"] = pd.NA

            return dfm[["Date", "股票代號", "Close", "Volume"]].dropna(subset=["Date", "Close"])

        except Exception:
            if attempt == cfg.twse_retries:
                return pd.DataFrame()
            time.sleep(cfg.twse_backoff * attempt)
    return pd.DataFrame()


def fetch_twse_history(session: requests.Session, cfg: StrategyConfig, codes: List[str], logger: GuiLogger, history_months: int) -> pd.DataFrame:
    hist_list = []
    for code in codes:
        try:
            df = get_stock_history(session, cfg, code, logger, history_months)
            if df is not None and not df.empty:
                df["股票代號"] = code
                hist_list.append(df)
        except Exception as e:
            logger.log(f"❌ [{code}] 歷史資料錯誤: {e}")
    if not hist_list:
        return pd.DataFrame()
    return pd.concat(hist_list, ignore_index=True)


def run_tech(cfg: StrategyConfig, session: requests.Session, codes: List[str], logger: GuiLogger, history_months: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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


# ==========================================================
# Backtest Functions
# ==========================================================

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

    cash = 1.0
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
    from_cache = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
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

def autosize_columns(ws, min_w=10, max_w=44):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(min_w, min(max_w, max_len + 2))


def style_header(ws, header_row):
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[header_row]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_explanation(ws, lines, start_row=1, start_col=1):
    title_font = Font(bold=True, size=12)
    normal_font = Font(size=11)
    for i, line in enumerate(lines):
        c = ws.cell(row=start_row + i, column=start_col, value=line)
        c.font = title_font if i == 0 else normal_font
        c.alignment = Alignment(wrap_text=True, vertical="top")


def highlight_true(ws, header_row, col_name):
    header_cells = list(ws[header_row])
    idx = None
    for i, cell in enumerate(header_cells, 1):
        if cell.value == col_name:
            idx = i
            break
    if idx is None:
        return
    col_letter = get_column_letter(idx)
    rng = f"{col_letter}{header_row + 1}:{col_letter}{ws.max_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=["TRUE"],
                                                  fill=PatternFill("solid", fgColor="FFF2CC")))


# ==========================================================
# Pipeline (核心執行流程)
# ==========================================================

def run_pipeline(cfg: StrategyConfig, logger: GuiLogger):
    s = build_session()

    logger.log("=" * 60)
    logger.log("🚀 StockTool v0.9.3 開始執行")
    logger.log(f"   評分系統: {'多因子評分' if cfg.use_enhanced_score else '簡易評分'}")
    logger.log(f"   技術指標: 強化版 (MTF={cfg.use_mtf_confirmation}, 背離={cfg.use_divergence_detection})")
    logger.log("=" * 60)

    logger.log("1) 取得股價資料...")
    price = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
    price = ensure_str_column(price, "股票代號")

    logger.log("2) 取得月營收...")
    revenue = get_or_fetch("revenue", lambda: fetch_revenue_latest(s, cfg), logger)
    revenue = ensure_str_column(revenue, "股票代號")

    logger.log("3) 取得 EPS...")
    eps_data = get_or_fetch("eps", lambda: fetch_eps_latest(s, cfg), logger)
    eps_data = ensure_str_column(eps_data, "股票代號")

    logger.log("4) 合併基本面資料...")
    df_sel = price.merge(revenue, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_data, on="股票代號", how="left")
    df_sel = ensure_str_column(df_sel, "股票代號")

    if "EPSYoY_顯示(%)" in eps_data.columns:
        df_sel["EPSYoY_顯示(%)"] = df_sel["EPSYoY_顯示(%)"]
    else:
        if "EPSYoY_raw" in df_sel.columns:
            df_sel["EPSYoY_顯示(%)"] = (df_sel["EPSYoY_raw"] * 100).fillna(0).round(2)
        else:
            df_sel["EPSYoY_顯示(%)"] = 0

    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # ==========================================================
    # v0.9.2：Top10 基本面回測模式
    # ==========================================================

    if cfg.use_top10_backtest:
        logger.log("=" * 60)
        logger.log("📊 啟動 Top10 基本面回測模式")
        logger.log("   ※ 直接使用 Score 最高的 10 檔股票建倉")
        logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
        logger.log("=" * 60)

        # ========== DEBUG: 基本面資料診斷 ==========
        print("\n" + "=" * 60)
        print("🔍 [DEBUG] 基本面資料合併後診斷")
        print("=" * 60)

        print(f"\n📊 df_sel 總筆數: {len(df_sel)}")
        print(f"📊 有營收YoY的筆數: {df_sel['營收YoY(%)'].notna().sum()}")
        print(f"📊 有EPS本期(非ETF)的筆數: {df_sel['EPS本期'].notna().sum()}")
        print(f"📊 有EPSYoY_raw的筆數: {df_sel['EPSYoY_raw'].notna().sum()}")

        # 顯示前5筆有EPS資料的股票
        eps_notna = df_sel[df_sel['EPS本期'].notna()].head(5)
        if len(eps_notna) > 0:
            print(f"\n📋 有EPS資料的前5檔股票:")
            for idx, row in eps_notna.iterrows():
                print(
                    f"   {row['股票代號']} {row.get('公司名稱_來源', '')} | EPS: {row.get('EPS本期', 'N/A')} | EPS YoY: {row.get('EPSYoY_顯示(%)', 'N/A')}%")
        else:
            print(f"\n⚠️ 沒有任何股票有 EPS 資料！")
            print(f"   請檢查 fetch_eps_latest 函數是否正常運作。")

        print("\n" + "=" * 60 + "\n")
        # ========== DEBUG 結束 ==========



        if cfg.use_enhanced_score:
            df_sel = calculate_multi_factor_score(df_sel, cfg)
            logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
        else:
            df_sel = calculate_simple_score(df_sel, cfg)

        df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

        top10_codes = df_sel.head(10)["股票代號"].dropna().astype(str).str.strip().tolist()
        logger.log(f"   Top10 股票: {top10_codes}")

        tech_all_top10, tech_today_top10, buy_today_top10 = run_tech(cfg, s, top10_codes, logger, cfg.history_months)

        if tech_all_top10.empty:
            logger.log("❌ 無法獲取 Top10 股票的歷史資料")
            return

        tech_all_top10["買點"] = True
        tech_all_top10["買點_基礎"] = True
        tech_all_top10["確認層級"] = 3

        score_map = df_sel.set_index("股票代號")["Score"].to_dict()
        gate_map = build_gate_map(cfg, df_sel)
        eq_top10, trades_top10, pf_kpi_top10, reason_stats_top10 = portfolio_backtest_topk_event(
            cfg, tech_all_top10, score_map, gate_map
        )
        sig_summary_top10 = signal_level_backtest_event(cfg, tech_all_top10)

        logger.log("\n" + "=" * 60)
        logger.log("📊 Top10 基本面回測結果")
        logger.log("=" * 60)
        logger.log("✅ Signal-level KPI:")
        logger.log(sig_summary_top10.to_string(index=False) if not sig_summary_top10.empty else "(無訊號)")
        logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
        logger.log(pf_kpi_top10.to_string(index=False) if not pf_kpi_top10.empty else "(無投組資料)")

        out_file = f"{cfg.out_file_prefix}_Top10Backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        startrow = 6
        name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            format_for_output(df_sel.head(10), sort_by_code=True).to_excel(writer, index=False, sheet_name="Top10_股票列表")
            if not eq_top10.empty:
                eq_top10.to_excel(writer, index=False, sheet_name="投組回測", startrow=startrow)
            if not trades_top10.empty:
                trades_out = trades_top10.merge(name_map, on="股票代號", how="left")
                trades_out = format_for_output(trades_out, sort_by_code=True)
                # ✅ 按進場日排序
                if "進場日" in trades_out.columns:
                    trades_out = trades_out.sort_values("進場日")
                trades_out.to_excel(writer, index=False, sheet_name="交易明細", startrow=0)
            if not pf_kpi_top10.empty:
                pf_kpi_top10.to_excel(writer, index=False, sheet_name="績效摘要", startrow=startrow)
            if not reason_stats_top10.empty:
                reason_stats_top10.to_excel(writer, index=False, sheet_name="出場原因統計")

        logger.log(f"✅ Top10 回測完成 → {out_file}")
        return

    # ==========================================================
    # 正常回測模式
    # ==========================================================

    if cfg.use_enhanced_score:
        df_sel_temp = calculate_multi_factor_score(df_sel, cfg)
        logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
    else:
        df_sel_temp = calculate_simple_score(df_sel, cfg)
        w_rev = cfg.simple_score_weight_rev
        w_eps = cfg.simple_score_weight_eps
        w_div = cfg.simple_score_weight_div
        w_pe = cfg.simple_score_weight_pe
        logger.log(f"   權重: 營收{w_rev:.0f}% / EPS{w_eps:.0f}% / 殖利率{w_div:.0f}% / PE{w_pe:.0f}%")

    df_sel_temp = df_sel_temp.sort_values("Score", ascending=False).reset_index(drop=True)

    logger.log(f"5) 抓取前 {cfg.top_n_for_tech} 檔股票的歷史日K...")

    if cfg.use_excel_stock_list:
        logger.log("📂 使用 Excel 指定股票清單")
        try:
            tech_codes = load_stock_list_from_excel(cfg.excel_stock_file)
        except Exception as e:
            logger.log(f"❌ Excel 選股失敗：{e}")
            return

        # ✅ v0.9.3 Excel 清單強制買點模式
        if cfg.excel_force_buy:
            logger.log("   📊 啟用 Excel 清單強制買點模式")
            logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
    else:
        tech_codes = df_sel_temp.head(cfg.top_n_for_tech)["股票代號"].dropna().astype(str).str.strip().tolist()
    logger.log(f"   選股檔數: {len(tech_codes)}，每檔 {cfg.history_months} 個月歷史資料")

    #tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)
    tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)

    # ✅ v0.9.3 Excel 清單強制買點模式：將買點強制設為 True
    if cfg.use_excel_stock_list and cfg.excel_force_buy:
        if not tech_all.empty:
            tech_all["買點"] = True
            tech_all["買點_基礎"] = True
            tech_all["確認層級"] = 3
            logger.log("   🔧 已強制將所有日期設為買點")

    if tech_all.empty:
        logger.log("❌ 無歷史資料，請檢查網路連線")
        return

    if cfg.use_enhanced_score:
        df_sel = calculate_multi_factor_score(df_sel, cfg)
    else:
        df_sel = calculate_simple_score(df_sel, cfg)

    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > cfg.strong_revenue_yoy) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < cfg.strong_pe_max) &
        (df_sel["股價"] > cfg.strong_price_min)
    ].copy()
    top10_sel = df_sel.head(10).copy()

    logger.log("6) 執行回測...")
    gate_map = build_gate_map(cfg, df_sel)
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi, reason_stats = portfolio_backtest_topk_event(cfg, tech_all, score_map, gate_map)
    sig_summary = signal_level_backtest_event(cfg, tech_all)

    try:
        yearly_perf = performance_by_year(trades)
        logger.log("✅ 年度績效分析：")
        if not yearly_perf.empty:
            logger.log(yearly_perf.to_string(index=False))
    except Exception as e:
        logger.log(f"⚠️ 年度績效分析失敗：{e}")
        yearly_perf = pd.DataFrame()

    wf_results = pd.DataFrame()
    if cfg.wf_enabled:
        logger.log("7) 執行 Walk-forward 分析...")
        wf_results = run_walk_forward(cfg, logger, s)

    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    name_map = ensure_str_column(name_map, "股票代號")
    eps_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    df_out_all = format_for_output(df_sel, sort_by_code=True)
    strong_out = format_for_output(strong_sel, sort_by_code=True)
    top10_out = format_for_output(top10_sel, sort_by_code=True)

    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today = ensure_str_column(tech_today, "股票代號")
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_disp_map)
        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    if buy_today is None or buy_today.empty:
        buy_today_out = pd.DataFrame([{
            "說明": "今日無符合買點條件的股票",
            "可能原因": "1. 市場震盪或下跌 2. 買點條件設定較嚴格 3. 選股檔數不足",
            "建議調整參數": "放寬 RSI_OVERSOLD / 關閉成交量過濾 / 關閉趨勢過濾 / 增加選股檔數",
            "當前 RSI_OVERSOLD": cfg.rsi_oversold,
            "當前 Volume Filter": cfg.require_volume_filter,
            "當前 Trend Filter": cfg.require_trend_filter,
            "當前 MTF Filter": cfg.use_mtf_confirmation,
            "選股檔數 (TopN)": cfg.top_n_for_tech,
            "歷史月數": cfg.history_months
        }])
        logger.log("   📭 今日無買點訊號（已建立診斷說明 Sheet）")
    else:
        buy_today = ensure_str_column(buy_today, "股票代號")
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_disp_map)
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)
        logger.log(f"   📈 今日買點數量: {len(buy_today_out)} 檔")
    # ==========================================================
    # ✅ v0.9.3 今日出場清單（計算當日需要賣出的股票）
    # ==========================================================

    exit_today_list = []

    if trades is not None and not trades.empty:
        # 獲取最新交易日
        latest_date = tech_today["Date"].max() if not tech_today.empty else datetime.now()

        # 獲取所有有進場但尚未出場的股票
        for code in tech_codes:
            code_trades = trades[trades["股票代號"] == code]
            if code_trades.empty:
                continue

            # 找出最新的出場日
            if "出場日" in code_trades.columns:
                last_exit = code_trades["出場日"].max()
                # 如果最後出場日 < 最新交易日，且還有進場記錄，表示仍在持有中
                if pd.to_datetime(last_exit) < pd.to_datetime(latest_date):
                    # 找出該股票最新的進場記錄（在最後出場日之後）
                    code_entries = code_trades[code_trades["出場日"] <= last_exit] if last_exit else code_trades
                    if not code_entries.empty:
                        latest_entry = code_entries.sort_values("進場日", ascending=False).iloc[0]
                        entry_price = latest_entry["進場價"]
                        entry_date = latest_entry["進場日"]

                        # 獲取當前價格
                        code_tech = tech_today[tech_today["股票代號"] == code]
                        if not code_tech.empty:
                            current_price = code_tech.iloc[0]["Close"]
                            ret = (current_price - entry_price) / entry_price
                            rsi = code_tech.iloc[0]["RSI"] if "RSI" in code_tech.columns else None
                            hold_days = (pd.to_datetime(latest_date) - pd.to_datetime(entry_date)).days

                            # 檢查出場條件
                            exit_reason = None
                            if ret <= cfg.stop_loss:
                                exit_reason = "STOP_LOSS"
                            elif ret >= cfg.take_profit:
                                exit_reason = "TAKE_PROFIT"
                            elif rsi is not None and rsi >= cfg.exit_rsi:
                                exit_reason = "RSI_EXIT"
                            elif hold_days >= cfg.hold_days:
                                exit_reason = "TIME_EXIT"

                            if exit_reason is not None:
                                # ✅ 獲取公司名稱
                                company_name = name_map[name_map["股票代號"] == code]["公司名稱_來源"].values
                                company_name_str = company_name[0] if len(company_name) > 0 else ""

                                exit_today_list.append({
                                    "股票代號": code,
                                    "公司名稱": company_name_str,
                                    "進場日": entry_date,
                                    "進場價": round(entry_price, 2),
                                    "今日收盤價": round(current_price, 2),
                                    "累計報酬(%)": round(ret * 100, 2),
                                    "持有天數": hold_days,
                                    "出場原因": exit_reason,
                                    "當前 RSI": round(rsi, 1) if rsi else None
                                })

    exit_today_df = pd.DataFrame(exit_today_list)

    if exit_today_df.empty:
        exit_today_df = pd.DataFrame([{
            "說明": "今日無需要出場的股票",
            "可能原因": "1. 無持股 2. 所有持倉均未觸發出場條件",
            "當前停損門檻": f"{cfg.stop_loss * 100:.1f}%",
            "當前停利門檻": f"{cfg.take_profit * 100:.1f}%",
            "當前 RSI 出場門檻": cfg.exit_rsi,
            "最大持有天數": cfg.hold_days
        }])
        logger.log("   📭 今日無出場訊號（已建立診斷說明 Sheet）")
    else:
        logger.log(f"   📤 今日出場數量: {len(exit_today_df)} 檔")

    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "出場原因", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades = ensure_str_column(trades, "股票代號")
        trades_out = trades.merge(name_map, on="股票代號", how="left")
        trades_out = format_for_output(trades_out, sort_by_code=True)
        if "進場日" in trades_out.columns:
            trades_out = trades_out.sort_values("進場日")

    out_file = f"{cfg.out_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6


    logger.log(f"8) 輸出 Excel: {out_file}")

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        if not tech_today_out.empty:
            tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)

        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)
        # ✅ v0.9.3 今日出場清單
        exit_today_df.to_excel(writer, index=False, sheet_name="今日出場清單", startrow=startrow)

        if not reason_stats.empty:
            reason_stats.to_excel(writer, index=False, sheet_name="出場原因統計")

        summary_sheet = pd.concat([pd.DataFrame([{"區塊": "Signal-level"}]),
                                   sig_summary,
                                   pd.DataFrame([{"區塊": f"Portfolio-level (Top{cfg.topk})"}]),
                                   pf_kpi], ignore_index=True)
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        if not eq.empty:
            eq.to_excel(writer, index=False, sheet_name="投組回測_TopK等權", startrow=startrow)
        if not trades_out.empty:
            trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)
        if not yearly_perf.empty:
            yearly_perf.to_excel(writer, sheet_name="年度績效", index=False)
        if not wf_results.empty:
            wf_results.to_excel(writer, sheet_name="WalkForward分析", index=False)
        # ==========================================================
        # Excel 美化（技術買點_今日、今日出場清單等）
        # ==========================================================

        # 技術買點_今日美化
        if "技術買點_今日" in writer.sheets:
            ws_buy = writer.sheets["技術買點_今日"]

            # 檢查是否有實際買點
            first_cell = ws_buy.cell(row=startrow + 1, column=1).value if ws_buy.max_row > startrow else None

            if first_cell == "說明":
                buy_explain = [
                    "【技術買點_今日】診斷說明",
                    "今日無符合買點條件的股票。",
                    "",
                    "可能的調整方式：",
                    f"  - 降低 RSI_OVERSOLD（目前為 {cfg.rsi_oversold}）",
                    f"  - 關閉「成交量過濾」require_volume_filter",
                    f"  - 關閉「趨勢過濾」require_trend_filter",
                    f"  - 關閉「多時間框架確認」use_mtf_confirmation",
                    f"  - 增加選股檔數 TopN_for_Tech（目前為 {cfg.top_n_for_tech}）",
                    "",
                    "※ 買點條件較嚴格時，可能數日無訊號，屬正常現象。"
                ]
                write_explanation(ws_buy, buy_explain, start_row=startrow + len(buy_today_out) + 2)
            else:
                buy_explain = [
                    "【技術買點_今日】說明",
                    "買點 = 超跌(過去10天RSI低於門檻) + 轉強(RSI回升或MACD翻正) + 趨勢(站穩MA20) + 成交量過濾",
                    "多時間框架確認：週線/月線趨勢確認可提高買點品質"
                ]
                write_explanation(ws_buy, buy_explain)

            header_row = startrow + 1
            style_header(ws_buy, header_row)
            ws_buy.freeze_panes = ws_buy[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_buy.max_column)
            ws_buy.auto_filter.ref = f"A{header_row}:{last_col}{ws_buy.max_row}"
            autosize_columns(ws_buy)

            # 只有在有實際買點時才高亮「買點」欄位
            if first_cell != "說明" and "買點" in [cell.value for cell in ws_buy[header_row]]:
                highlight_true(ws_buy, header_row, "買點")

        # 今日出場清單美化
        if "今日出場清單" in writer.sheets:
            ws_exit = writer.sheets["今日出場清單"]

            # 檢查是否有實際出場
            first_cell = ws_exit.cell(row=startrow + 1, column=1).value if ws_exit.max_row > startrow else None

            if first_cell == "說明":
                exit_explain = [
                    "【今日出場清單】診斷說明",
                    "今日無需要出場的股票。",
                    "",
                    "出場條件：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天",
                    "",
                    "如果持有股票但未觸發條件，表示仍在正常持有中。"
                ]
                write_explanation(ws_exit, exit_explain, start_row=startrow + len(exit_today_df) + 2)
            else:
                exit_explain = [
                    "【今日出場清單】說明",
                    "以下股票今日觸發賣出條件，建議賣出：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天"
                ]
                write_explanation(ws_exit, exit_explain)

            header_row = startrow + 1
            style_header(ws_exit, header_row)
            ws_exit.freeze_panes = ws_exit[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_exit.max_column)
            ws_exit.auto_filter.ref = f"A{header_row}:{last_col}{ws_exit.max_row}"
            autosize_columns(ws_exit)
    logger.log("\n" + "=" * 60)
    logger.log("📊 回測結果摘要")
    logger.log("=" * 60)
    logger.log("✅ Signal-level KPI:")
    logger.log(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
    logger.log(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")
    logger.log("\n✅ 出場原因統計:")
    logger.log(reason_stats.to_string(index=False) if not reason_stats.empty else "(無交易資料)")
    logger.log(f"\n✅ 完成 → {out_file}")


# ==========================================================
# GUI 主視窗
# ==========================================================

class StrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StockTool v0.9.4-GUI (Multi-Factor + Top10 Backtest + Portfolio)")

        self.log_queue = queue.Queue()
        self.logger = GuiLogger(self.log_queue)

        saved_config = load_config()
        self.cfg = StrategyConfig()
        self.cfg.update_from_dict(saved_config)

        # V0.9.4 買賣記錄
        self.portfolio = PortfolioDB(DEFAULT_PORTFOLIO_DB)
        # 記憶體中現價（stock_id → price）
        self._current_prices: Dict[str, float] = {}

        self._build_ui()
        self._poll_log_queue()
        self._load_config_to_ui()

    def _build_ui(self):
        self.geometry("1280x720")

        # V0.9.4 Tab 化：notebook 包兩個分頁（不改 V0.9.3 既有 widget 結構）
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1：策略參數（V0.9.3 原本內容搬進來）
        strategy_tab = ttk.Frame(self.notebook)
        self.notebook.add(strategy_tab, text="⚙️ 策略參數")

        # Tab 2：買賣記錄（V0.9.4 新增）
        self.portfolio_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.portfolio_tab, text="📒 買賣記錄")
        self._build_portfolio_tab(self.portfolio_tab)

        # 綁定 Tab 切換 → 切到買賣記錄時自動 refresh
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # V0.9.3 原本的 container（左參數 + 右 Console），改掛到 strategy_tab 下
        container = ttk.Frame(strategy_tab)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        left_canvas = tk.Canvas(container, width=400)
        left_scrollbar = ttk.Scrollbar(container, orient="vertical", command=left_canvas.yview)
        left_scrollable_frame = ttk.Frame(left_canvas)

        left_scrollable_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.create_window((0, 0), window=left_scrollable_frame, anchor="nw", width=380)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="left", fill="y")

        right = ttk.Frame(container)
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        left = left_scrollable_frame

        ttk.Label(left, text="⚙️ 策略參數設定", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))

        self.vars: Dict[str, tk.Variable] = {}

        # 1. 基本參數
        basic_frame = ttk.LabelFrame(left, text="📊 基本參數", padding=5)
        basic_frame.pack(fill="x", pady=5)
        self._add_entry(basic_frame, "選股檔數 (TopN)", "top_n_for_tech", tk.IntVar, self.cfg.top_n_for_tech)
        self._add_entry(basic_frame, "歷史月數", "history_months", tk.IntVar, self.cfg.history_months)
        self._add_entry(basic_frame, "回測月數", "tech_months", tk.IntVar, self.cfg.tech_months)
        self._add_entry(basic_frame, "持股檔數 (TopK)", "topk", tk.IntVar, self.cfg.topk)

        # 2. 評分系統
        score_frame = ttk.LabelFrame(left, text="⭐ 評分系統", padding=5)
        score_frame.pack(fill="x", pady=5)

        self.use_enhanced_score_var = tk.BooleanVar(value=self.cfg.use_enhanced_score)
        ttk.Radiobutton(score_frame, text="多因子評分 (動能+成長)", variable=self.use_enhanced_score_var, value=True).pack(anchor="w")
        ttk.Radiobutton(score_frame, text="簡易評分 (可調權重+門檻)", variable=self.use_enhanced_score_var, value=False).pack(anchor="w")

        weight_frame = ttk.Frame(score_frame)
        weight_frame.pack(fill="x", pady=5)
        ttk.Label(weight_frame, text="因子權重:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._add_entry(weight_frame, "動能1M", "factor_weight_mom1", tk.DoubleVar, self.cfg.factor_weight_mom1)
        self._add_entry(weight_frame, "動能3M", "factor_weight_mom3", tk.DoubleVar, self.cfg.factor_weight_mom3)
        self._add_entry(weight_frame, "動能6M", "factor_weight_mom6", tk.DoubleVar, self.cfg.factor_weight_mom6)
        self._add_entry(weight_frame, "營收YoY", "factor_weight_rev", tk.DoubleVar, self.cfg.factor_weight_rev)
        self._add_entry(weight_frame, "EPS YoY", "factor_weight_eps", tk.DoubleVar, self.cfg.factor_weight_eps)

        self.adv_btn = ttk.Button(score_frame, text="⚙ 簡易評分進階設定", command=self._open_simple_score_settings)
        self.adv_btn.pack(fill="x", pady=(6, 0))

        # 3. 技術指標
        tech_frame = ttk.LabelFrame(left, text="📈 技術指標 (強化版)", padding=5)
        tech_frame.pack(fill="x", pady=5)

        self.mtf_var = tk.BooleanVar(value=self.cfg.use_mtf_confirmation)
        ttk.Checkbutton(tech_frame, text="多時間框架確認 (週線/月線)", variable=self.mtf_var).pack(anchor="w")

        self.divergence_var = tk.BooleanVar(value=self.cfg.use_divergence_detection)
        ttk.Checkbutton(tech_frame, text="RSI 背離檢測", variable=self.divergence_var).pack(anchor="w")

        self._add_entry(tech_frame, "成交量爆發倍數", "volume_surge_multiplier", tk.DoubleVar,
                        self.cfg.volume_surge_multiplier)
        self._add_entry(tech_frame, "RSI 超賣門檻", "rsi_oversold", tk.IntVar, self.cfg.rsi_oversold)
        self._add_entry(tech_frame, "MA20 容忍度 (%)", "ma20_tolerance", tk.DoubleVar, self.cfg.ma20_tolerance * 100)

        self.volume_filter_var = tk.BooleanVar(value=self.cfg.require_volume_filter)
        ttk.Checkbutton(tech_frame, text="需要成交量過濾", variable=self.volume_filter_var).pack(anchor="w")

        # ✅ 進階技術參數
        ttk.Separator(tech_frame, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(tech_frame, text="--- 進階技術參數 ---", font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.trend_filter_var = tk.BooleanVar(value=self.cfg.require_trend_filter)
        ttk.Checkbutton(tech_frame, text="需要趨勢過濾 (站穩MA20)", variable=self.trend_filter_var).pack(anchor="w")

        self.use_aggressive_signal_var = tk.BooleanVar(value=self.cfg.use_aggressive_signal)
        ttk.Checkbutton(tech_frame, text="使用積極轉強訊號 (RSI門檻較高)",
                        variable=self.use_aggressive_signal_var).pack(anchor="w")

        self._add_entry(tech_frame, "RSI 轉強門檻 (積極)", "rsi_aggressive", tk.IntVar, self.cfg.rsi_aggressive)
        self._add_entry(tech_frame, "RSI 轉強門檻 (保守)", "rsi_recover", tk.IntVar, self.cfg.rsi_recover)
        self._add_entry(tech_frame, "超跌檢查天數", "oversold_lookback", tk.IntVar, self.cfg.oversold_lookback)
        self._add_entry(tech_frame, "MA20 斜率計算天數", "ma_slope_days", tk.IntVar, self.cfg.ma_slope_days)

        # 4. 出場參數
        exit_frame = ttk.LabelFrame(left, text="🚪 出場參數", padding=5)
        exit_frame.pack(fill="x", pady=5)
        self._add_entry(exit_frame, "停損 (%)", "stop_loss", tk.DoubleVar, self.cfg.stop_loss * 100)
        self._add_entry(exit_frame, "停利 (%)", "take_profit", tk.DoubleVar, self.cfg.take_profit * 100)
        self._add_entry(exit_frame, "RSI 出場", "exit_rsi", tk.IntVar, self.cfg.exit_rsi)
        self._add_entry(exit_frame, "最大持有天數", "hold_days", tk.IntVar, self.cfg.hold_days)
        self._add_entry(exit_frame, "交易成本 (%)", "roundtrip_cost_pct", tk.DoubleVar, self.cfg.roundtrip_cost_pct * 100)

        # 5. Walk-forward 分析
        wf_frame = ttk.LabelFrame(left, text="🔄 Walk-forward 分析", padding=5)
        wf_frame.pack(fill="x", pady=5)

        self.wf_enabled_var = tk.BooleanVar(value=self.cfg.wf_enabled)
        ttk.Checkbutton(wf_frame, text="啟用 Walk-forward 分析", variable=self.wf_enabled_var).pack(anchor="w")

        wf_params_frame = ttk.Frame(wf_frame)
        wf_params_frame.pack(fill="x", pady=5)
        self._add_entry(wf_params_frame, "訓練期 (年)", "wf_train_years", tk.IntVar, self.cfg.wf_train_years)
        self._add_entry(wf_params_frame, "測試期 (年)", "wf_test_years", tk.IntVar, self.cfg.wf_test_years)
        self._add_entry(wf_params_frame, "步進 (年)", "wf_step_years", tk.IntVar, self.cfg.wf_step_years)

        # 6. 選股來源
        source_frame = ttk.LabelFrame(left, text="📁 選股來源", padding=5)
        source_frame.pack(fill="x", pady=5)

        self.use_excel_var = tk.BooleanVar(value=self.cfg.use_excel_stock_list)
        ttk.Checkbutton(source_frame, text="使用 Excel 股票清單", variable=self.use_excel_var).pack(anchor="w")
        self._add_entry(source_frame, "Excel 檔案", "excel_stock_file", tk.StringVar, self.cfg.excel_stock_file)

        # ✅ v0.9.3 Excel 清單強制買點模式
        self.excel_force_buy_var = tk.BooleanVar(value=self.cfg.excel_force_buy)
        ttk.Checkbutton(
            source_frame,
            text="📊 Excel 清單強制買點模式（跳過技術買點過濾）",
            variable=self.excel_force_buy_var
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(source_frame, text="  ※ 使用 Excel 股票清單 + 不經過買點過濾（強制滿倉）", foreground="gray").pack(anchor="w")

        # v0.9.2 Top10 基本面回測開關
        self.top10_backtest_var = tk.BooleanVar(value=self.cfg.use_top10_backtest)
        ttk.Checkbutton(
            source_frame,
            text="📊 使用 Top10_基本面 進行回測（跳過技術買點）",
            variable=self.top10_backtest_var
        ).pack(anchor="w", pady=(5, 0))
        ttk.Label(source_frame, text="  ※ 直接使用評分最高的10檔股票建倉，不經過買點過濾", foreground="gray").pack(anchor="w")
        # 7. 強勢股過濾
        strong_frame = ttk.LabelFrame(left, text="💪 強勢股過濾 (報表用)", padding=5)
        strong_frame.pack(fill="x", pady=5)
        self._add_entry(strong_frame, "最低營收YoY (%)", "strong_revenue_yoy", tk.DoubleVar, self.cfg.strong_revenue_yoy)
        self._add_entry(strong_frame, "最高本益比", "strong_pe_max", tk.DoubleVar, self.cfg.strong_pe_max)
        self._add_entry(strong_frame, "最低股價", "strong_price_min", tk.DoubleVar, self.cfg.strong_price_min)

        # 8. 按鈕區
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill="x", pady=10)

        self.run_btn = ttk.Button(btn_frame, text="▶ 執行策略", command=self._on_run)
        self.run_btn.pack(fill="x", pady=2)

        self.save_btn = ttk.Button(btn_frame, text="💾 儲存設定", command=self._on_save_config)
        self.save_btn.pack(fill="x", pady=2)

        self.reset_btn = ttk.Button(btn_frame, text="🔄 載入預設", command=self._on_reset_config)
        self.reset_btn.pack(fill="x", pady=2)

        self.clear_btn = ttk.Button(btn_frame, text="🗑 清除控制台", command=self._on_clear_console)
        self.clear_btn.pack(fill="x", pady=2)

        # 右側 Console
        ttk.Label(right, text="📝 執行記錄 (Program Console)", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        console_frame = ttk.Frame(right)
        console_frame.pack(fill="both", expand=True, pady=(6, 0))

        self.console = tk.Text(console_frame, height=40, wrap="word")
        console_scrollbar = ttk.Scrollbar(console_frame, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=console_scrollbar.set)

        self.console.pack(side="left", fill="both", expand=True)
        console_scrollbar.pack(side="right", fill="y")

        tip = ("💡 提示:\n"
               "   - v0.9.2 新增: Top10 基本面回測模式\n"
               "   - 參數調整後可按「儲存設定」保存，下次啟動自動載入\n"
               "   - 左側面板可滾動查看所有參數")
        ttk.Label(right, text=tip, foreground="#555", justify="left").pack(anchor="w", pady=(6, 0))

    def _add_entry(self, parent, label, key, var_cls, default):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=18).pack(side="left")
        if var_cls == tk.BooleanVar:
            v = var_cls(value=default)
            ttk.Checkbutton(row, variable=v).pack(side="left")
        else:
            v = var_cls(value=default)
            ttk.Entry(row, textvariable=v, width=12).pack(side="left")
        self.vars[key] = v

    def _load_config_to_ui(self):
        for key, var in self.vars.items():
            if hasattr(self.cfg, key):
                value = getattr(self.cfg, key)
                if key in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                    value = value * 100.0
                var.set(value)
        self.use_enhanced_score_var.set(self.cfg.use_enhanced_score)
        self.use_excel_var.set(self.cfg.use_excel_stock_list)
        self.volume_filter_var.set(self.cfg.require_volume_filter)
        self.mtf_var.set(self.cfg.use_mtf_confirmation)
        self.divergence_var.set(self.cfg.use_divergence_detection)
        self.wf_enabled_var.set(self.cfg.wf_enabled)
        self.top10_backtest_var.set(self.cfg.use_top10_backtest)
        self.excel_force_buy_var.set(self.cfg.excel_force_buy)

        # ✅ 新增以下程式碼
        self.trend_filter_var.set(self.cfg.require_trend_filter)
        self.use_aggressive_signal_var.set(self.cfg.use_aggressive_signal)

    def _save_ui_to_config(self):
        for key, var in self.vars.items():
            if hasattr(self.cfg, key):
                value = var.get()
                if key in ["stop_loss", "take_profit", "roundtrip_cost_pct", "ma20_tolerance"]:
                    value = value / 100.0
                setattr(self.cfg, key, value)
        self.cfg.use_enhanced_score = self.use_enhanced_score_var.get()
        self.cfg.use_excel_stock_list = self.use_excel_var.get()
        self.cfg.require_volume_filter = self.volume_filter_var.get()
        self.cfg.use_mtf_confirmation = self.mtf_var.get()
        self.cfg.use_divergence_detection = self.divergence_var.get()
        self.cfg.wf_enabled = self.wf_enabled_var.get()
        self.cfg.use_top10_backtest = self.top10_backtest_var.get()
        self.cfg.excel_force_buy = self.excel_force_buy_var.get()

        # ✅ 新增以下程式碼
        self.cfg.require_trend_filter = self.trend_filter_var.get()
        self.cfg.use_aggressive_signal = self.use_aggressive_signal_var.get()

    def _on_save_config(self):
        self._save_ui_to_config()
        if save_config(self.cfg.to_dict()):
            self.logger.log("✅ 設定已儲存到 config.json")
        else:
            self.logger.log("❌ 設定儲存失敗")

    def _on_reset_config(self):
        if messagebox.askyesno("確認", "確定要恢復所有預設設定嗎？"):
            self.cfg.update_from_dict(DEFAULT_CONFIG)
            self._load_config_to_ui()
            save_config(self.cfg.to_dict())
            self.logger.log("🔄 已恢復預設設定")

    def _open_simple_score_settings(self):
        win = tk.Toplevel(self)
        win.title("簡易評分參數設定")
        win.geometry("550x650")
        win.transient(self)
        win.grab_set()

        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row = 0

        ttk.Label(scrollable_frame, text="═ 權重設定（總和建議100%） ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(10, 5), sticky="w")
        row += 1

        self.simple_vars = {}

        ttk.Label(scrollable_frame, text="營收YoY 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_rev"] = tk.DoubleVar(value=self.cfg.simple_score_weight_rev)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_rev"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="EPSYoY 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_eps"] = tk.DoubleVar(value=self.cfg.simple_score_weight_eps)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_eps"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="殖利率 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_div"] = tk.DoubleVar(value=self.cfg.simple_score_weight_div)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_div"], width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="本益比 權重 (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["weight_pe"] = tk.DoubleVar(value=self.cfg.simple_score_weight_pe)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["weight_pe"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（負值表示扣分）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        ttk.Label(scrollable_frame, text="═ 門檻過濾（低於門檻直接排除） ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(5, 5), sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="最低營收YoY (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_rev_yoy"] = tk.DoubleVar(value=self.cfg.simple_min_rev_yoy)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_rev_yoy"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最低EPSYoY (%)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_eps_yoy"] = tk.DoubleVar(value=self.cfg.simple_min_eps_yoy)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_eps_yoy"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最低EPS (元)：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["min_eps"] = tk.DoubleVar(value=self.cfg.simple_min_eps)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["min_eps"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（-999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Label(scrollable_frame, text="最高本益比：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["max_pe"] = tk.DoubleVar(value=self.cfg.simple_max_pe)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["max_pe"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（999 = 不限制）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        row += 1

        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        def set_defaults():
            self.simple_vars["weight_rev"].set(35)
            self.simple_vars["weight_eps"].set(35)
            self.simple_vars["weight_div"].set(20)
            self.simple_vars["weight_pe"].set(-5)
            self.simple_vars["min_rev_yoy"].set(-999)
            self.simple_vars["min_eps_yoy"].set(-999)
            self.simple_vars["min_eps"].set(-999)
            self.simple_vars["max_pe"].set(999)

        ttk.Button(scrollable_frame, text="恢復預設值", command=set_defaults).grid(row=row, column=0, columnspan=2, pady=5)
        row += 1

        def save_settings():
            self.cfg.simple_score_weight_rev = self.simple_vars["weight_rev"].get()
            self.cfg.simple_score_weight_eps = self.simple_vars["weight_eps"].get()
            self.cfg.simple_score_weight_div = self.simple_vars["weight_div"].get()
            self.cfg.simple_score_weight_pe = self.simple_vars["weight_pe"].get()
            self.cfg.simple_min_rev_yoy = self.simple_vars["min_rev_yoy"].get()
            self.cfg.simple_min_eps_yoy = self.simple_vars["min_eps_yoy"].get()
            self.cfg.simple_min_eps = self.simple_vars["min_eps"].get()
            self.cfg.simple_max_pe = self.simple_vars["max_pe"].get()
            win.destroy()
            self.logger.log("✅ 簡易評分參數已更新")
            save_config(self.cfg.to_dict())

        ttk.Button(scrollable_frame, text="儲存設定", command=save_settings).grid(row=row, column=0, columnspan=2, pady=10)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.console.insert("end", msg + "\n")
                self.console.see("end")
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    def _on_clear_console(self):
        self.console.delete("1.0", "end")

    # ==========================================================
    # V0.9.4 買賣記錄 Tab（不動 V0.9.3 上面所有 method）
    # ==========================================================
    def _on_tab_changed(self, event):
        """Tab 切換時自動 refresh 買賣記錄"""
        try:
            current = self.notebook.index(self.notebook.select())
            if current == 1:  # Tab 2 = 買賣記錄
                self._refresh_portfolio_view()
        except Exception as e:
            self.logger.log(f"⚠️ Tab 切換 refresh 失敗：{e}")

    def _build_portfolio_tab(self, parent):
        """建立「買賣記錄」Tab 的 UI"""
        # 上方：5 個總覽 Label
        summary_frame = ttk.LabelFrame(parent, text="📊 持倉總覽", padding=8)
        summary_frame.pack(fill="x", padx=8, pady=(8, 4))
        self._summary_labels = {}
        for i, (key, label) in enumerate([
            ("total_cost", "總成本"),
            ("total_market_value", "總市值"),
            ("total_unrealized_pl", "未實現損益"),
            ("total_realized_pl", "已實現損益"),
            ("total_return_pct", "總報酬率 %"),
        ]):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=0, column=i, padx=10, pady=2, sticky="w")
            ttk.Label(cell, text=label, font=("Segoe UI", 9), foreground="#666").pack(anchor="w")
            val_lbl = ttk.Label(cell, text="—", font=("Segoe UI", 12, "bold"))
            val_lbl.pack(anchor="w")
            self._summary_labels[key] = val_lbl

        # 中間：持倉明細 Treeview
        pos_frame = ttk.LabelFrame(parent, text="🌳 持倉明細", padding=4)
        pos_frame.pack(fill="both", expand=True, padx=8, pady=4)
        pos_cols = ("代號", "名稱", "股數", "均價", "現價", "市值", "未實現損益", "報酬率%", "已實現損益")
        self._positions_tree = ttk.Treeview(pos_frame, columns=pos_cols, show="headings", height=8)
        for col, w in zip(pos_cols, [60, 80, 80, 70, 70, 90, 90, 70, 90]):
            self._positions_tree.heading(col, text=col)
            self._positions_tree.column(col, width=w, anchor="e" if col not in ("代號", "名稱") else "w")
        pos_scroll = ttk.Scrollbar(pos_frame, orient="vertical", command=self._positions_tree.yview)
        self._positions_tree.configure(yscrollcommand=pos_scroll.set)
        self._positions_tree.pack(side="left", fill="both", expand=True)
        pos_scroll.pack(side="right", fill="y")

        # 下方：交易明細 Treeview
        tx_frame = ttk.LabelFrame(parent, text="📋 交易明細", padding=4)
        tx_frame.pack(fill="both", expand=True, padx=8, pady=4)
        tx_cols = ("id", "日期", "代號", "名稱", "買/賣", "股數", "價格", "手續費", "備註")
        self._tx_tree = ttk.Treeview(tx_frame, columns=tx_cols, show="headings", height=8)
        for col, w in zip(tx_cols, [40, 80, 60, 80, 50, 70, 70, 60, 120]):
            self._tx_tree.heading(col, text=col)
            self._tx_tree.column(col, width=w, anchor="w" if col in ("代號", "名稱", "買/賣", "備註", "日期") else "e")
        tx_scroll = ttk.Scrollbar(tx_frame, orient="vertical", command=self._tx_tree.yview)
        self._tx_tree.configure(yscrollcommand=tx_scroll.set)
        self._tx_tree.pack(side="left", fill="both", expand=True)
        tx_scroll.pack(side="right", fill="y")

        # 最下：按鈕區
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(btn_frame, text="➕ 新增買入", command=self._open_buy_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="➖ 新增賣出", command=self._open_sell_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="💲 更新現價", command=self._update_prices_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 刪除選中", command=self._delete_selected_tx).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🔄 重新整理", command=self._refresh_portfolio_view).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="📤 匯出 Excel", command=self._export_portfolio_excel).pack(side="right", padx=2)

    def _refresh_portfolio_view(self):
        """重新查詢 DB，更新總覽 + 兩個 Treeview"""
        try:
            positions = self.portfolio.get_positions(self._current_prices)
            summary = self.portfolio.get_summary(self._current_prices)
            txs = self.portfolio.list_transactions()

            # 總覽
            self._summary_labels["total_cost"].config(text=f"{summary.total_cost:,.0f}")
            self._summary_labels["total_market_value"].config(text=f"{summary.total_market_value:,.0f}")
            pl_color = "#0a7d2c" if summary.total_unrealized_pl >= 0 else "#c00000"
            self._summary_labels["total_unrealized_pl"].config(text=f"{summary.total_unrealized_pl:+,.0f}", foreground=pl_color)
            real_color = "#0a7d2c" if summary.total_realized_pl >= 0 else "#c00000"
            self._summary_labels["total_realized_pl"].config(text=f"{summary.total_realized_pl:+,.0f}", foreground=real_color)
            ret_color = "#0a7d2c" if summary.total_return_pct >= 0 else "#c00000"
            self._summary_labels["total_return_pct"].config(text=f"{summary.total_return_pct:+.2f}%", foreground=ret_color)

            # 持倉明細
            for item in self._positions_tree.get_children():
                self._positions_tree.delete(item)
            for p in positions:
                self._positions_tree.insert("", "end", values=(
                    p.stock_id, p.stock_name,
                    f"{p.shares:,.0f}",
                    f"{p.avg_cost:,.2f}",
                    f"{p.current_price:,.2f}" if p.current_price > 0 else "—",
                    f"{p.market_value:,.0f}" if p.current_price > 0 else "—",
                    f"{p.unrealized_pl:+,.0f}" if p.current_price > 0 else "—",
                    f"{p.unrealized_pl_pct:+.2f}%" if p.current_price > 0 else "—",
                    f"{p.realized_pl:+,.0f}",
                ))

            # 交易明細
            for item in self._tx_tree.get_children():
                self._tx_tree.delete(item)
            for t in txs:
                self._tx_tree.insert("", "end", values=(
                    t.id, t.trade_date, t.stock_id, t.stock_name,
                    "買" if t.action == "BUY" else "賣",
                    f"{t.shares:,.0f}",
                    f"{t.price:,.2f}",
                    f"{t.fee:,.0f}",
                    t.note,
                ))

        except Exception as e:
            messagebox.showerror("Refresh 失敗", str(e))

    def _open_buy_dialog(self):
        """新增買入對話框"""
        win = tk.Toplevel(self)
        win.title("新增買入")
        win.geometry("360x320")
        win.transient(self)
        win.grab_set()

        # 欄位
        fields = {}
        rows = [
            ("stock_id",   "股票代號", ""),
            ("stock_name", "股票名稱", ""),
            ("trade_date", "買入日期", datetime.now().strftime("%Y-%m-%d")),
            ("shares",     "買入股數", "0"),
            ("price",      "買入價格", "0"),
            ("fee",        "手續費",   "0"),
            ("note",       "備註",     ""),
        ]
        for i, (key, label, default) in enumerate(rows):
            ttk.Label(win, text=label, width=10, anchor="e").grid(row=i, column=0, padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=default)
            ttk.Entry(win, textvariable=v, width=24).grid(row=i, column=1, padx=8, pady=4, sticky="w")
            fields[key] = v

        def on_submit():
            try:
                self.portfolio.add_buy(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    fee=float(fields["fee"].get() or 0),
                    stock_name=fields["stock_name"].get().strip(),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 買入新增成功：{fields['stock_id'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=len(rows), column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=len(rows), column=1, padx=8, pady=12, sticky="w")

    def _open_sell_dialog(self):
        """新增賣出對話框"""
        win = tk.Toplevel(self)
        win.title("新增賣出")
        win.geometry("360x300")
        win.transient(self)
        win.grab_set()

        fields = {}
        rows = [
            ("stock_id",   "股票代號", ""),
            ("trade_date", "賣出日期", datetime.now().strftime("%Y-%m-%d")),
            ("shares",     "賣出股數", "0"),
            ("price",      "賣出價格", "0"),
            ("fee",        "手續費",   "0"),
            ("note",       "備註",     ""),
        ]
        for i, (key, label, default) in enumerate(rows):
            ttk.Label(win, text=label, width=10, anchor="e").grid(row=i, column=0, padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=default)
            ttk.Entry(win, textvariable=v, width=24).grid(row=i, column=1, padx=8, pady=4, sticky="w")
            fields[key] = v

        def on_submit():
            try:
                self.portfolio.add_sell(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    fee=float(fields["fee"].get() or 0),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 賣出新增成功：{fields['stock_id'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=len(rows), column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=len(rows), column=1, padx=8, pady=12, sticky="w")

    def _update_prices_dialog(self):
        """批次更新現價（所有持倉列出來，預填上次輸入）"""
        positions = self.portfolio.get_positions()
        if not positions:
            messagebox.showinfo("無持倉", "目前沒有持倉股票可更新現價")
            return

        win = tk.Toplevel(self)
        win.title("更新現價")
        win.geometry("380x420")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="請輸入每檔股票的目前市價：", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

        price_vars = {}
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=4)
        for i, p in enumerate(positions):
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{p.stock_id} {p.stock_name}", width=20, anchor="w").pack(side="left")
            cur = self._current_prices.get(p.stock_id, 0.0)
            v = tk.StringVar(value=f"{cur:.2f}" if cur > 0 else "")
            ttk.Entry(row, textvariable=v, width=14).pack(side="right")
            price_vars[p.stock_id] = v

        def on_submit():
            for sid, var in price_vars.items():
                txt = var.get().strip()
                if txt:
                    try:
                        self._current_prices[sid] = float(txt)
                    except ValueError:
                        messagebox.showerror("格式錯誤", f"{sid} 現價格式錯誤：{txt!r}", parent=win)
                        return
            self.logger.log(f"✅ 已更新 {len(price_vars)} 檔現價")
            win.destroy()
            self._refresh_portfolio_view()

        ttk.Button(win, text="確定", command=on_submit).pack(side="right", padx=10, pady=10)
        ttk.Button(win, text="取消", command=win.destroy).pack(side="right", padx=4, pady=10)

    def _delete_selected_tx(self):
        """刪除選中的交易（從交易明細 Treeview）"""
        sel = self._tx_tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在「交易明細」表格中選取要刪除的紀錄")
            return
        if not messagebox.askyesno("確認刪除", f"確定要刪除 {len(sel)} 筆交易紀錄？此操作無法復原。"):
            return
        try:
            for item in sel:
                vals = self._tx_tree.item(item, "values")
                tx_id = int(vals[0])
                self.portfolio.delete_transaction(tx_id)
            self.logger.log(f"🗑 已刪除 {len(sel)} 筆交易")
            self._refresh_portfolio_view()
        except Exception as e:
            messagebox.showerror("刪除失敗", str(e))

    def _export_portfolio_excel(self):
        """匯出 4 sheet Excel（讓使用者選存檔位置）"""
        default_name = f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        out = filedialog.asksaveasfilename(
            title="匯出買賣記錄",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel 檔案", "*.xlsx"), ("所有檔案", "*.*")],
        )
        if not out:
            return
        try:
            self.portfolio.export_excel(out, current_prices=self._current_prices)
            self.logger.log(f"📤 已匯出：{out}")
            messagebox.showinfo("匯出成功", f"已寫入：\n{out}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    def _on_run(self):
        self.run_btn.config(state="disabled")
        self.console.insert("end", "=" * 60 + "\n")
        self.console.insert("end", "🚀 StockTool v0.9.3 開始執行\n")
        self.console.insert("end", "=" * 60 + "\n")
        self.console.see("end")

        self._save_ui_to_config()
        cfg = self.cfg
        save_config(cfg.to_dict())

        def worker():
            try:
                run_pipeline(cfg, self.logger)
            except Exception as e:
                self.logger.log(f"❌ 執行失敗：{e}")
                import traceback
                self.logger.log(traceback.format_exc())
            finally:
                self.run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = StrategyGUI()
    app.mainloop()
