"""
檔名：StockTool.py

版本：v0.8.1-GUI (Excel Selection + History Cache + Performance Breakdown)
最後更新：2026-05-20 (Asia/Taipei)

------------------------------------------------------------
【程式整體流程（Core Flow）】

1) 下載 / 讀取資料（含 cache）：
   - 股價（TWSE + TPEX）
   - 月營收（mopsfin）
   - EPS（mopsfin）

2) 合併基本面資料 → 建立 df_sel：
   - 營收 YoY
   - EPS YoY
   - PE / 殖利率
   - Score（排序用）

3) 選股來源（v0.8.1）：
   - 模式 A：Score 排序 → 取 TopN（原本）
   - 模式 B：Excel 指定股票清單 ✅（新增）

4) 抓歷史資料（History Cache）：
   - 每檔股票獨立 cache（60 個月初始化）
   - 每日只更新當月資料（增量更新）
   - 避免重抓歷史（效能大幅提升）

5) 技術分析（calc_tech_indicators）：
   - MA5 / MA20
   - RSI / MACD
   - 三段式買點：
        ① 超跌（RSI < rsi_oversold）
        ② 轉強（RSI 或 MACD）
        ③ 趨勢確認（MA + Volume）

6) 回測（TopK 投組）：
   - 等權配置（TopK）
   - 僅空手時建倉
   - 事件型出場：
        StopLoss / TakeProfit / RSI Exit / Time Exit

7) KPI 計算：
   - Signal-level（單筆事件）
   - Portfolio-level（投組）
   - 年度績效（v0.8.0新增）

8) Excel 輸出：
   - 全市場
   - 強勢股
   - Top10
   - 技術分析
   - 技術買點
   - 投組回測
   - 年度績效 ✅

------------------------------------------------------------
【策略核心（Strategy Logic）】

✔ 進場：
   - 三段式：回檔 → 轉強 → 趨勢
   - 本質：Trend-following + Pullback

✔ 投組：
   - TopK 等權（預設 K=3，可調整）

✔ 出場：
   - StopLoss
   - TakeProfit
   - RSI Exit
   - Time Exit（HOLD天數）

✔ Gate（可開關）：
   - 營收YoY > min_rev_yoy
   - EPSYoY > min_eps_yoy
   - EPSYoY NaN 可選放行

✔ 成本：
   - round-trip cost（預設 0.4%）

------------------------------------------------------------
【v0.8.1 新增功能】

1. Excel 選股模式 ✅
   - 可切換：
        □ 使用 Score 自動選股
        ■ 使用 Excel 指定股票清單
   - Excel 格式：
        股票代號 或 code

   用途：
   - 主觀選股回測
   - ETF 成分股測試
   - 主題型策略（AI / 高股息 / 半導體）

------------------------------------------------------------
【v0.8.0 新功能】

1. History Cache：
   - 每檔股票獨立 cache
   - 初始化抓 60 個月
   - 每日只更新當月
   - merge + 去重

2. Performance Breakdown：
   - 分年績效分析
   - 觀察策略在不同市場環境表現

------------------------------------------------------------
【v0.7.5 Data Cache】

- price / revenue / eps 分離 cache
- 每日更新一次
- 降低 API call

------------------------------------------------------------
【v0.7.4 Cache Layer】

- get_or_fetch 控制下載
- 當日資料→直接讀 cache
- 支援離線回測

------------------------------------------------------------
【重要工程設計】

✅ 分層設計

- Data Layer（cache）
- Strategy Layer（tech_months）
- Portfolio Layer（TopK）

✅ df_sel 與 df_out 分離
- df_sel：回測用（不可動）
- df_out：輸出用（排序 / 欄位調整）

✅ 技術指標只影響策略，不影響資料層

------------------------------------------------------------
【已知特性】

✔ 策略類型：
   - Trend-following + Pullback
   - 投組 alpha（非單筆交易 alpha）

✔ 風險特性：
   - 報酬集中於趨勢行情
   - 震盪期可能下降

------------------------------------------------------------
【未來可擴充方向】

- Excel 權重投組（portfolio allocation）
- Equity Curve（資金曲線）
- Drawdown 曲線
- Walk-forward analysis
- 參數 grid search

------------------------------------------------------------
【依賴套件】

- tkinter（GUI）
- pandas
- requests
- openpyxl

------------------------------------------------------------
"""


from __future__ import annotations

import io
import os
import time
import queue
import threading
import warnings
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional, List

import pandas as pd
import requests

import tkinter as tk
from tkinter import ttk, messagebox

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

warnings.filterwarnings("ignore")


# ==========================================================
# 0) Config（v0.7.3 Option A 預設）
# ==========================================================

HISTORY_DIR = "cache/history"
HISTORY_MONTHS = 60

@dataclass
class StrategyConfig:
    # universe / data
    top_n_for_tech: int = 28
    tech_months: int = 24
    timeout: int = 30
    verify_ssl: bool = False

    # ✅ v0.8.1 Excel stock list
    use_excel_stock_list: bool = False
    excel_stock_file: str = "stock_list.xlsx"

    # TWSE fetch stability
    twse_retries: int = 3
    twse_backoff: float = 0.8
    twse_sleep: float = 0.12

    # portfolio
    topk: int = 3                      # C：TopK 等權
    hold_days: int = 5
    roundtrip_cost_pct: float = 0.004  # 0.4%

    # event-driven exit (Option A defaults)
    stop_loss: float = -0.03
    take_profit: float = 0.03         # Option A：TP 5%
    exit_rsi: int = 60                 # Option A：RSI 62

    # fundamental gate
    use_gate: bool = True
    min_rev_yoy: float = 2
    min_eps_yoy: float = 2
    allow_eps_yoy_nan: bool = True     # 避免 EPSYoY 缺值造成 Trades=0

    # --- 風險指標參數（Sharpe / Sortino 用）---
    risk_free_annual: float = 0.0
    mar_annual: float = 0.0
    trading_days: int = 252

    # signal params (keep close to your stable settings)
    rsi_oversold: int = 35
    oversold_lookback: int = 10
    rsi_recover: int = 40
    rsi_aggressive: int = 45
    use_aggressive_signal: bool = True

    require_trend_filter: bool = True
    ma_slope_days: int = 3
    ma20_tolerance: float = 0.01
    require_volume_filter: bool = True

    # --- 強勢股（報表用；避免 NameError；也可讓你在 GUI 調整）---
    strong_revenue_yoy: float = 10.0
    strong_pe_max: float = 30.0
    strong_price_min: float = 10.0

    # output
    out_file_prefix: str = "選股報表"


# ==========================================================
# 1) Logger（把訊息送進 GUI Console）
# ==========================================================
class GuiLogger:
    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.q.put(f"[{ts}] {msg}")


# ==========================================================
# 2) Session（requests）
# ==========================================================
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.7.3-GUI",
        "Accept": "application/json,text/plain,*/*"
    })
    return s


# ==========================================================
# 3) Utility functions
# ==========================================================

# ==========================================================
# Cache System（只下載一次資料）
# ==========================================================

def find_col(cols, keywords):
    """
    在欄位名稱中搜尋符合關鍵字的欄位名稱

    例如：
    find_col(df.columns, ["成交量", "Volume"])
    """
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


# ✅ ✅ ✅ 最後是 get_or_fetch
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




def get_or_fetch(name: str, fetch_func, logger: GuiLogger):
    """
    通用 cache 控制器（支援多資料種類）

    name:
        price / revenue / eps / universe
    """
    file_path = get_cache_file(name)
    today = datetime.today().strftime("%Y-%m-%d")

    # 沒資料
    if not os.path.exists(file_path):
        logger.log(f"📥 [{name}] 無快取 → 下載資料")
        df = fetch_func()
        save_cache(file_path, df)
        return df

    # 讀資料
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
    """
    報表格式統一：
    - 股票代號第1欄、公司名稱_來源第2欄
    - 依股票代號升冪排序（只輸出用，避免影響選股/回測）
    """
    if df is None or df.empty:
        return df
    if "股票代號" in df.columns:
        df["股票代號"] = df["股票代號"].astype(str).str.strip()
    if "股票代號" in df.columns and "公司名稱_來源" in df.columns:
        cols = ["股票代號", "公司名稱_來源"] + [c for c in df.columns if c not in ["股票代號", "公司名稱_來源"]]
        df = df[cols]
    if sort_by_code and "股票代號" in df.columns:
        df = df.sort_values("股票代號", ascending=True)
    return df.reset_index(drop=True)

# ==========================================================
# ✅ v0.8.1 Excel Stock List Loader
# ==========================================================

def load_stock_list_from_excel(file_path):
    """
    從 Excel 讀指定股票清單
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到 Excel: {file_path}")

    df = pd.read_excel(file_path)

    col = find_col(df.columns, ["股票", "code"])

    if col is None:
        raise ValueError("Excel 必須包含 '股票代號' 或 'code' 欄位")

    codes = df[col].astype(str).str.strip().tolist()

    return codes

# ==========================================================
# History Cache System (v0.8.0)
# ==========================================================

def get_history_file(stock_id):
    return f"{HISTORY_DIR}/{stock_id}.xlsx"


def init_stock_history(session, cfg, stock_id):
    months = month_starts_back(HISTORY_MONTHS)

    frames = []
    for m in months:
        df = fetch_twse_stock_day_month(session, cfg, stock_id, m)
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    df_all = pd.concat(frames)
    df_all = df_all.drop_duplicates(subset=["Date"])
    df_all = df_all.sort_values("Date")

    return df_all


def update_stock_history(session, cfg, stock_id, df_old):
    today_month = datetime.today().strftime("%Y%m01")

    df_new = fetch_twse_stock_day_month(session, cfg, stock_id, today_month)

    if df_new is None or df_new.empty:
        return df_old

    df_all = pd.concat([df_old, df_new])
    df_all = df_all.drop_duplicates(subset=["Date"])
    df_all = df_all.sort_values("Date")

    return df_all


def get_stock_history(session, cfg, stock_id, logger):

    os.makedirs(HISTORY_DIR, exist_ok=True)
    file_path = get_history_file(stock_id)

    # ✅ 沒資料
    if not os.path.exists(file_path):
        logger.log(f"📥 [{stock_id}] 初始化 60個月歷史資料")
        df = init_stock_history(session, cfg, stock_id)
        save_cache(file_path, df)
        return df

    # ✅ 有資料 → 更新
    df_old, _ = load_cache(file_path)

    logger.log(f"🔄 [{stock_id}] 更新當月資料")
    df_new = update_stock_history(session, cfg, stock_id, df_old)

    save_cache(file_path, df_new)

    return df_new

def fetch_csv_requests(session: requests.Session, url: str, cfg: StrategyConfig, encodings=("utf-8-sig", "utf-8")) -> pd.DataFrame:
    r = session.get(url, timeout=cfg.timeout, verify=cfg.verify_ssl)
    r.raise_for_status()
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"讀取失敗：{url}，最後錯誤：{last_err}")


# ==========================================================
# 4) Data fetchers (prices/revenue/eps)
# ==========================================================
def fetch_prices(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

    twse = pd.DataFrame(session.get(twse_url, timeout=cfg.timeout).json())
    tpex = pd.DataFrame(session.get(tpex_url, timeout=cfg.timeout).json())

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

    price = pd.concat(
        [twse[["股票代號", "公司名稱_來源", "股價", "漲跌"]],
         tpex[["股票代號", "公司名稱_來源", "股價", "漲跌"]]],
        ignore_index=True
    )

    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    price = price.drop_duplicates("股票代號").reset_index(drop=True)
    return price

def fetch_prices_wrapper(session, cfg, logger):
    """
    包一層讓 cache 可以呼叫
    """
    return fetch_prices(session, cfg)



def fetch_revenue_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv",
    ]
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
    urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv",
    ]
    eps = pd.concat([fetch_csv_requests(session, u, cfg) for u in urls], ignore_index=True)

    code_col = find_col(eps.columns, ["公司代號"])
    year_col = find_col(eps.columns, ["年度"])
    q_col = find_col(eps.columns, ["季別"])
    eps_col = find_col(eps.columns, ["基本每股盈餘", "每股盈餘"])

    if code_col is None or year_col is None or q_col is None or eps_col is None:
        raise RuntimeError(f"EPS 欄位無法識別：{eps.columns}")

    eps = eps.rename(columns={code_col: "股票代號", year_col: "年度", q_col: "季別", eps_col: "EPS"})
    eps["股票代號"] = eps["股票代號"].astype(str).str.strip()
    eps["年度"] = pd.to_numeric(eps["年度"], errors="coerce")
    eps["季別"] = pd.to_numeric(eps["季別"], errors="coerce")
    eps["EPS"] = pd.to_numeric(eps["EPS"], errors="coerce")

    latest_year = eps["年度"].max()
    latest_q = eps.loc[eps["年度"] == latest_year, "季別"].max()

    #cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    #cur = cur.rename(columns={"EPS": "EPS本期"})

    #prev = eps[(eps["年度"] == latest_year - 1) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    #prev = prev.rename(columns={"EPS": "EPS去年"})

    # ✅ v0.8.2：改成「累計 EPS YoY」

    # 今年累計 EPS（Q1~Qn）
    cur = eps[eps["年度"] == latest_year].copy()
    cur = cur[cur["季別"] <= latest_q]
    cur = cur.groupby("股票代號")["EPS"].sum().reset_index()
    cur = cur.rename(columns={"EPS": "EPS本期"})

    # 去年同期累計 EPS
    prev = eps[eps["年度"] == latest_year - 1].copy()
    prev = prev[prev["季別"] <= latest_q]
    prev = prev.groupby("股票代號")["EPS"].sum().reset_index()
    prev = prev.rename(columns={"EPS": "EPS去年"})

    out = cur.merge(prev, on="股票代號", how="left")
    out["EPSYoY_raw"] = (out["EPS本期"] - out["EPS去年"]) / out["EPS去年"]
    out["EPSYoY_顯示(%)"] = (out["EPSYoY_raw"] * 100).replace([float("inf"), -float("inf")], 0).fillna(0)

    #out["EPS季別"] = f"{int(latest_year)}Q{int(latest_q)}"
    out["EPS期間"] = f"{int(latest_year)} Q1~Q{int(latest_q)}"

#    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates("股票代號").reset_index(drop=True)
    cols = ["股票代號", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]

    # ✅ 動態加入存在欄位
    final_cols = []
    for c in ["股票代號", "EPS期間", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]:
        if c in out.columns:
            final_cols.append(c)

    return out[final_cols].drop_duplicates("股票代號").reset_index(drop=True)

# ==========================================================
# 15) TWSE STOCK_DAY fetch + indicators + backtests + Excel + GUI
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
            if js is None:
                raise RuntimeError("Non-JSON response")

            if js.get("stat") != "OK" or "data" not in js:
                empty_df = pd.DataFrame()
                empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
                return pd.DataFrame()

            fields = js.get("fields", [])
            data = js.get("data", [])
            if not fields or not data:
                empty_df = pd.DataFrame()
                empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
                return pd.DataFrame()

            dfm = pd.DataFrame(data, columns=fields)

            date_col = find_col(dfm.columns, ["日期"])
            vol_col = find_col(dfm.columns, ["成交股數"])
            open_col = find_col(dfm.columns, ["開盤價"])
            high_col = find_col(dfm.columns, ["最高價"])
            low_col = find_col(dfm.columns, ["最低價"])
            close_col = find_col(dfm.columns, ["收盤價"])
            if date_col is None or close_col is None:
                empty_df = pd.DataFrame()
                empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
                return pd.DataFrame()

            rename_map = {date_col: "Date_roc", open_col: "Open", high_col: "High", low_col: "Low", close_col: "Close"}
            if vol_col:
                rename_map[vol_col] = "Volume"
            dfm = dfm.rename(columns=rename_map)

            dfm["Date"] = dfm["Date_roc"].apply(roc_to_ad)
            dfm["Date"] = pd.to_datetime(dfm["Date"])
            dfm["股票代號"] = str(stock_no).strip()

            for c in ["Open", "High", "Low", "Close"]:
                if c in dfm.columns:
                    dfm[c] = to_num_series(dfm[c])
            if "Volume" in dfm.columns:
                dfm["Volume"] = to_num_series(dfm["Volume"])
            else:
                dfm["Volume"] = pd.NA

            dfm = dfm.dropna(subset=["Date", "Close"]).copy()
            return dfm[["Date", "股票代號", "Open", "High", "Low", "Close", "Volume"]].copy()

        except Exception:
            if attempt == cfg.twse_retries:
                empty_df = pd.DataFrame()
                empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
                return pd.DataFrame()

            time.sleep(cfg.twse_backoff * attempt)

    empty_df = pd.DataFrame()
    empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
    return pd.DataFrame()


def fetch_twse_history(session: requests.Session, cfg: StrategyConfig, codes: List[str], logger: GuiLogger) -> pd.DataFrame:
    """
    v0.8.0：改為使用 History Cache（每檔股票）
    """

    hist_list = []

    for code in codes:
        try:
            df = get_stock_history(session, cfg, code, logger)
            if df is not None and not df.empty:
                df["股票代號"] = code
                hist_list.append(df)
        except Exception as e:
            logger.log(f"❌ [{code}] 歷史資料錯誤: {e}")

    if not hist_list:
        return pd.DataFrame()

    return pd.concat(hist_list, ignore_index=True)
def calc_tech_indicators(cfg: StrategyConfig, df_hist: pd.DataFrame) -> pd.DataFrame:
    df_hist = df_hist.sort_values("Date").copy()

    # ==========================================================
    # ✅ v0.8.0：依 tech_months 限制回測區間
    # ==========================================================
    if cfg.tech_months is not None:
        cutoff_date = datetime.today() - pd.DateOffset(months=cfg.tech_months)
        df_hist = df_hist[df_hist["Date"] >= cutoff_date]

    df_hist["MA5"] = df_hist["Close"].rolling(5).mean()
    df_hist["MA20"] = df_hist["Close"].rolling(20).mean()
    df_hist["VolMA20"] = df_hist["Volume"].rolling(20).mean()

    # RSI(14)
    delta = df_hist["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df_hist["RSI"] = 100 - (100 / (1 + rs))

    # MACD(12,26,9)
    ema12 = df_hist["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df_hist["Close"].ewm(span=26, adjust=False).mean()
    df_hist["MACD"] = ema12 - ema26
    df_hist["MACD_signal"] = df_hist["MACD"].ewm(span=9, adjust=False).mean()
    df_hist["MACD_hist"] = df_hist["MACD"] - df_hist["MACD_signal"]

    # 三段式買點
    oversold = df_hist["RSI"] < cfg.rsi_oversold
    oversold_recent = oversold.rolling(cfg.oversold_lookback).max().shift(1).fillna(0).astype(bool)

    recover_level = cfg.rsi_aggressive if cfg.use_aggressive_signal else cfg.rsi_recover
    rsi_cross_up = (df_hist["RSI"] >= recover_level) & (df_hist["RSI"].shift(1) < recover_level)
    macd_hist_turn = (df_hist["MACD_hist"] > 0) & (df_hist["MACD_hist"].shift(1) <= 0)
    turn_strong = rsi_cross_up | macd_hist_turn

    ma20_slope = df_hist["MA20"] - df_hist["MA20"].shift(cfg.ma_slope_days)
    trend_ok = (df_hist["Close"] >= df_hist["MA20"] * (1 - cfg.ma20_tolerance)) & (ma20_slope > 0)
    volume_ok = (df_hist["Volume"] >= df_hist["VolMA20"]*1.5)

    buy = oversold_recent & turn_strong
    if cfg.require_trend_filter:
        buy = buy & trend_ok
    if cfg.require_volume_filter:
        buy = buy & volume_ok

    # ✅ 新增這行（關鍵）
    #buy = buy & (df_hist["RSI"] > 45)

    df_hist["買點"] = buy
    df_hist["訊號型態"] = "三段式_B(折衷)"

    df_hist["Ret_1D_past(%)"] = df_hist["Close"].pct_change(1) * 100
    df_hist["Ret_5D_past(%)"] = df_hist["Close"].pct_change(5) * 100

    return df_hist


def run_tech(cfg: StrategyConfig, session: requests.Session, codes: List[str], logger: GuiLogger) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hist = fetch_twse_history(session, cfg, codes, logger)
    if hist.empty:
        empty_df = pd.DataFrame()
        empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
        return pd.DataFrame()

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_tech_indicators(cfg, g)
        g2["股票代號"] = str(code).strip()
        parts.append(g2)

    tech_all = pd.concat(parts, ignore_index=True)
    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()

    return tech_all, tech_today, buy_today


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
        empty_df = pd.DataFrame()
        empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
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
        empty_df = pd.DataFrame()
        empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
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
    """
    Gate：營收YoY > 0 且 EPSYoY > 0（缺值可放行）
    """
    code = df_sel["股票代號"].astype(str).str.strip()
    cond_rev = df_sel["營收YoY(%)"].fillna(0) > cfg.min_rev_yoy
    if cfg.allow_eps_yoy_nan:
        cond_eps = (df_sel["EPSYoY_raw"].fillna(0) > cfg.min_eps_yoy) | (df_sel["EPSYoY_raw"].isna())
    else:
        cond_eps = (df_sel["EPSYoY_raw"].fillna(0) > cfg.min_eps_yoy)
    gate = (cond_rev & cond_eps).astype(bool)
    return dict(zip(code, gate))

def portfolio_backtest_topk_event(cfg: StrategyConfig, tech_all: pd.DataFrame, score_map: dict, gate_map: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
#def portfolio_backtest_topk_event(cfg: StrategyConfig, tech_all: pd.DataFrame, score_map: dict, gate_map: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    TopK 等權投組（僅空手時建倉）
    - 當日買點候選 →（可套 Gate）→ 挑 Score 前 K 檔等權進場
    - 每持倉獨立事件型出場
    """
    if tech_all is None or tech_all.empty:
        empty_df = pd.DataFrame()
        empty_reason = pd.DataFrame(columns=["出場原因", "次數", "比例(%)"])
        return pd.DataFrame()

    df = tech_all[["Date", "股票代號", "Close", "買點", "RSI"]].copy()
    df = df.dropna(subset=["Date", "Close"])
    df["股票代號"] = df["股票代號"].astype(str).str.strip()

    # 修正 score_map key（避免映射失敗）
    score_map = {str(k).strip(): v for k, v in score_map.items()}
    df["Score"] = df["股票代號"].map(score_map).fillna(-1e18)

    by_code = {c: g.sort_values("Date").reset_index(drop=True) for c, g in df.groupby("股票代號")}
    all_dates = sorted(df["Date"].unique())

    cash = 1.0
    positions = {}  # code -> dict(shares, entry_price, entry_date, entry_idx)
    equity_rows = []
    trade_rows = []

    entry_cost = cfg.roundtrip_cost_pct / 2
    exit_cost = cfg.roundtrip_cost_pct / 2

    for d in all_dates:
        d = pd.to_datetime(d)

        # --- 出場（先處理）---
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

            proceeds = shares * px
            proceeds *= (1.0 - exit_cost)
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

        # --- 進場（僅空手時）---
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

        # --- daily equity ---
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

    # ===== 出場原因統計 =====
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

# ==========================================================
# Performance Breakdown (v0.8.0)
# ==========================================================

def performance_by_year(trades_df):
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()

    df = trades_df.copy()
    #df["year"] = pd.to_datetime(df["entry_date"]).dt.year
    # ✅ 自動找進場日期欄位（防止欄位名稱不同）
    date_col = find_col(df.columns, ["entry", "進場", "買進", "date"])

    if date_col is None:
        raise ValueError("找不到進場日期欄位（entry_date / 進場日 / 買進日）")

    df["year"] = pd.to_datetime(df[date_col]).dt.year

    out = []

    for y, g in df.groupby("year"):
        #returns = g["return"]
        # ✅ 自動找報酬欄位（防欄位名稱不同）
        ret_col = find_col(g.columns, ["return", "報酬", "損益", "ret", "%"])

        if ret_col is None:
            raise ValueError("找不到報酬欄位（return / 報酬 / 損益）")

        returns = g[ret_col]

        total = len(g)
        win_rate = (returns > 0).mean() * 100
        avg_ret = returns.mean() * 100
        pf = profit_factor(returns)

        out.append({
            "year": y,
            "trades": total,
            "win_rate(%)": round(win_rate, 2),
            "avg_return(%)": round(avg_ret, 2),
            "profit_factor": round(pf, 2) if pf else None
        })

    return pd.DataFrame(out).sort_values("year")


# ==========================================================
# 16) Excel 美化（不再有 wscell）
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
    """✅ 正確：ws[header_row]"""
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
    ws.conditional_formatting.add(
        rng,
        CellIsRule(operator="equal", formula=["TRUE"],
                   fill=PatternFill("solid", fgColor="FFF2CC"))
    )


# ==========================================================
# 17) Pipeline（供 GUI 呼叫）
# ==========================================================
def run_pipeline(cfg: StrategyConfig, logger: GuiLogger):
    """
    GUI 入口：執行完整策略流程，並把 log 寫進 GUI console
    """
    s = build_session()
    #logger.log("1) 下載股價（TWSE+TPEX）...")
    #price = fetch_prices(s, cfg)
    #price = get_or_fetch(lambda: fetch_prices_wrapper(s, cfg, logger), logger)

    logger.log("1) 取得股價資料...")
    price = get_or_fetch("price", lambda: fetch_prices_wrapper(s, cfg, logger), logger)

    logger.log("2) 取得月營收...")
    revenue = get_or_fetch("revenue", lambda: fetch_revenue_latest(s, cfg), logger)

    logger.log("3) 取得 EPS...")
    eps = get_or_fetch("eps", lambda: fetch_eps_latest(s, cfg), logger)


    logger.log("2) 下載最新月營收（mopsfin L+O；暫時跳過 SSL 驗證）...")
    rev_latest = fetch_revenue_latest(s, cfg)

    logger.log("3) 下載最新EPS（mopsfin L+O；暫時跳過 SSL 驗證）...")
    eps_latest = fetch_eps_latest(s, cfg)

    logger.log("4) 合併基本面資料...")
    df_sel = price.merge(rev_latest, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_latest, on="股票代號", how="left")
    df_sel["股票代號"] = df_sel["股票代號"].astype(str).str.strip()

    # 基本面衍生 + Score（與你既有邏輯一致）
    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]
    df_sel["Score"] = (
        df_sel["營收YoY(%)"].fillna(0) * 0.35 +
        (df_sel["EPSYoY_raw"].fillna(0) * 100) * 0.35 +
        df_sel["殖利率(估)"].fillna(0) * 100 * 0.20 -
        df_sel["PE"].fillna(0) * 0.05
    )
    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

    # Gate map
    gate_map = build_gate_map(cfg, df_sel)

    # 表格用
    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > cfg.strong_revenue_yoy) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < cfg.strong_pe_max) &
        (df_sel["股價"] > cfg.strong_price_min)
        ].copy()
    top10_sel = df_sel.head(10).copy()

    logger.log(f"5) 抓歷史日K（TWSE STOCK_DAY）Top{cfg.top_n_for_tech}（不使用Yahoo）...")

    # ==========================================================
    # ✅ v0.8.1 選股來源切換（最重要）
    # ==========================================================

    if cfg.use_excel_stock_list:
        logger.log("📂 使用 Excel 指定股票清單")

        try:
            tech_codes = load_stock_list_from_excel(cfg.excel_stock_file)
        except Exception as e:
            logger.log(f"❌ Excel 選股失敗：{e}")
            return
    else:
        tech_codes = df_sel.head(cfg.top_n_for_tech)["股票代號"].dropna().astype(str).str.strip().tolist()

    tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger)

    # KPI
    sig_summary = signal_level_backtest_event(cfg, tech_all)
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi, reason_stats = portfolio_backtest_topk_event(cfg, tech_all, score_map, gate_map)

    # ==========================================================
    # ✅ v0.8.0 分年績效分析
    # ==========================================================

    try:
        yearly_perf = performance_by_year(trades)
        logger.log("✅ 年度績效分析：")
        logger.log(yearly_perf.to_string(index=False))
    except Exception as e:
        logger.log(f"⚠️ 年度績效分析失敗：{e}")
        yearly_perf = pd.DataFrame()

    # ===== output tables =====
    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    df_out_all = format_for_output(df_sel.copy(), sort_by_code=True)
    strong_out = format_for_output(strong_sel.copy(), sort_by_code=True)
    top10_out = format_for_output(top10_sel.copy(), sort_by_code=True)

    eps_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_disp_map)
        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    if buy_today is None or buy_today.empty:
        buy_today_out = tech_today_out.head(0).copy() if tech_today_out is not None and not tech_today_out.empty else pd.DataFrame()
    else:
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_disp_map)
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)

    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "出場原因", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades_out = trades.merge(name_map, on="股票代號", how="left")

        # ✅ 先做格式整理（但不要排序）
        trades_out = format_for_output(trades_out, sort_by_code=False)

        # ✅ 依進場日排序（你要求）
        if "進場日" in trades_out.columns:
            trades_out = trades_out.sort_values("進場日")

        #trades_out = format_for_output(trades_out, sort_by_code=True)

    # ===== Excel output =====
    out_file = f"{cfg.out_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6

    logger.log("輸出 Excel...")
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)
        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)
        reason_stats.to_excel(writer, index=False, sheet_name="出場原因統計")

        summary_sheet = pd.concat(
            [pd.DataFrame([{"區塊": "Signal-level(v0.7.3_event_exit)"}]),
             sig_summary,
             pd.DataFrame([{"區塊": f"Portfolio-level(v0.7.3_Top{cfg.topk}_EqualWeight)"}]),
             pf_kpi],
            ignore_index=True
        )
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        eq.to_excel(writer, index=False, sheet_name="投組回測_TopK等權", startrow=startrow)
        trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)

        # ✅ 新增
        #yearly_perf.to_excel(writer, sheet_name="年度績效", index=False)

        # ✅ v0.8.0
        if yearly_perf is not None and not yearly_perf.empty:
            yearly_perf.to_excel(writer, sheet_name="年度績效", index=False)

        ws_tech = writer.sheets["技術分析_今日"]
        ws_buy = writer.sheets["技術買點_今日"]
        ws_sum = writer.sheets["回測摘要"]

        tech_explain = [
            "【技術分析_今日】說明",
            f"Top{cfg.topk} 等權投組 + 事件型出場（SL={cfg.stop_loss:.0%}, TP={cfg.take_profit:.0%}, RSI={cfg.exit_rsi}, HOLD={cfg.hold_days}日）。",
            "本表顯示 Ret_1D_past/Ret_5D_past（過去報酬），避免最新日空欄位。"
        ]
        buy_explain = [
            "【技術買點_今日】說明",
            "空表代表今日無訊號（正常）。"
        ]
        bt_explain = [
            "【回測摘要】說明",
            "Signal-level：買點事件用事件型出場計算報酬（含成本）。",
            f"Portfolio-level：Top{cfg.topk} 等權投組，事件型出場。",
        ]

        write_explanation(ws_tech, tech_explain)
        write_explanation(ws_buy, buy_explain)
        write_explanation(ws_sum, bt_explain)

        header_row = startrow + 1
        for ws in (ws_tech, ws_buy, ws_sum):
            style_header(ws, header_row)
            ws.freeze_panes = ws[f"A{header_row + 1}"]
            last_col = get_column_letter(ws.max_column)
            ws.auto_filter.ref = f"A{header_row}:{last_col}{ws.max_row}"
            autosize_columns(ws)

        highlight_true(ws_tech, header_row, "買點")
        highlight_true(ws_buy, header_row, "買點")

    # ===== console summary =====
    logger.log("✅ Signal-level KPI（事件型）:")
    logger.log(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    logger.log(f"✅ Portfolio-level KPI（Top{cfg.topk} 等權）:")
    logger.log(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")

    logger.log("✅ 出場原因統計：")
    if not reason_stats.empty:
        logger.log(reason_stats.to_string(index=False))
    else:
        logger.log("(無交易資料)")

    logger.log(f"✅ 完成 → {out_file}")
    if not cfg.verify_ssl:
        logger.log("⚠️ 注意：mopsfin 憑證異常期間，本程式暫用 verify=False（短期救急用）。")


# ==========================================================
# 18) GUI（Config window + Program Console）
# ==========================================================
class StrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StockTool v0.8.0-GUI (TopK Equal Weight)")

        self.log_queue = queue.Queue()
        self.logger = GuiLogger(self.log_queue)

        self.cfg = StrategyConfig()  # default = v0.7.3 option A

        self._build_ui()
        self._poll_log_queue()

    def _build_ui(self):
        self.geometry("980x720")

        # layout
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(container)
        left.pack(side="left", fill="y")

        right = ttk.Frame(container)
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # ---- Config panel ----
        ttk.Label(left, text="Config (可調整策略參數)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))

        self.vars: Dict[str, tk.Variable] = {}
        self._add_entry(left, "TopN_for_Tech", "top_n_for_tech", tk.IntVar, self.cfg.top_n_for_tech)
        self._add_entry(left, "Tech_Months", "tech_months", tk.IntVar, self.cfg.tech_months)
        self._add_entry(left, "TopK (Equal Weight)", "topk", tk.IntVar, self.cfg.topk)

        self._add_check(left, "Use Fundamental Gate", "use_gate", self.cfg.use_gate)
        self._add_entry(left, "MIN_REV_YOY", "min_rev_yoy", tk.DoubleVar, self.cfg.min_rev_yoy)
        self._add_entry(left, "MIN_EPS_YOY", "min_eps_yoy", tk.DoubleVar, self.cfg.min_eps_yoy)
        self._add_check(left, "Allow EPSYoY NaN (avoid Trades=0)", "allow_eps_yoy_nan", self.cfg.allow_eps_yoy_nan)
        self._add_check(left, "Require Volume Filter", "require_volume_filter", self.cfg.require_volume_filter)

        # ✅ Excel 選股模式
        self.use_excel_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left,
            text="Use Excel Stock List",
            variable=self.use_excel_var
        ).pack(anchor="w")

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Label(left, text="Event Exit (v0.7.3 Option A defaults)", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self._add_entry(left, "STOP_LOSS (e.g. -0.04)", "stop_loss", tk.DoubleVar, self.cfg.stop_loss)
        self._add_entry(left, "TAKE_PROFIT (e.g. 0.05)", "take_profit", tk.DoubleVar, self.cfg.take_profit)
        self._add_entry(left, "EXIT_RSI (e.g. 62)", "exit_rsi", tk.IntVar, self.cfg.exit_rsi)
        self._add_entry(left, "HOLD_DAYS", "hold_days", tk.IntVar, self.cfg.hold_days)
        self._add_entry(left, "ROUNDTRIP_COST_PCT", "roundtrip_cost_pct", tk.DoubleVar, self.cfg.roundtrip_cost_pct)

        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Signal Params", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self._add_entry(left, "RSI_OVERSOLD", "rsi_oversold", tk.IntVar, self.cfg.rsi_oversold)
        self._add_entry(left, "MA20_TOLERANCE", "ma20_tolerance", tk.DoubleVar, self.cfg.ma20_tolerance)

        self._add_entry(left, "Strong Rev YoY", "strong_revenue_yoy", tk.DoubleVar, self.cfg.strong_revenue_yoy)
        self._add_entry(left, "Strong PE Max", "strong_pe_max", tk.DoubleVar, self.cfg.strong_pe_max)
        self._add_entry(left, "Strong Price Min", "strong_price_min", tk.DoubleVar, self.cfg.strong_price_min)

        ttk.Separator(left).pack(fill="x", pady=8)
        self.run_btn = ttk.Button(left, text="Run Strategy", command=self._on_run)
        self.run_btn.pack(fill="x", pady=(6, 0))

        # ✅ 新增 Clear Console 按鈕
        self.clear_btn = ttk.Button(left, text="Clear Console", command=self._on_clear_console)
        self.clear_btn.pack(fill="x", pady=(6, 0))



        # ---- Console panel ----
        ttk.Label(right, text="Program Console", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.console = tk.Text(right, height=30, wrap="word")
        self.console.pack(fill="both", expand=True, pady=(6, 0))

        # quick tips
        tip = ("Tip: 參數改完按 Run Strategy。執行中 UI 不會卡（threading）。\n"
               "輸出 Excel 在程式同資料夾。")
        ttk.Label(right, text=tip, foreground="#555").pack(anchor="w", pady=(6, 0))

    def _add_entry(self, parent, label, key, var_cls, default):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=24).pack(side="left")
        v = var_cls(value=default)
        self.vars[key] = v
        ttk.Entry(row, textvariable=v, width=16).pack(side="left")

    def _add_check(self, parent, label, key, default):
        v = tk.BooleanVar(value=default)
        self.vars[key] = v
        ttk.Checkbutton(parent, text=label, variable=v).pack(anchor="w", pady=2)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.console.insert("end", msg + "\n")
                self.console.see("end")
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    def _read_config(self) -> StrategyConfig:
        cfg = StrategyConfig()
        # map GUI vars -> cfg fields
        for k, v in self.vars.items():
            setattr(cfg, k, v.get())
        return cfg

    def _on_clear_console(self):
        """清空 Program Console"""
        self.console.delete("1.0", "end")


    def _on_run(self):
        self.run_btn.config(state="disabled")
        self.console.insert("end", "========== RUN ==========\n")
        self.console.see("end")

        cfg = self._read_config()

        cfg.use_excel_stock_list = self.use_excel_var.get()

        def worker():
            try:
                run_pipeline(cfg, self.logger)
            except Exception as e:
                self.logger.log(f"❌ 執行失敗：{e}")
            finally:
                self.run_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = StrategyGUI()
    app.mainloop()
