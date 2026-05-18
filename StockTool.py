"""
檔名：StockTool.py
版本：v0.7.2-C（TopK=3 等權投組，完整可執行，分2段貼上）
最後更新：2026-05-16 (Asia/Taipei)

============================================================
【目的】
- 在 v0.7.1（事件型出場 B2）基礎上，依你選擇的 C：
  => 將 Portfolio-level 改為「TopK（預設 K=3）等權投組」回測
  => 目標：降低風險集中、改善 MDD、提升 Sharpe，通常也能讓 PF 往上走

============================================================
【v0.7.2-C 策略重點】
1) 進場（投組層級）：
   - 僅在「空手」時進場（保持你原本投顧式直覺：一次建倉）
   - 當天若有買點，挑 Score 前 K 檔（K=3）等權投入
2) 出場（每個持倉各自事件型出場，先觸發先出）：
   - 停損 ret <= STOP_LOSS
   - 停利 ret >= TAKE_PROFIT
   - RSI 出場 RSI >= EXIT_RSI
   - 最長持有 <= HOLD_DAYS（時間出場）
3) Gate（可開關 USE_FUNDAMENTAL_GATE，且避免全滅）：
   - 營收YoY(%) > MIN_REV_YOY
   - EPSYoY_raw > MIN_EPS_YOY 或 EPSYoY_raw is NaN（缺值先放行）
4) 報表格式（你7點）：
   - 公司名稱_來源固定在股票代號後一欄
   - 所有含股票代號表格輸出時依股票代號升冪排序（僅輸出用，不影響選股/回測）
   - 技術分析_今日不顯示 forward returns（最新日必空），改顯示 Ret_1D_past/Ret_5D_past
   - 技術買點_今日空表仍保留欄位＋說明
   - 投組交易明細補公司名稱_來源

============================================================
【重要工程設計（避免 KPI 漂移）】
- df_sel：選股/回測使用（依 Score 排序）→ 不做輸出排序/欄位重排
- df_out：僅輸出 Excel 使用（排序/欄位）→ 不回寫影響 df_sel

============================================================
【B2 出場參數（沿用你選的 B2）】
STOP_LOSS = -4%
TAKE_PROFIT = +4%
EXIT_RSI = 60
HOLD_DAYS = 5

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

warnings.filterwarnings("ignore")

# ==========================================================
# 0) 參數區（可調）
# ==========================================================
TOP_N_FOR_TECH = 60
TECH_MONTHS = 12
OUT_FILE_PREFIX = "選股報表"

VERIFY_SSL = False
TIMEOUT = 30

TWSE_REQUEST_RETRIES = 3
TWSE_BACKOFF_BASE = 0.8
TWSE_SLEEP_SECONDS = 0.12

# ---- TopK 等權投組（v0.7.2-C）----
TOPK = 3  # 你選 C：Top3 等權

# ---- Gate（真的會用到）----
USE_FUNDAMENTAL_GATE = True
MIN_REV_YOY = 0.0
MIN_EPS_YOY = 0.0

# ---- B2 事件型出場參數 ----
STOP_LOSS = -0.04
TAKE_PROFIT = 0.04
EXIT_RSI = 60

# ---- 技術訊號參數（沿用）----
RSI_OVERSOLD = 40
OVERSOLD_LOOKBACK = 10
RSI_RECOVER = 40
RSI_AGGRESSIVE = 45
USE_AGGRESSIVE_SIGNAL = True

REQUIRE_TREND_FILTER = True
MA_SLOPE_DAYS = 3
MA20_TOLERANCE = 0.01
REQUIRE_VOLUME_FILTER = False

# ---- 回測/成本 ----
HOLD_DAYS = 5
ROUNDTRIP_COST_PCT = 0.004  # round-trip total cost
ENTRY_COST = ROUNDTRIP_COST_PCT / 2
EXIT_COST = ROUNDTRIP_COST_PCT / 2

# ---- Sharpe/Sortino ----
RISK_FREE_ANNUAL = 0.0
MAR_ANNUAL = 0.0
TRADING_DAYS = 252

# ---- 強勢股（表格用）----
STRONG_REVENUE_YOY = 10
STRONG_PE_MAX = 30
STRONG_PRICE_MIN = 10


# ==========================================================
# 1) Session
# ==========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.7.2-C",
    "Accept": "application/json,text/plain,*/*"
})


# ==========================================================
# 2) 通用工具
# ==========================================================
def find_col(cols, keywords):
    """欄位模糊匹配（避免欄位名變動）"""
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
    """requests 抓 CSV → pandas parse（mopsfin 憑證異常時 verify=False 救急）"""
    r = session.get(url, timeout=TIMEOUT, verify=VERIFY_SSL)
    r.raise_for_status()
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception as e:
            last_err = e
    raise RuntimeError(f"讀取失敗：{url}，最後錯誤：{last_err}")


def month_starts_back(n_months: int):
    """近 n 個月 YYYYMM01（含本月）"""
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
    """民國日期 '113/09/02' → date"""
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


# ==========================================================
# 3) 輸出格式（只用於 df_out，不影響 df_sel）
# ==========================================================
def format_for_output(df: pd.DataFrame, sort_by_code: bool = True) -> pd.DataFrame:
    """
    - 公司名稱_來源放在股票代號後一欄
    - 依股票代號升冪排序（只輸出用）
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
# 4) 今日快照：TWSE + TPEX
# ==========================================================
def fetch_prices():
    # TWSE
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    twse = pd.DataFrame(session.get(twse_url, timeout=TIMEOUT).json())

    code_col = find_col(twse.columns, ["證券代號", "Code"])
    close_col = find_col(twse.columns, ["收盤價", "ClosingPrice"])
    chg_col = find_col(twse.columns, ["漲跌價差", "Change"])
    name_col = find_col(twse.columns, ["證券名稱", "Name"])
    if code_col is None or close_col is None:
        raise RuntimeError(f"TWSE 欄位無法識別：{twse.columns}")

    twse = twse.rename(columns={
        code_col: "股票代號",
        close_col: "股價",
        chg_col: "漲跌",
        name_col: "公司名稱_來源"
    })

    # TPEX
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    tpex = pd.DataFrame(session.get(tpex_url, timeout=TIMEOUT).json())

    tpex_code = find_col(tpex.columns, ["SecuritiesCompanyCode", "股票代號", "Code"])
    tpex_close = find_col(tpex.columns, ["Close", "收盤", "ClosingPrice"])
    tpex_chg = find_col(tpex.columns, ["Change", "漲跌"])
    tpex_name = find_col(tpex.columns, ["CompanyName", "公司名稱", "Name"])
    if tpex_code is None or tpex_close is None:
        raise RuntimeError(f"TPEX 欄位無法識別：{tpex.columns}")

    tpex = tpex.rename(columns={
        tpex_code: "股票代號",
        tpex_close: "股價",
        tpex_chg: "漲跌",
        tpex_name: "公司名稱_來源"
    })

    price = pd.concat(
        [twse[["股票代號", "股價", "漲跌", "公司名稱_來源"]],
         tpex[["股票代號", "股價", "漲跌", "公司名稱_來源"]]],
        ignore_index=True
    )

    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    price = price.drop_duplicates("股票代號").reset_index(drop=True)
    return price


# ==========================================================
# 5) 營收：最新月
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


# ==========================================================
# 6) EPS：最新季 + YoY（raw + 顯示欄）
# ==========================================================
def fetch_eps_latest():
    urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv",
    ]
    eps = pd.concat([fetch_csv_requests(u) for u in urls], ignore_index=True)

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

    cur = eps[(eps["年度"] == latest_year) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    cur = cur.rename(columns={"EPS": "EPS本期"})

    prev = eps[(eps["年度"] == latest_year - 1) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].copy()
    prev = prev.rename(columns={"EPS": "EPS去年"})

    out = cur.merge(prev, on="股票代號", how="left")
    out["EPSYoY_raw"] = (out["EPS本期"] - out["EPS去年"]) / out["EPS去年"]
    out["EPSYoY_顯示(%)"] = (out["EPSYoY_raw"] * 100).replace([float("inf"), -float("inf")], 0).fillna(0)

    out["EPS季別"] = f"{int(latest_year)}Q{int(latest_q)}"
    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates("股票代號").reset_index(drop=True)


# ==========================================================
# 7) TWSE STOCK_DAY：容錯抓取
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


def fetch_twse_stock_day_month(stock_no: str, yyyymm01: str):
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}

    for attempt in range(1, TWSE_REQUEST_RETRIES + 1):
        try:
            r = session.get(url, params=params, timeout=TIMEOUT)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")

            js = safe_parse_json(r)
            if js is None:
                raise RuntimeError("Non-JSON response")

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

        except Exception:
            if attempt == TWSE_REQUEST_RETRIES:
                return pd.DataFrame()
            time.sleep(TWSE_BACKOFF_BASE * attempt)

    return pd.DataFrame()


def fetch_twse_history(codes, months=TECH_MONTHS):
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
# 8) 技術指標 + 買點（三段式）
# ==========================================================
def calc_tech_indicators(df_hist):
    df_hist = df_hist.sort_values("Date").copy()

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

    # 過去報酬（輸出用）
    df_hist["Ret_1D_past(%)"] = df_hist["Close"].pct_change(1) * 100
    df_hist["Ret_5D_past(%)"] = df_hist["Close"].pct_change(5) * 100

    return df_hist


def run_tech_and_backtest(codes):
    """產出 tech_all / tech_today / buy_today"""
    hist = fetch_twse_history(codes, months=TECH_MONTHS)
    if hist.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_tech_indicators(g)
        g2["股票代號"] = str(code).strip()
        parts.append(g2)

    tech_all = pd.concat(parts, ignore_index=True)
    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()
    return tech_all, tech_today, buy_today


# ==========================================================
# 9) 事件型出場（回傳原因）
# ==========================================================
def event_exit_return(path_df: pd.DataFrame, entry_idx: int):
    entry_price = float(path_df.loc[entry_idx, "Close"])
    last_idx = min(entry_idx + HOLD_DAYS, len(path_df) - 1)

    exit_idx = last_idx
    gross_ret = float(path_df.loc[last_idx, "Close"]) / entry_price - 1.0
    reason = "TIME_EXIT"

    for j in range(entry_idx + 1, last_idx + 1):
        px = float(path_df.loc[j, "Close"])
        rsi = float(path_df.loc[j, "RSI"]) if pd.notna(path_df.loc[j, "RSI"]) else None
        ret = px / entry_price - 1.0

        if ret <= STOP_LOSS:
            exit_idx, gross_ret, reason = j, ret, "STOP_LOSS"
            break
        if ret >= TAKE_PROFIT:
            exit_idx, gross_ret, reason = j, ret, "TAKE_PROFIT"
            break
        if rsi is not None and rsi >= EXIT_RSI:
            exit_idx, gross_ret, reason = j, ret, "RSI_EXIT"
            break

    net_ret = (1.0 + gross_ret) * (1.0 - ROUNDTRIP_COST_PCT) - 1.0
    return exit_idx, gross_ret, net_ret, reason
# ==========================================================
# 10) KPI 工具
# ==========================================================
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


def annualize_sharpe(daily_returns, rf_annual=0.0):
    r = pd.Series(daily_returns).dropna()
    if len(r) < 10:
        return None
    rf_d = rf_annual / TRADING_DAYS
    mu = (r.mean() - rf_d) * TRADING_DAYS
    sigma = r.std(ddof=1) * (TRADING_DAYS ** 0.5)
    if sigma == 0:
        return None
    return float(mu / sigma)


def annualize_sortino(daily_returns, mar_annual=0.0):
    r = pd.Series(daily_returns).dropna()
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


# ==========================================================
# 11) Signal-level：事件型回測
# ==========================================================
def signal_level_backtest_event(tech_all: pd.DataFrame):
    if tech_all is None or tech_all.empty:
        return pd.DataFrame()

    returns_net = []
    for code, g in tech_all.groupby("股票代號", sort=False):
        g = g.sort_values("Date").reset_index(drop=True)
        sig_idx = g.index[g["買點"] == True].tolist()
        if not sig_idx:
            continue
        for idx in sig_idx:
            _, _, net_ret, _ = event_exit_return(g, idx)
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


# ==========================================================
# 12) Portfolio-level：TopK 等權投組（v0.7.2-C）
# ==========================================================
def portfolio_backtest_topk_event(tech_all: pd.DataFrame, score_map: dict, gate_map: dict):
    """
    TopK 等權投組（K=TOPK）：
    - 僅在空手時進場：當天買點候選挑 Score 前 K 檔等權進場
    - 每個持倉獨立事件型出場（停損/停利/RSI/時間）
    - equity = cash + sum(shares * price)
    - entry/exit 各扣一半成本（ENTRY_COST/EXIT_COST）
    """
    if tech_all is None or tech_all.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = tech_all[["Date", "股票代號", "Close", "買點", "RSI"]].copy()
    df = df.dropna(subset=["Date", "Close"])

    # 代號/score_map key 統一，避免 Score 全 NaN
    df["股票代號"] = df["股票代號"].astype(str).str.strip()
    score_map = {str(k).strip(): v for k, v in score_map.items()}
    df["Score"] = df["股票代號"].map(score_map).fillna(-1e18)

    # 每檔價格序列（用於當日估值/出場）
    by_code = {c: g.sort_values("Date").reset_index(drop=True) for c, g in df.groupby("股票代號")}
    all_dates = sorted(df["Date"].unique())

    cash = 1.0
    positions = {}  # code -> dict(shares, entry_price, entry_date, entry_idx)
    equity_rows = []
    trade_rows = []

    for d in all_dates:
        d = pd.to_datetime(d)

        # ---------- 出場檢查（逐筆持倉） ----------
        to_close = []
        for code, pos in positions.items():
            g = by_code.get(code)
            if g is None:
                continue
            idx_list = g.index[g["Date"] == d].tolist()
            if not idx_list:
                continue

            cur_idx = idx_list[0]
            entry_idx = pos["entry_idx"]
            entry_price = pos["entry_price"]

            # 只有在持有窗內才檢查（不然就是已超過，等同 TIME_EXIT）
            if cur_idx > min(entry_idx + HOLD_DAYS, len(g) - 1):
                cur_idx = min(entry_idx + HOLD_DAYS, len(g) - 1)

            px = float(g.loc[cur_idx, "Close"])
            rsi = float(g.loc[cur_idx, "RSI"]) if pd.notna(g.loc[cur_idx, "RSI"]) else None
            ret = px / entry_price - 1.0

            reason = None
            if ret <= STOP_LOSS:
                reason = "STOP_LOSS"
            elif ret >= TAKE_PROFIT:
                reason = "TAKE_PROFIT"
            elif (rsi is not None) and (rsi >= EXIT_RSI):
                reason = "RSI_EXIT"
            elif cur_idx == min(entry_idx + HOLD_DAYS, len(g) - 1):
                reason = "TIME_EXIT"

            if reason is not None:
                to_close.append((code, px, ret, reason))

        # 執行出場（收回現金）
        for code, px, ret, reason in to_close:
            pos = positions.pop(code)
            shares = pos["shares"]

            proceeds = shares * px
            proceeds *= (1.0 - EXIT_COST)  # 出場成本
            cash += proceeds

            net_ret = (1.0 + ret) * (1.0 - ROUNDTRIP_COST_PCT) - 1.0
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

        # ---------- 進場（只有空手才建倉） ----------
        if len(positions) == 0:
            cand = df[(df["Date"] == d) & (df["買點"] == True)].copy()

            if USE_FUNDAMENTAL_GATE:
                cand["GateOK"] = cand["股票代號"].map(gate_map).fillna(False)
                cand = cand[cand["GateOK"] == True].copy()

            if not cand.empty:
                cand = cand.sort_values("Score", ascending=False).head(TOPK)

                # 等權投入：每檔投入 cash / K
                k = len(cand)
                if k > 0:
                    alloc_each = cash / k
                    cash = 0.0

                    for _, row in cand.iterrows():
                        code = str(row["股票代號"]).strip()
                        g = by_code.get(code)
                        if g is None:
                            cash += alloc_each  # 無資料退回現金
                            continue

                        idx_list = g.index[g["Date"] == d].tolist()
                        if not idx_list:
                            cash += alloc_each
                            continue

                        entry_idx = idx_list[0]
                        entry_price = float(g.loc[entry_idx, "Close"])

                        # 進場成本
                        alloc_after_cost = alloc_each * (1.0 - ENTRY_COST)
                        shares = alloc_after_cost / entry_price if entry_price > 0 else 0.0

                        positions[code] = {
                            "shares": shares,
                            "entry_price": entry_price,
                            "entry_date": d,
                            "entry_idx": entry_idx
                        }

        # ---------- 計算每日 Equity ----------
        equity = cash
        for code, pos in positions.items():
            g = by_code.get(code)
            if g is None:
                continue
            cur = g[g["Date"] == d]
            if cur.empty:
                # 若當天無價，使用上次價（簡化：用 entry_price）
                px = pos["entry_price"]
            else:
                px = float(cur.iloc[0]["Close"])
            equity += pos["shares"] * px

        equity_rows.append({"Date": d, "Equity": equity})

    eq = pd.DataFrame(equity_rows).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    trades = pd.DataFrame(trade_rows)

    # KPI
    eq["Ret"] = eq["Equity"].pct_change()
    eq["Peak"] = eq["Equity"].cummax()
    eq["Drawdown"] = eq["Equity"] / eq["Peak"] - 1
    mdd = eq["Drawdown"].min()

    sharpe = annualize_sharpe(eq["Ret"], rf_annual=RISK_FREE_ANNUAL)
    sortino = annualize_sortino(eq["Ret"], mar_annual=MAR_ANNUAL)

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

    return eq, trades, kpi


# ==========================================================
# 13) Excel 美化（正確版，不含 wscell）
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
    """表頭深藍底白字、置中（正確版本）"""
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)

    # ws[header_row] 代表該列所有 cell（tuple）
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
# 14) 主流程
# ==========================================================
def main():
    print("1) 下載股價（TWSE+TPEX）...")
    price = fetch_prices()

    print("2) 下載最新月營收（mopsfin L+O；暫時跳過 SSL 驗證）...")
    rev_latest = fetch_revenue_latest()

    print("3) 下載最新EPS（mopsfin L+O；暫時跳過 SSL 驗證）...")
    eps_latest = fetch_eps_latest()

    print("4) 合併基本面資料...")
    # df_sel：選股/回測用（Score排序）
    df_sel = price.merge(rev_latest, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_latest, on="股票代號", how="left")
    df_sel["股票代號"] = df_sel["股票代號"].astype(str).str.strip()

    # 指標
    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # Score（raw NaN 視為 0）
    df_sel["Score"] = (
        df_sel["營收YoY(%)"].fillna(0) * 0.35 +
        (df_sel["EPSYoY_raw"].fillna(0) * 100) * 0.35 +
        df_sel["殖利率(估)"].fillna(0) * 100 * 0.20 -
        df_sel["PE"].fillna(0) * 0.05
    )
    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

    # Gate map（EPSYoY_raw 缺值放行，避免全滅）
    gate_series = (
        (df_sel["營收YoY(%)"].fillna(0) > MIN_REV_YOY) &
        (
            (df_sel["EPSYoY_raw"].fillna(0) > MIN_EPS_YOY) |
            (df_sel["EPSYoY_raw"].isna())
        )
    )
    gate_map = dict(zip(df_sel["股票代號"], gate_series.astype(bool)))

    # 表格：強勢股 / Top10（不影響回測）
    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > STRONG_REVENUE_YOY) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < STRONG_PE_MAX) &
        (df_sel["股價"] > STRONG_PRICE_MIN)
    ].copy()
    top10_sel = df_sel.head(10).copy()

    print(f"5) 抓歷史日K（TWSE STOCK_DAY）Top{TOP_N_FOR_TECH}（不使用Yahoo）...")
    tech_codes = df_sel.head(TOP_N_FOR_TECH)["股票代號"].dropna().tolist()
    tech_all, tech_today, buy_today = run_tech_and_backtest(tech_codes)

    # v0.7.2-C：Signal-level 仍用事件型
    sig_summary = signal_level_backtest_event(tech_all)

    # v0.7.2-C：Portfolio-level 改 TopK 等權
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi = portfolio_backtest_topk_event(tech_all, score_map, gate_map)

    # ========= 輸出用 df_out（格式不影響回測） =========
    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    df_out_all = format_for_output(df_sel.copy(), sort_by_code=True)
    strong_out = format_for_output(strong_sel.copy(), sort_by_code=True)
    top10_out = format_for_output(top10_sel.copy(), sort_by_code=True)

    eps_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    # 技術分析_今日（補公司名 + EPSYoY顯示）
    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_disp_map)
        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    # 技術買點_今日（空表保留）
    if buy_today is None or buy_today.empty:
        buy_today_out = tech_today_out.head(0).copy() if tech_today_out is not None and not tech_today_out.empty else pd.DataFrame()
    else:
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_disp_map)
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)

    # 投組交易明細（補公司名）
    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "出場原因", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades_out = trades.merge(name_map, on="股票代號", how="left")
        trades_out = format_for_output(trades_out, sort_by_code=True)

    tech_explain = [
        "【技術分析_今日】說明",
        f"v0.7.2-C：投組為 Top{TOPK} 等權（僅空手時進場），事件型出場（SL-4%, TP+4%, RSI>=60, <=5日）。",
        "本表顯示 Ret_1D_past/Ret_5D_past（過去報酬），避免最新日空欄位。",
    ]
    buy_explain = [
        "【技術買點_今日】說明",
        "本表列出今日符合買點規則的股票；若為空表代表今日無訊號（非錯誤）。"
    ]
    bt_explain = [
        "【回測摘要】說明（v0.7.2-C）",
        f"Portfolio-level：Top{TOPK} 等權投組，事件型出場。",
        "Gate：營收YoY>0 且 EPSYoY>0（EPSYoY缺值放行避免全滅）。"
    ]

    out_file = f"{OUT_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)
        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)

        summary_sheet = pd.concat(
            [pd.DataFrame([{"區塊": "Signal-level(v0.7.2_event_exit)"}]), sig_summary,
             pd.DataFrame([{"區塊": f"Portfolio-level(v0.7.2_Top{TOPK}_EqualWeight)"}]), pf_kpi],
            ignore_index=True
        )
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        eq.to_excel(writer, index=False, sheet_name="投組回測_TopK等權", startrow=startrow)
        trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)

        ws_tech = writer.sheets["技術分析_今日"]
        ws_buy = writer.sheets["技術買點_今日"]
        ws_sum = writer.sheets["回測摘要"]

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

    print("✅ Signal-level KPI（v0.7.2 事件型）:")
    print(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    print(f"✅ Portfolio-level KPI（v0.7.2 Top{TOPK} 等權）:")
    print(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")
    print(f"✅ 完成 → {out_file}")

    if not VERIFY_SSL:
        print("⚠️ 注意：mopsfin 憑證異常期間，本程式暫用 verify=False（短期救急用）。")


if __name__ == "__main__":
    main()