import pandas as pd
import requests
from datetime import datetime

# ========= 1️⃣ 全市場股價 =========
twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
twse = pd.DataFrame(requests.get(twse_url).json())

# 自動欄位 mapping
twse = twse.rename(columns={
    "Code":"股票代號",
    "ClosingPrice":"股價",
    "Change":"漲跌"
})

twse["股票代號"] = twse["股票代號"].astype(str)
twse["股價"] = pd.to_numeric(twse["股價"], errors="coerce")
twse["漲跌"] = pd.to_numeric(twse["漲跌"], errors="coerce")

# ========= 2️⃣ 營收 =========
#rev = pd.read_csv("https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv")

#rev = pd.read_csv("https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv")

import io
import requests

url = "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv"
res = requests.get(url)


if res.status_code != 200:
    raise Exception(f"下載失敗: {url}")

#rev = pd.read_csv(io.StringIO(res.text))
rev = pd.read_csv(io.BytesIO(res.content), encoding="utf-8")

print("營收欄位:", rev.columns)  # ✅ 先看實際欄位

# 🔍 自動抓欄位
def find_col(cols, keywords):
    for c in cols:
        if any(k in c for k in keywords):
            return c
    return None

code_col = find_col(rev.columns, ["公司代號"])
rev_col = find_col(rev.columns, ["當月營收"])
yoy_col = find_col(rev.columns, ["增減", "年增"])

if code_col is None:
    raise Exception(f"❌ 找不到營收欄位 {rev.columns}")

rev = rev.rename(columns={
    code_col: "股票代號",
    rev_col: "營收",
    yoy_col: "營收YoY"
})

# ✅ 型別處理
rev["股票代號"] = rev["股票代號"].astype(str)
rev["營收"] = pd.to_numeric(
    rev["營收"].astype(str).str.replace(",",""), errors="coerce") / 1e8

if "營收YoY" in rev.columns:
    rev["營收YoY"] = pd.to_numeric(
        rev["營收YoY"].astype(str).str.replace("%",""), errors="coerce")
else:
    rev["營收YoY"] = 0  # 找不到就先補0

    # ✅ 只取最新月份
    rev["年月"] = pd.to_numeric(rev["年月"], errors="coerce")
    latest_month = rev["年月"].max()
    rev = rev[rev["年月"] == latest_month]


#==============
#rev = rev.rename(columns={
#    "公司代號":"股票代號",
#    "營業收入-當月營收":"營收",
#    "累計營業收入-前期比較增減 (%)":"營收YoY"
#})
#
#rev["股票代號"] = rev["股票代號"].astype(str)
#
#rev["營收"] = pd.to_numeric(
#    rev["營收"].astype(str).str.replace(",",""), errors="coerce") / 1e8
#
#rev["營收YoY"] = pd.to_numeric(
#    rev["營收YoY"].astype(str).str.replace("%",""), errors="coerce")
#
#===================

# ========= 3️⃣ EPS =========
#eps = pd.read_csv("https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv")
url_eps = "https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv"
res_eps = requests.get(url_eps)

#eps = pd.read_csv(io.StringIO(res_eps.text))
eps = pd.read_csv(io.BytesIO(res_eps.content), encoding="utf-8")

eps = eps.rename(columns={
    "公司代號":"股票代號",
    "基本每股盈餘(元)":"EPS"
})

eps["股票代號"] = eps["股票代號"].astype(str)

# ========= 4️⃣ 合併 =========
df = twse.merge(rev[["股票代號","營收","營收YoY"]], on="股票代號", how="left")
df = df.merge(eps[["股票代號","EPS"]], on="股票代號", how="left")

# ========= 5️⃣ 指標 =========
df["PE"] = df["股價"] / df["EPS"]
df["殖利率"] = (df["EPS"] * 0.7) / df["股價"]

# ========= 6️⃣ 評分（核心🔥）
df["Score"] = (
    df["營收YoY"].fillna(0)*0.4 +
    df["EPS"].fillna(0)*0.3 +
    df["殖利率"].fillna(0)*100*0.2 -
    df["PE"].fillna(0)*0.05
)

df = df.sort_values(by="Score", ascending=False)


# ========= 7️⃣ 篩選（實戰🔥）
#strong = df[
#    (df["營收YoY"] > 10) &
#    (df["EPS"] > 0) &
#    (df["PE"] < 30)
#]

strong = df[
    (df["營收YoY"] > 10) &
    (df["EPS"] > 0) &
    (df["PE"] < 30) &
    (df["股價"] > 10)
]
# ========= 8️⃣ 輸出 =========
top10 = df.head(10)

file = f"選股報表_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

#with pd.ExcelWriter(file, engine="openpyxl") as writer:
#    df.to_excel(writer, index=False, sheet_name="全市場")
#    strong.to_excel(writer, index=False, sheet_name="強勢股")


with pd.ExcelWriter(file, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="全市場")
    strong.to_excel(writer, index=False, sheet_name="強勢股")
    top10.to_excel(writer, index=False, sheet_name="Top10")

# ===== 技術面（簡化日資料）=====
df["MA5"] = df["股價"].rolling(5).mean()
df["MA20"] = df["股價"].rolling(20).mean()

# RSI（簡化版）
delta = df["股價"].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

rs = gain.rolling(14).mean() / loss.rolling(14).mean()
df["RSI"] = 100 - (100 / (1 + rs))

# MACD（簡化）
df["EMA12"] = df["股價"].ewm(span=12).mean()
df["EMA26"] = df["股價"].ewm(span=26).mean()
df["MACD"] = df["EMA12"] - df["EMA26"]

df["買點"] = (
    (df["RSI"] < 35) &
    (df["MACD"] > 0)
)

df["多頭"] = df["MA5"] > df["MA20"]
df["強勢股"] = df["買點"] & df["多頭"]

df["明日報酬"] = df["股價"].shift(-1) / df["股價"] - 1

# 只看買點
buy = df[df["買點"] == True]

avg_return = buy["明日報酬"].mean()

print("✅ 策略平均報酬:", round(avg_return*100, 2), "%")
print("✅ 訊號數量:", len(buy))

buy.to_excel(writer, index=False, sheet_name="買點清單")


print("✅ 完成 →", file)