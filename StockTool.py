import pandas as pd
import requests
from datetime import datetime

# ===== 1) 公司清單 =====
companies = [
    ("2317","鴻海"),("2382","廣達"),("3231","緯創"),("6669","緯穎"),
    ("2356","英業達"),("4938","和碩"),("2376","技嘉"),("2357","華碩"),
    ("2330","台積電"),("2308","台達電"),("1101","台泥"),("1504","東元")
]

df_comp = pd.DataFrame(companies, columns=["股票代號","公司名称"])

# ===== 2) 股價 (TWSE) =====
twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
twse = pd.DataFrame(requests.get(twse_url).json())
#=========================
twse = pd.DataFrame(requests.get(twse_url).json())

twse = pd.DataFrame(requests.get(twse_url).json())

print("TWSE欄位:", twse.columns)

# ✅ 同時支援中英文欄位
def find_col(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None

code_col = find_col(twse.columns, ["證券代號", "Code"])
price_col = find_col(twse.columns, ["收盤價", "ClosingPrice"])
change_col = find_col(twse.columns, ["漲跌價差", "Change"])

if code_col is None or price_col is None:
    raise Exception(f"❌ 無法識別欄位: {twse.columns}")

twse = twse.rename(columns={
    code_col: "股票代號",
    price_col: "股價",
    change_col: "漲跌"
})

# 型別處理
twse["股票代號"] = twse["股票代號"].astype(str).str.strip()
twse["股價"] = pd.to_numeric(twse["股價"], errors="coerce")

#==================================
#twse = twse.rename(columns={
#    "證券代號":"股票代號",
#    "收盤價":"股價"
#})

twse["股票代號"] = twse["股票代號"].astype(str).str.strip()


twse["股票代號"] = twse["股票代號"].astype(str)

# ===== 3) 營收 =====
rev_url = "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv"
rev = pd.read_csv(rev_url)

rev = rev.rename(columns={
    "公司代號":"股票代號",
    "營業收入-當月營收":"營收"
})
rev["股票代號"] = rev["股票代號"].astype(str)

# ===== 4) EPS =====
eps_url = "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv"
eps = pd.read_csv(eps_url)

eps = eps.rename(columns={
    "公司代號":"股票代號",
    "基本每股盈餘(元)":"EPS"
})
eps["股票代號"] = eps["股票代號"].astype(str)

# ===== 5) 合併 =====
df = df_comp.merge(twse[["股票代號","股價"]], on="股票代號", how="left")
df = df.merge(rev[["股票代號","營收"]], on="股票代號", how="left")
df = df.merge(eps[["股票代號","EPS"]], on="股票代號", how="left")

# ===== 6) 輸出 Excel =====
filename = f"stock_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
df.to_excel(filename, index=False)

print("✅ 已產生 Excel:", filename)
