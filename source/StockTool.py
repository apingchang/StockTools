"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                               StockTool.py                                   ║
║                          台灣股市量化選股系統 v0.9.5-alpha                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
V0.9.5-alpha
【版本資訊】
Version: v0.9.5-alpha
最後更新: 2026-06-14 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: tkinter, pandas, requests, openpyxl, numpy, itertools

════════════════════════════════════════════════════════════════════════════════
【v0.9.5-alpha 更新內容】2026-06-14
════════════════════════════════════════════════════════════════════════════════
【手動選股 Tab 升級】（Phase 1：背景重抓股價 + PE 過濾）
- App 啟動時背景重抓股價（跳過今天已抓的 cache）
- 手動選股 Tab「🔄 重新抓股價」按鈕
- Race condition 防呆（_bg_price_fetching flag）
- PE 接近 0 過濾（EPS < 0.05 → PE = None，解決大城地產 PE=300 爆炸值）

【手動選股 Tab 升級】（Phase 2：股利DB + 修殖利率年份對應 bug）
- 股利歷史庫 dividend_history.db（同 eps_history 風格）
- 修 Bug：殖利率年份對應錯誤（cy-1=今年、cy-2=去年、cy-3=前年）

【手動選股 Tab 升級】（Phase 3：補抓股利 + 100檔/次分批）
- 「💰 補抓全部股利 (一次性)」→「💰 掃描全部股票 (100檔/次)」
- 新增「🎯 指定股補抓 (推薦 Free tier)」按鈕
- 每次只抓 100 檔、可分散跑（Free tier 300-1000 筆/月額度友善）
- 新增 scripts/fetch_dividend.py（CLI 補抓介面、對話中也能跑）

【手動選股 Tab 升級】（Phase 4：B 邏輯篩選 + DB cache 過期）
- 改用 pass_score (達標) + data_score (有資料) 雙計分
- 殖利率 None 不再被視為達標、None 排到結果後面
- 至少要有一個條件有資料才納入結果
- 沒結果 → 「❌ 這次篩選沒有合格股票」+ 可能原因提示
- DB cache 過期（> 30 天）→ 自動重抓 FinMind
- 新加 _query_div_history_with_fetched 函數（用 fetched_at 判斷過期）
- 強化 402 額度訊息（已完成 X/Y 檔｜請下月重置或升級 plan）

【pytest】59 個 test 全部通過 ✅
- test_dividend_year_mapping.py（5 個）
- test_pe_filter.py（5 個）
- test_dividend_specific.py（10 個）
- test_dividend_fetch_all.py（6 個）
- test_dividend_scan_batch.py（8 個）
- test_fetch_dividend_cli.py（10 個）
- test_filter_b_logic.py（7 個）
- test_div_cache_expiry.py（8 個）

════════════════════════════════════════════════════════════════════════════════
【v0.9.4 更新內容】2026-06-11
════════════════════════════════════════════════════════════════════════════════
Phase 2.3 — 買賣記錄 5 項更新：
1. 股票股利配發（price=0）支援
2. 萬年曆日期挑選（_CalendarDialog，純 Tkinter 原生）
3. 成本加計手續費 + 證交稅（Treeview 新增「證交稅」欄）
4. 策略參數設定支援券商折扣（broker_discount，預設 1.0）
5. 交易明細可編輯（✏️編輯，action/shares/price/date 皆可改）

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
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
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
    "eps_history_db": "eps_history.db",
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
    "out_file_prefix": "選股報表",
    # V0.9.4 phase2.3: 交易成本設定（台股預設值）
    "broker_discount": 1.0,          # 券商折扣（1.0 = 無折扣，0.6 = 6折）
    # V0.9.5: 手動選股 Preset
    "manual_select_presets": {},
    "manual_select_last_preset": None,
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
    eps_history_db: str = "eps_history.db"
    # V0.9.4 phase2.3: 券商折扣（1.0 = 無折扣，0.6 = 6折）
    broker_discount: float = 1.0
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
    # V0.9.5: 手動選股 Preset
    manual_select_presets: dict = field(default_factory=dict)
    manual_select_last_preset: str = None

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.9.5-alpha",
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


# ==========================================================


# 股利歷史庫（跟 eps_history 同一風格）
DIV_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dividend_history (
    stock_id    TEXT    NOT NULL,
    year        INTEGER NOT NULL,
    cash        REAL,
    stock       REAL,
    source      TEXT,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (stock_id, year)
);
CREATE INDEX IF NOT EXISTS idx_div_period ON dividend_history(year);
"""

def _init_div_history_db(db_path: str):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DIV_HISTORY_SCHEMA)
        conn.commit()

def _upsert_div_history(db_path: str, rows: list):
    """rows: [(stock_id, year, cash, stock, source), ...]"""
    import sqlite3
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO dividend_history
               (stock_id, year, cash, stock, source)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(rows)

def _query_div_history(db_path: str, codes: list) -> dict:
    """查詢多檔股票的所有年度股利 → {code: {year: {cash, stock}}}"""
    import sqlite3
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"SELECT stock_id, year, cash, stock FROM dividend_history WHERE stock_id IN ({placeholders})",
            codes,
        ).fetchall()
    result: Dict[str, Dict[int, Dict[str, float]]] = {}
    for code, year, cash, stock in rows:
        result.setdefault(str(code).strip(), {})
        result[str(code).strip()][year] = {"cash": cash or 0.0, "stock": stock or 0.0}
    return result


def _query_div_history_with_fetched(db_path: str, codes: list) -> dict:
    """查詢多檔股票的股利 + fetched_at → {code: {"_fetched_at": iso_str, "years": {year: {cash, stock}}}}

    V0.9.5+ 用來判斷 DB 資料是否過期（> cache_max_age_days 天）
    """
    import sqlite3
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"SELECT stock_id, year, cash, stock, fetched_at FROM dividend_history WHERE stock_id IN ({placeholders})",
            codes,
        ).fetchall()
    result: Dict[str, Dict] = {}
    for code, year, cash, stock, fetched_at in rows:
        code = str(code).strip()
        if code not in result:
            result[code] = {"_fetched_at": fetched_at, "years": {}}
        result[code]["years"][year] = {"cash": cash or 0.0, "stock": stock or 0.0}
    return result

def _div_history_stats(db_path: str) -> dict:
    import sqlite3
    if not os.path.exists(db_path):
        return {"total": 0, "stocks": 0, "years": 0}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM dividend_history").fetchone()[0]
        stocks = conn.execute("SELECT COUNT(DISTINCT stock_id) FROM dividend_history").fetchone()[0]
        years = conn.execute("SELECT COUNT(DISTINCT year) FROM dividend_history").fetchone()[0]
    return {"total": total, "stocks": stocks, "years": years}


# V0.9.4 phase4: EPS 歷史庫（補抓不到去年同期的解法）
# 每日把最新一季 EPS 存進 SQLite，累積一年後 fetch_eps_latest 就能算 YoY
# ==========================================================
EPS_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS eps_history (
    stock_id    TEXT    NOT NULL,
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    eps         REAL,
    source      TEXT,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (stock_id, year, quarter)
);
CREATE INDEX IF NOT EXISTS idx_eps_period ON eps_history(year, quarter);
"""


def _init_eps_history_db(db_path: str):
    """初始化/建立 EPS 歷史庫（不重複執行也不會壞）"""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript(EPS_HISTORY_SCHEMA)
        conn.commit()


def _upsert_eps_history(db_path: str, rows: list):
    """
    rows: [(stock_id, year, quarter, eps, source), ...]
    用 REPLACE 策略：新資料覆蓋舊的（讓 CSV 更新時自動修正）
    """
    import sqlite3
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO eps_history
               (stock_id, year, quarter, eps, source)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(rows)


def _query_eps_history(db_path: str, year: int, quarter: int) -> pd.DataFrame:
    """查詢指定 (year, quarter) 的歷史 EPS"""
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT stock_id, year, quarter, eps FROM eps_history WHERE year = ? AND quarter = ?",
            conn, params=(year, quarter),
        )
    if not df.empty:
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
    return df


def _eps_history_stats(db_path: str) -> dict:
    """回傳歷史庫摘要（給 GUI 狀態列用）"""
    import sqlite3
    if not os.path.exists(db_path):
        return {"total": 0, "periods": 0, "latest": None}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM eps_history").fetchone()[0]
        periods = conn.execute("SELECT COUNT(DISTINCT year*10+quarter) FROM eps_history").fetchone()[0]
        latest = conn.execute(
            "SELECT year, quarter, COUNT(*) FROM eps_history "
            "ORDER BY year DESC, quarter DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "periods": periods,
        "latest": f"{latest[0]}Q{latest[1]} ({latest[2]}筆)" if latest else None,
    }


# ==========================================================
# V0.9.5: 手動選股功能 - FinMind 資料拉取輔助
# ==========================================================

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# 手動選股進度（背景 thread 寫、UI thread 讀）
_MS_PROGRESS = {"stage": "", "done": 0, "total": 0, "msg": "", "error": ""}


def _fetch_market_stock_list() -> pd.DataFrame:
    """
    從 TWSE / TPEx 抓全市場股票代號與名稱（當 pipeline 未執行時的 fallback）。
    回傳 DataFrame：[股票代號, 股票名稱]
    """
    import sqlite3
    # 優先用 eps_history.db 湊出名單（已有股票代號，快速）
    db_path = "eps_history.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            codes = pd.read_sql_query(
                "SELECT DISTINCT stock_id FROM eps_history ORDER BY stock_id", conn)
            conn.close()
            if not codes.empty:
                df = codes.copy()
                df["股票名稱"] = ""
                return df.rename(columns={"stock_id": "股票代號"})
        except Exception:
            pass

    # TWSE / TPEx 上市股票清單（從 ISIN 頁面）
    rows = []
    for url in ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
                 "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]:
        try:
            r = requests.get(url, timeout=20, verify=False)
            from io import StringIO
            tables = pd.read_html(StringIO(r.text), header=0)
            for t in tables:
                if "有價證券代號及名稱" in t.columns:
                    # 第一欄是「代號　名稱」混合，需用空白拆開
                    combined = t["有價證券代號及名稱"].dropna().tolist()
                    for item in combined:
                        s = str(item).strip()
                        # 格式：「1101　台泥」或「1101 台泥」
                        parts = s.split(maxsplit=1)
                        if len(parts) == 2 and parts[0].strip().isdigit() and len(parts[0].strip()) == 4:
                            rows.append({"股票代號": parts[0].strip(), "股票名稱": parts[1].strip()})
                    break  # 只處理第一張表
        except Exception:
            continue

    if rows:
        result = pd.DataFrame(rows).drop_duplicates("股票代號")
        result["股票代號"] = result["股票代號"].astype(str).str.strip()
        return result
    return pd.DataFrame(columns=["股票代號", "股票名稱"])

_FINMIND_PRICE_CACHE = {}   # {stock_id: {date: row}}
_FINMIND_DIVIDEND_CACHE = {}  # {stock_id: {year: {cash, stock}}}


def _finmind_get(dataset: str, stock_id: str, start: str, end: str, retry: int = 2) -> list:
    """統一的 FinMind API 呼叫（含 429 回退、402 額度檢查）。

    重要：402 Payment Required 表示 FinMind plan 額度用完
          此時應規舉到上层、不要 silently 回傳空 list
    （空 list 會讓 caller 誤以為「該股沒股利」而不是「API 額度不夠」）
    """
    for attempt in range(retry + 1):
        try:
            r = requests.get(FINMIND_BASE, params={
                "dataset": dataset,
                "data_id": stock_id,
                "start_date": start,
                "end_date": end,
            }, timeout=20)
            if r.status_code == 429:
                time.sleep(61)
                continue
            if r.status_code == 402:
                # FinMind plan 額度用完 → 拋例外（不再 silently 回傳空）
                raise RuntimeError(
                    "FinMind 額度已用完（status 402）｜請升級 plan 或等下月重置"
                    f"｜URL: {r.url}"
                )
            r.raise_for_status()
            d = r.json()
            return d.get("data", []) or []
        except RuntimeError:
            # 402 額度錯誤直接往上拋
            raise
        except Exception:
            if attempt < retry:
                time.sleep(2)
            return []
    return []


def _parse_roc_year(year_str: str) -> int:
    """把 "113年第3季" → 2024（西元年）。民國年 = 西元年 - 1911。"""
    import re
    m = re.match(r"(\d+)年", str(year_str))
    if m:
        return int(m.group(1)) + 1911  # 錯誤：-1911；修正：+1911
    return 0


def _fetch_finmind_prices_batch(stock_ids: List[str],
                                progress_callback=None) -> pd.DataFrame:
    """
    批次抓取股票現價（FinMind TaiwanStockPrice，支援 rate limit 回退）。
    每批 10 個，間隔 0.35s，超過 300/h 會被擋 → 等 61s 再試。
    progress_callback(n_done, n_total) 可傳進來做 UI 更新。
    """
    rows = []
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    total = len(stock_ids)
    _MS_PROGRESS["stage"] = "股價"
    _MS_PROGRESS["total"] = total

    for i, code in enumerate(stock_ids):
        code = str(code).strip()
        if code in _FINMIND_PRICE_CACHE:
            cached = _FINMIND_PRICE_CACHE[code]
            if cached:
                rows.append({"股票代號": code,
                            "現價": cached.get("close"),
                            "成交量_張": (cached.get("Trading_Volume", 0) or 0) / 1000})
        else:
            data = _finmind_get("TaiwanStockPrice", code, start_date, end_date)
            if data:
                latest = data[-1]
                _FINMIND_PRICE_CACHE[code] = latest
                rows.append({"股票代號": code,
                            "現價": latest.get("close"),
                            "成交量_張": (latest.get("Trading_Volume", 0) or 0) / 1000})
            else:
                _FINMIND_PRICE_CACHE[code] = None

            # Rate limit：每小時最多 300 次 → 每次間隔 12s
            # 實測 0.35s 可用（用 threading 並行），但避免一次打太多
            _MS_PROGRESS["done"] = i + 1
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, total)
            time.sleep(0.35)

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", "現價", "成交量_張"])


def _fetch_finmind_dividend(stock_ids: List[str],
                             db_path: str = "dividend_history.db",
                             progress_callback=None,
                             skip_remote: bool = False,
                             cache_max_age_days: int = 30) -> pd.DataFrame:
    """
    取得近 3 年股利（先查 DB，沒有的、或過期的才即時抓 FinMind 並寫回 DB）。
    - skip_remote=True: DB 沒有的回 None，不抓 FinMind（避免 rate limit）
    - cache_max_age_days：DB 資料超過 N 天視為過期（預設 30 天）→ 重抓 FinMind
      （避免 DB 過期→使用者誤以為沒額度問題是 DB 缺漏）
    - 第一次跑：會 FinMind 抓一批 + 寫 DB
    - 之後跑：只查 DB，不打網路
    """
    rows = []
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"

    # 1. 先查 DB（含 fetched_at 用來判斷過期）
    _init_div_history_db(db_path)
    cached_with_fetched = _query_div_history_with_fetched(
        db_path, [str(c).strip() for c in stock_ids]
    )
    cached = _query_div_history(db_path, [str(c).strip() for c in stock_ids])

    # 2. 區分「DB 有的」跟「要即時抓的」
    #    - DB 沒有的 → 抓
    #    - DB 有但過期的（> cache_max_age_days）→ 抓
    #    - DB 有且新鮮的 → 跳過
    #    - cache_max_age_days < 0 視為「永不過期」→ 保持原本行為（向後相容）
    from datetime import datetime as _dt, timedelta as _td
    if cache_max_age_days < 0:
        threshold_iso = None  # 永不過期
    else:
        threshold_iso = (_dt.now() - _td(days=cache_max_age_days)).isoformat()
    to_fetch = []
    for c in [str(c).strip() for c in stock_ids]:
        if c not in cached_with_fetched:
            to_fetch.append(c)
        elif threshold_iso is not None:
            fetched_at = cached_with_fetched[c].get("_fetched_at", "")
            if fetched_at and fetched_at < threshold_iso:
                to_fetch.append(c)  # 過期
    if skip_remote:
        # 跳過 FinMind 抓取：DB 沒有的回 None（避免 rate limit）
        to_fetch = []
    fetch_rows: list = []
    _MS_PROGRESS["stage"] = "股利"
    _MS_PROGRESS["total"] = len(to_fetch)
    _MS_PROGRESS["error"] = ""  # 重設錯誤狀態
    import re as _re_div
    try:
        for i, code in enumerate(to_fetch):
            _MS_PROGRESS["done"] = i
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
            by_year: Dict[int, Dict[str, float]] = {}
            for rec in data:
                year_str = rec.get("year", "")
                cash_raw = float(rec.get("CashEarningsDistribution") or 0)
                stock_raw = float(rec.get("StockEarningsDistribution") or 0)
                m_q = _re_div.match(r"(\d+)年第(\d+)季", year_str)
                m_h1 = _re_div.match(r"(\d+)年前半年度", year_str)
                m_h2 = _re_div.match(r"(\d+)年後半年度", year_str)
                m_y = _re_div.match(r"^(\d+)年$", year_str)  # 純年（無季/半年度）
                if m_q:
                    yr = int(m_q.group(1)) + 1911
                    by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0})
                    by_year[yr]["cash"] = max(by_year[yr]["cash"], cash_raw)
                    by_year[yr]["stock"] = max(by_year[yr]["stock"], stock_raw)
                elif m_h1:
                    yr = int(m_h1.group(1)) + 1911
                    by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0})
                    by_year[yr]["cash"] += cash_raw
                    by_year[yr]["stock"] += stock_raw
                elif m_h2:
                    yr = int(m_h2.group(1)) + 1911
                    by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0})
                    by_year[yr]["cash"] += cash_raw
                    by_year[yr]["stock"] += stock_raw
                elif m_y:
                    yr = int(m_y.group(1)) + 1911
                    by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0})
                    by_year[yr]["cash"] = max(by_year[yr]["cash"], cash_raw)
                    by_year[yr]["stock"] = max(by_year[yr]["stock"], stock_raw)
                else:
                    continue
            # 寫入 DB
            for yr, d in by_year.items():
                fetch_rows.append((code, yr, d["cash"], d["stock"], "finmind"))
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, len(to_fetch))
            time.sleep(0.35)
    except RuntimeError as e:
        # FinMind 402 額度已用完 → 記下錯誤、跳出 loop
        # 保留已抓到的 fetch_rows（不丢）
        _MS_PROGRESS["error"] = str(e)
        print(f"❌ FinMind 額度錯誤：{e}（已抓 {len(fetch_rows)} 筆、部分寫入 DB）")
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
        # 重新讀一次 DB 拿新資料
        cached = _query_div_history(db_path, [str(c).strip() for c in stock_ids])

    # 3. 組裝結果
    for code in [str(c).strip() for c in stock_ids]:
        by_year = cached.get(code, {})
        this_yr = by_year.get(current_year, {})
        last_yr = by_year.get(current_year - 1, {})
        prev_yr = by_year.get(current_year - 2, {})
        rows.append({
            "股票代號": code,
            f"{current_year}現金股利": this_yr.get("cash", 0.0),
            f"{current_year}股票股利": this_yr.get("stock", 0.0),
            f"{current_year - 1}現金股利": last_yr.get("cash", 0.0),
            f"{current_year - 1}股票股利": last_yr.get("stock", 0.0),
            f"{current_year - 2}現金股利": prev_yr.get("cash", 0.0),
            f"{current_year - 2}股票股利": prev_yr.get("stock", 0.0),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", f"{current_year}現金股利", f"{current_year}股票股利",
                 f"{current_year - 1}現金股利", f"{current_year - 1}股票股利",
                 f"{current_year - 2}現金股利", f"{current_year - 2}股票股利"])

def _background_fetch_all_dividend(stock_ids: List[str], db_path: str = "dividend_history.db",
                                  progress_callback=None, batch_size: Optional[int] = None) -> int:
    """
    背景抓取全市場股利寫入 DB（手動啟動用）。

    Parameters
    ----------
    stock_ids : List[str]
        股票代號清單
    db_path : str
        DB 路徑
    progress_callback : callable
        進度回呼 (done, total)
    batch_size : int | None
        - None = 一次抓全部缺漏（舊行為）
        - 100  = 只抓缺漏中的前 N 檔（V0.9.5+ 推薦用，Free tier 額度友善）

    Returns
    -------
    int
        這次實際抓的股數（原本沒資料的）
        -1 = FinMind 402 額度錯誤
         0 = 沒缺漏、沒抓
    """
    _init_div_history_db(db_path)
    cached = _query_div_history(db_path, [str(c).strip() for c in stock_ids])
    to_fetch = [c for c in stock_ids if str(c).strip() not in cached]
    if not to_fetch:
        return 0
    # V0.9.5+: 批次切片（Free tier 額度友善、可分散跑）
    if batch_size is not None and batch_size > 0 and len(to_fetch) > batch_size:
        to_fetch = to_fetch[:batch_size]
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"
    fetch_rows: list = []
    total = len(to_fetch)
    quota_exceeded = False
    for i, code in enumerate(to_fetch):
        try:
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
        except RuntimeError as e:
            # FinMind 402 額度用完 → 停止 loop、保留已抓的
            print(f"❌ {e}")
            quota_exceeded = True
            break
        for rec in data:
            yr = _parse_roc_year(rec.get("year", ""))
            if yr == 0:
                continue
            cash_raw = float(rec.get("CashEarningsDistribution") or 0)
            stock_raw = float(rec.get("StockEarningsDistribution") or 0)
            fetch_rows.append((code, yr, cash_raw, stock_raw, "finmind"))
        time.sleep(0.35)
        if progress_callback:
            try:
                progress_callback(i + 1, total)
            except Exception:
                pass
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
    # 用「負值」表示 FinMind 額度錯誤（讓 caller 知道不是完成）
    if quota_exceeded:
        return -1
    return len(to_fetch)



def _run_manual_selection(
    price_df: pd.DataFrame,      # 來自 pipeline 的股價資料 [股票代號, 股價, ...]
    revenue_df: pd.DataFrame,     # 來自 pipeline 的營收資料 [股票代號, 累計營收YoY(%), ...]
    eps_df: pd.DataFrame,         # 來自 pipeline 的 EPS 資料 [股票代號, EPS本期, ...]
    filters: dict,
    top_n: int = 500,
) -> pd.DataFrame:
    """
    根據 filters 條件，從已知的市場股票中篩選並回傳結果。

    filters 格式：
        {
            "min_rev_yoy": 10.0,          # 累計營收 YoY >= 此值（None = skip）
            "min_pe": None,                # PE <= 此值（None = skip）
            "min_price": None,             # 現價 >= 此值（None = skip）
            "min_volume": None,            # 成交量(張) >= 此值（None = skip）
            "min_bvps": None,             # 淨值 >= 此值（None = skip，暫不支援）
            "min_cash_div": None,          # 今年現金股利 >= 此值（None = skip）
            "min_stock_div": None,         # 今年股票股利 >= 此值（None = skip）
            "min_last_cash_div": None,     # 去年現金股利 >= 此值（None = skip）
            "min_last_stock_div": None,    # 去年股票股利 >= 此值（None = skip）
            "sort_by": ["rev_yoy", "stock_div", "cash_div", "pe"],
        }
    """
    # 1. 取得全市場股票代號與名稱
    # 優先用 pipeline 的 price_df；若為空才 fallback 抓全市場名單
    price_df = price_df.copy() if price_df is not None else pd.DataFrame()
    if price_df.empty:
        base = _fetch_market_stock_list()
    else:
        if "公司名稱_來源" in price_df.columns:
            name_col = "公司名稱_來源"
        else:
            name_col = [c for c in price_df.columns if "名稱" in c or "name" in c.lower()]
            name_col = name_col[0] if name_col else None

        price_cols = ["股票代號"]
        if name_col:
            price_cols.append(name_col)
        # 如果 cache 也有「股價」或「現價」也一起拉進來
        for cc in ["股價", "現價", "成交量", "成交量_張", "漲跌"]:
            if cc in price_df.columns and cc not in price_cols:
                price_cols.append(cc)
        base = price_df[price_cols].drop_duplicates("股票代號").copy()
        base["股票代號"] = base["股票代號"].astype(str).str.strip()
        if name_col:
            base = base.rename(columns={name_col: "股票名稱"})
        else:
            base["股票名稱"] = ""
        # 統一欄位名：「股價」→「現價」、「成交量_張」不變
        if "股價" in base.columns and "現價" not in base.columns:
            base = base.rename(columns={"股價": "現價"})

    # 2. 取得現價：若 base 已有「現價」就用 cache，不抓 FinMind
    if "現價" in base.columns:
        # 已有現價（來自 cache），不重抓 FinMind
        # cache 不一定有成交量，若沒有則先移除「成交量」條件
        if "成交量_張" not in base.columns:
            base["成交量_張"] = None  # None 表示 cache 沒資料
        # 「漲跌」欄位只在 cache 才有，移到後面
    else:
        all_codes = base["股票代號"].tolist()
        price_finmind = _fetch_finmind_prices_batch(all_codes)
        if not price_finmind.empty:
            base = base.merge(price_finmind, on="股票代號", how="left")
        else:
            base["現價"] = None
            base["成交量_張"] = 0

    # 3. 合併營收 YoY（容錯：空 df 跳過）
    if not revenue_df.empty and "股票代號" in revenue_df.columns:
        revenue_df = revenue_df.copy()
        revenue_df["股票代號"] = revenue_df["股票代號"].astype(str).str.strip()
        rev_cols = ["股票代號", "營收YoY(%)"]
        rev_cols = [c for c in rev_cols if c in revenue_df.columns]
        if len(rev_cols) == 2:
            base = base.merge(revenue_df[rev_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "營收YoY(%)" not in base.columns:
        base["營收YoY(%)"] = None

    # 4. 合併 EPS（容錯：空 df 跳過）
    if not eps_df.empty and "股票代號" in eps_df.columns:
        eps_df = eps_df.copy()
        eps_df["股票代號"] = eps_df["股票代號"].astype(str).str.strip()
        eps_cols = ["股票代號", "EPS本期"]
        eps_cols = [c for c in eps_cols if c in eps_df.columns]
        if len(eps_cols) == 2:
            base = base.merge(eps_df[eps_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "EPS本期" not in base.columns:
        base["EPS本期"] = None

    # 5. 計算 PE
    # 注：EPS 接近 0 會讓 PE 爆炸（ex: EPS=0.01、股價=24 → PE=2400）
    #     設 PE = None 讓使用者看到 --，比看到「3000 倍 PE」合理
    # 門檻：EPS >= 0.05 元視為有意義的獲利能力（低於 0.05 視為雞蛋水餃股）
    PE_MIN_EPS = 0.05
    base["PE"] = None
    pe_mask = (
        (base["現價"].notna()) & (base["現價"] > 0)
        & (base["EPS本期"].notna()) & (base["EPS本期"] >= PE_MIN_EPS)
    )
    base.loc[pe_mask, "PE"] = (base.loc[pe_mask, "現價"] / base.loc[pe_mask, "EPS本期"]).round(2)

    # 6. 抓 FinMind 股利（會用 DB 快取，只在 DB 沒有的才抓 FinMind）
    all_codes = base["股票代號"].tolist()
    div_df = _fetch_finmind_dividend(all_codes)
    if not div_df.empty:
        base = base.merge(div_df, on="股票代號", how="left")
    else:
        cy = datetime.now().year
        for suf in [f"{cy}現金股利", f"{cy}股票股利",
                    f"{cy - 1}現金股利", f"{cy - 1}股票股利",
                    f"{cy - 2}現金股利", f"{cy - 2}股票股利"]:
            if suf not in base.columns:
                base[suf] = None

    # 7. 今年/去年現金股利欄位（干擾名稱，用固定名）
    # 重要：FinMind `TaiwanStockDividend` 的 year 欄位是「會計年度」
    #       ex: year=2025 = 2025 年度盈餘的股利，在 2026 年除息發放
    #   台灣人說「今年現金股利」= 當年除息 = DB year=cy-1
    #   因此正確對應是 cy-1=今年、cy-2=去年、cy-3=前年
    #   （不要直接用 cy，因為 DB 通常還沒抓當年度的決公告資料）
    cy = datetime.now().year
    base["今年現金股利"] = base.get(f"{cy - 1}現金股利", None)
    base["今年股票股利"] = base.get(f"{cy - 1}股票股利", None)
    base["去年現金股利"] = base.get(f"{cy - 2}現金股利", None)
    base["去年股票股利"] = base.get(f"{cy - 2}股票股利", None)
    # 前年度（保留給 UI 顯示）
    base["前年現金股利"] = base.get(f"{cy - 3}現金股利", None)
    base["前年股票股利"] = base.get(f"{cy - 3}股票股利", None)

    # 8. 今年現金殖利率 = 今年現金股利 / 現價
    # 註：現金股利若為 0（該公司該年未配息），殖利率應為 None 而不是 0
    base["今年現金殖利率(%)"] = None
    yld_mask = (base["現價"].notna()) & (base["現價"] > 0) & (base["今年現金股利"].notna()) & (base["今年現金股利"] > 0)
    base.loc[yld_mask, "今年現金殖利率(%)"] = (
        base.loc[yld_mask, "今年現金股利"] / base.loc[yld_mask, "現價"] * 100
    ).round(2)

    # 9. 去年現金殖利率
    # 註：現金股利若為 0，殖利率應為 None
    base["去年現金殖利率(%)"] = None
    yld2_mask = (base["現價"].notna()) & (base["現價"] > 0) & (base["去年現金股利"].notna()) & (base["去年現金股利"] > 0)
    base.loc[yld2_mask, "去年現金殖利率(%)"] = (
        base.loc[yld2_mask, "去年現金股利"] / base.loc[yld2_mask, "現價"] * 100
    ).round(2)

    # 10. 應用篩選條件（V0.9.5+ B 邏輯）
    #     改動：原本是「AND mask」直接排除，這版改成「每檔股票計分」
    #     - pass_score：達標的條件數（有資料且值 >= 門檻）
    #     - data_score：有資料的條件數（有值，不管是否達標）
    #     - 至少要有一個被勾選的條件「有資料」才納入結果（_data_score > 0）
    #     - None 的股票不視為「達標」、排到結果後面（但仍可見在 top_n 後段）
    #     - 沒結果會在 caller 判斷並提示「這次篩選沒有合格股票」
    pass_score = pd.Series([0] * len(base), index=base.index)
    data_score = pd.Series([0] * len(base), index=base.index)

    # 累計營收 YoY ≥ X
    if filters.get("min_rev_yoy") is not None:
        rev = base["營收YoY(%)"]
        has_data = rev.notna()
        passes = has_data & (rev >= filters["min_rev_yoy"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # PE ≤ X（注意：filters key 是 min_pe 但語意是「PE 不超過」）
    if filters.get("min_pe") is not None:
        pe = base["PE"]
        has_data = pe.notna()
        passes = has_data & (pe <= filters["min_pe"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 現價 ≥ X
    if filters.get("min_price") is not None:
        price = base["現價"]
        has_data = price.notna() & (price > 0)
        passes = has_data & (price >= filters["min_price"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 月均成交量 ≥ X
    if filters.get("min_volume") is not None:
        vol = base["成交量_張"]
        has_data = vol.notna()
        passes = has_data & (vol >= filters["min_volume"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 今年現金股利 ≥ X（元）
    if filters.get("min_cash_div") is not None:
        cd = base["今年現金股利"]
        has_data = cd.notna()
        passes = has_data & (cd >= filters["min_cash_div"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 今年股票股利 ≥ X（元）
    if filters.get("min_stock_div") is not None:
        sd = base["今年股票股利"]
        has_data = sd.notna()
        passes = has_data & (sd >= filters["min_stock_div"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 去年現金股利 ≥ X（元）
    if filters.get("min_last_cash_div") is not None:
        cd = base["去年現金股利"]
        has_data = cd.notna()
        passes = has_data & (cd >= filters["min_last_cash_div"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 去年股票股利 ≥ X（元）
    if filters.get("min_last_stock_div") is not None:
        sd = base["去年股票股利"]
        has_data = sd.notna()
        passes = has_data & (sd >= filters["min_last_stock_div"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 今年現金殖利率 ≥ X%
    # V0.9.5+ B 邏輯重點：殖利率 None 不視為「達標」、要當「未達標」記錄
    if filters.get("min_cash_div_yld") is not None:
        yld = base["今年現金殖利率(%)"]
        has_data = yld.notna()
        passes = has_data & (yld >= filters["min_cash_div_yld"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 去年現金殖利率 ≥ X%
    if filters.get("min_last_cash_yld") is not None:
        yld = base["去年現金殖利率(%)"]
        has_data = yld.notna()
        passes = has_data & (yld >= filters["min_last_cash_yld"])
        data_score = data_score + has_data.astype(int)
        pass_score = pass_score + passes.astype(int)

    # 過濾：至少要有一個被勾選的條件「有資料」（_data_score > 0）
    # 注：如果是「什麼都沒勾」的情況、_data_score 全 0、則不過濾（保留全部）
    if (data_score > 0).any():
        result = base[data_score > 0].copy()
        result["_pass_score"] = pass_score[data_score > 0]
        result["_data_score"] = data_score[data_score > 0]
    else:
        result = base.copy()
        result["_pass_score"] = pass_score
        result["_data_score"] = data_score

    # 11. 排序：通過分數多 > 資料分數多 > 殖利率有值 > 殖利率高 > 股票股利高 > 營收 YoY 高 > PE 低
    # 這樣可以達到「B 邏輯：None 排後面、至少一項過、達標多的排前面」
    result["_yld_has_data"] = result["今年現金殖利率(%)"].notna().astype(int)
    result["_sort_yld"] = -result["今年現金殖利率(%)"].fillna(-9999)  # 殖利率高在前（None 排最後）
    result["_sort_rev"] = result["營收YoY(%)"].fillna(-9999)
    result["_sort_stock"] = result["今年股票股利"].fillna(0)
    result["_sort_pe"] = result["PE"].fillna(9999)

    result = result.sort_values(
        ["_pass_score", "_data_score", "_yld_has_data", "_sort_yld", "_sort_stock", "_sort_rev", "_sort_pe"],
        ascending=[False, False, False, False, False, False, True]
    ).reset_index(drop=True)

    result = result.head(top_n).reset_index(drop=True)

    # 12. 整理輸出欄位
    out_cols = ["股票代號", "股票名稱", "現價", "營收YoY(%)",
                "今年股票股利", "今年現金殖利率(%)", "PE",
                "成交量_張", "今年現金股利",
                "去年現金股利", "去年股票股利", "去年現金殖利率(%)", "EPS本期",
                f"{cy}現金股利", f"{cy - 1}現金股利", f"{cy - 2}現金股利"]
    out_cols = [c for c in out_cols if c in result.columns]
    # 整理重複的現金股利（保留乾淨的今年/去年/前年）
    result = result[out_cols].rename(columns={
        "成交量_張": "成交量(張)",
        f"{cy}現金股利": "今年現金股利_原始",
        f"{cy - 1}現金股利": "去年現金股利_原始",
        f"{cy - 2}現金股利": "前年現金股利_原始",
    })
    # 還原乾淨名稱
    result = result.rename(columns={
        "今年現金股利_原始": "今年現金股利_原始",
    })
    # 重新整理輸出（最終顯示欄位）
    # 先把「營收YoY(%)」改名為「累計營收YoY(%)」供 Treeview 顯示
    result = result.rename(columns={"營收YoY(%)": "累計營收YoY(%)"})
    final_cols = ["股票代號", "股票名稱", "現價", "累計營收YoY(%)",
                  "今年股票股利", "今年現金股利", "今年現金殖利率(%)",
                  "去年股票股利", "去年現金股利", "去年現金殖利率(%)",
                  "PE", "成交量(張)", "EPS本期"]
    final_cols = [c for c in final_cols if c in result.columns]
    return result[final_cols].rename(columns={
        "今年現金股利": "今年現金股利_原始",
        "去年現金股利": "去年現金股利_原始",
    }).rename(columns={
        "今年現金股利_原始": "今年現金股利(元)",
        "去年現金股利_原始": "去年現金股利(元)",
        "今年股票股利": "今年股票股利(元)",
        "去年股票股利": "去年股票股利(元)",
    })


# ==========================================================
# 通用工具
# ==========================================================

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
    eps = eps.dropna(subset=["年度", "季別", "股票代號"])

    if eps.empty:
        return pd.DataFrame()

    # 找「覆蓋率達標」的最新季，避免年初時只取到少數 Q4 公告的公司
    # 邏輯：以最大覆蓋數為基準，要求 >= 80% 才採用
    year_q_counts = eps.groupby(["年度", "季別"]).size().reset_index(name='count')
    max_count = int(year_q_counts['count'].max())
    threshold = max_count * 0.8
    candidates = year_q_counts[year_q_counts['count'] >= threshold]

    if candidates.empty:
        # 全部都不達標（罕見），退而求其次用最大覆蓋那一季
        latest_row = year_q_counts.sort_values('count', ascending=False).iloc[0]
    else:
        latest_row = candidates.sort_values(['年度', '季別'], ascending=False).iloc[0]

    latest_year = int(latest_row['年度'])
    latest_q = int(latest_row['季別'])
    latest_count = int(latest_row['count'])
    coverage_pct = latest_count / max_count * 100

    print(f"📊 EPS 最新季: {latest_year}Q{latest_q}（{latest_count}/{max_count} 筆，覆蓋率 {coverage_pct:.0f}%）")

    # ========== V0.9.4 phase4: 寫入歷史庫 ==========
    # 每天都存最新一季，累積一年後 fetch_eps_latest 就能算 YoY
    try:
        _init_eps_history_db(cfg.eps_history_db)
        rows_to_save = [
            (str(r["股票代號"]).strip(), int(r["年度"]), int(r["季別"]),
             float(r["EPS"]) if pd.notna(r["EPS"]) else None, "twse_csv")
            for _, r in eps.iterrows()
        ]
        saved = _upsert_eps_history(cfg.eps_history_db, rows_to_save)
        stats = _eps_history_stats(cfg.eps_history_db)
        print(f"💾 歷史庫: 本次存 {saved} 筆，總累計 {stats['total']} 筆 / {stats['periods']} 季")
    except Exception as e:
        print(f"⚠️ 寫入歷史庫失敗（不影響本函式結果）：{e}")

    cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS本期"})

    # ========== V0.9.4 phase4: 從歷史庫查去年同期 ==========
    # TWSE CSV 只保留最新一季，必須靠歷史庫才能跨年比對
    prev_year = latest_year - 1
    prev_from_csv = eps[(eps["年度"] == prev_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS去年"})
    prev_from_db = _query_eps_history(cfg.eps_history_db, prev_year, latest_q)
    if not prev_from_db.empty:
        prev_from_db = prev_from_db.rename(columns={"eps": "EPS去年"})[["stock_id", "EPS去年"]]
        prev_from_db = prev_from_db.rename(columns={"stock_id": "股票代號"})
        # CSV 與 DB 合併，CSV 優先（更新）
        prev = prev_from_csv.merge(prev_from_db, on="股票代號", how="outer", suffixes=("_csv", "_db"))
        prev["EPS去年"] = prev["EPS去年_csv"].combine_first(prev["EPS去年_db"])
        prev = prev[["股票代號", "EPS去年"]]
        print(f"📂 去年同期 {prev_year}Q{latest_q}: CSV {len(prev_from_csv)} 筆 + 歷史庫 {len(prev_from_db)} 筆 → 合併 {len(prev)} 筆")
    else:
        prev = prev_from_csv
        if prev.empty:
            print(f"⚠️ 去年同期 {prev_year}Q{latest_q} 沒有資料（CSV 無、歷史庫也無）→ YoY 將全 NA")

    out = cur.merge(prev, on="股票代號", how="left")

    def safe_yoy(row):
        if pd.isna(row["EPS去年"]) or row["EPS去年"] == 0:
            return pd.NA
        return (row["EPS本期"] - row["EPS去年"]) / abs(row["EPS去年"])

    out["EPSYoY_raw"] = out.apply(safe_yoy, axis=1)
    out["EPSYoY_顯示(%)"] = out["EPSYoY_raw"].apply(
        lambda x: round(x * 100, 2) if pd.notna(x) else pd.NA
    )
    out["EPS季別"] = f"{latest_year}Q{latest_q}"

    print(f"📊 EPS 計算結果: 本期 {len(out)} 筆，有 YoY 資料 {out['EPSYoY_raw'].notna().sum()} 筆")

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
    logger.log("🚀 StockTool v0.9.5-alpha 開始執行")
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

        # ✅ v0.9.4 Excel 清單強制買點模式
        if cfg.excel_force_buy:
            logger.log("   📊 啟用 Excel 清單強制買點模式")
            logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
    else:
        tech_codes = df_sel_temp.head(cfg.top_n_for_tech)["股票代號"].dropna().astype(str).str.strip().tolist()
    logger.log(f"   選股檔數: {len(tech_codes)}，每檔 {cfg.history_months} 個月歷史資料")

    #tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)
    tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)

    # ✅ v0.9.4 Excel 清單強制買點模式：將買點強制設為 True
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
# V0.9.4 phase2.3: 萬年曆挑選日期（純 Tkinter 原生，無額外 dependency）
# ==========================================================
class _CalendarDialog:
    """
    簡單彈出式月曆。
    使用方式：
        date_str = _CalendarDialog.pick(parent, initial="2026-06-11")
        # date_str == "YYYY-MM-DD"（str）或 None（取消）
    """
    DAY_HEADER = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, parent, initial: str = ""):
        self.result: Optional[str] = None

        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        self.win.title("挑選日期")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial:
            try:
                self.current = datetime.strptime(initial, "%Y-%m-%d")
            except ValueError:
                self.current = datetime.now()
        else:
            self.current = datetime.now()

        self._build()
        self.win.deiconify()
        # wait_window() blocks until win is destroyed (_select / _cancel / X).
        # GUI stays fully responsive; grab_set() makes this window modal.
        self.win.wait_window()

    def _build(self):
        win = self.win

        # ── 頂部導航列 ──
        nav = ttk.Frame(win)
        nav.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(nav, text="◀◀", width=3,
                   command=lambda: self._navigate_years(-1)).pack(side="left")
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._navigate(-1)).pack(side="left")

        # 年份 label（點擊可直接修改年份）
        self._year_lbl = tk.Label(nav, text="", font=("Segoe UI", 9, "bold"),
                                   cursor="hand2", bg="#e8f0fe", padx=4)
        self._year_lbl.pack(side="left", padx=(4, 0))
        self._year_lbl.bind("<Button-1>", lambda e: self._open_year_dialog())

        # 月份 label（點擊可直接修改月份）
        self._month_lbl = tk.Label(nav, text="", width=10, font=("Segoe UI", 10, "bold"),
                                   cursor="hand2", bg="#fff8e1", padx=4)
        self._month_lbl.pack(side="left", padx=4, expand=True)
        self._month_lbl.bind("<Button-1>", lambda e: self._open_month_menu())

        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._navigate(1)).pack(side="right")
        ttk.Button(nav, text="▶▶", width=3,
                   command=lambda: self._navigate_years(1)).pack(side="right")

        # ── 星期抬頭 ──
        hdr = ttk.Frame(win)
        hdr.pack(fill="x", padx=8, pady=(0, 2))
        for d in self.DAY_HEADER:
            lbl = ttk.Label(hdr, text=d, width=4, anchor="center",
                             font=("Segoe UI", 8, "bold"))
            lbl.pack(side="left", padx=1)
            if d == "六":
                lbl.config(foreground="#0070c0")
            elif d == "日":
                lbl.config(foreground="#c00000")

        # ── 日按鈕區域 ──
        self._day_frame = ttk.Frame(win)
        self._day_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._render_days()

        # ── 底部按鈕 ──
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=(0, 8))
        ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side="left", padx=8)

    def _navigate_years(self, delta: int):
        """往前/往後跳一年"""
        self.current = self.current.replace(year=self.current.year + delta)
        self._render_days()

    def _navigate(self, delta: int):
        """往前/往後跳一個月"""
        y, m = self.current.year, self.current.month
        m += delta
        if m > 12:
            m, y = 1, y + 1
        elif m < 1:   # Bugfix: month=0 → 12 月（往前翻年）
            m, y = 12, y - 1
        self.current = self.current.replace(year=y, month=m)
        self._render_days()

    def _open_year_dialog(self):
        """點年份 → 彈出對話框直接輸入年份"""
        dlg = tk.Toplevel(self.win)
        dlg.overrideredirect(True)
        dlg.attributes("-topmost", True)
        rx = self._year_lbl.winfo_rootx()
        ry = self._year_lbl.winfo_rooty() + self._year_lbl.winfo_height()
        dlg.geometry(f"+{rx}+{ry}")
        tk.Label(dlg, text="年份：", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=str(self.current.year))
        ent = tk.Entry(dlg, textvariable=var, width=6, font=("Segoe UI", 10))
        ent.pack(side="left")
        ent.focus()
        ent.select_range(0, "end")

        def commit():
            try:
                yr = int(var.get())
                if 1950 <= yr <= 2100:
                    self.current = self.current.replace(year=yr)
                    self._render_days()
            except ValueError:
                pass
            dlg.destroy()

        tk.Button(dlg, text="確定", font=("Segoe UI", 9), command=commit).pack(side="left", padx=4)
        tk.Button(dlg, text="取消", font=("Segoe UI", 9), command=dlg.destroy).pack(side="left")
        ent.bind("<Return>", lambda e: commit())
        ent.bind("<Escape>", lambda e: dlg.destroy())

    def _open_month_menu(self):
        """點月份 → 彈出 1-12 月快速選單"""
        mnu = tk.Toplevel(self.win)
        mnu.overrideredirect(True)
        mnu.attributes("-topmost", True)
        mx = self._month_lbl.winfo_rootx()
        my = self._month_lbl.winfo_rooty() + self._month_lbl.winfo_height()
        mnu.geometry(f"+{mx}+{my}")
        for m in range(1, 13):
            tk.Button(mnu, text=f"{m} 月", font=("Segoe UI", 10), width=5,
                      command=lambda month=m: self._apply_month_and_close(month, mnu)
                      ).pack(fill="x")

    def _apply_month_and_close(self, month: int, mnu: tk.Toplevel):
        self.current = self.current.replace(month=month)
        mnu.destroy()
        self._render_days()

    def _render_days(self):
        for w in self._day_frame.winfo_children():
            w.destroy()
        year, month = self.current.year, self.current.month
        self._year_lbl.config(text=f"{year} 年")
        self._month_lbl.config(text=f"{month} 月")
        first_wd = datetime(year, month, 1).weekday()
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days
        for _ in range(first_wd):
            ttk.Label(self._day_frame).grid(row=0, column=_, padx=1, pady=1)
        for d in range(1, days_in_month + 1):
            row = (first_wd + d - 1) // 7
            col = (first_wd + d - 1) % 7
            date_str = f"{year:04d}-{month:02d}-{d:02d}"
            btn = tk.Button(self._day_frame, text=str(d), width=4, height=1,
                           font=("Segoe UI", 9),
                           command=lambda ds=date_str: self._select(ds))
            btn.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            wd = (first_wd + d - 1) % 7
            if wd == 5:
                btn.config(foreground="#0070c0", bg="#f0f4ff")
            elif wd == 6:
                btn.config(foreground="#c00000", bg="#fff0f0")
            else:
                btn.config(foreground="#222222", bg="#f5f5f5")
        for c in range(7):
            self._day_frame.columnconfigure(c, weight=1)

    def _select(self, date_str: str):
        self.result = date_str
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def _on_close(self):
        self._cancel()

    @staticmethod
    def pick(parent, initial: str = "") -> Optional[str]:
        return _CalendarDialog(parent, initial).result
# ==========================================================
# GUI 主視窗
# ==========================================================

class StrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StockTool v0.9.5-alpha (Multi-Factor + Top10 Backtest + Portfolio)")

        self.log_queue = queue.Queue()
        self.logger = GuiLogger(self.log_queue)

        saved_config = load_config()
        self.cfg = StrategyConfig()
        self.cfg.update_from_dict(saved_config)

        # V0.9.4 phase2.3: 買賣記錄（broker_discount 從 StrategyConfig 讀）
        self.portfolio = PortfolioDB(DEFAULT_PORTFOLIO_DB,
                                    broker_discount=self.cfg.broker_discount)
        # 記憶體中現價（stock_id → price）
        self._current_prices: Dict[str, float] = {}

        self._build_ui()
        self._poll_log_queue()
        self._load_config_to_ui()

        # V0.9.5: 啟動時背景重抓股價（若 cache 過期就重抓、今天就跳過）
        # 用 flag 避免和「手動重抓股價」按鈕重複觸發
        self._bg_price_fetching = False
        self._price_last_update: Optional[datetime] = None
        self.after(800, self._startup_bg_fetch_price)

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

        # Tab 3：手動選股（V0.9.5 新增）
        self.manual_select_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_select_tab, text="🔍 手動選股")
        self._build_manual_select_tab(self.manual_select_tab)

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

        # ✅ v0.9.4 Excel 清單強制買點模式
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
            self.simple_vars["broker_discount"].set(1.0)

        # ── V0.9.4 phase2.3: 交易成本設定 ──
        ttk.Separator(scrollable_frame, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        row += 1
        ttk.Label(scrollable_frame, text="═ 交易成本設定 ═", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=2, pady=(4, 5), sticky="w")
        row += 1

        ttk.Label(scrollable_frame, text="券商折扣：").grid(row=row, column=0, sticky="w", padx=10, pady=2)
        self.simple_vars["broker_discount"] = tk.DoubleVar(value=self.cfg.broker_discount)
        ttk.Entry(scrollable_frame, textvariable=self.simple_vars["broker_discount"], width=10).grid(row=row, column=1, sticky="w")
        ttk.Label(scrollable_frame, text="（1.0 = 無折扣，0.6 = 6折，0.5 = 5折）", foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
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
            self.simple_vars["broker_discount"].set(1.0)

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
            self.cfg.broker_discount = self.simple_vars["broker_discount"].get()
            # V0.9.4 phase2.3: 即時更新 PortfolioDB 的券商折扣
            self.portfolio.broker_discount = self.cfg.broker_discount
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
        """Tab 切換時自動 refresh 買賣記錄 + 抓持倉現價"""
        try:
            current = self.notebook.index(self.notebook.select())
            if current == 1:  # Tab 2 = 買賣記錄
                self._refresh_portfolio_view()
                # 背景執行抓現價（不 blocking GUI）
                self.after(100, self._auto_fetch_positions_prices)
        except Exception as e:
            self.logger.log(f"⚠️ Tab 切換 refresh 失敗：{e}")

    def _auto_fetch_positions_prices(self):
        """切到買賣記錄 Tab 時自動抓持倉所有股票現價（背景 thread）"""
        positions = self.portfolio.get_positions()
        if not positions:
            return
        stock_ids = [p.stock_id for p in positions if p.stock_id]

        def worker():
            from portfolio import fetch_prices_batch
            try:
                results = fetch_prices_batch(stock_ids)
                # 用 after 回主執行緒更新 GUI
                self.after(0, lambda: self._apply_fetched_prices(results))
            except Exception as e:
                self.after(0, lambda: self.logger.log(f"⚠️ 自動抓現價失敗：{e}"))

        threading.Thread(target=worker, daemon=True).start()
        self.logger.log(f"📡 背景抓 {len(stock_ids)} 檔現價中...")

    def _apply_fetched_prices(self, results: Dict[str, Dict[str, Any]]):
        """把背景抓回來的現價套到 GUI（主執行緒）"""
        for sid, info in results.items():
            if info.get("ok") and info.get("price", 0) > 0:
                self._current_prices[sid] = info["price"]
                # 同時補上股票名稱（如果 DB 沒有的話）
                if info.get("name"):
                    self._backfill_stock_name(sid, info["name"])
        self._refresh_portfolio_view()
        ok_count = sum(1 for v in results.values() if v.get("ok"))
        self.logger.log(f"✅ 現價抓取完成：{ok_count}/{len(results)} 檔成功")

    def _backfill_stock_name(self, stock_id: str, name: str):
        """把抓到的名稱補回 DB 中所有該代號的紀錄"""
        try:
            with self.portfolio._connect() as conn:
                conn.execute(
                    "UPDATE transactions SET stock_name=? WHERE stock_id=? AND (stock_name IS NULL OR stock_name='')",
                    (name, stock_id)
                )
                conn.commit()
        except Exception:
            pass

    def _build_portfolio_tab(self, parent):
        """建立「買賣記錄」Tab 的 UI"""
        # 上方：8 個總覽 Label（2行×4欄）V0.9.4 phase2.3: 加手續費/證交稅/淨利潤
        summary_frame = ttk.LabelFrame(parent, text="📊 持倉總覽", padding=8)
        summary_frame.pack(fill="x", padx=8, pady=(8, 4))
        self._summary_labels = {}

        # Row 0: 成本/市值/未實現/手續費
        row0 = [
            ("total_cost", "總成本（含費用）"),
            ("total_market_value", "總市值"),
            ("total_unrealized_pl", "未實現損益"),
            ("total_fee", "累計手續費"),
        ]
        # Row 1: 證交稅/已實現淨/總報酬率/空白
        row1 = [
            ("total_tax", "累計證交稅"),
            ("net_realized_pl", "已實現淨損益"),
            ("total_return_pct", "總報酬率 %"),
            ("total_pl", "總損益（含費）"),
        ]

        for col, (key, label) in enumerate(row0):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=0, column=col, padx=10, pady=2, sticky="w")
            ttk.Label(cell, text=label, font=("Segoe UI", 9), foreground="#666").pack(anchor="w")
            val_lbl = ttk.Label(cell, text="—", font=("Segoe UI", 12, "bold"))
            val_lbl.pack(anchor="w")
            self._summary_labels[key] = val_lbl

        for col, (key, label) in enumerate(row1):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=1, column=col, padx=10, pady=2, sticky="w")
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
        self._positions_tree.bind("<<TreeviewSelect>>", self._on_position_selected)

        # 下方：交易明細 Treeview
        tx_frame = ttk.LabelFrame(parent, text="📋 交易明細", padding=4)
        tx_frame.pack(fill="both", expand=True, padx=8, pady=4)
        tx_cols = ("id", "日期", "代號", "名稱", "買/賣", "股數", "價格", "手續費", "證交稅", "備註")  # V0.9.4 phase2.3: 加證交稅欄
        self._tx_tree = ttk.Treeview(tx_frame, columns=tx_cols, show="headings", height=8)
        for col, w in zip(tx_cols, [40, 80, 60, 80, 50, 65, 65, 55, 55, 100]):
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
        ttk.Button(btn_frame, text="✏️ 編輯", command=self._open_edit_tx_dialog).pack(side="left", padx=2)  # V0.9.4 phase2.3
        ttk.Button(btn_frame, text="📤 匯出 Excel", command=self._export_portfolio_excel).pack(side="right", padx=2)

    # ==========================================================
    # V0.9.5: 手動選股 Tab
    # ==========================================================
    def _build_manual_select_tab(self, parent):
        """建立「手動選股」Tab 的 UI"""
        # ---- 上方：狀態列 ----
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", padx=8, pady=(6, 0))
        self._ms_status = tk.StringVar(value="請先執行一次「策略回測」以載入市場資料，或直接點「選股」從 FinMind 抓取最新資料")
        ttk.Label(status_frame, textvariable=self._ms_status,
                  foreground="#555555", font=("Helvetica", 9)).pack(anchor="w")

        # 進度條（默認隱藏，選股中才顯示）
        self._ms_progress = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self._ms_progress.pack(anchor="w", pady=(2, 0))
        self._ms_progress.pack_forget()

        # ---- 主區：左側條件 + 右側結果 ----
        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)

        # ── 左面板：篩選條件 + Preset ──
        left_frame = ttk.LabelFrame(paned, text="🔎 篩選條件", padding=8)
        paned.add(left_frame, weight=0)

        # Preset 管理
        preset_top = ttk.Frame(left_frame)
        preset_top.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_top, text="Preset：", font=("Helvetica", 9, "bold")).pack(side="left")
        self._ms_preset_var = tk.StringVar(value="")
        self._ms_preset_combo = ttk.Combobox(preset_top, textvariable=self._ms_preset_var,
                                             state="readonly", width=14)
        self._ms_preset_combo.pack(side="left", padx=4)
        self._ms_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._ms_load_preset())
        ttk.Button(preset_top, text="💾 儲存", width=5,
                   command=self._ms_save_preset).pack(side="left", padx=1)
        ttk.Button(preset_top, text="🗑 刪", width=4,
                   command=self._ms_delete_preset).pack(side="left", padx=1)

        # 篩選條件 Entry（每列：[checkbox] [label] [Entry]）
        # 格式：(label_text, config_key, default_value, skip_value, unit)
        self._ms_filter_vars = {}
        self._ms_filter_defaults = {
            "min_rev_yoy":      (10.0,  None,  "% YoY"),
            "min_stock_div":    (0.0,   None,  "元/股"),
            "min_cash_div_yld": (1.0,   None,  "%殖利率"),
            "min_pe":           (30.0,  None,  "倍"),
            "min_price":        (10.0,  None,  "元"),
            "min_volume":       (100.0, None,  "張/月均"),
            "min_last_stock_div":(0.0,  None,  "元/股"),
            "min_last_cash_yld":(1.0,   None,  "%殖利率"),
        }
        filter_labels = {
            "min_rev_yoy":      "累計營收 YoY ≥",
            "min_stock_div":    "今年股票股利 ≥",
            "min_cash_div_yld": "今年現金殖利率 ≥",
            "min_pe":           "本益比 (PE) ≤",
            "min_price":        "現價 ≥",
            "min_volume":       "月均成交量 ≥",
            "min_last_stock_div":"去年股票股利 ≥",
            "min_last_cash_yld":"去年現金殖利率 ≥",
        }

        def _add_filter_row(parent, label, key, default_val, skip_val, unit):
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=2)
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(row, variable=var)
            cb.pack(side="left")
            ttk.Label(row, text=label, width=20).pack(side="left")
            entry_var = tk.DoubleVar(value=default_val)
            ttk.Entry(row, textvariable=entry_var, width=8).pack(side="left")
            ttk.Label(row, text=unit, width=7).pack(side="left")
            self._ms_filter_vars[key] = (var, entry_var, skip_val)

        for key, (default, skip, unit) in self._ms_filter_defaults.items():
            _add_filter_row(left_frame, filter_labels[key], key, default, skip, unit)

        # 結果上限
        limit_row = ttk.Frame(left_frame)
        limit_row.pack(fill="x", pady=(6, 0))
        ttk.Label(limit_row, text="結果上限：", width=20).pack(side="left")
        self._ms_limit_var = tk.IntVar(value=500)
        ttk.Entry(limit_row, textvariable=self._ms_limit_var, width=8).pack(side="left")
        ttk.Label(limit_row, text="檔", width=7).pack(side="left")

        # 按鈕
        btn_row = ttk.Frame(left_frame)
        btn_row.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_row, text="🔍 開始選股",
                   command=self._ms_run_selection).pack(fill="x", pady=1)
        # V0.9.5: 手動重抓股價（背景跑中就跳過）
        ttk.Button(btn_row, text="🔄 重新抓股價",
                   command=self._ms_force_refresh_price).pack(fill="x", pady=1)
        self._ms_price_status = tk.StringVar(value="股價未抓取")
        ttk.Label(btn_row, textvariable=self._ms_price_status,
                  font=("Helvetica", 8), foreground="#666666").pack(anchor="w", pady=(0, 4))
        # V0.9.5+: 指定股補抓（Free tier 適用：手動輸入股號、只要用少數 API 額度）
        # 順序放在 💰 上面（推薦用法：只抓關心的）
        ttk.Button(btn_row, text="🎯 指定股補抓 (推薦 Free tier)",
                   command=self._ms_fetch_specific_dividend).pack(fill="x", pady=1)
        # V0.9.5+: 掃描全部股票 (100檔/次) — 一個月一個月慢慢補、按次分批避免 Free tier 爆 402
        ttk.Button(btn_row, text="💰 掃描全部股票 (100檔/次)",
                   command=self._ms_fetch_all_dividend).pack(fill="x", pady=1)
        self._ms_dividend_status = tk.StringVar(value="股利 DB: 計算中...")
        ttk.Label(btn_row, textvariable=self._ms_dividend_status,
                  font=("Helvetica", 8), foreground="#666666").pack(anchor="w", pady=(0, 4))
        ttk.Button(btn_row, text="📋 全選",
                   command=self._ms_select_all).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="☐ 全不選",
                   command=self._ms_select_none).pack(fill="x", pady=1)
        ttk.Button(btn_row, text="📤 匯出 Excel",
                   command=self._ms_export_excel).pack(fill="x", pady=1)

        # ── 右面板：結果列表 ──
        right_frame = ttk.LabelFrame(paned, text="📊 篩選結果", padding=4)
        paned.add(right_frame, weight=1)

        # Treeview with checkbox
        cols = ("勾選","代號","名稱","現價","累計YoY%",
                "今股票","今現金殖%","PE","成交量(張)",
                "去年股票","去年現金殖%")
        self._ms_tree = ttk.Treeview(right_frame, columns=cols, show="headings",
                                     selectmode="none", height=25)
        col_widths = (40, 60, 100, 70, 70, 65, 80, 50, 80, 65, 80)
        for col, w in zip(cols, col_widths):
            self._ms_tree.heading(col, text=col)
            self._ms_tree.column(col, width=w, anchor="center")

        ms_scroll_y = ttk.Scrollbar(right_frame, orient="vertical", command=self._ms_tree.yview)
        ms_scroll_x = ttk.Scrollbar(right_frame, orient="horizontal", command=self._ms_tree.xview)
        self._ms_tree.configure(yscrollcommand=ms_scroll_y.set, xscrollcommand=ms_scroll_x.set)
        self._ms_tree.pack(fill="both", expand=True)
        ms_scroll_y.pack(side="right", fill="y")
        ms_scroll_x.pack(side="bottom", fill="x")

        # Click to toggle checkbox
        self._ms_tree.bind("<Button-1>", self._ms_toggle_check)

        # 右鍵選單
        self._ms_tree.bind("<Button-3>", self._ms_show_context_menu)

        # 初始化：載入上次 preset + 讀取 pipeline 資料狀態
        self._ms_load_preset()
        self._ms_refresh_pipeline_status()
        self._ms_refresh_dividend_status()

    def _ms_refresh_pipeline_status(self):
        """更新狀態列：顯示 pipeline 資料是否已載入"""
        has_price = hasattr(self, '_price_df') and self._price_df is not None and not self._price_df.empty
        has_revenue = hasattr(self, '_revenue_df') and self._revenue_df is not None and not self._revenue_df.empty
        has_eps = hasattr(self, '_eps_df') and self._eps_df is not None and not self._eps_df.empty

        status = []
        if has_price: status.append(f"股價({len(self._price_df)}筆)")
        if has_revenue: status.append(f"營收({len(self._revenue_df)}筆)")
        if has_eps: status.append(f"EPS({len(self._eps_df)}筆)")

        if status:
            self._ms_status.set("✅ Pipeline 資料已就緒：" + " / ".join(status) +
                               "｜可直接選股，或點「選股」從 FinMind 實時抓取")
        else:
            self._ms_status.set("⚠️ Pipeline 尚未執行｜點「選股」將從 FinMind 即時抓取市場資料")

    def _ms_get_filters(self) -> dict:
        """從 UI 讀取目前的篩選條件，回傳 dict。"""
        f = {}
        for key, (cb_var, entry_var, skip_val) in self._ms_filter_vars.items():
            if cb_var.get():  # 有勾選
                f[key] = entry_var.get()
            else:
                f[key] = skip_val  # None = skip
        f["top_n"] = self._ms_limit_var.get()
        return f

    # ==========================================================
    # V0.9.5: 背景重抓股價（啟動時 + 手動按鈕）
    # ==========================================================
    def _startup_bg_fetch_price(self):
        """App 啟動 0.8s 後背景重抓股價（跳過選項：pipeline 剛抓過且是今天）
        - 用 get_or_fetch：meta last_update == today → 用 cache、不抓
        - 反之走 fetch_prices 重抓、寫回 cache
        - 重抓中使用者點「重新抓股價」按鈕 → 旗標判斷跳過
        """
        if self._bg_price_fetching:
            return
        self._bg_price_fetching = True
        self._ms_price_status.set("🔄 背景抓取股價中（啟動時自動）...")
        self._ms_status.set("🔄 背景重抓股價中（啟動時自動、跳過今天已抓的 cache）...")

        def _bg_worker():
            try:
                _s = build_session()
                # get_or_fetch 內部會判斷 meta last_update == today
                df = get_or_fetch("price", lambda: fetch_prices(_s, self.cfg), self.logger)
                self.after(0, lambda: self._on_bg_price_done(df, source="啟動時自動"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_bg_price_err(err, source="啟動時自動"))

        threading.Thread(target=_bg_worker, daemon=True).start()

    def _ms_force_refresh_price(self):
        """手動選股 Tab「🔄 重新抓股價」按鈕
        - 若背景正在抓 → 跳過、提示使用者（避免重複打 FinMind）
        - 反之強制重抓（不走 cache）
        """
        if self._bg_price_fetching:
            self._ms_status.set("⏳ 背景抓取股價中｜按鈕已跳過、請稍候...")
            self.logger.log("⏳ 背景抓股價中，手動按鈕跳過（避免重複打 FinMind）")
            return

        self._bg_price_fetching = True
        self._ms_status.set("🔄 手動重抓股價中（強制重抓、不走 cache）...")
        self._ms_price_status.set("🔄 抓取中...")

        def _force_worker():
            try:
                _s = build_session()
                # 強制重抓：直接呼叫 fetch_prices（不查 cache）
                df = fetch_prices(_s, self.cfg)
                # 寫回 cache（更新 meta last_update = today）
                save_cache(get_cache_file("price"), df)
                self.after(0, lambda: self._on_bg_price_done(df, source="手動重抓"))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_bg_price_err(err, source="手動重抓"))

        threading.Thread(target=_force_worker, daemon=True).start()

    def _on_bg_price_done(self, df, source: str = ""):
        """背景重抓股價完成（不論啟動或手動）→ 更新 GUI"""
        self._bg_price_fetching = False
        if df is not None and not df.empty:
            self._price_df = df
            self._price_last_update = datetime.now()
            self._update_price_status_label()
            self._ms_status.set(f"✅ 股價資料就緒（{source}、{len(df)} 筆）｜可點「選股」")
            self.logger.log(f"✅ {source}股價完成：{len(df)} 筆")
        else:
            self._ms_status.set(f"⚠️ {source}股價完成但無資料")
            self.logger.log(f"⚠️ {source}股價完成但無資料")

    def _on_bg_price_err(self, err: str, source: str = ""):
        """背景重抓股價失敗 → log + 更新狀態列（不阻擋使用者）"""
        self._bg_price_fetching = False
        self._ms_price_status.set(f"⚠️ {source}失敗：{err[:40]}")
        self._ms_status.set(f"⚠️ {source}股價失敗：{err}（可手動重試）")
        self.logger.log(f"⚠️ {source}股價失敗：{err}")

    def _update_price_status_label(self):
        """更新手動選股 Tab 的「股價更新時間」label"""
        if self._price_last_update:
            self._ms_price_status.set(
                f"股價更新：{self._price_last_update.strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # ==========================================================
    # V0.9.5: 一次性補抓全部股利（避免每次選股都打 FinMind）
    # ==========================================================
    def _ms_refresh_dividend_status(self):
        """更新股利 DB 狀態 label：顯示「股利 DB: 351/2374 檔（缺漏 2023）」"""
        try:
            _init_div_history_db("dividend_history.db")
            price_df = getattr(self, "_price_df", None)
            if price_df is None or price_df.empty:
                # fallback: 從 price cache 讀
                for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                    if os.path.exists(p):
                        try:
                            price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                            break
                        except Exception:
                            pass
            if price_df is None or price_df.empty:
                self._ms_dividend_status.set("股利 DB: 無法計算（未抓到股價名單）")
                return
            all_codes = price_df["股票代號"].astype(str).str.strip().tolist()
            cached = _query_div_history("dividend_history.db", all_codes)
            in_db = len(cached)
            total = len(all_codes)
            missing = total - in_db
            if missing == 0:
                self._ms_dividend_status.set(f"股利 DB: ✅ {in_db}/{total} 檔（全部就絡）")
            else:
                self._ms_dividend_status.set(f"股利 DB: {in_db}/{total} 檔（缺漏 {missing}）")
        except Exception as e:
            self._ms_dividend_status.set(f"股利 DB: 查詢失敗 {str(e)[:30]}")

    # V0.9.5+: 「💰 掃描全部股票」分批參數
    _MS_SCAN_BATCH = 100  # 每批 100 檔（Free tier 300-1000 筆/月額度友善）

    def _ms_fetch_all_dividend(self):
        """手動選股 Tab「💰 掃描全部股票 (100檔/次)」按鈕
        - 從 price_df 取所有股票代號
        - 比對 DB，只補抓缺漏中的「前 100 檔」
        - 一個月一個月慢慢補：跑完停、下次再按繼續抓下一批
        - 全部抓完後股利 DB 完整、可發現關注清單外的標的
        """
        # 避免重複
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 掃描股利中，請稍候...")
            return

        # 計算缺漏數
        self._ms_refresh_dividend_status()
        cur = self._ms_dividend_status.get()
        if "缺漏 0" in cur or "全部就絡" in cur:
            self._ms_status.set("✅ 股利 DB 完整、無需補抓")
            return

        # 解析缺漏數（從 status label 抓數字）
        import re as _re_scan
        m = _re_scan.search(r"缺漏\s*(\d+)", cur)
        missing = int(m.group(1)) if m else 0
        if missing <= 0:
            self._ms_status.set("✅ 股利 DB 完整、無需補抓")
            return

        # 分批計算
        batch = self._MS_SCAN_BATCH
        this_batch = min(batch, missing)
        runs_left_total = (missing + batch - 1) // batch  # 含這次

        # 確認
        if not messagebox.askyesno(
            "確認掃描股利",
            f"這次會從 FinMind 掃描補抓 {this_batch} 檔股利寫入本地 DB。\n\n"
            f"目前狀態：{cur}\n\n"
            f"📦 分批設定：{batch} 檔/次\n"
            f"⏱️ 預計 {int(this_batch * 0.4) + 1} 秒、{this_batch} 筆 API 額度\n"
            f"🔁 全部補完約需再按 {runs_left_total} 次（可分散在不同天）\n\n"
            f"💡 Free tier 額度 300-1000 筆/月，建議一天最多跑 1-2 次\n"
            f"💡 想只抓關注個股可用「🎯 指定股補抓」更省額度\n\n"
            f"按「Yes」開始，期間可按「取消」中斷。",
        ):
            return

        self._ms_dividend_fetching = True
        self._ms_status.set(f"🔄 掃描股利中（{this_batch}/{missing} 檔、請勿關 App）...")

        # 取得所有股票代號
        price_df = getattr(self, "_price_df", None)
        if price_df is None or price_df.empty:
            for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                if os.path.exists(p):
                    try:
                        price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                        break
                    except Exception:
                        pass
        if price_df is None or price_df.empty:
            self._ms_dividend_fetching = False
            self._ms_status.set("❌ 掃描失敗：未取得股價名單（請先點「重抓股價」）")
            return
        all_codes = price_df["股票代號"].astype(str).str.strip().tolist()

        def _fetch_worker():
            try:
                # 背景補抓：給 progress_callback 讓 UI 更新
                def _progress(done, total):
                    self.after(0, lambda d=done, t=total: self._ms_status.set(
                        f"🔄 掃描股利中... {d}/{t}（{int(d/t*100)}%）"
                    ))

                added = _background_fetch_all_dividend(
                    all_codes, db_path="dividend_history.db",
                    progress_callback=_progress, batch_size=batch,
                )
                self.after(0, lambda: self._on_dividend_fetch_done(added))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_dividend_fetch_err(err))

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _on_dividend_fetch_done(self, added: int):
        """補抓股利完成（💰 掃描全部股票 / 🎯 指定股補抓 共用）
        - 重新 refresh DB 狀態 → 算出剩餘缺漏
        - 顯示「這次 +X 檔｜剩 Y 檔（再 N 次可補完）」
        """
        self._ms_dividend_fetching = False
        self._ms_refresh_dividend_status()
        cur = self._ms_dividend_status.get()
        if added == -1:
            # FinMind 額度用完（_background_fetch_all_dividend 回傳 -1）
            self._ms_status.set(
                "❌ 補抓中斷：FinMind 額度用完（status 402）｜"
                "已補抓的資料已寫入 DB"
            )
            self.logger.log("❌ 補抓股利中斷：FinMind 額度用完（status 402）")
            return
        # 從 cur 抓剩餘缺漏（regex）
        import re as _re_done
        m = _re_done.search(r"缺漏\s*(\d+)", cur)
        remaining = int(m.group(1)) if m else 0
        if remaining == 0:
            # 全部完成
            self._ms_status.set(f"✅ 補抓股利完成：新增 {added} 檔｜{cur}")
            self.logger.log(f"✅ 補抓股利完成：新增 {added} 檔（全部就絡）")
        else:
            # 還有缺漏、告訴使用者還要按幾次
            batch = self._MS_SCAN_BATCH
            runs_left = (remaining + batch - 1) // batch
            self._ms_status.set(
                f"✅ 這次補 {added} 檔｜剩 {remaining} 檔（再按 {runs_left} 次可補完）｜{cur}"
            )
            self.logger.log(f"✅ 補抓股利：這次 +{added}｜剩 {remaining} 檔（{runs_left} 次可補完）")
        # 自動重跑選股（讓使用者直接看到補抓後的結果）
        self._ms_run_selection()

    def _on_dividend_fetch_err(self, err: str):
        """補抓股利失敗"""
        self._ms_dividend_fetching = False
        self._ms_status.set(f"❌ 補抓股利失敗：{err}（可重試）")
        self.logger.log(f"❌ 補抓股利失敗：{err}")

    def _ms_fetch_specific_dividend(self):
        """手動選股 Tab「🎯 指定股補抓」按鈕

        適用情境：FinMind Free tier 額度不夠一次抓全部
        流程：
          1. 跳出輸入框（多行、可貼上「2330, 2454, 2317」這類格式）
          2. 解析股號、只抓那些
          3. 寫入 DB、狀態列顯示進度
        """
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 補抓股利中，請稍候...")
            return

        # 對話框：可輸入多行股號（逗號、空格、換行分隔）
        from tkinter import simpledialog
        default = "2330, 2454, 2317"  # 台積電、聯發科、鴻海
        codes_raw = simpledialog.askstring(
            "指定股補抓股利",
            "請輸入要補抓的股號（可貼上）：\n"
            "格式：「2330, 2454, 2317」或一行一個\n"
            "限 1-100 檔（超過 100 不收）",
            initialvalue=default,
            parent=self.manual_select_tab,
        )
        if not codes_raw:
            return

        # 解析
        import re as _re_codes
        codes = [c.strip() for c in _re_codes.split(r"[\s,，]+", codes_raw) if c.strip()]
        # 限 100 檔
        if len(codes) > 100:
            messagebox.showwarning("超過限制", f"只取前 100 檔（你輸入 {len(codes)} 檔）")
            codes = codes[:100]
        if not codes:
            messagebox.showwarning("無股號", "請至少輸入 1 個股號")
            return

        # 看哪些不在 DB
        _init_div_history_db("dividend_history.db")
        cached = _query_div_history("dividend_history.db", codes)
        to_fetch = [c for c in codes if c not in cached]
        if not to_fetch:
            messagebox.showinfo("無需補抓", f"這 {len(codes)} 檔都已在 DB 中，無需補抓")
            return

        if not messagebox.askyesno(
            "確認補抓",
            f"將補抓 {len(to_fetch)} 檔股利到本地 DB。\n"
            f"（{len(codes) - len(to_fetch)} 檔已在 DB 跳過）\n\n"
            f"預計需要 {int(len(to_fetch) * 0.4) + 1} 秒、{len(to_fetch)} 筆 API 額度。",
        ):
            return

        self._ms_dividend_fetching = True
        self._ms_status.set(f"🔄 指定股補抓中（{len(to_fetch)} 檔）...")

        def _fetch_worker():
            try:
                def _progress(done, total):
                    self.after(0, lambda d=done, t=total: self._ms_status.set(
                        f"🔄 指定股補抓中... {d}/{t}（{int(d/t*100)}%）"
                    ))

                added = _background_fetch_all_dividend(
                    to_fetch, db_path="dividend_history.db", progress_callback=_progress,
                )
                self.after(0, lambda: self._on_dividend_fetch_done(added))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_dividend_fetch_err(err))

        threading.Thread(target=_fetch_worker, daemon=True).start()

    def _ms_run_selection(self):
        """點「選股」：抓取資料 → 篩選 → 顯示結果"""
        # V0.9.5: 背景抓股價中→跳過避免重複打 FinMind
        if self._bg_price_fetching:
            self._ms_status.set("⏳ 背景抓股價中，請稍候再點「選股」...")
            self.logger.log("⏳ 背景抓股價中，「選股」跳過（避免重複打 FinMind）")
            return
        # V0.9.5: 背景補抓股利中→跳過
        if getattr(self, "_ms_dividend_fetching", False):
            self._ms_status.set("⏳ 補抓股利中，請稍候再點「選股」...")
            self.logger.log("⏳ 補抓股利中，「選股」跳過")
            return

        filters = self._ms_get_filters()
        top_n = filters.pop("top_n", 500)

        # 顯示進度條
        self._ms_progress.pack(anchor="w", pady=(2, 0))
        self._ms_progress["value"] = 0
        self._ms_status.set("🔄 抓取資料中，請稍候...")
        self._ms_tree.delete(*self._ms_tree.get_children())
        self.update_idletasks()

        # 啟動進度輪詢 timer
        self._ms_poll_running = True
        self._ms_poll_progress()

        def _do():
            try:
                # 優先用 pipeline 快取
                price_df = getattr(self, '_price_df', None)
                revenue_df = getattr(self, '_revenue_df', None)
                eps_df = getattr(self, '_eps_df', None)

                # fallback 1：若 GUI 沒記、但 cache/ 有 → 讀 cache
                # 注：讀 cache 前先檢查 last_update；若 != today 就走 get_or_fetch 重抓
                #     （避免六日不開盤下「last_update 是昨天 = today」就誤判過期）
                from datetime import datetime as _dt
                _today = _dt.now().strftime("%Y-%m-%d")
                def _is_cache_fresh(path):
                    try:
                        _meta = pd.read_excel(path, sheet_name="meta", engine="openpyxl")
                        _last = str(_meta.loc[0, "last_update"])
                        return _last >= _today   # 含今天（避免跨交易日誤判）
                    except Exception:
                        return False
                if price_df is None or price_df.empty:
                    for p in ["cache/price.xlsx", "source/cache/price.xlsx"]:
                        if os.path.exists(p):
                            if _is_cache_fresh(p):
                                try:
                                    price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                    print(f"✅ 讀 price cache (last_update={pd.read_excel(p, sheet_name='meta', engine='openpyxl').loc[0, 'last_update']}): {len(price_df)} 筆")
                                    break
                                except Exception:
                                    pass
                            else:
                                # cache 過期 → 走 get_or_fetch 重抓（會自動寫回 cache）
                                try:
                                    _s = build_session()
                                    price_df = get_or_fetch("price", lambda: fetch_prices(_s, self.cfg), self.logger)
                                    print(f"♻️ price cache 過期 → 重抓 {len(price_df)} 筆")
                                    break
                                except Exception as _e:
                                    print(f"⚠️ price 重抓失敗：{_e} → fallback 讀舊 cache")
                                    try:
                                        price_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                        print(f"✅ 讀 price cache (舊): {len(price_df)} 筆")
                                        break
                                    except Exception:
                                        pass
                if revenue_df is None or revenue_df.empty:
                    for p in ["cache/revenue.xlsx", "source/cache/revenue.xlsx"]:
                        if os.path.exists(p):
                            try:
                                revenue_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                print(f"✅ 讀 revenue cache: {len(revenue_df)} 筆")
                                break
                            except Exception:
                                pass
                if eps_df is None or eps_df.empty:
                    for p in ["cache/eps.xlsx", "source/cache/eps.xlsx"]:
                        if os.path.exists(p):
                            try:
                                eps_df = pd.read_excel(p, sheet_name="data", engine="openpyxl")
                                print(f"✅ 讀 eps cache: {len(eps_df)} 筆")
                                break
                            except Exception:
                                pass

                result = _run_manual_selection(
                    price_df=price_df if (price_df is not None and not price_df.empty) else pd.DataFrame(),
                    revenue_df=revenue_df if (revenue_df is not None and not revenue_df.empty) else pd.DataFrame(),
                    eps_df=eps_df if (eps_df is not None and not eps_df.empty) else pd.DataFrame(),
                    filters=filters,
                    top_n=top_n,
                )
                self._ms_result_df = result
                self._ms_poll_running = False
                self.after(0, lambda: self._ms_display_results(result))
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # 完整訊息寫到主 console（背景 thread 也能輸出）
                print(f"[手動選股失敗] {e}\n{tb}")
                err_msg = f"❌ 選股失敗：{e}\n{tb.splitlines()[-1] if tb else ''}"
                self._ms_poll_running = False
                self.after(0, lambda msg=err_msg: self._ms_status.set(msg))

        threading.Thread(target=_do, daemon=True).start()

    def _ms_poll_progress(self):
        """每 0.5 秒更新狀態列 + 進度條"""
        if not getattr(self, '_ms_poll_running', False):
            self._ms_progress.pack_forget()
            return
        stage = _MS_PROGRESS.get("stage", "")
        done = _MS_PROGRESS.get("done", 0)
        total = _MS_PROGRESS.get("total", 0)
        err = _MS_PROGRESS.get("error", "")
        if err:
            # V0.9.5+ 強化 402 額度提示
            if "402" in err or "額度" in err:
                self._ms_status.set(
                    f"❌ FinMind 額度用完（status 402）｜已完成 {done}/{total} 檔｜"
                    f"已寫入的資料已保存｜💡 請下月重置後再跑或升級 plan"
                )
            else:
                self._ms_status.set(f"❌ {err[:80]}")
        elif total > 0:
            pct = min(100, int(done / total * 100))
            self._ms_progress["value"] = pct
            self._ms_status.set(f"🔄 抓取{stage}中... {done}/{total} ({pct}%)")
        else:
            self._ms_status.set(f"🔄 準備抓取{stage}...")
        self.after(500, self._ms_poll_progress)

    def _ms_display_results(self, result):
        """把 DataFrame 顯示在 Treeview 上"""
        self._ms_tree.delete(*self._ms_tree.get_children())
        if result.empty:
            # V0.9.5+ 强化提示：可能原因
            self._ms_status.set(
                "❌ 這次篩選沒有合格股票｜可能原因："
                "(1) 條件太嚴格、(2) DB 缺漏（殖利率/股利為 None 的股票已被排除）、"
                "(3) 可按「💰 掃描全部股票 (100檔/次)」補抓股利"
            )
            self.logger.log("❌ 篩選無結果（可能條件太嚴格或 DB 缺漏）")
            return

        # 快取勾選狀態（股票代號 → 是否勾選）
        self._ms_checked = {}

        for _, row in result.iterrows():
            code = str(row.get("股票代號", "")).strip()
            name = str(row.get("股票名稱", "")).strip()
            price = row.get("現價")
            price_str = f"{price:.2f}" if price and str(price) not in ("nan","None") else "—"
            rev = row.get("累計營收YoY(%)")
            rev_str = f"{rev:.2f}" if rev and str(rev) not in ("nan","None") else "—"
            stock_div = row.get("今年股票股利(元)", "—")
            stock_str = f"{stock_div:.2f}" if isinstance(stock_div, float) and str(stock_div) not in ("nan","None") else "—"
            cash_yld = row.get("今年現金殖利率(%)")
            cash_str = f"{cash_yld:.2f}" if cash_yld and str(cash_yld) not in ("nan","None") else "—"
            pe = row.get("PE")
            pe_str = f"{pe:.2f}" if pe and str(pe) not in ("nan","None") else "—"
            vol = row.get("成交量(張)")
            vol_str = f"{int(vol):,}" if vol and str(vol) not in ("nan","None") else "—"
            last_stock = row.get("去年股票股利(元)")
            last_stock_str = f"{last_stock:.2f}" if isinstance(last_stock, float) and str(last_stock) not in ("nan","None") else "—"
            last_cash = row.get("去年現金殖利率(%)")
            last_cash_str = f"{last_cash:.2f}" if last_cash and str(last_cash) not in ("nan","None") else "—"

            tag = "checked" if self._ms_checked.get(code, False) else "unchecked"
            self._ms_tree.insert("", "end", iid=code, values=(
                "☑" if self._ms_checked.get(code, False) else "☐",
                code, name, price_str, rev_str,
                stock_str, cash_str, pe_str, vol_str,
                last_stock_str, last_cash_str
            ), tags=(tag,))

        self._ms_status.set(f"✅ 符合條件：{len(result)} 檔（上限 {self._ms_limit_var.get()} 檔）｜排序：營收YoY > 今年股票 > 今年現金殖% > PE")

    def _ms_toggle_check(self, event):
        """點 Treeview 任一列 → toggle 勾選狀態"""
        region = self._ms_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self._ms_tree.identify_column(event.x)
        if column != "#1":  # 只有第一欄（勾選欄）可以 toggle
            return
        item_id = self._ms_tree.identify_row(event.y)
        if not item_id:
            return

        current = self._ms_checked.get(item_id, False)
        self._ms_checked[item_id] = not current
        vals = list(self._ms_tree.item(item_id, "values"))
        vals[0] = "☑" if not current else "☐"
        self._ms_tree.item(item_id, values=vals,
                           tags=("checked" if not current else "unchecked",))

    def _ms_select_all(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = True
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☑"
            self._ms_tree.item(item, values=vals, tags=("checked",))

    def _ms_select_none(self):
        for item in self._ms_tree.get_children():
            self._ms_checked[item] = False
            vals = list(self._ms_tree.item(item, "values"))
            vals[0] = "☐"
            self._ms_tree.item(item, values=vals, tags=("unchecked",))

    def _ms_show_context_menu(self, event):
        """右鍵：全選 / 全不選"""
        menu = tk.Menu(self.manual_select_tab, tearoff=0)
        menu.add_command(label="☑ 全選", command=self._ms_select_all)
        menu.add_command(label="☐ 全不選", command=self._ms_select_none)
        menu.post(event.x_root, event.y_root)

    def _ms_export_excel(self):
        """匯出選中的股票到 Excel"""
        if not hasattr(self, '_ms_result_df') or self._ms_result_df is None or self._ms_result_df.empty:
            messagebox.showwarning("無資料", "請先執行「選股」")
            return

        checked = [code for code, v in self._ms_checked.items() if v]
        if not checked:
            messagebox.showwarning("未勾選", "請先勾選要匯出的股票")
            return

        result = self._ms_result_df[
            self._ms_result_df["股票代號"].astype(str).str.strip().isin(checked)
        ].copy()

        # 加入「使用者設定的篩選門檻值」當備註欄
        filters = self._ms_get_filters()
        for key, (cb_var, entry_var, skip_val) in self._ms_filter_vars.items():
            label_map = {
                "min_rev_yoy": "篩_累計營收YoY%",
                "min_stock_div": "篩_今年股票股利元",
                "min_cash_div_yld": "篩_今年現金殖利率%",
                "min_pe": "篩_PE上限",
                "min_price": "篩_現價下限",
                "min_volume": "篩_成交量下限張",
                "min_last_stock_div": "篩_去年股票股利元",
                "min_last_cash_yld": "篩_去年現金殖利率%",
            }
            col_name = label_map.get(key, key)
            val = entry_var.get() if cb_var.get() else "不限"
            result[col_name] = val

        filepath = filedialog.asksaveasfilename(
            title="匯出手動選股結果",
            defaultextension=".xlsx",
            filetypes=["Excel 活頁簿 (*.xlsx)"],
            initialfile=f"手動選股_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        )
        if not filepath:
            return

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = Workbook()
            ws = wb.active
            ws.title = "手動選股"

            headers = list(result.columns)
            ws.append(headers)

            header_fill = PatternFill("solid", fgColor="4472C4")
            header_font = Font(color="FFFFFF", bold=True)
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

            for row_data in result.values.tolist():
                ws.append(row_data)

            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

            wb.save(filepath)
            messagebox.showinfo("匯出成功", f"已匯出 {len(result)} 檔\n→ {filepath}")
        except Exception as e:
            messagebox.showerror("匯出失敗", str(e))

    # ── Preset 管理 ──
    def _ms_get_presets(self) -> dict:
        raw = self.cfg.to_dict().get("manual_select_presets", {})
        return raw if isinstance(raw, dict) else {}

    def _ms_save_preset(self):
        """彈出對話框，輸入 preset 名稱，儲存當前條件"""
        name = simpledialog.askstring("儲存 Preset", "請輸入Preset名稱：",
                                      initialvalue="我的篩選")
        if not name:
            return
        name = name.strip()
        filters = self._ms_get_filters()
        presets = self._ms_get_presets()
        presets[name] = filters
        self.cfg.update_from_dict({"manual_select_presets": presets,
                                   "manual_select_last_preset": name})
        save_config(self.cfg.to_dict())
        self._ms_refresh_preset_list()
        self._ms_preset_var.set(name)
        messagebox.showinfo("已儲存", f"Preset「{name}」已儲存")

    def _ms_load_preset(self):
        """根據目前選中的 preset 名稱，載入條件到 UI"""
        name = self._ms_preset_var.get().strip()
        presets = self._ms_get_presets()
        data = presets.get(name, {})
        if not data:
            return

        # 還原 top_n
        if "top_n" in data:
            self._ms_limit_var.set(int(data["top_n"]))

        # 還原各 filter（跳過 top_n key）
        for key, val in data.items():
            if key == "top_n":
                continue
            if key in self._ms_filter_vars:
                cb_var, entry_var, skip_val = self._ms_filter_vars[key]
                cb_var.set(val is not None and val != skip_val)
                if val is not None:
                    entry_var.set(float(val))

    def _ms_delete_preset(self):
        name = self._ms_preset_var.get().strip()
        if not name:
            return
        if not messagebox.askyesno("確認刪除", f"刪除 Preset「{name}」？"):
            return
        presets = self._ms_get_presets()
        presets.pop(name, None)
        last = self.cfg.to_dict().get("manual_select_last_preset")
        self.cfg.update_from_dict({"manual_select_presets": presets})
        if last == name:
            self.cfg.update_from_dict({"manual_select_last_preset": None})
        save_config(self.cfg.to_dict())
        self._ms_refresh_preset_list()
        self._ms_preset_var.set("")
        messagebox.showinfo("已刪除", f"Preset「{name}」已刪除")

    def _ms_refresh_preset_list(self):
        """重新整理 preset 下拉選項，並自動選中上次"""
        presets = list(self._ms_get_presets().keys())
        self._ms_preset_combo["values"] = presets
        last = self.cfg.to_dict().get("manual_select_last_preset")
        if last and last in presets:
            self._ms_preset_var.set(last)
        elif presets:
            self._ms_preset_var.set(presets[0])

    def _on_position_selected(self, event):
        """持倉明細任一列被點擊 → 顯示該股票完整統計"""
        sel = self._positions_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = self._positions_tree.item(item, "values")
        # vals: (代號, 名稱, 股數, 均價, 現價, 市值, 未實現損益, 報酬率%, 已實現損益)
        stock_id = str(vals[0]).strip()
        self._show_position_detail(stock_id)

    def _show_position_detail(self, stock_id: str):
        """顯示指定股票的完整統計視窗（V0.9.4 phase2.3：可滾動 + 預估賣出成本）"""
        txs = self.portfolio.list_transactions()
        stock_txs = [t for t in txs if t.stock_id == stock_id]
        if not stock_txs:
            return

        stock_name = stock_txs[0].stock_name or stock_id
        buys = [t for t in stock_txs if t.action == "BUY"]
        sells = [t for t in stock_txs if t.action == "SELL"]

        # 計算
        total_fee = sum(t.fee for t in stock_txs)
        total_tax = sum(t.tax for t in stock_txs)
        total_shares = sum(t.shares for t in buys) - sum(t.shares for t in sells)
        buy_cost_excl_fee = sum(t.shares * t.price for t in buys)
        sell_net = sum(t.shares * t.price - t.fee - t.tax for t in sells)
        realized_pl = sell_net - buy_cost_excl_fee if sells else 0.0
        avg_cost = buy_cost_excl_fee / sum(t.shares for t in buys) if buys else 0.0
        cur_price = self._current_prices.get(stock_id, 0.0)
        cur_mv = total_shares * cur_price

        # 預估賣出（以現價）
        est_fee = max(20, cur_mv * 0.001425 * self.portfolio.broker_discount)
        est_tax = cur_mv * 0.003
        est_net = cur_mv - est_fee - est_tax
        unrealized_pl = (cur_price - avg_cost) * total_shares if total_shares > 0 else 0.0

        # 建立可滾動視窗
        win = tk.Toplevel(self)
        win.title(f"📊 {stock_id} {stock_name} — 統計明細")
        win.geometry("540x500")
        win.transient(self)

        # Canvas + Scrollbar
        canvas = tk.Canvas(win, highlightthickness=0, bg="#f5f5f5")
        vscroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        # 所有內容放在 content_frame 裡
        cf = tk.Frame(canvas, bg="#f5f5f5")
        canvas.create_window((0, 0), window=cf, anchor="nw")

        def on_frame_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        cf.bind("<Configure>", on_frame_config)

        # 工具函式
        def lbl(parent, text, font=("Segoe UI", 10), fg="#222", **kw):
            return tk.Label(parent, text=text, font=font, fg=fg, bg="#f5f5f5", **kw)

        def section_hdr(parent, text):
            hdr = tk.Frame(parent, bg="#0070c0", pady=3)
            hdr.pack(fill="x", padx=10, pady=(12, 4))
            tk.Label(hdr, text=text, font=("Segoe UI", 10, "bold"),
                    fg="white", bg="#0070c0").pack(anchor="w", padx=8)

        def stat(parent, label, value, color="black"):
            row = tk.Frame(parent, bg="#f5f5f5")
            row.pack(fill="x", padx=14)
            tk.Label(row, text=label, font=("Segoe UI", 10),
                    anchor="e", width=20, bg="#f5f5f5").pack(side="left")
            tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                    anchor="w", foreground=color, bg="#f5f5f5").pack(side="left", padx=(6, 0))

        # ── 抬頭 ──
        hdr_f = tk.Frame(cf, bg="#0055a5", pady=8)
        hdr_f.pack(fill="x")
        tk.Label(hdr_f, text=f"{stock_id}  {stock_name}",
                font=("Segoe UI", 13, "bold"), fg="white", bg="#0055a5").pack(pady=(0, 2))
        tk.Label(hdr_f, text=f"共 {len(stock_txs)} 筆交易（買入 {len(buys)} 筆 / 賣出 {len(sells)} 筆）",
                font=("Segoe UI", 9), fg="#cce0ff", bg="#0055a5").pack()

        # ── 持有概況 ──
        section_hdr(cf, "【持有概況】")
        stat(cf, "目前持有股數", f"{total_shares:,.0f} 股")
        stat(cf, "平均成本（不含費用）", f"{avg_cost:,.4f} 元")
        stat(cf, "目前現價", f"{cur_price:,.2f} 元")
        stat(cf, "市值", f"{cur_mv:,.2f} 元")
        stat(cf, "未實現損益", f"{unrealized_pl:+,.2f} 元",
             "#0a7d2c" if unrealized_pl >= 0 else "#c00000")

        # ── 預估賣出（以現價）──
        section_hdr(cf, "【預估賣出（以現價）】")
        stat(cf, "預估手續費", f"{est_fee:,.2f} 元（費率 {self.portfolio.broker_discount*0.1425:.4f}%）")
        stat(cf, "預估證交稅", f"{est_tax:,.2f} 元（0.3%）")
        stat(cf, "預估淨收入", f"{est_net:,.2f} 元",
             "#0a7d2c" if est_net >= cur_mv - cur_mv * 0.004425 else "#c00000")
        stat(cf, "含費總成本", f"{(total_fee + sum(t.shares*t.price+t.fee for t in buys)):,.2f} 元")

        # ── 費用累計 ──
        section_hdr(cf, "【費用累計】")
        stat(cf, "總手續費", f"{total_fee:,.2f} 元")
        stat(cf, "總證交稅", f"{total_tax:,.2f} 元")
        stat(cf, "總買入成本（含費）", f"{sum(t.shares*t.price+t.fee for t in buys):,.2f} 元")

        # ── 已實現損益 ──
        if sells:
            section_hdr(cf, "【已實現損益】")
            stat(cf, "總賣出淨收入", f"{sell_net:,.2f} 元")
            stat(cf, "含費總成本", f"{buy_cost_excl_fee + total_fee:,.2f} 元")
            stat(cf, "已實現損益（扣費稅）", f"{realized_pl:+,.2f} 元",
                 "#0a7d2c" if realized_pl >= 0 else "#c00000")

        # ── 交易明細 mini table ──
        section_hdr(cf, "【交易明細】")
        t_frame = tk.Frame(cf, bg="white")
        t_frame.pack(fill="both", expand=False, padx=10, pady=(4, 12))
        cols = ("日期", "買/賣", "股數", "價格", "手續費", "證交稅", "備註")
        mini = ttk.Treeview(t_frame, columns=cols, show="headings", height=8)
        for col, w in zip(cols, [90, 40, 65, 65, 60, 60, 90]):
            mini.heading(col, text=col)
            mini.column(col, width=w, anchor="e" if col not in ("日期","備註") else "w")
        mini.pack(side="left", fill="both", expand=True)
        ts = ttk.Scrollbar(t_frame, orient="vertical", command=mini.yview)
        mini.configure(yscrollcommand=ts.set)
        ts.pack(side="right", fill="y")
        for t in sorted(stock_txs, key=lambda x: x.trade_date):
            mini.insert("", "end", values=(
                t.trade_date,
                "買" if t.action == "BUY" else "賣",
                f"{t.shares:,.0f}",
                f"{t.price:,.2f}",
                f"{t.fee:,.2f}",
                f"{t.tax:,.2f}",
                t.note or "",
            ))

        # ── 關閉按鈕 ──
        tk.Frame(cf, bg="#f5f5f5", height=20).pack()  # bottom padding
        tk.Button(cf, text="關閉", font=("Segoe UI", 10),
                 command=win.destroy).pack(pady=(0, 16))

        # 啟動滾輪（Linux 用 MouseWheel）
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _refresh_portfolio_view(self):
        """重新查詢 DB，更新總覽 + 兩個 Treeview"""
        try:
            positions = self.portfolio.get_positions(self._current_prices)
            summary = self.portfolio.get_summary(self._current_prices)
            txs = self.portfolio.list_transactions()

            # 總覽（8 個 label）V0.9.4 phase2.3
            self._summary_labels["total_cost"].config(text=f"{summary.total_cost:,.0f}")
            self._summary_labels["total_market_value"].config(text=f"{summary.total_market_value:,.0f}")
            pl_color = "#0a7d2c" if summary.total_unrealized_pl >= 0 else "#c00000"
            self._summary_labels["total_unrealized_pl"].config(text=f"{summary.total_unrealized_pl:+,.0f}", foreground=pl_color)
            self._summary_labels["total_fee"].config(text=f"{summary.total_fee:,.0f}")
            self._summary_labels["total_tax"].config(text=f"{summary.total_tax:,.0f}")
            net_color = "#0a7d2c" if summary.net_realized_pl >= 0 else "#c00000"
            self._summary_labels["net_realized_pl"].config(text=f"{summary.net_realized_pl:+,.0f}", foreground=net_color)
            ret_color = "#0a7d2c" if summary.total_return_pct >= 0 else "#c00000"
            self._summary_labels["total_return_pct"].config(text=f"{summary.total_return_pct:+.2f}%", foreground=ret_color)
            pl_color2 = "#0a7d2c" if summary.total_pl >= 0 else "#c00000"
            self._summary_labels["total_pl"].config(text=f"{summary.total_pl:+,.0f}", foreground=pl_color2)

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
                    f"{t.tax:,.0f}",   # V0.9.4 phase2.3: 顯示證交稅（買入為 0）
                    t.note,
                ))

        except Exception as e:
            messagebox.showerror("Refresh 失敗", str(e))

    # ── V0.9.4 phase2.3: 萬年曆挑選日期 ──
    def _pick_date(self, win: tk.Toplevel, var: tk.StringVar, entry: ttk.Entry):
        """打開萬年曆，選中後把 YYYY-MM-DD 寫入 StringVar + Entry"""
        initial = var.get().strip()
        chosen = _CalendarDialog.pick(win, initial)
        if chosen:
            var.set(chosen)
            pass  # date written to var by var.set(chosen) above

    def _open_buy_dialog(self):
        """新增買入對話框（V0.9.4 phase2.3：支援股利配發 price=0、萬年曆選日期）"""
        win = tk.Toplevel(self)
        win.title("新增買入")
        win.geometry("460x420")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        e = ttk.Entry(win, textvariable=v, width=22)
        e.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        fields["stock_id"] = v

        # Row 1: 股票名稱（自動帶出，設為 readonly）
        ttk.Label(win, text="股票名稱", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="（輸入代號後自動帶出）")
        ttk.Label(win, textvariable=v, foreground="#555", font=("Segoe UI", 9)
                   ).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["stock_name"] = v

        # Row 2: 買入日期（entry + 萬年曆按鈕）V0.9.4 phase2.3
        ttk.Label(win, text="買入日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 買入股數
        ttk.Label(win, text="買入股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 買入價格（支援 price=0 股利配發）V0.9.4 phase2.3
        ttk.Label(win, text="買入價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        price_entry = ttk.Entry(win, textvariable=v, width=22)
        price_entry.grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估手續費 label（V0.9.4 phase2.3: 支援 price=0 股利）
        est_label = ttk.Label(win, text="預估手續費：—（股利配發請設 price=0，手續費為 0）",
                              foreground="#444", font=("Segoe UI", 9, "bold"))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # ── 股票代號失焦 → 自動抓現價 + 名稱 ──
        def on_stock_id_focusout(event=None):
            sid = fields["stock_id"].get().strip()
            if not sid or not sid.isdigit():
                return
            def worker():
                from portfolio import fetch_stock_info
                try:
                    info = fetch_stock_info(sid)
                except Exception as e:
                    info = {"ok": False, "error": str(e)}
                def update_ui():
                    if info.get("ok"):
                        fields["stock_name"].set(info.get("name", ""))
                        if info.get("price", 0) > 0 and fields["price"].get() in ("0", ""):
                            fields["price"].set(f"{info['price']:.2f}")
                        self._update_fee_estimate(fields, "BUY", est_label, win)
                        self.logger.log(f"📡 {sid} {info.get('name', '')} 現價 {info.get('price', 0):.2f}")
                    else:
                        self.logger.log(f"⚠️ {sid} 抓不到現價：{info.get('error', '')}")
                win.after(0, update_ui)
            threading.Thread(target=worker, daemon=True).start()

        # 綁定 FocusOut
        for child in win.grid_slaves():
            if isinstance(child, ttk.Entry) and child.grid_info().get("row") == 0:
                child.bind("<FocusOut>", on_stock_id_focusout)
                child.bind("<Return>", on_stock_id_focusout)
                break

        # 股數 / 價格改變 → 重算預估
        def on_change(*_):
            self._update_fee_estimate(fields, "BUY", est_label, win)
        for k in ("shares", "price"):
            fields[k].trace_add("write", on_change)

        def on_submit():
            try:
                self.portfolio.add_buy(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    stock_name=fields["stock_name"].get().strip(),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 買入新增成功：{fields['stock_id'].get()} {fields['stock_name'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

    def _open_sell_dialog(self):
        """新增賣出對話框（V0.9.4 phase2.3：萬年曆選日期、手續費+證交稅自動算）"""
        win = tk.Toplevel(self)
        win.title("新增賣出")
        win.geometry("460x400")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        e = ttk.Entry(win, textvariable=v, width=22)
        e.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        fields["stock_id"] = v

        # Row 1: 股票名稱
        ttk.Label(win, text="股票名稱", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="（輸入代號後自動帶出）")
        ttk.Label(win, textvariable=v, foreground="#555", font=("Segoe UI", 9)
                   ).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["stock_name"] = v

        # Row 2: 賣出日期（entry + 萬年曆按鈕）V0.9.4 phase2.3
        ttk.Label(win, text="賣出日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 賣出股數
        ttk.Label(win, text="賣出股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 賣出價格
        ttk.Label(win, text="賣出價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="0")
        ttk.Entry(win, textvariable=v, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value="")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估成本（手續費 + 證交稅）V0.9.4 phase2.3
        est_label = ttk.Label(win, text="預估成本：—（賣出需繳手續費 + 0.3% 證交稅）",
                              foreground="#444", font=("Segoe UI", 9, "bold"))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # ── 股票代號失焦 → 自動抓現價 + 名稱 ──
        def on_stock_id_focusout(event=None):
            sid = fields["stock_id"].get().strip()
            if not sid or not sid.isdigit():
                return
            def worker():
                from portfolio import fetch_stock_info
                try:
                    info = fetch_stock_info(sid)
                except Exception as e:
                    info = {"ok": False, "error": str(e)}
                def update_ui():
                    if info.get("ok"):
                        fields["stock_name"].set(info.get("name", ""))
                        if info.get("price", 0) > 0 and fields["price"].get() in ("0", ""):
                            fields["price"].set(f"{info['price']:.2f}")
                        self._update_fee_estimate(fields, "SELL", est_label, win)
                        self.logger.log(f"📡 {sid} {info.get('name', '')} 現價 {info.get('price', 0):.2f}")
                    else:
                        self.logger.log(f"⚠️ {sid} 抓不到現價：{info.get('error', '')}")
                win.after(0, update_ui)
            threading.Thread(target=worker, daemon=True).start()

        # 綁定 FocusOut
        for child in win.grid_slaves():
            if isinstance(child, ttk.Entry) and child.grid_info().get("row") == 0:
                child.bind("<FocusOut>", on_stock_id_focusout)
                child.bind("<Return>", on_stock_id_focusout)
                break

        # 股數 / 價格改變 → 重算預估
        def on_change(*_):
            self._update_fee_estimate(fields, "SELL", est_label, win)
        for k in ("shares", "price"):
            fields[k].trace_add("write", on_change)

        def on_submit():
            try:
                self.portfolio.add_sell(
                    stock_id=fields["stock_id"].get().strip(),
                    trade_date=fields["trade_date"].get().strip(),
                    shares=float(fields["shares"].get()),
                    price=float(fields["price"].get()),
                    note=fields["note"].get().strip(),
                )
                self.logger.log(f"✅ 賣出新增成功：{fields['stock_id'].get()}")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("新增失敗", str(e), parent=win)

        ttk.Button(win, text="確定", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

    def _update_fee_estimate(self, fields: Dict[str, tk.StringVar], action: str, label: ttk.Label, win: tk.Toplevel):
        """即時更新對話框的『預估手續費 / 成本』label（V0.9.4 phase2.3: 支援 price=0 股利配發）"""
        try:
            shares = float(fields["shares"].get() or 0)
            price = float(fields["price"].get() or 0)
            if shares <= 0:
                label.config(text="預估手續費：—（請輸入股數）")
                return
            if price == 0:
                # V0.9.4 phase2.3: 股利配發（price=0）時不收手續費
                if action == "BUY":
                    label.config(text="股利配發：手續費 0 元（無需填價格）")
                else:
                    label.config(text="預估成本：—（請輸入賣出價格）")
                return
            from portfolio import estimate_total_cost
            est = estimate_total_cost(action, shares, price, self.portfolio.broker_discount)
            if action == "BUY":
                label.config(text=f"預估手續費：{est['fee']:,.2f} 元（買入不收證交稅）")
            else:
                label.config(text=f"預估成本：手續費 {est['fee']:,.2f} + 證交稅 {est['tax']:,.2f} = 共 {est['total']:,.2f} 元")
        except (ValueError, tk.TclError):
            label.config(text="預估手續費：—")

    def _update_prices_dialog(self):
        """V0.9.4：批次從 TWSE 抓現價（可手動覆寫）"""
        positions = self.portfolio.get_positions()
        if not positions:
            messagebox.showinfo("無持倉", "目前沒有持倉股票可更新現價")
            return

        win = tk.Toplevel(self)
        win.title("更新現價（TWSE 自動抓）")
        win.geometry("420x460")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="從 TWSE / TPEx 抓取每檔現價（可手動修改）",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(win, text="按「自動抓 TWSE」按鈕一次抓全部，個別欄位可手動覆寫",
                  foreground="#666", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(0, 8))

        price_vars = {}
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=4)
        for p in positions:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{p.stock_id} {p.stock_name}", width=20, anchor="w").pack(side="left")
            cur = self._current_prices.get(p.stock_id, 0.0)
            v = tk.StringVar(value=f"{cur:.2f}" if cur > 0 else "")
            ttk.Entry(row, textvariable=v, width=14).pack(side="right")
            price_vars[p.stock_id] = v

        def fetch_all():
            stock_ids = list(price_vars.keys())
            def worker():
                from portfolio import fetch_prices_batch
                try:
                    results = fetch_prices_batch(stock_ids)
                except Exception as e:
                    win.after(0, lambda: messagebox.showerror("抓取失敗", str(e), parent=win))
                    return
                def apply():
                    for sid, info in results.items():
                        if info.get("ok") and info.get("price", 0) > 0:
                            price_vars[sid].set(f"{info['price']:.2f}")
                            if info.get("name"):
                                self._backfill_stock_name(sid, info["name"])
                    self.logger.log(f"📡 自動抓取完成：{sum(1 for v in results.values() if v.get('ok'))}/{len(results)} 檔")
                win.after(0, apply)
            threading.Thread(target=worker, daemon=True).start()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="📡 自動抓 TWSE", command=fetch_all).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="確定", command=lambda: apply_and_close()).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="取消", command=win.destroy).pack(side="right", padx=2)

        def apply_and_close():
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

    # V0.9.4 phase2.3: 編輯交易明細
    def _open_edit_tx_dialog(self):
        """編輯選中的交易（支援 BUY/SELL 修改，fee/tax 自動重算）V0.9.4 phase2.3 修復：action 可編輯"""
        sel = self._tx_tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在「交易明細」表格中選取要編輯的紀錄")
            return
        item = sel[0]
        vals = self._tx_tree.item(item, "values")
        tx_id = int(vals[0])
        tx = self.portfolio.get_transaction(tx_id)
        if not tx:
            messagebox.showerror("錯誤", "找不到這筆交易，請重新整理後再試")
            return

        win = tk.Toplevel(self)
        win.title(f"編輯交易 #{tx_id}")
        win.geometry("460x440")
        win.transient(self)
        win.grab_set()

        fields = {}

        # Row 0: 股票代號（readonly）
        ttk.Label(win, text="股票代號", width=10, anchor="e").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Label(win, text=f"{tx.stock_id} {tx.stock_name}", foreground="#555", font=("Segoe UI", 9, "bold")
                  ).grid(row=0, column=1, padx=8, pady=4, sticky="w")

        # Row 1: 買/賣（可切換 BUY↔SELL）V0.9.4 phase2.3 fix: 改為 Combobox
        ttk.Label(win, text="買/賣", width=10, anchor="e").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=tx.action)  # "BUY" or "SELL"
        action_cbox = ttk.Combobox(win, textvariable=v, values=["BUY", "SELL"],
                                   state="readonly", width=8)
        action_cbox.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        fields["action"] = v

        # Row 2: 交易日期（entry + 萬年曆按鈕）
        ttk.Label(win, text="交易日期", width=10, anchor="e").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        date_frame = ttk.Frame(win)
        date_frame.grid(row=2, column=1, padx=8, pady=4, sticky="w")
        v = tk.StringVar(value=tx.trade_date)
        date_entry = ttk.Entry(date_frame, textvariable=v, width=14)
        date_entry.pack(side="left")
        ttk.Button(date_frame, text="📅", width=3, padding="2px",
                   command=lambda v=v, de=date_entry: self._pick_date(win, v, de)
                   ).pack(side="left", padx=(4, 0))
        fields["trade_date"] = v

        # Row 3: 股數
        ttk.Label(win, text="股數", width=10, anchor="e").grid(row=3, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=str(tx.shares))
        ttk.Entry(win, textvariable=v, width=22).grid(row=3, column=1, padx=8, pady=4, sticky="w")
        fields["shares"] = v

        # Row 4: 價格（支援 price=0 股利配發 BUY）
        ttk.Label(win, text="價格", width=10, anchor="e").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=str(tx.price))
        ttk.Entry(win, textvariable=v, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        fields["price"] = v

        # Row 5: 備註
        ttk.Label(win, text="備註", width=10, anchor="e").grid(row=5, column=0, padx=8, pady=4, sticky="e")
        v = tk.StringVar(value=tx.note or "")
        ttk.Entry(win, textvariable=v, width=22).grid(row=5, column=1, padx=8, pady=4, sticky="w")
        fields["note"] = v

        # Row 6: 預估訊息 label
        est_label = ttk.Label(win, text="（ fee / 證交稅將自動重算）",
                              foreground="#444", font=("Segoe UI", 9))
        est_label.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        # fee/tax 自動重算（當 action / shares / price 改變時）V0.9.4 phase2.3
        def _recalc(action, shares, price, label):
            try:
                if shares <= 0:
                    label.config(text="（ fee / 證交稅將自動重算）")
                    return
                if price == 0 and action == "BUY":
                    label.config(text="股利配發：手續費 0 元（fee/tax 將自動更新）")
                    return
                if price <= 0:
                    label.config(text="（ fee / 證交稅將自動重算）")
                    return
                from portfolio import estimate_total_cost
                est = estimate_total_cost(action, shares, price, self.portfolio.broker_discount)
                if action == "BUY":
                    label.config(text=f"預估手續費：{est['fee']:,.2f} 元（fee/tax 將自動更新）")
                else:
                    label.config(text=f"預估成本：手續費 {est['fee']:,.2f} + 證交稅 {est['tax']:,.2f} = 共 {est['total']:,.2f} 元")
            except ValueError:
                label.config(text="（ fee / 證交稅將自動重算）")

        def on_change(*_):
            action = fields["action"].get()
            try:
                shares = float(fields["shares"].get() or 0)
                price = float(fields["price"].get() or 0)
            except ValueError:
                shares, price = 0.0, 0.0
            _recalc(action, shares, price, est_label)

        for k in ("action", "shares", "price"):
            fields[k].trace_add("write", on_change)
        on_change()  # 初始顯示一次

        def on_submit():
            try:
                tx.action = fields["action"].get()  # 可能 BUY↔SELL
                tx.trade_date = fields["trade_date"].get().strip()
                tx.shares = float(fields["shares"].get())
                tx.price = float(fields["price"].get())
                tx.note = fields["note"].get().strip()
                # fee / tax 自動重算（以新的 action 為準）
                if tx.action == "BUY":
                    from portfolio import calc_fee
                    tx.fee = calc_fee(tx.shares, tx.price, self.portfolio.broker_discount)
                    tx.tax = 0.0
                else:
                    from portfolio import calc_fee, calc_tax
                    tx.fee = calc_fee(tx.shares, tx.price, self.portfolio.broker_discount)
                    tx.tax = calc_tax(tx.shares, tx.price)
                self.portfolio.update_transaction(tx)
                self.logger.log(f"✏️ 交易 #{tx_id} 已更新（{tx.action}）")
                win.destroy()
                self._refresh_portfolio_view()
            except Exception as e:
                messagebox.showerror("更新失敗", str(e), parent=win)

        ttk.Button(win, text="儲存", command=on_submit).grid(row=7, column=0, padx=8, pady=12, sticky="e")
        ttk.Button(win, text="取消", command=win.destroy).grid(row=7, column=1, padx=8, pady=12, sticky="w")

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
        self.console.insert("end", "🚀 StockTool v0.9.5-alpha 開始執行\n")
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
