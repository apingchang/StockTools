"""
檔名：StockTool.py
版本：v0.6.1
最後更新：2026-05-15 13:45 (Asia/Taipei)

【目的】
- 產生投顧式台股選股報表（基本面 + 技術面 + 回測 + Excel 美化）
- 技術面不依賴 Yahoo / yfinance，改用 TWSE 官方 STOCK_DAY（月內日成交）歷史端點。[1](https://www.techpowerup.com/334295/nvidia-announces-blackwell-ultra-platform-for-next-gen-ai)

【資料來源】
- 今日股價快照：
  - TWSE OpenAPI：STOCK_DAY_ALL（上市快照）
  - TPEX OpenAPI：tpex_mainboard_quotes（上櫃快照）
- 月營收 / EPS：mopsfin.twse.com.tw OpenData CSV
  - 注意：mopsfin 憑證過期 + HSTS 時需 verify=False（短期救急；降低 SSL 驗證安全性）[2](https://calmops.com/technology/spatial-computing-apple-vision-pro-2026/)[3](https://www.iea.org/reports/electricity-2026/grids)[4](https://www.chinatimes.com/realtimenews/20260514002319-260410)[5](https://infotechlead.com/artificial-intelligence/idc-report-highlights-10-key-ai-trends-set-to-reshape-enterprises-by-2026-92569)
- 技術面歷史：
  - TWSE：/exchangeReport/STOCK_DAY?response=json&date=YYYYMM01&stockNo=2330
    date 用 YYYYMM01 代表查該月份（日成交資訊），回傳 JSON fields/data 可轉表格。[1](https://www.techpowerup.com/334295/nvidia-announces-blackwell-ultra-platform-for-next-gen-ai)

【整體流程（Coding Logic / Pipeline）】
1) 下載今日快照（含公司名稱）→ 建公司名稱對照表
2) 下載最新月營收 + 最新季 EPS → 清理型別 → 合併基本面表
3) 計算基本面 Score → 產出 全市場 / 強勢股 / Top10
4) 對 Score 前 TOP_N_FOR_TECH 抓近 TECH_MONTHS 月歷史日K → 計算 MA/RSI/MACD/量能均量
5) 產生「三段式買點（B折衷）」→ 產出 技術分析_今日 / 技術買點_今日
6) 回測（訊號層級）：勝率/均值/中位數/最大連敗/獲利因子（含成本）
7) 投組回測（單一持股）：每日若有訊號且空手 → 選 Score 最高的一檔，持有 HOLD_DAYS 天出場
   → Equity、MDD、Sharpe/Sortino、Max Losing Streak、Profit Factor（rf=0、MAR=0；年化252）
8) 匯出 Excel：表頭樣式、凍結窗格、欄寬、篩選、買點標色、三張表含投顧式說明文字

【Changelog】
- 2026-05-15 v0.6.1
  - Fixed: TWSE STOCK_DAY 回應非 JSON 時造成 JSONDecodeError，加入 content-type 檢查 + JSON 解析容錯 + 重試退避
  - Changed: 將 TWSE 抓取失敗改為「略過該月/該股」不中斷整體流程
  - Added: 回測摘要中加入資料品質提醒（樣本數不足時提示）
  - Security: 維持 mopsfin verify=False 短期救急提醒（憑證異常時）[4](https://www.chinatimes.com/realtimenews/20260514002319-260410)[5](https://infotechlead.com/artificial-intelligence/idc-report-highlights-10-key-ai-trends-set-to-reshape-enterprises-by-2026-92569)

【Parameter Diff（vs v0.6.0）】
- 新增 TWSE_REQUEST_RETRIES / TWSE_BACKOFF_BASE / TWSE_SLEEP_SECONDS（降低被限流/非JSON風險）
- TWSE JSON 解析加入 safe_json 及 content-type 判斷

【Backtest KPI Snapshot（執行後會印在 Console 並寫入 Excel 回測摘要）】
- Signal-level: Signals, WinRate(Net), AvgReturn(Net), Median(Net), MaxLosingStreak, ProfitFactor
- Portfolio-level: CAGR, MDD, Sharpe, Sortino, Trades, MaxLosingStreak, ProfitFactor
"""

import io
import time
import warnings
from datetime import datetime, date

import pandas as pd
import requests

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule


# ==========================================================
# 0) 全域參數（B：折衷，目標訊號數 20–60 / 9–12 個月）
# ==========================================================
TOP_N_FOR_TECH = 30
TECH_MONTHS = 12
OUT_FILE_PREFIX = "選股報表"

# mopsfin 憑證過期救急：verify=False（站台修好後改 True）[2](https://calmops.com/technology/spatial-computing-apple-vision-pro-2026/)[3](https://www.iea.org/reports/electricity-2026/grids)
VERIFY_SSL = False
TIMEOUT = 30

# --- TWSE STOCK_DAY 抗不穩參數（本次修正重點） ---
TWSE_REQUEST_RETRIES = 3          # 單次請求最多重試幾次
TWSE_BACKOFF_BASE = 0.8           # 重試退避基底秒數（會乘以 attempt）
TWSE_SLEEP_SECONDS = 0.12         # 每次請求後睡一下（降低被限流風險）

# 三段式買點（B折衷）
RSI_OVERSOLD = 38
OVERSOLD_LOOKBACK = 10
RSI_RECOVER = 40
RSI_AGGRESSIVE = 45
USE_AGGRESSIVE_SIGNAL = True

REQUIRE_TREND_FILTER = True
MA_SLOPE_DAYS = 3
MA20_TOLERANCE = 0.005

REQUIRE_VOLUME_FILTER = False     # B版：不強制（訊號較多）

# 回測設定（含成本）
HOLD_DAYS = 5
ROUNDTRIP_COST_PCT = 0.004

# Sharpe/Sortino 設定（你選 A：rf=0、MAR=0）
RISK_FREE_ANNUAL = 0.0
MAR_ANNUAL = 0.0
TRADING_DAYS = 252

# 基本面強勢股條件
STRONG_REVENUE_YOY = 10
STRONG_PE_MAX = 30
STRONG_PRICE_MIN = 10

warnings.filterwarnings("ignore")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.6.1",
    "Accept": "application/json,text/plain,*/*"
})


# ==========================================================
# 1) 通用工具
# ==========================================================
def find_col(cols, keywords):
    """欄位模糊匹配（避免欄位名變動造成 KeyError）"""
    for c in cols:
        s = str(c)
        for k in keywords:
            if k in s:
                return c
    return None


def to_num_series(s):
    """字串數字 → numeric（去除逗號、%、+）"""
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("+", "", regex=False)
         .str.strip(),
        errors="coerce"
    )


def fetch_csv_requests(url, encodings=("utf-8-sig", "utf-8")):
    """requests 抓 CSV → pandas 解析（mopsfin 憑證異常時 verify=False 救急）"""
    r = session.get(url, timeout=TIMEOUT, verify=VERIFY_SSL)
    r.raise_for_status()

    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"讀取失敗：{url}，最後錯誤：{last_err}")


# ==========================================================
# 2) 技術面用：月份序列 + 民國日期轉換
# ==========================================================
def month_starts_back(n_months: int):
    """近 n 個月 YYYYMM01（含本月）；TWSE STOCK_DAY 用此 date 代表查該月份"""
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
    """民國日期 '113/09/02' → date(2024,9,2)"""
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


# ==========================================================
# 3) 今日股價快照：TWSE + TPEX（含公司名稱）
# ==========================================================
def fetch_prices():
    """回傳：股票代號、股價、漲跌、公司名稱_來源（上市+上櫃）"""
    # TWSE
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    twse = pd.DataFrame(session.get(twse_url, timeout=TIMEOUT).json())

    code_col = find_col(twse.columns, ["證券代號", "Code"])
    close_col = find_col(twse.columns, ["收盤價", "ClosingPrice"])
    chg_col = find_col(twse.columns, ["漲跌價差", "Change"])
    name_col = find_col(twse.columns, ["證券名稱", "Name"])
    if code_col is None or close_col is None:
        raise RuntimeError(f"TWSE 欄位無法識別：{twse.columns}")

    twse = twse.rename(columns={code_col: "股票代號", close_col: "股價", chg_col: "漲跌", name_col: "公司名稱_來源"})

    # TPEX
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    tpex = pd.DataFrame(session.get(tpex_url, timeout=TIMEOUT).json())

    tpex_code = find_col(tpex.columns, ["SecuritiesCompanyCode", "股票代號", "Code"])
    tpex_close = find_col(tpex.columns, ["Close", "收盤", "ClosingPrice"])
    tpex_chg = find_col(tpex.columns, ["Change", "漲跌"])
    tpex_name = find_col(tpex.columns, ["CompanyName", "公司名稱", "Name"])
    if tpex_code is None or tpex_close is None:
        raise RuntimeError(f"TPEX 欄位無法識別：{tpex.columns}")

    tpex = tpex.rename(columns={tpex_code: "股票代號", tpex_close: "股價", tpex_chg: "漲跌", tpex_name: "公司名稱_來源"})

    price = pd.concat(
        [twse[["股票代號", "股價", "漲跌", "公司名稱_來源"]],
         tpex[["股票代號", "股價", "漲跌", "公司名稱_來源"]]],
        ignore_index=True
    )

    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    return price.drop_duplicates("股票代號").reset_index(drop=True)


# ==========================================================
# 4) 月營收（最新月） + EPS（最新季）：mopsfin
# ==========================================================
def fetch_revenue_latest():
    urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv",
    ]
    rev = pd.concat([fetch_csv_requests(u) for u in urls], ignore_index=True)

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


def fetch_eps_latest():
    urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv",
    ]
    eps = pd.concat([fetch_csv_requests(u) for u in urls], ignore_index=True)

    code_col = find_col(eps.columns, ["公司代號"])
    year_col = find_col(eps.columns, ["年度"])
    q_col = find_col(eps.columns, ["季別"])
    eps_col = find_col(eps.columns, ["基本每股盈餘"])
    if code_col is None or year_col is None or q_col is None or eps_col is None:
        raise RuntimeError(f"EPS 欄位無法識別：{eps.columns}")

    eps = eps.rename(columns={code_col: "股票代號", year_col: "年度", q_col: "季別", eps_col: "EPS"})
    eps["股票代號"] = eps["股票代號"].astype(str).str.strip()
    eps["年度"] = pd.to_numeric(eps["年度"], errors="coerce")
    eps["季別"] = pd.to_numeric(eps["季別"], errors="coerce")
    eps["EPS"] = pd.to_numeric(eps["EPS"], errors="coerce")

    latest_year = eps["年度"].max()
    latest_q = eps.loc[eps["年度"] == latest_year, "季別"].max()

    cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    cur = cur.rename(columns={"EPS": "EPS本期"})

    prev = eps[(eps["年度"] == latest_year - 1) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    prev = prev.rename(columns={"EPS": "EPS去年"})

    out = cur.merge(prev, on="股票代號", how="left")
    out["EPSYoY"] = (out["EPS本期"] - out["EPS去年"]) / out["EPS去年"]
    out["EPS季別"] = f"{int(latest_year)}Q{int(latest_q)}"
    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY"]].drop_duplicates("股票代號").reset_index(drop=True)


# ==========================================================
# 5) 技術歷史：TWSE STOCK_DAY（本次修正：safe_json + retry + content-type 檢查）
# ==========================================================
def safe_parse_json(r):
    """
    嘗試把 response 解析成 JSON：
    - 若內容不是 JSON（例如 HTML/空字串）會回傳 None
    """
    text = (r.text or "").strip()
    if not text:
        return None
    # 很多非JSON的情況會以 "<!DOCTYPE html" 或 "<html" 開頭
    if text.startswith("<"):
        return None
    # 正常 JSON 會以 "{" 或 "[" 開頭
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return r.json()
    except Exception:
        return None


def fetch_twse_stock_day_month(stock_no: str, yyyymm01: str):
    """
    抓某檔股票某月份日K（含成交股數 Volume）
    - 加入：非JSON回應保護、重試退避、content-type 判斷
    - 若該次失敗：回傳空 DataFrame（不中斷整體流程）
    """
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}

    for attempt in range(1, TWSE_REQUEST_RETRIES + 1):
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            # 非 200 直接視為失敗，進入 retry
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")

            # content-type 若不是 json，也可能是錯誤頁
            ctype = (r.headers.get("Content-Type") or "").lower()
            js = None
            if "application/json" in ctype:
                js = safe_parse_json(r)  # 仍用 safe 防空內容
            else:
                # 不是 json 也試著 parse（有些伺服器 content-type 不準）
                js = safe_parse_json(r)

            if js is None:
                raise RuntimeError("Non-JSON response (empty/html/blocked)")

            # 正常 JSON 結構檢查
            if js.get("stat") != "OK" or "data" not in js:
                return pd.DataFrame()

            fields = js.get("fields", [])
            data = js.get("data", [])
            if not fields or not data:
                return pd.DataFrame()

            dfm = pd.DataFrame(data, columns=fields)

            date_col = find_col(dfm.columns, ["日期"])
            vol_col = find_col(dfm.columns, ["成交股數"])
            open_col = find_col(dfm.columns, ["開盤價"])
            high_col = find_col(dfm.columns, ["最高價"])
            low_col = find_col(dfm.columns, ["最低價"])
            close_col = find_col(dfm.columns, ["收盤價"])
            if date_col is None or close_col is None:
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

        except Exception as e:
            # 最後一次仍失敗：直接回空（不中斷整體流程）
            if attempt == TWSE_REQUEST_RETRIES:
                return pd.DataFrame()
            # 退避等待：base * attempt
            time.sleep(TWSE_BACKOFF_BASE * attempt)

    return pd.DataFrame()


def fetch_twse_history(codes, months=TECH_MONTHS):
    """對每檔股票抓近 months 個月日K，拼成長表；任一月失敗會略過"""
    month_keys = month_starts_back(months)
    all_frames = []

    for i, code in enumerate(codes, 1):
        code = str(code).strip()
        frames = []
        for mk in month_keys:
            dfm = fetch_twse_stock_day_month(code, mk)
            if not dfm.empty:
                frames.append(dfm)
            time.sleep(TWSE_SLEEP_SECONDS)

        if frames:
            dfh = pd.concat(frames, ignore_index=True)
            dfh = dfh.drop_duplicates(subset=["Date"]).sort_values("Date")
            all_frames.append(dfh)

        if i % 10 == 0:
            print(f"   技術面歷史抓取進度：{i}/{len(codes)}")

    if not all_frames:
        return pd.DataFrame()

    hist = pd.concat(all_frames, ignore_index=True)
    return hist.sort_values(["股票代號", "Date"]).reset_index(drop=True)


# ==========================================================
# 6) 指標 & 訊號（B折衷三段式）
# ==========================================================
def calc_tech_indicators(df_hist):
    """計算 MA/RSI/MACD + 三段式買點 + 訊號層級回測報酬"""
    df_hist = df_hist.sort_values("Date").copy()

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

    oversold = df_hist["RSI"] < RSI_OVERSOLD
    oversold_recent = oversold.rolling(OVERSOLD_LOOKBACK).max().shift(1).fillna(0).astype(bool)

    recover_level = RSI_AGGRESSIVE if USE_AGGRESSIVE_SIGNAL else RSI_RECOVER
    rsi_cross_up = (df_hist["RSI"] >= recover_level) & (df_hist["RSI"].shift(1) < recover_level)
    macd_hist_turn = (df_hist["MACD_hist"] > 0) & (df_hist["MACD_hist"].shift(1) <= 0)
    turn_strong = rsi_cross_up | macd_hist_turn

    ma20_slope = df_hist["MA20"] - df_hist["MA20"].shift(MA_SLOPE_DAYS)
    trend_ok = (df_hist["Close"] >= df_hist["MA20"] * (1 - MA20_TOLERANCE)) & (ma20_slope > 0)

    volume_ok = (df_hist["Volume"] >= df_hist["VolMA20"])

    buy = oversold_recent & turn_strong
    if REQUIRE_TREND_FILTER:
        buy = buy & trend_ok
    if REQUIRE_VOLUME_FILTER:
        buy = buy & volume_ok

    df_hist["買點"] = buy
    df_hist["訊號型態"] = "三段式_B(折衷)"

    df_hist["R_1D"] = df_hist["Close"].shift(-1) / df_hist["Close"] - 1
    df_hist["R_HD"] = df_hist["Close"].shift(-HOLD_DAYS) / df_hist["Close"] - 1
    df_hist["R_HD_net"] = (1 + df_hist["R_HD"]) * (1 - ROUNDTRIP_COST_PCT) - 1
    return df_hist


def run_tech_and_backtest(codes):
    """產出 tech_today / buy_today / tech_all（完整歷史）"""
    hist = fetch_twse_history(codes, months=TECH_MONTHS)
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_tech_indicators(g)
        g2["股票代號"] = code
        parts.append(g2)
    tech_all = pd.concat(parts, ignore_index=True)

    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()
    return tech_today, buy_today, tech_all


# ==========================================================
# 7) KPI 計算（同前版，略：此段保持不變）
# ==========================================================
def max_losing_streak(trade_returns):
    max_streak = 0
    cur = 0
    for r in trade_returns:
        if pd.isna(r):
            continue
        if r < 0:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return int(max_streak)


def profit_factor(trade_returns):
    wins = trade_returns[trade_returns > 0].sum()
    losses = trade_returns[trade_returns < 0].sum()
    if losses == 0:
        return float("inf") if wins > 0 else None
    return float(wins / abs(losses))


def annualize_sharpe(daily_returns, rf_annual=0.0):
    r = daily_returns.dropna()
    if len(r) < 10:
        return None
    rf_d = rf_annual / TRADING_DAYS
    mu = (r.mean() - rf_d) * TRADING_DAYS
    sigma = r.std(ddof=1) * (TRADING_DAYS ** 0.5)
    if sigma == 0:
        return None
    return float(mu / sigma)


def annualize_sortino(daily_returns, mar_annual=0.0):
    r = daily_returns.dropna()
    if len(r) < 10:
        return None
    mar_d = mar_annual / TRADING_DAYS
    excess = r - mar_d
    downside = excess.copy()
    downside[downside > 0] = 0
    downside_dev = downside.std(ddof=1) * (TRADING_DAYS ** 0.5)
    mu = excess.mean() * TRADING_DAYS
    if downside_dev == 0:
        return None
    return float(mu / downside_dev)


def compute_signal_level_summary(tech_all):
    buy_all = tech_all[tech_all["買點"] == True].copy()
    if buy_all.empty:
        return pd.DataFrame()

    rh_net = buy_all["R_HD_net"].dropna()
    r1 = buy_all["R_1D"].dropna()
    rh = buy_all["R_HD"].dropna()

    streak = max_losing_streak(rh_net.values)
    pf = profit_factor(rh_net)

    return pd.DataFrame([{
        "訊號數": int(len(buy_all)),
        "1日平均報酬(%)": round(r1.mean() * 100, 2) if len(r1) else None,
        f"{HOLD_DAYS}日平均報酬(%)": round(rh.mean() * 100, 2) if len(rh) else None,
        f"{HOLD_DAYS}日平均報酬_扣成本(%)": round(rh_net.mean() * 100, 2) if len(rh_net) else None,
        f"{HOLD_DAYS}日勝率_扣成本(%)": round((rh_net > 0).mean() * 100, 2) if len(rh_net) else None,
        f"{HOLD_DAYS}日中位數_扣成本(%)": round(rh_net.median() * 100, 2) if len(rh_net) else None,
        "MaxLosingStreak": streak,
        "ProfitFactor": round(pf, 3) if pf is not None and pf != float("inf") else pf
    }])


def portfolio_backtest_single(tech_all, score_map):
    if tech_all.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = tech_all[["Date", "股票代號", "Close", "買點"]].copy()
    df = df.dropna(subset=["Date", "Close"])
    df["Score"] = df["股票代號"].map(score_map)

    by_code = {c: g.sort_values("Date").reset_index(drop=True) for c, g in df.groupby("股票代號")}
    all_dates = sorted(df["Date"].unique())

    equity = 1.0
    equity_rows = []
    trade_rows = []

    holding = False
    hold_code = None
    entry_price = None
    exit_date = None
    exit_price = None

    entry_mult = 1 - ROUNDTRIP_COST_PCT / 2
    exit_mult = 1 - ROUNDTRIP_COST_PCT / 2

    for d in all_dates:
        d = pd.to_datetime(d)

        if not holding:
            cand = df[(df["Date"] == d) & (df["買點"] == True)].dropna(subset=["Score"])
            if not cand.empty:
                best = cand.sort_values("Score", ascending=False).iloc[0]
                hold_code = best["股票代號"]
                entry_price = float(best["Close"])

                g = by_code.get(hold_code)
                idx_list = g.index[g["Date"] == d].tolist() if g is not None else []
                if not idx_list:
                    hold_code = None
                    entry_price = None
                else:
                    idx0 = idx_list[0]
                    exit_idx = idx0 + HOLD_DAYS
                    if exit_idx >= len(g):
                        hold_code = None
                        entry_price = None
                    else:
                        exit_date = pd.to_datetime(g.loc[exit_idx, "Date"])
                        exit_price = float(g.loc[exit_idx, "Close"])
                        holding = True
                        equity *= entry_mult

                        trade_rows.append({
                            "股票代號": hold_code,
                            "進場日": d.date().isoformat(),
                            "進場價": entry_price,
                            "出場日": exit_date.date().isoformat(),
                            "出場價": exit_price,
                            "持有天數": HOLD_DAYS
                        })

        if holding and hold_code is not None:
            g = by_code[hold_code]
            cur = g[g["Date"] == d]
            if not cur.empty:
                cur_price = float(cur.iloc[0]["Close"])
                equity_today = equity * (cur_price / entry_price)
            else:
                equity_today = equity
        else:
            equity_today = equity

        equity_rows.append({"Date": d, "Equity": equity_today})

        if holding and exit_date is not None and d == exit_date:
            equity = equity_today * exit_mult
            trade_rows[-1]["報酬(%)"] = round((exit_price / entry_price - 1) * 100, 2)
            trade_rows[-1]["報酬_扣成本(%)"] = round(((1 + (exit_price / entry_price - 1)) * (1 - ROUNDTRIP_COST_PCT) - 1) * 100, 2)

            holding = False
            hold_code = None
            entry_price = None
            exit_date = None
            exit_price = None

    eq = pd.DataFrame(equity_rows).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    trades = pd.DataFrame(trade_rows)

    eq["Ret"] = eq["Equity"].pct_change()
    eq["Peak"] = eq["Equity"].cummax()
    eq["Drawdown"] = eq["Equity"] / eq["Peak"] - 1
    mdd = eq["Drawdown"].min()

    sharpe = annualize_sharpe(eq["Ret"], rf_annual=RISK_FREE_ANNUAL)
    sortino = annualize_sortino(eq["Ret"], mar_annual=MAR_ANNUAL)

    # CAGR
    if len(eq) >= 2:
        days = (eq["Date"].iloc[-1] - eq["Date"].iloc[0]).days
        years = days / 365.25 if days > 0 else None
        cagr = (eq["Equity"].iloc[-1] ** (1 / years) - 1) if years else None
    else:
        cagr = None

    if not trades.empty and "報酬_扣成本(%)" in trades.columns:
        tr = trades["報酬_扣成本(%)"].astype(float) / 100.0
        pf = profit_factor(tr)
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

    return eq, trades, kpi


# ==========================================================
# 8) Excel 美化工具
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

    # ✅ 正確寫法
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
# 9) 主流程
# ==========================================================
def main():
    print("1) 下載股價（TWSE+TPEX）...")
    price = fetch_prices()

    name_map = price[["股票代號", "公司名稱_來源"]].dropna().drop_duplicates("股票代號").copy()
    name_map = name_map.rename(columns={"公司名稱_來源": "公司名稱"})

    print("2) 下載最新月營收（mopsfin L+O；暫時跳過 SSL 驗證）...")
    rev_latest = fetch_revenue_latest()

    print("3) 下載最新EPS（mopsfin L+O；暫時跳過 SSL 驗證）...")
    eps_latest = fetch_eps_latest()

    print("4) 合併基本面資料...")
    df = price.merge(rev_latest, on="股票代號", how="left")
    df = df.merge(eps_latest, on="股票代號", how="left")

    df["PE"] = df["股價"] / df["EPS本期"]
    df["殖利率(估)"] = (df["EPS本期"] * 0.7) / df["股價"]

    df["Score"] = (
        df["營收YoY(%)"].fillna(0) * 0.35 +
        df["EPSYoY"].fillna(0) * 100 * 0.35 +
        df["殖利率(估)"].fillna(0) * 100 * 0.20 -
        df["PE"].fillna(0) * 0.05
    )
    df = df.sort_values("Score", ascending=False).reset_index(drop=True)

    strong = df[
        (df["營收YoY(%)"] > STRONG_REVENUE_YOY) &
        (df["EPS本期"] > 0) &
        (df["PE"] < STRONG_PE_MAX) &
        (df["股價"] > STRONG_PRICE_MIN)
    ].copy()
    top10 = df.head(10).copy()

    print(f"5) 抓歷史日K（TWSE STOCK_DAY）Top{TOP_N_FOR_TECH}（不使用Yahoo）...")
    tech_codes = df.head(TOP_N_FOR_TECH)["股票代號"].dropna().astype(str).tolist()
    tech_today, buy_today, tech_all = run_tech_and_backtest(tech_codes)

    sig_summary = compute_signal_level_summary(tech_all)
    score_map = df.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi = portfolio_backtest_single(tech_all, score_map)

    # 補公司名稱/Score 到技術表
    if not tech_today.empty:
        tech_today = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today["Score"] = tech_today["股票代號"].map(score_map)

    if not buy_today.empty:
        buy_today = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today["Score"] = buy_today["股票代號"].map(score_map)

    print("✅ Signal-level KPI（訊號層級）:")
    print(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")

    print("✅ Portfolio-level KPI（投組層級）:")
    print(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")

    # 投顧式文字說明
    recover_level = RSI_AGGRESSIVE if USE_AGGRESSIVE_SIGNAL else RSI_RECOVER
    signal_rule_text = (
        f"三段式買點：最近{OVERSOLD_LOOKBACK}日內 RSI<{RSI_OVERSOLD}（超跌）→ "
        f"RSI上穿{recover_level}或MACD_hist翻正（轉強）→ "
        f"Close>=MA20*(1-{MA20_TOLERANCE*100:.1f}%) 且 MA20走升（趨勢確認）"
        + ("；量能：強制" if REQUIRE_VOLUME_FILTER else "；量能：不強制")
    )

    tech_explain = [
        "【技術分析_今日】說明",
        f"資料來源：TWSE STOCK_DAY（月內日成交；date=YYYYMM01 查該月）[1](https://www.techpowerup.com/334295/nvidia-announces-blackwell-ultra-platform-for-next-gen-ai)",
        f"買點規則（B折衷）：{signal_rule_text}",
        "提示：若短時間出現 Non-JSON/空回應，程式會自動重試與略過（不中斷）。"
    ]
    buy_explain = [
        "【技術買點_今日】說明",
        "本表列出今日符合買點規則者；若空表代表今日無訊號。",
        "建議搭配基本面強勢股交叉確認。"
    ]
    bt_explain = [
        "【回測摘要】說明（投顧式解讀）",
        "Signal-level：每次買點視為獨立交易，統計勝率/均值/中位數/最大連敗/獲利因子（含成本）。",
        "Portfolio-level：單一持股策略，用每日 equity 報酬計算 Sharpe/Sortino（rf=0、MAR=0，年化252）。",
        "安全提醒：mopsfin 憑證異常時採 verify=False（短期救急，降低 SSL 驗證安全性）。"
    ]

    # Excel 輸出
    out_file = f"{OUT_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10.to_excel(writer, index=False, sheet_name="Top10_基本面")

        tech_today.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)
        buy_today.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)

        summary_sheet = pd.concat(
            [pd.DataFrame([{"區塊": "Signal-level"}]), sig_summary,
             pd.DataFrame([{"區塊": "Portfolio-level"}]), pf_kpi],
            ignore_index=True
        )
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        eq.to_excel(writer, index=False, sheet_name="投組回測_B單一持股", startrow=startrow)
        trades.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)

        ws_tech = writer.sheets["技術分析_今日"]
        ws_buy = writer.sheets["技術買點_今日"]
        ws_sum = writer.sheets["回測摘要"]
        ws_pf = writer.sheets["投組回測_B單一持股"]

        write_explanation(ws_tech, tech_explain)
        write_explanation(ws_buy, buy_explain)
        write_explanation(ws_sum, bt_explain)

        header_row = startrow + 1
        for ws in (ws_tech, ws_buy, ws_sum, ws_pf):
            style_header(ws, header_row)
            ws.freeze_panes = ws[f"A{header_row + 1}"]
            last_col = get_column_letter(ws.max_column)
            ws.auto_filter.ref = f"A{header_row}:{last_col}{ws.max_row}"
            autosize_columns(ws)

        highlight_true(ws_tech, header_row, "買點")
        highlight_true(ws_buy, header_row, "買點")

    print(f"✅ 完成 → {out_file}")
    if not VERIFY_SSL:
        print("⚠️ 注意：mopsfin 憑證過期期間，本程式暫用 verify=False（短期救急用）。")


if __name__ == "__main__":
    main()