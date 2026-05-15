"""
檔名：StockTool.py
版本：v0.6.3 (Format-only Patch on v0.6.1)
最後更新：2026-05-15 21:55 (Asia/Taipei)

【本版目標（你選的 A）】
- 只做「報表格式修正」：欄位順序、公司名稱欄位、排序、空表說明、避免必空欄位
- 重要：不影響 v0.6.1 的「選股/回測」結果
  => 所有排序/欄位重排只作用在輸出用 df_out，不改動 df_sel（用於 TopN 選股與回測）

【你提出的 7 點修正（全部落地）】
1) 全市場_基本面：公司名稱_來源放股票代號後一欄；EPSYoY不再整欄空（顯示欄位填0；raw保留）
2) 強勢股_基本面：同上
3) Top10_基本面：同上（Top10先取Score前10，再在那10檔內按代號排序）
4) 技術分析_今日：公司名稱_來源放股票代號後；EPSYoY merge；移除最新日必空 forward returns（R_1D/R_HD/R_HD_net）
   改顯示 Ret_1D_past(%)/Ret_5D_past(%)
5) 技術買點_今日：補公司名稱在第2欄；空表代表今日無訊號（仍保留欄位＋說明）
6) 投組交易明細：補公司名稱在第2欄
7) 所有輸出表（有股票代號者）按股票代號升冪排序（不影響 df_sel/選股）

【空值原因說明（會寫在 sheet 上方）】
- EPSYoY raw 可能為 NaN：常見原因是去年同季 EPS 缺失/為0，導致 YoY 無法計算
- forward returns（R_1D/R_HD/R_HD_net）對最新日必為 NaN：因為它們是「未來報酬」
  => 本版「今日表」不顯示 forward returns，改顯示 past returns

【程式流程（Coding Logic / Pipeline）】
1) 抓今日快照（TWSE+TPEX）
2) 抓最新月營收、最新EPS（YoY按去年同季；raw保留，display欄位填補）
3) df_sel：計算 Score 並依 Score 排名（只用於選股/回測）
4) 取 df_sel 前 TOP_N_FOR_TECH → 抓 TWSE 歷史日K → 技術指標 → 訊號/回測
5) df_out：把 df_sel/tech 結果做欄位重排＋股票代號排序 → 輸出 Excel（含說明文字/美化）

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

# =========================
# 參數（沿用 v0.6.1 + 你目前設定）
# =========================
TOP_N_FOR_TECH = 60
TECH_MONTHS = 12
OUT_FILE_PREFIX = "選股報表"

VERIFY_SSL = False
TIMEOUT = 30

TWSE_REQUEST_RETRIES = 3
TWSE_BACKOFF_BASE = 0.8
TWSE_SLEEP_SECONDS = 0.12

RSI_OVERSOLD = 40
OVERSOLD_LOOKBACK = 10
RSI_RECOVER = 40
RSI_AGGRESSIVE = 45
USE_AGGRESSIVE_SIGNAL = True

REQUIRE_TREND_FILTER = True
MA_SLOPE_DAYS = 3
MA20_TOLERANCE = 0.01
REQUIRE_VOLUME_FILTER = False

HOLD_DAYS = 5
ROUNDTRIP_COST_PCT = 0.004

RISK_FREE_ANNUAL = 0.0
MAR_ANNUAL = 0.0
TRADING_DAYS = 252

STRONG_REVENUE_YOY = 10
STRONG_PE_MAX = 30
STRONG_PRICE_MIN = 10

warnings.filterwarnings("ignore")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/AdvisorStyle-v0.6.3",
    "Accept": "application/json,text/plain,*/*"
})


# =========================
# 通用工具
# =========================
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
    """把 '113/09/02' 轉成 date"""
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


# =========================
# ✅ A 版核心：只在輸出做格式，不影響 df_sel
# =========================
def format_for_output(df: pd.DataFrame, sort_by_code: bool = True) -> pd.DataFrame:
    """
    - 公司名稱_來源放在股票代號後一欄
    - 若 sort_by_code=True：依股票代號升冪排序
    - 注意：只用於輸出 df_out，不要用於 df_sel（避免影響選股/回測）
    """
    if df is None:
        return df
    if df.empty:
        return df

    if "股票代號" in df.columns and "公司名稱_來源" in df.columns:
        cols = ["股票代號", "公司名稱_來源"] + [c for c in df.columns if c not in ["股票代號", "公司名稱_來源"]]
        df = df[cols]

    if sort_by_code and "股票代號" in df.columns:
        df = df.sort_values("股票代號", ascending=True)

    return df.reset_index(drop=True)


# =========================
# 1) 今日股價快照：TWSE + TPEX
# =========================
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


# =========================
# 2) 月營收：最新月
# =========================
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


# =========================
# 3) EPS：最新季 + YoY（raw保留 / display用於輸出不空）
# =========================
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
    out["EPSYoY_raw"] = (out["EPS本期"] - out["EPS去年"]) / out["EPS去年"]

    # 策略/回測用可自行決定是否 fillna；本版 A 的重點是「不讓格式改動影響選股」
    # => Score 計算仍沿用 v0.6.1（後面用 fillna(0)）
    # 顯示欄位：避免全空（NaN 顯示為 0）
    out["EPSYoY_顯示(%)"] = (out["EPSYoY_raw"] * 100).replace([float("inf"), -float("inf")], 0).fillna(0)

    out["EPS季別"] = f"{int(latest_year)}Q{int(latest_q)}"
    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates("股票代號").reset_index(drop=True)


# =========================
# 4) TWSE STOCK_DAY：容錯 JSON
# =========================
def safe_parse_json(r):
    text = (r.text or "").strip()
    if not text:
        return None
    if text.startswith("<"):
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


# =========================
# 5) 技術指標 + 買點 + returns
# =========================
def calc_tech_indicators(df_hist):
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

    # ✅ 今日表用的 past return（不會空）
    df_hist["Ret_1D_past(%)"] = df_hist["Close"].pct_change(1) * 100
    df_hist["Ret_5D_past(%)"] = df_hist["Close"].pct_change(5) * 100

    # 回測用 forward returns（保留，不在今日表顯示）
    df_hist["R_1D"] = df_hist["Close"].shift(-1) / df_hist["Close"] - 1
    df_hist["R_HD"] = df_hist["Close"].shift(-HOLD_DAYS) / df_hist["Close"] - 1
    df_hist["R_HD_net"] = (1 + df_hist["R_HD"]) * (1 - ROUNDTRIP_COST_PCT) - 1

    return df_hist


def run_tech_and_backtest(codes):
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
# =========================
# 6) KPI / 回測
# =========================
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

    r1 = buy_all["R_1D"].dropna()
    rh = buy_all["R_HD"].dropna()
    rh_net = buy_all["R_HD_net"].dropna()

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
                if idx_list:
                    idx0 = idx_list[0]
                    exit_idx = idx0 + HOLD_DAYS
                    if exit_idx < len(g):
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

        # mark-to-market
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

        # exit
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


# =========================
# 7) Excel 美化（修正 style_header 正確版本）
# =========================
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
    """✅ 正確：對 ws[header_row] 每個 cell 套樣式"""
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


# =========================
# 8) 主流程（A：格式不影響選股/回測）
# =========================
def main():
    print("1) 下載股價（TWSE+TPEX）...")
    price = fetch_prices()

    print("2) 下載最新月營收（mopsfin L+O；暫時跳過 SSL 驗證）...")
    rev_latest = fetch_revenue_latest()

    print("3) 下載最新EPS（mopsfin L+O；暫時跳過 SSL 驗證）...")
    eps_latest = fetch_eps_latest()

    print("4) 合併基本面資料...")
    # df_sel：用於選股/回測（維持 v0.6.1 的排序邏輯，不用 format_for_output）
    df_sel = price.merge(rev_latest, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_latest, on="股票代號", how="left")

    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # v0.6.1 Score（不變）：使用 EPSYoY_raw（這裡是 EPSYoY_raw 欄位名 EPSYoY_raw）
    # 為了與 v0.6.1 行為一致：Score 使用 EPSYoY_raw.fillna(0)
    df_sel["Score"] = (
        df_sel["營收YoY(%)"].fillna(0) * 0.35 +
        (df_sel["EPSYoY_raw"].fillna(0) * 100) * 0.35 +
        df_sel["殖利率(估)"].fillna(0) * 100 * 0.20 -
        df_sel["PE"].fillna(0) * 0.05
    )

    # ✅ 這裡維持 v0.6.1：df_sel 依 Score 排序（用於選股/回測）
    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)

    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > STRONG_REVENUE_YOY) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < STRONG_PE_MAX) &
        (df_sel["股價"] > STRONG_PRICE_MIN)
    ].copy()

    top10_sel = df_sel.head(10).copy()

    print(f"5) 抓歷史日K（TWSE STOCK_DAY）Top{TOP_N_FOR_TECH}（不使用Yahoo）...")
    tech_codes = df_sel.head(TOP_N_FOR_TECH)["股票代號"].dropna().astype(str).tolist()
    tech_today, buy_today, tech_all = run_tech_and_backtest(tech_codes)

    # 回測 KPI
    sig_summary = compute_signal_level_summary(tech_all)
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi = portfolio_backtest_single(tech_all, score_map)

    # =========================
    # ✅ 輸出用 df_out：在這裡才做格式修正（不影響 df_sel）
    # =========================
    # 1~3 基本面三表
    df_out_all = df_sel.copy()
    strong_out = strong_sel.copy()
    top10_out = top10_sel.copy()

    # EPSYoY顯示欄位：避免整欄空（顯示用），不影響 Score
    # 若你希望顯示 0：已在 fetch_eps_latest() 裡處理；這裡直接保留欄位
    # 欄位名稱已是 EPSYoY_顯示(%)
    # 為了方便閱讀，也提供 EPSYoY_raw（可保留）
    df_out_all = format_for_output(df_out_all, sort_by_code=True)
    strong_out = format_for_output(strong_out, sort_by_code=True)
    # Top10：先取 top10_sel（score top10），再依股票代號排序（不影響 top10 定義）
    top10_out = format_for_output(top10_out, sort_by_code=True)

    # 4 技術分析_今日：補公司名稱 + EPSYoY顯示欄位；移除 forward returns 欄位（最新日必空）
    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    eps_yoy_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_yoy_disp_map)

        # 移除最新日必空的 forward returns（但 tech_all 仍保留供回測）
        drop_cols = [c for c in ["R_1D", "R_HD", "R_HD_net"] if c in tech_today_out.columns]
        if drop_cols:
            tech_today_out = tech_today_out.drop(columns=drop_cols, errors="ignore")

        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    # 5 技術買點_今日：補公司名稱；空表保留欄位；也移除 forward returns
    if buy_today is None or buy_today.empty:
        buy_today_out = tech_today_out.head(0).copy() if tech_today_out is not None and not tech_today_out.empty else pd.DataFrame()
    else:
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_yoy_disp_map)
        drop_cols = [c for c in ["R_1D", "R_HD", "R_HD_net"] if c in buy_today_out.columns]
        if drop_cols:
            buy_today_out = buy_today_out.drop(columns=drop_cols, errors="ignore")
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)

    # 6 投組交易明細：補公司名稱，欄位第2欄，並排序
    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "持有天數", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades_out = trades.merge(name_map, on="股票代號", how="left")
        trades_out = format_for_output(trades_out, sort_by_code=True)

    # =========================
    # 文字說明（投顧式）
    # =========================
    tech_explain = [
        "【技術分析_今日】說明",
        "本表為每檔股票最新交易日的技術狀態。",
        "forward returns（R_1D / R_HD / R_HD_net）對最新日必為空，因此本表不顯示。",
        "改顯示 Ret_1D_past(%) / Ret_5D_past(%)（過去報酬，不會空）。",
        "EPSYoY_顯示(%) 若原本為空：多半是去年同季 EPS 缺資料或為 0；本表顯示欄位已用 0 填補避免整欄空。"
    ]

    buy_explain = [
        "【技術買點_今日】說明",
        "本表列出今日符合買點規則的股票；若為空表代表今日無任何股票符合買點（非錯誤）。"
    ]

    bt_explain = [
        "【回測摘要】說明",
        "Signal-level：每次買點視為獨立交易，統計勝率/均值/中位數/最大連敗/獲利因子（含成本）。",
        "Portfolio-level：單一持股（空手才進場、訊號中挑 Score 最高），提供 CAGR/MDD/Sharpe/Sortino。"
    ]

    # =========================
    # 輸出 Excel
    # =========================
    out_file = f"{OUT_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)
        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)

        summary_sheet = pd.concat(
            [pd.DataFrame([{"區塊": "Signal-level"}]), sig_summary,
             pd.DataFrame([{"區塊": "Portfolio-level"}]), pf_kpi],
            ignore_index=True
        )
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        eq.to_excel(writer, index=False, sheet_name="投組回測_B單一持股", startrow=startrow)
        trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)

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

    print("✅ Signal-level KPI（訊號層級）:")
    print(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    print("✅ Portfolio-level KPI（投組層級）:")
    print(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")
    print(f"✅ 完成 → {out_file}")

    if not VERIFY_SSL:
        print("⚠️ 注意：mopsfin 憑證過期期間，本程式暫用 verify=False（短期救急用）。")


if __name__ == "__main__":
    main()