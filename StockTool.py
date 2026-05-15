import io
import time
import warnings
from datetime import datetime, date

import pandas as pd
import requests

# =========================
# 參數區
# =========================
TOP_N_FOR_TECH = 30          # 對基本面 Top N 做技術分析（TWSE 歷史）
TECH_MONTHS = 9              # 技術面抓近幾個月
OUT_FILE_PREFIX = "選股報表"

# mopsfin 憑證過期：暫用 verify=False（短期救急；有安全風險）
VERIFY_SSL = False
TIMEOUT = 30

# 買點模式：保守 + 積極（避免永遠 0 訊號）
USE_AGGRESSIVE_SIGNAL = True

warnings.filterwarnings("ignore")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/6.1"
})

# =========================
# 小工具
# =========================
def find_col(cols, keywords):
    for c in cols:
        s = str(c)
        for k in keywords:
            if k in s:
                return c
    return None

def to_num_series(s):
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("+", "", regex=False)
         .str.strip(),
        errors="coerce"
    )

def fetch_csv_requests(url, encodings=("utf-8-sig", "utf-8")):
    r = session.get(url, timeout=TIMEOUT, verify=VERIFY_SSL)
    r.raise_for_status()

    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(
                io.BytesIO(r.content),
                encoding=enc,
                engine="python",
                on_bad_lines="skip"
            )
        except Exception as e:
            last_err = e

    raise RuntimeError(f"讀取失敗：{url}，最後錯誤：{last_err}")

def month_starts_back(n_months: int):
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

# =========================
# 1) 今日股價：TWSE + TPEX（基本面用）
# =========================
def fetch_prices():
    # TWSE（上市快照）
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

    # TPEX（上櫃快照）
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
        [
            twse[["股票代號", "股價", "漲跌", "公司名稱_來源"]],
            tpex[["股票代號", "股價", "漲跌", "公司名稱_來源"]],
        ],
        ignore_index=True
    )

    price["股票代號"] = price["股票代號"].astype(str).str.strip()
    price["股價"] = pd.to_numeric(price["股價"], errors="coerce")
    price["漲跌"] = pd.to_numeric(price["漲跌"], errors="coerce")
    price = price.drop_duplicates(subset=["股票代號"], keep="first").reset_index(drop=True)
    return price

# =========================
# 2) 月營收：mopsfin L + O（暫時 verify=False）
# =========================
def fetch_revenue_latest():
    rev_urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv",
    ]
    frames = [fetch_csv_requests(u) for u in rev_urls]
    rev = pd.concat(frames, ignore_index=True)

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

    out = rev[["股票代號", "年月", "當月營收(億元)", "營收YoY(%)"]].drop_duplicates("股票代號")
    return out.reset_index(drop=True)

# =========================
# 3) EPS：mopsfin L + O（暫時 verify=False）
# =========================
def fetch_eps_latest():
    eps_urls = [
        "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
        "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv",
    ]
    frames = [fetch_csv_requests(u) for u in eps_urls]
    eps = pd.concat(frames, ignore_index=True)

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
    out = out.drop_duplicates(subset=["股票代號"], keep="first").reset_index(drop=True)

    # ✅✅✅ 這裡是你剛剛 SyntaxError 的修正點（補上 ] ）
    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY"]]

# =========================
# 4) 技術面（TWSE STOCK_DAY）
# =========================
def fetch_twse_stock_day_month(stock_no: str, yyyymm01: str):
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}
    r = session.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    js = r.json()

    if js.get("stat") != "OK" or "data" not in js:
        return pd.DataFrame()

    fields = js.get("fields", [])
    data = js.get("data", [])
    if not fields or not data:
        return pd.DataFrame()

    dfm = pd.DataFrame(data, columns=fields)

    date_col = find_col(dfm.columns, ["日期"])
    open_col = find_col(dfm.columns, ["開盤價"])
    high_col = find_col(dfm.columns, ["最高價"])
    low_col = find_col(dfm.columns, ["最低價"])
    close_col = find_col(dfm.columns, ["收盤價"])

    if date_col is None or close_col is None:
        return pd.DataFrame()

    dfm = dfm.rename(columns={
        date_col: "Date_roc",
        open_col: "Open",
        high_col: "High",
        low_col: "Low",
        close_col: "Close",
    })

    dfm["Date"] = dfm["Date_roc"].apply(roc_to_ad)
    dfm["Date"] = pd.to_datetime(dfm["Date"])
    dfm["股票代號"] = str(stock_no).strip()

    for c in ["Open", "High", "Low", "Close"]:
        if c in dfm.columns:
            dfm[c] = to_num_series(dfm[c])

    dfm = dfm.dropna(subset=["Date", "Close"]).copy()
    return dfm[["Date", "股票代號", "Open", "High", "Low", "Close"]].copy()

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
            time.sleep(0.15)

        if frames:
            dfh = pd.concat(frames, ignore_index=True)
            dfh = dfh.drop_duplicates(subset=["Date"]).sort_values("Date")
            all_frames.append(dfh)

        if i % 10 == 0:
            print(f"   技術面歷史抓取進度：{i}/{len(codes)}")

    if not all_frames:
        return pd.DataFrame()

    hist = pd.concat(all_frames, ignore_index=True)
    hist = hist.sort_values(["股票代號", "Date"]).reset_index(drop=True)
    return hist

def calc_tech_indicators(df_hist):
    df_hist = df_hist.sort_values("Date").copy()

    df_hist["MA5"] = df_hist["Close"].rolling(5).mean()
    df_hist["MA20"] = df_hist["Close"].rolling(20).mean()

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

    df_hist["MACD_cross_up"] = (df_hist["MACD"] > df_hist["MACD_signal"]) & \
                              (df_hist["MACD"].shift(1) <= df_hist["MACD_signal"].shift(1))
    df_hist["BullTrend"] = df_hist["MA5"] > df_hist["MA20"]

    if USE_AGGRESSIVE_SIGNAL:
        df_hist["買點"] = (df_hist["RSI"] < 45) & (df_hist["MACD_hist"] > 0) & (df_hist["MA5"] >= df_hist["MA20"])
    else:
        df_hist["買點"] = (df_hist["RSI"] < 35) & df_hist["MACD_cross_up"] & df_hist["BullTrend"]

    df_hist["R_1D"] = df_hist["Close"].shift(-1) / df_hist["Close"] - 1
    df_hist["R_5D"] = df_hist["Close"].shift(-5) / df_hist["Close"] - 1
    return df_hist

def run_tech_and_backtest(codes):
    hist = fetch_twse_history(codes, months=TECH_MONTHS)
    if hist.empty:
        tech_today = pd.DataFrame()
        buy_today = pd.DataFrame()
        backtest_summary = pd.DataFrame([{
            "訊號數": 0, "1日平均報酬(%)": None, "5日平均報酬(%)": None, "5日勝率(%)": None, "5日中位數報酬(%)": None
        }])
        return tech_today, buy_today, backtest_summary

    parts = []
    for code, g in hist.groupby("股票代號", sort=False):
        g2 = calc_tech_indicators(g)
        g2["股票代號"] = code
        parts.append(g2)

    tech_all = pd.concat(parts, ignore_index=True)

    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()

    buy_all = tech_all[tech_all["買點"] == True].copy()
    r1 = buy_all["R_1D"].dropna()
    r5 = buy_all["R_5D"].dropna()

    backtest_summary = pd.DataFrame([{
        "訊號數": int(len(buy_all)),
        "1日平均報酬(%)": round(r1.mean() * 100, 2) if len(r1) else None,
        "5日平均報酬(%)": round(r5.mean() * 100, 2) if len(r5) else None,
        "5日勝率(%)": round((r5 > 0).mean() * 100, 2) if len(r5) else None,
        "5日中位數報酬(%)": round(r5.median() * 100, 2) if len(r5) else None
    }])
    return tech_today, buy_today, backtest_summary

# =========================
# 主流程
# =========================
def main():
    print("1) 下載股價（TWSE+TPEX）...")
    price = fetch_prices()

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
        (df["營收YoY(%)"] > 10) &
        (df["EPS本期"] > 0) &
        (df["PE"] < 30) &
        (df["股價"] > 10)
    ].copy()
    top10 = df.head(10).copy()

    print(f"5) 抓歷史日K（TWSE STOCK_DAY）Top{TOP_N_FOR_TECH}（不使用Yahoo）...")
    tech_codes = df.head(TOP_N_FOR_TECH)["股票代號"].dropna().astype(str).tolist()
    tech_today, buy_today, backtest_summary = run_tech_and_backtest(tech_codes)

    print("✅ 技術回測摘要：")
    print(backtest_summary.to_string(index=False))

    out_file = f"{OUT_FILE_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10.to_excel(writer, index=False, sheet_name="Top10_基本面")
        tech_today.to_excel(writer, index=False, sheet_name="技術分析_今日")
        buy_today.to_excel(writer, index=False, sheet_name="技術買點_今日")
        backtest_summary.to_excel(writer, index=False, sheet_name="回測摘要")

    print(f"✅ 完成 → {out_file}")
    if not VERIFY_SSL:
        print("⚠️ 注意：mopsfin 憑證過期期間，本程式暫用 verify=False 下載公開資料（短期救急用）。")

if __name__ == "__main__":
    main()