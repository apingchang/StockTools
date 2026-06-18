#!/usr/bin/env python3
"""
import_goodinfo_history.py
============================
【V0.9.5-goodinfo3 修】 2026-06-17 12:03
  * 修 import_dividend 合併 bug：
    - 原本：{**cash_agg, **share_agg} 用 dict unpack、後者覆蓋前者
      → 對 cash 跟 share 都有資料的股票，cash 被洗成 0（1,710 筆 / 646 檔）
    - 修法：明確取 cash_agg.cash + share_agg.stock
【V0.9.5-goodinfo2 新增】 2026-06-17 11:10
  * import_yield_rate() 寫入 6 個殖利率檔
  * DB schema 加 cash_yield_pct / share_yield_pct
  * --only yield 選項
一次性把 goodinfo 匯出的 xls 歷史資料寫入 StockTools DB。

【來源檔案】放在 .tmp/goodinfo_export/ 下：
  dividend/  P50UpDividend10Y.xls  → 現金股利（高價股，2017~2026）
            P20-50Dividend10Y.xls  → 現金股利（中價股）
            P20LDividend10Y.xls    → 現金股利（低價股）
            P50UShare10Y.xls       → 股票股利（高價股）
            P20-50Share10Y.xls     → 股票股利（中價股）
            P20LShare10Y.xls       → 股票股利（低價股）
            P50U_DividendRate.xls  → 現金殖利率（高價股，2017~2026, V0.9.5-goodinfo）
            P20-50_DividendRate.xls → 現金殖利率（中價股）
            P20L_DividendRate.xls  → 現金殖利率（低價股）
            P50U_ShareRate.xls     → 股票殖利率（高價股，2017~2026）
            P20-50_ShareRate.xls   → 股票殖利率（中價股）
            P20L_ShareRate.xls     → 股票殖利率（低價股）
  eps/       P50UEPS12Y.xls       → EPS（高價股，2014~2025）
            P20-50EPS12Y.xls      → EPS（中價股）
            P20LEPS12Y.xls        → EPS（低價股）
  price/     P50UAverage12Y.xls   → 平均股價（高價股，2015~2026）
            P20-50AverageY12.xls  → 平均股價（中價股）
            P20LAverageY12.xls    → 平均股價（低價股）
  revenue/   P50URevRate12Y.xls   → 營收年增率（高價股）
            P20~50RevRate12Y.xls  → 營收年增率（中價股，有~）
            P20LRevRate12Y.xls    → 營收年增率（低價股）

【寫入目標】
  dividend_history.db  → 現金股利 + 股票股利（加總年度）+ 殖利率
  eps_history.db       → 年度 EPS
  .tmp/avg_price_history.json → 平均股價（給殖利率計算用，不寫 DB）
  .tmp/revenue_rate_history.json → 營收年增率（純參考，不寫 DB）

【重要 mapping 規則】
  股利 year 對應：
    - goodinfo 的「2017發放年度」= 該年度除息的股利
    - 直接寫入 DB year（不用 -1），因為 goodinfo 已是除息年
    - 同一 stock_id + year 跨三個價位帶的話加總（雖然不該重複）

  FinMind year 對應（留給日後 FinMind 補差額時用）：
    - FinMind TaiwanStockDividend 用 CashExDividendTradingDate 的西元年當分組 key
    - 同一 stock_id + year 多季加總

  殖利率（V0.9.5-goodinfo）：
    - goodinfo DividendRate/ShareRate 的「2017現金殖利率」= 2017 年除息基準日的殖利率
    - 殖利率已是百分比（3.17 = 3.17%），直接寫入 cash_yield_pct
    - 同一 stock_id + year 跨三個價位帶的話「取平均」（與股利加總不同）
    - 沒有殖利率 = 0（該年沒配息）→ 寫 0（不是 NULL，避免誤判為缺資料）
    - 寫入策略：只更新殖利率、不動既有 cash/stock

【用法】
  cd /home/aping/MyProjects/StockTools/source
  python ../scripts/import_goodinfo_history.py          # 全部
  python ../scripts/import_goodinfo_history.py --only div   # 只跑股利
  python ../scripts/import_goodinfo_history.py --only yield # 只跑殖利率（V0.9.5-goodinfo）
  python ../scripts/import_goodinfo_history.py --only eps   # 只跑 EPS
  python ../scripts/import_goodinfo_history.py --dry        # 預演（不寫 DB）
"""
import os
import re
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 路徑
SCRIPT_DIR = Path(__file__).parent.resolve()
SOURCE_DIR = SCRIPT_DIR.parent / "source"
EXPORT_DIR = Path("/home/aping/.openclaw/workspace/股神/.tmp/goodinfo_export")
TMP_DIR = SCRIPT_DIR.parent / ".tmp"

DB_DIV = SOURCE_DIR / "dividend_history.db"
DB_EPS = SOURCE_DIR / "eps_history.db"
DB_PORTFOLIO = SOURCE_DIR / "portfolio.db"

# ─────────────────────────────────────────
# 工具：讀 goodinfo HTML-xls
# ─────────────────────────────────────────
try:
    import pandas as pd
except ImportError:
    print("❌ 需要 pandas: pip install pandas openpyxl")
    sys.exit(1)


def load_goodinfo(folder: str, suffix_map: dict) -> pd.DataFrame:
    """
    載入某資料夾下的三個 goodinfo 檔案，合併成 DataFrame。
    suffix_map: {"P50U": "Dividend10Y", "P20-50": "Dividend10Y", "P20L": "Dividend10Y"}
    特殊規則：
      - dividend/ 的 P50U 其實叫 P50Up
      - revenue/  的 P20-50 其實叫 P20~50
      - price/    的 P20-50/P20L 其實後綴是 AverageY12 (Y 在前)
    """
    FILE_PREFIX_MAP = {
        ("dividend", "P50U", "Dividend10Y"): "P50Up",
        ("dividend", "P50U", "Share10Y"):    "P50U",
        ("dividend", "P20-50", "Dividend10Y"): "P20-50",
        ("dividend", "P20-50", "Share10Y"):   "P20-50",
        ("dividend", "P20L", "Dividend10Y"):  "P20L",
        ("dividend", "P20L", "Share10Y"):     "P20L",
        ("revenue",  "P20-50"): "P20~50",
    }
    PRICE_SUFFIX = {"P50U": "Average12Y", "P20-50": "AverageY12", "P20L": "AverageY12"}

    frames = []
    for gkey, suffix in suffix_map.items():
        prefix_key = (folder, gkey, suffix)
        prefix = FILE_PREFIX_MAP.get(prefix_key, gkey)

        if folder == "price":
            suffix = PRICE_SUFFIX.get(gkey, suffix)

        fpath = EXPORT_DIR / folder / f"{prefix}{suffix}.xls"
        if not fpath.exists():
            print(f"  ⚠️  找不到 {fpath}，跳過")
            continue
        df = pd.read_html(fpath)[0]
        df["_group"] = gkey
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"{folder}/ 找不到對應的 goodinfo 檔案")
    out = pd.concat(frames, ignore_index=True)
    return out


# ─────────────────────────────────────────
# 1. 寫入 dividend_history.db
# ─────────────────────────────────────────
def import_dividend(dry: bool = False):
    """把 goodinfo 現金股利 + 股票股利年度加總寫入 dividend_history.db"""
    print("\n" + "="*70)
    print("【1/3】匯入股利資料 → dividend_history.db")
    print("="*70)

    # 載入
    div_cash = load_goodinfo("dividend", {
        "P50U": "Dividend10Y", "P20-50": "Dividend10Y", "P20L": "Dividend10Y"})
    div_share = load_goodinfo("dividend", {
        "P50U": "Share10Y", "P20-50": "Share10Y", "P20L": "Share10Y"})

    # 股利年度欄位
    cash_years = [c for c in div_cash.columns if "發放年度" in c]  # ['2017發放年度', ...]
    share_years = [c for c in div_share.columns if "發放年度" in c]

    # 解析年份數字
    def year_num(col: str) -> int:
        m = re.search(r'(\d{4})', col)
        return int(m.group(1)) if m else None

    cash_year_nums = sorted(set(year_num(c) for c in cash_years if year_num(c)))
    share_year_nums = sorted(set(year_num(c) for c in share_years if year_num(c)))
    print(f"  現金股利年份: {cash_year_nums}")
    print(f"  股票股利年份: {share_year_nums}")

    # 按 stock_id + year 分組加總
    # 規則：同一 stock_id + year，三個價位帶的加總（理論上不重複，但保險起見）
    cash_agg: dict = defaultdict(lambda: {"cash": 0.0, "stock": 0.0})
    share_agg: dict = defaultdict(lambda: {"cash": 0.0, "stock": 0.0})

    for df, agg in [(div_cash, cash_agg), (div_share, share_agg)]:
        years = cash_years if df is div_cash else share_years
        for _, row in df.iterrows():
            sid = str(row["代號"]).strip()
            for ycol in years:
                yr = year_num(ycol)
                if yr is None:
                    continue
                val = row.get(ycol)
                if pd.isna(val) or val == 0:
                    continue
                key = (sid, yr)
                if df is div_cash:
                    agg[key]["cash"] += float(val)
                else:
                    agg[key]["stock"] += float(val)

    # 【V0.9.5-goodinfo3 修 Bug】合併 cash + stock 同一張表
    # 【原本 bug】{**cash_agg, **share_agg} 用 dict unpack、後者覆蓋前者
    #   結果：對 cash 跟 share 都有資料的股票（ex: 5386 2018 cash=2.5/share=1.5），
    #         share_agg 的 {"cash":0,"stock":1.5} 會覆蓋 cash_agg 的 {"cash":2.5,"stock":0}
    #         → DB cash=0, stock=1.5（cash 被洗成 0！）
    # 【修法】明確取 cash_agg.cash + share_agg.stock（兩個來源不同、不會衝突）
    #   cash = sum(cash_agg.cash)        ← 只來自 cash 檔
    #   stock = sum(share_agg.stock)     ← 只來自 share 檔
    all_agg: dict = {}
    all_keys = set(cash_agg.keys()) | set(share_agg.keys())
    for (sid, yr) in all_keys:
        cash_vals = cash_agg.get((sid, yr), {}).get("cash", 0.0)
        stock_vals = share_agg.get((sid, yr), {}).get("stock", 0.0)
        all_agg[(sid, yr)] = {"cash": cash_vals, "stock": stock_vals}

    print(f"  合計 {len(all_agg)} 筆 (stock_id, year) 組合")

    if dry:
        print(f"\n  🟡 Dry run — 前 10 筆預覽：")
        for (sid, yr), vals in list(all_agg.items())[:10]:
            print(f"    {sid} {yr}: cash={vals['cash']:.2f}, stock={vals['stock']:.2f}")
        return

    # 寫入 DB
    _init_div_db(str(DB_DIV))
    rows = [
        (sid, yr, round(vals["cash"], 6), round(vals["stock"], 6), "goodinfo", None, None)
        for (sid, yr), vals in all_agg.items()
    ]
    _upsert_div_history(str(DB_DIV), rows)

    # 統計
    conn = sqlite3.connect(str(DB_DIV))
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM dividend_history WHERE source='goodinfo'").fetchone()[0]
    stocks = cur.execute("SELECT COUNT(DISTINCT stock_id) FROM dividend_history WHERE source='goodinfo'").fetchone()[0]
    years = cur.execute("SELECT COUNT(DISTINCT year) FROM dividend_history WHERE source='goodinfo'").fetchone()[0]
    conn.close()
    print(f"\n  ✅ 寫入完成：{total} 列 / {stocks} 檔 / {years} 個年度")
    print(f"     DB 路徑: {DB_DIV}")


# ─────────────────────────────────────────────────────────
# 1.5 修 Bug V0.9.5-goodinfo4+5：2026 cash 誤存「合計股利」
# ─────────────────────────────────────────────────────────
# 【Bug 描述】2026-06-18 William 13:05 反映
# - 「現金股利你還是把現金＋股票作家總了！以 2442 為例 2026 現金應該是 2.0 不是 2.7」
# - 【根因】goodinfo 從 2026 開始，Dividend10Y 檔的 `{year}發放年度` 欄位
#   **改存「合計股利」（cash + stock）**而不是「現金股利」！
#   - 2017-2025：10Y_div 欄位 = 現金股利 ✓
#   - 2026 開始：10Y_div 欄位 = 合計股利 ✗（同一股 10Y_share 還是股票股利）
#   - 結果：DB 的 2026 cash 欄位存的是 合計、不是真正的現金
#
# 【證據】
# | 代號 | DB 2026 cash | goodinfo 10Y_div 2026 | 單年 2026 現金 | 單年 2026 合計 |
# | 2442 | 2.7 (BUG)   | 2.7                  | 2.0            | 2.7            |
# | 2548 | 8.5 (BUG)   | 8.5                  | 8.0            | 8.5            |
# | 1294 | 5.0 (BUG)   | 5.0                  | 3.0            | 5.0            |
# | 5386 | 6.5 (BUG)   | 6.5                  | 1.5            | 6.5            |
#
# 【修法】
# 從 2026 單年檔 (P50U_2026股利股息.xls / P20-50_2026股利股息.xls / P20L_2026股利股息.xls)
# 取正確的「現金股利」/「股票股利」覆寫 DB
# 這兩個檔有完整的「現金/股票/合計」三欄、能正確區分
#
# 【期別處理】goodinfo 「股利發放期別」可能是：
#   - 「2026」：年配（一次發整年）
#   - 「26H1」+「26H2」：半年配（兩個 record 都要加總）
#   - 「26Q2」+「26Q3」+「26Q4」：季配（三個 record 都要加總）
#   - 「2025」+「2026」+「2027」：跨年度（今天日期還沒到的也含在裡）
#   → 取 2026 範圍（期別是「2026」、「26H1」、「26H2」、「26Q1~Q4」），同股加總
# ─────────────────────────────────────────────────────────

def import_2026_dividend(dry: bool = False):
    """【V0.9.5-goodinfo4+5 修 Bug】從 2026 單年檔覆寫 DB 的 2026 cash/stock

    為什麼需要這個 function？
    goodinfo 從 2026 開始把 10Y 檔的「現金股利」欄位改成存「合計股利」
    → 必須用 2026 單年檔（有完整 現金/股票/合計 三欄）才能拿到正確的現金
    """
    print("\n" + "="*70)
    print("【1.5/3】修 2026 cash bug：用 2026 單年檔覆寫")
    print("="*70)

    # 2026 單年檔：3 個價位帶
    SINGLE_YEAR_FILES = [
        ("P50U",   "P50U_2026股利股息.xls"),
        ("P20-50", "P20-50_2026股利股息.xls"),
        ("P20L",   "P20L_2026股利股息.xls"),
    ]

    frames = []
    for gkey, fname in SINGLE_YEAR_FILES:
        fpath = EXPORT_DIR / "dividend" / fname
        if not fpath.exists():
            print(f"  ⚠️  找不到 {fpath}、跳過")
            continue
        df = pd.read_html(fpath)[0]
        df["_group"] = gkey
        frames.append(df)

    if not frames:
        print(f"  ❌ 2026 單年檔完全不見、不執行修補")
        return

    all_div = pd.concat(frames, ignore_index=True)
    print(f"  2026 單年檔合計: {len(all_div)} 列 / {all_div['代號'].nunique()} 檔")

    # 取 2026 範圍的 record
    # 期別可能是「2026」/「26H1」/「26H2」/「26Q1」~「26Q4」
    # 不取「2025」/「2027」/「25H1」/「25H2」（那是別年度）
    def is_2026(period: str) -> bool:
        if pd.isna(period):
            return False
        s = str(period).strip()
        return s == "2026" or s.startswith("26H") or s.startswith("26Q")

    all_div["_is_2026"] = all_div["股利發放期別"].apply(is_2026)
    sub_2026 = all_div[all_div["_is_2026"]].copy()
    print(f"  2026 範圍 record: {len(sub_2026)} 列")

    # 同一股可能多筆（H1+H2 或 Q1~Q4）、加總
    # 【重要】skipna=False：保留 NaN 避免「有資料」以為「全 0」
    # 例：9946 26Q4 現金=NaN、股票=0.0、原本要保留「該年現金未公佈」語意
    agg = (
        sub_2026.groupby("代號")
        .agg({
            "現金股利": lambda s: s.sum(skipna=False),  # 保留 NaN
            "股票股利": lambda s: s.sum(skipna=False),  # 保留 NaN
            "除息交易日": "first",  # 除息交易日只有年度、配一次
        })
        .reset_index()
    )
    agg["代號"] = agg["代號"].astype(str).str.strip()
    agg["_ex_date"] = agg["除息交易日"].apply(_parse_roc_short_date)
    print(f"  2026 加總後股票數: {len(agg)} 檔")

    # 跳過沒資料的股（兩項都是 NaN 才是真的沒資料）
    # 【重要】不要 fillna(0.0) ！會讓 cash=NaN 變成 cash=0、失去「未公布」語意
    agg = agg[agg["現金股利"].notna() | agg["股票股利"].notna()]
    print(f"  有效資料: {len(agg)} 檔（現金或股票至少一項有值）")

    if dry:
        print(f"\n  🟡 Dry run — 前 10 筆預覽：")
        for _, r in agg.head(10).iterrows():
            sid = r["代號"]
            cash = r["現金股利"] if not pd.isna(r["現金股利"]) else 0.0
            stock = r["股票股利"] if not pd.isna(r["股票股利"]) else 0.0
            ex = r["_ex_date"]
            print(f"    {sid}: 現金={cash:.3f}, 股票={stock:.3f}, 除息日={ex}")
        return

    # UPSERT 進 DB：覆寫 cash/stock + 順便寫 ex_date、保留殖利率（殖利率從 10Y rate 檔來、已對）
    # 【重要】必須用 UPDATE 而不是 INSERT OR REPLACE
    #   INSERT OR REPLACE 會洗掉 cash_yield_pct / share_yield_pct 這兩個欄位
    #   改用 UPDATE：只動 cash/stock/ex_date/三個欄位、保留殖利率不變
    _init_div_db(str(DB_DIV))
    conn = sqlite3.connect(str(DB_DIV))
    cur = conn.cursor()

    updated = 0
    inserted = 0
    skipped_no_data = 0
    for _, r in agg.iterrows():
        sid = str(r["代號"]).strip()
        cash_raw = r["現金股利"]
        stock_raw = r["股票股利"]
        ex_date = r["_ex_date"]

        cash_is_nan = pd.isna(cash_raw)
        stock_is_nan = pd.isna(stock_raw)

        # 兩個都是 NaN → 完全沒資料、跳過
        if cash_is_nan and stock_is_nan:
            skipped_no_data += 1
            continue

        # 取得現有 cash/stock（保留 NaN 那邊、避免蓋掉既有 10Y 加總的 data）
        existing = cur.execute(
            "SELECT cash, stock, cash_yield_pct, share_yield_pct FROM dividend_history WHERE stock_id=? AND year=?",
            (sid, 2026)
        ).fetchone()

        if existing is not None:
            old_cash, old_stock = existing[0], existing[1]
            # 只覆寫「有資料」的欄位、另一欄位保留 DB 原值
            # 例：9946 季配 2026、cash=NaN stock=0.0 → 保留 old_cash（可能是各季加總）
            new_cash = round(float(cash_raw), 6) if not cash_is_nan else old_cash
            new_stock = round(float(stock_raw), 6) if not stock_is_nan else old_stock
            cur.execute(
                """UPDATE dividend_history
                   SET cash=?, stock=?, ex_date=?, fetched_at=datetime('now','localtime')
                   WHERE stock_id=? AND year=?""",
                (new_cash, new_stock, ex_date, sid, 2026)
            )
            updated += 1
        else:
            # 新 record：cash NaN 預設 0.0、stock NaN 預設 0.0
            cash = round(float(cash_raw), 6) if not cash_is_nan else 0.0
            stock = round(float(stock_raw), 6) if not stock_is_nan else 0.0
            cur.execute(
                """INSERT INTO dividend_history
                   (stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, 2026, cash, stock, "goodinfo", ex_date, None, None, None)
            )
            inserted += 1

    conn.commit()
    conn.close()
    print(f"\n  ✅ 覆寫完成：{updated} 筆 UPDATE、{inserted} 筆 INSERT、{skipped_no_data} 筆跳過（未公布）")
    print(f"     DB 路徑: {DB_DIV}")


def _init_div_db(db_path: str):
    """初始化 dividend_history.db schema（V0.9.5-goodinfo 加殖利率欄）"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dividend_history (
            stock_id    TEXT    NOT NULL,
            year        INTEGER NOT NULL,
            cash        REAL    NOT NULL DEFAULT 0,
            stock       REAL    NOT NULL DEFAULT 0,
            source      TEXT    NOT NULL,
            fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            ex_date     TEXT,
            ex_date_close REAL,
            cash_yield_pct  REAL,    -- V0.9.5-goodinfo：該年現金殖利率（%, goodinfo 來源）
            share_yield_pct REAL,    -- V0.9.5-goodinfo：該年股票殖利率（%, goodinfo 來源）
            PRIMARY KEY (stock_id, year)
        )""")
    # V0.9.5-goodinfo：動態加殖利率欄（既有 DB 自動 migration）
    for col_sql in [
        "ALTER TABLE dividend_history ADD COLUMN cash_yield_pct REAL",
        "ALTER TABLE dividend_history ADD COLUMN share_yield_pct REAL",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass  # 欄位已存在（重複 migration 安全）
    conn.commit()
    conn.close()


def _upsert_div_history(db_path: str, rows: list):
    """rows: [(stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct), ...]
    V0.9.5-goodinfo：9-tuple（向後相容 5-tuple、7-tuple）
      - 5-tuple: (sid, year, cash, stock, source)
      - 7-tuple: (sid, year, cash, stock, source, ex_date, ex_date_close)
      - 9-tuple: 上 + cash_yield_pct + share_yield_pct
    """
    conn = sqlite3.connect(db_path)
    normalized = []
    for r in rows:
        if len(r) == 5:
            normalized.append((r[0], r[1], r[2], r[3], r[4], None, None, None, None))
        elif len(r) == 7:
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], None, None))
        else:
            normalized.append(r)
    conn.executemany(
        """INSERT OR REPLACE INTO dividend_history
           (stock_id, year, cash, stock, source, ex_date, ex_date_close,
            cash_yield_pct, share_yield_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        normalized,
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# 2. 寫入 eps_history.db
# ─────────────────────────────────────────
def import_eps(dry: bool = False):
    """把 goodinfo 年度 EPS 寫入 eps_history.db"""
    print("\n" + "="*70)
    print("【2/3】匯入 EPS 資料 → eps_history.db")
    print("="*70)

    eps = load_goodinfo("eps", {"P50U": "EPS12Y", "P20-50": "EPS12Y", "P20L": "EPS12Y"})

    # EPS 年度欄位
    eps_years = [c for c in eps.columns if re.match(r'\d{4}EPS', c)]
    eps_year_nums = sorted(int(re.search(r'(\d{4})', c).group(1)) for c in eps_years)
    print(f"  EPS 年份: {eps_year_nums}")

    # 收集 (stock_id, year) → eps，寫入時用 quarter=4 表示年度合計
    rows = []
    for _, row in eps.iterrows():
        sid = str(row["代號"]).strip()
        for ycol in eps_years:
            yr_match = re.search(r'(\d{4})', ycol)
            if not yr_match:
                continue
            yr = int(yr_match.group(1))
            val = row.get(ycol)
            if pd.isna(val):
                continue
            rows.append((sid, yr, 4, float(val), "goodinfo"))  # quarter=4 代表年度合計

    print(f"  合計 {len(rows)} 筆 (stock_id, year=西元)")

    if dry:
        print(f"\n  🟡 Dry run — 前 10 筆預覽：")
        for r in rows[:10]:
            print(f"    {r}")
        return

    _init_eps_db(str(DB_EPS))
    _upsert_eps_history(str(DB_EPS), rows)

    conn = sqlite3.connect(str(DB_EPS))
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM eps_history WHERE source='goodinfo'").fetchone()[0]
    stocks = cur.execute("SELECT COUNT(DISTINCT stock_id) FROM eps_history WHERE source='goodinfo'").fetchone()[0]
    years = cur.execute("SELECT COUNT(DISTINCT year) FROM eps_history WHERE source='goodinfo'").fetchone()[0]
    conn.close()
    print(f"\n  ✅ 寫入完成：{total} 列 / {stocks} 檔 / {years} 個年度")
    print(f"     DB 路徑: {DB_EPS}")


def _init_eps_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eps_history (
            stock_id    TEXT    NOT NULL,
            year        INTEGER NOT NULL,
            quarter     INTEGER NOT NULL,
            eps         REAL,
            source      TEXT,
            fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (stock_id, year, quarter)
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eps_period ON eps_history(year, quarter)")
    conn.commit()
    conn.close()


def _upsert_eps_history(db_path: str, rows: list):
    conn = sqlite3.connect(db_path)
    conn.executemany(
        """INSERT OR REPLACE INTO eps_history
           (stock_id, year, quarter, eps, source, fetched_at)
           VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))""",
        rows,
    )
    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# 2.5 寫入殖利率（V0.9.5-goodinfo：6 個殖利率檔一次匯入）
# ─────────────────────────────────────────
def import_yield_rate(dry: bool = False):
    """把 goodinfo 6 個殖利率檔（3 個現金 + 3 個股票）寫入 dividend_history.db

    來源檔：
      dividend/P50U_DividendRate.xls   - 高價股 2017~2026 現金殖利率
      dividend/P20-50_DividendRate.xls - 中價股 2017~2026 現金殖利率
      dividend/P20L_DividendRate.xls   - 低價股 2017~2026 現金殖利率
      dividend/P50U_ShareRate.xls      - 高價股 2017~2026 股票殖利率
      dividend/P20-50_ShareRate.xls    - 中價股 2017~2026 股票殖利率
      dividend/P20L_ShareRate.xls      - 低價股 2017~2026 股票殖利率

    重要 mapping 規則：
      1. 殖利率已是百分比（3.17 = 3.17%），直接寫入 cash_yield_pct
      2. 同一 stock_id + year 跨三個價位帶的話「取平均」（與股利加總不同）
         理由：三個價位帶可能都有同檔、平均比加總更合理
      3. 0 值代表「該年該類無配息」（ex: 現金股利為 0、現金殖利率=0）→ 寫 0
         與 cash/stock=0 一致語意、讓 App 可以直接判斷
      4. NaN (原本沒資料) → 跳過、不寫入（保留原值）
      5. 只 UPDATE cash_yield_pct / share_yield_pct、不動 cash/stock/ex_date
         （殖利率是「補充資訊」、不該覆蓋股利金額或除息日）
    """
    print("\n" + "="*70)
    print("【2.5/4】寫入殖利率 → UPDATE dividend_history.db (V0.9.5-goodinfo)")
    print("="*70)

    # 載入 6 個檔
    # 跟股利檔不同的是、殖利率檔前綴是 P50U/P20-50/P20L、不是 P50Up/P20~50
    YIELD_FILES = [
        ("dividend", "P50U",   "DividendRate", "_DividendRate"),  # 現金殖利率
        ("dividend", "P20-50", "DividendRate", "_DividendRate"),
        ("dividend", "P20L",   "DividendRate", "_DividendRate"),
        ("dividend", "P50U",   "ShareRate",    "_ShareRate"),     # 股票殖利率
        ("dividend", "P20-50", "ShareRate",    "_ShareRate"),
        ("dividend", "P20L",   "ShareRate",    "_ShareRate"),
    ]

    cash_frames = []
    share_frames = []
    for folder, gkey, kind, suffix in YIELD_FILES:
        fpath = EXPORT_DIR / folder / f"{gkey}{suffix}.xls"
        if not fpath.exists():
            print(f"  ⚠️  找不到 {fpath}，跳過")
            continue
        df = pd.read_html(fpath)[0]
        df["_group"] = gkey
        if kind == "DividendRate":
            cash_frames.append(df)
        else:
            share_frames.append(df)

    if not cash_frames or not share_frames:
        print("  ❌ 殖利率檔不完整（現金/股票需都有）")
        return

    cash_all = pd.concat(cash_frames, ignore_index=True)
    share_all = pd.concat(share_frames, ignore_index=True)
    print(f"  現金殖利率檔合計: {len(cash_all)} 列 / {cash_all['代號'].nunique()} 檔")
    print(f"  股票殖利率檔合計: {len(share_all)} 列 / {share_all['代號'].nunique()} 檔")

    # 解析年度欄位
    def year_num(col: str) -> int:
        m = re.search(r'(\d{4})', col)
        return int(m.group(1)) if m else None

    cash_years = [c for c in cash_all.columns if "現金殖利率" in c]
    share_years = [c for c in share_all.columns if "股票殖利率" in c]
    print(f"  現金殖利率年份: {sorted(set(year_num(c) for c in cash_years if year_num(c)))}")
    print(f"  股票殖利率年份: {sorted(set(year_num(c) for c in share_years if year_num(c)))}")

    # 聚合（取平均，不加總）
    # key: (stock_id, year) → {cash_yield_pct: [...], share_yield_pct: [...]}
    cash_agg: dict = defaultdict(list)
    share_agg: dict = defaultdict(list)

    for df, agg, year_cols in [
        (cash_all, cash_agg, cash_years),
        (share_all, share_agg, share_years),
    ]:
        for _, row in df.iterrows():
            sid = str(row["代號"]).strip()
            for ycol in year_cols:
                yr = year_num(ycol)
                if yr is None:
                    continue
                val = row.get(ycol)
                # 0 是「沒配息」的合法值（殖利率=0）→ 寫入
                # NaN 是「缺資料」→ 跳過
                if pd.isna(val):
                    continue
                agg[(sid, yr)].append(float(val))

    print(f"  現金殖利率組合: {len(cash_agg)} 筆")
    print(f"  股票殖利率組合: {len(share_agg)} 筆")

    if dry:
        print(f"\n  🟡 Dry run — 前 10 筆預覽（現金殖利率）:")
        keys = sorted(cash_agg.keys())[:10]
        for k in keys:
            vals = cash_agg[k]
            avg = sum(vals) / len(vals) if vals else 0
            print(f"    {k[0]} {k[1]}: {vals} → avg={avg:.2f}%")
        return

    # UPDATE DB：只更新殖利率、不動 cash/stock/ex_date
    _init_div_db(str(DB_DIV))
    conn = sqlite3.connect(str(DB_DIV))
    cur = conn.cursor()

    # 合併 cash + share
    all_keys = set(cash_agg.keys()) | set(share_agg.keys())
    updated = 0
    skipped_no_data = 0
    for (sid, yr) in all_keys:
        cash_vals = cash_agg.get((sid, yr), [])
        share_vals = share_agg.get((sid, yr), [])
        cash_avg = sum(cash_vals) / len(cash_vals) if cash_vals else None
        share_avg = sum(share_vals) / len(share_vals) if share_vals else None

        # 查 DB 現有記錄
        cur.execute(
            "SELECT 1 FROM dividend_history WHERE stock_id=? AND year=?",
            (sid, yr),
        )
        exists = cur.fetchone() is not None
        if not exists:
            skipped_no_data += 1
            continue

        # UPDATE 殖利率（保留既有 cash/stock/ex_date）
        cur.execute(
            """UPDATE dividend_history
               SET cash_yield_pct = COALESCE(?, cash_yield_pct),
                   share_yield_pct = COALESCE(?, share_yield_pct),
                   fetched_at = datetime('now','localtime')
               WHERE stock_id = ? AND year = ?""",
            (cash_avg, share_avg, sid, yr),
        )
        if cur.rowcount > 0:
            updated += 1

    conn.commit()

    # 統計
    cur.execute("SELECT COUNT(*) FROM dividend_history WHERE cash_yield_pct IS NOT NULL")
    total_cash_yld = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dividend_history WHERE share_yield_pct IS NOT NULL")
    total_share_yld = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(DISTINCT stock_id) FROM dividend_history WHERE cash_yield_pct IS NOT NULL"
    )
    stocks_with_cash_yld = cur.fetchone()[0]
    conn.close()

    print(f"\n  ✅ 更新完成：")
    print(f"     UPDATE 殖利率: {updated} 筆")
    print(f"     略過（DB 沒對應股利記錄）: {skipped_no_data} 筆")
    print(f"  📊 DB 狀態：")
    print(f"     有 cash_yield_pct: {total_cash_yld} 筆 / {stocks_with_cash_yld} 檔")
    print(f"     有 share_yield_pct: {total_share_yld} 筆")
    print(f"     DB 路徑: {DB_DIV}")


# ─────────────────────────────────────────
# 3. 匯出平均股價 → JSON（給殖利率計算用）
# ─────────────────────────────────────────
def import_avg_price(dry: bool = False):
    """把 goodinfo 平均股價匯出成 JSON，給其他工具算殖利率"""
    print("\n" + "="*70)
    print("【3/3】匯出平均股價 → .tmp/avg_price_history.json")
    print("="*70)

    avg_price = load_goodinfo("price", {
        "P50U": "Average12Y", "P20-50": "Average12Y", "P20L": "Average12Y"})

    # price 資料夾的 suffix_map 要特殊處理（AverageY12 vs Average12Y）
    # 重載一次用正確的 suffix
    price_frames = []
    PRICE_FILE = {
        "P50U":   ("P50UAverage12Y",    "Average12Y"),
        "P20-50": ("P20-50AverageY12", "AverageY12"),
        "P20L":   ("P20LAverageY12",    "AverageY12"),
    }
    for gkey, (prefix, suffix) in PRICE_FILE.items():
        fpath = EXPORT_DIR / "price" / f"{prefix}.xls"
        if not fpath.exists():
            print(f"  ⚠️  找不到 {fpath}")
            continue
        df = pd.read_html(fpath)[0]
        df["_group"] = gkey
        price_frames.append(df)

    avg_price = pd.concat(price_frames, ignore_index=True)

    # 年度均價欄位
    price_years = [c for c in avg_price.columns if re.match(r'\d{4}日均價', c)]
    price_year_nums = sorted(int(re.search(r'(\d{4})', c).group(1)) for c in price_years)
    print(f"  股價年份: {price_year_nums}")
    print(f"  總股票數: {avg_price['代號'].nunique()} 檔")

    # 轉成 {stock_id: {year: avg_price}}
    out = {}
    for _, row in avg_price.iterrows():
        sid = str(row["代號"]).strip()
        out[sid] = {}
        for ycol in price_years:
            yr = int(re.search(r'(\d{4})', ycol).group(1))
            val = row.get(ycol)
            if pd.isna(val) or val == 0:
                continue
            out[sid][yr] = float(val)

    if dry:
        print(f"\n  🟡 Dry run — 前 3 檔預覽：")
        for sid in list(out.keys())[:3]:
            print(f"    {sid}: {out[sid]}")
        return

    out_path = TMP_DIR / "avg_price_history.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 寫入完成：{len(out)} 檔")
    print(f"     檔案路徑: {out_path}")
    print("     用法：python -c \"import json; d=json.load(open('path')); print(d.get('2330'))\"")


# ─────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="goodinfo 歷史資料一次性匯入")
    parser.add_argument("--dry", action="store_true", help="預演模式（不寫 DB）")
    parser.add_argument("--only", choices=["div", "yield", "eps", "price", "2026exdate", "nodiv"], help="只跑指定類型")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════╗
║   goodinfo 歷史資料匯入腳本                          ║
║   匯入目錄: {EXPORT_DIR}
║   Dry run:  {args.dry}
╚══════════════════════════════════════════════════════╝
    """)

    start = datetime.now()

    if args.only in [None, "div"]:
        import_dividend(dry=args.dry)
        # 【V0.9.5-goodinfo4+5 修 Bug】2026 cash 誤存合計 → 用 2026 單年檔覆寫
        import_2026_dividend(dry=args.dry)

    if args.only in [None, "yield"]:
        import_yield_rate(dry=args.dry)

    if args.only in [None, "eps"]:
        import_eps(dry=args.dry)

    if args.only in [None, "price"]:
        import_avg_price(dry=args.dry)

    if args.only in [None, "2026exdate"]:
        import_dividend_2026_exdate(dry=args.dry)

    if args.only in [None, "nodiv"]:
        mark_no_dividend_stocks(dry=args.dry)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n🎉 全部完成！耗時 {elapsed:.1f} 秒")


# ──────────────────────────────────────────────────
# 4. goodinfo 2026 股利股息檔（含除息日）UPDATE DB
# ──────────────────────────────────────────────────
import re as _re_2026


def _parse_roc_short_date(s):
    """把 "'26/01/22" 或 "26/01/22" → "2026-01-22" (西元)
    規則：'YY/MM/DD，YY 補成 20YY（2000 年以後）
    失敗或空值回傳 None
    """
    if pd.isna(s):
        return None
    s = str(s).strip().lstrip("'")  # 去首引號
    m = _re_2026.match(r'(\d{2})/(\d{2})/(\d{2})', s)
    if not m:
        return None
    yy, mm, dd = m.groups()
    yr = 2000 + int(yy)
    if not (1 <= int(mm) <= 12 and 1 <= int(dd) <= 31):
        return None
    return f"{yr}-{int(mm):02d}-{int(dd):02d}"


def import_dividend_2026_exdate(dry: bool = False):
    """讀 goodinfo 2026 股利股息檔（3 個 .xls），把除息日寫入 dividend_history.db

    設計重點：
    1. 這 3 個檔是 10Y 檔的「2026 加強版」→ 多了「除息交易日」欄位
    2. 10Y 檔已寫過 2026 股利金額 (source='goodinfo')
       → 本函式只 UPDATE ex_date，不覆寫 cash/stock（10Y 可能是加總、更準確）
    3. 2026 股利除息日若已過（例 2026/01/22）→ ex_date 寫入，ex_date_close 留 NULL
       → 之後可由 FinMind 補、或 App fallback 用最新收盤價
    4. 2026 除息日若未到（多數股票股利）→ ex_date 還是寫入（供未來參考）
       → ex_date_close 一律 NULL → App 殖利率計算用最新收盤價
    5. 同檔多筆同 year (例 26H1 + 26H2) → 採用「最早 ex_date」並加註來源
    """
    print("\n" + "="*70)
    print("【4/4】補入 2026 股利除息日 → UPDATE dividend_history.db")
    print("="*70)

    # 3 個檔案路徑
    files_2026 = [
        ("P50U",   EXPORT_DIR / "dividend" / "P50U_2026股利股息.xls"),
        ("P20-50", EXPORT_DIR / "dividend" / "P20-50_2026股利股息.xls"),
        ("P20L",   EXPORT_DIR / "dividend" / "P20L_2026股利股息.xls"),
    ]

    frames = []
    for gkey, fpath in files_2026:
        if not fpath.exists():
            print(f"  ⚠️  找不到 {fpath}，跳過")
            continue
        df = pd.read_html(fpath)[0]
        df["_group"] = gkey
        frames.append(df)
    if not frames:
        print("  ❌ 3 個 2026 檔都找不到")
        return

    all_2026 = pd.concat(frames, ignore_index=True)
    print(f"  3 檔合計: {len(all_2026)} 列, {all_2026['代號'].nunique()} 檔")

    # 解析除息交易日為 ISO 格式
    all_2026["_ex_date"] = all_2026["除息交易日"].apply(_parse_roc_short_date)
    has_exdate = all_2026["_ex_date"].notna().sum()
    print(f"  有除息日資料: {has_exdate} 列 / {len(all_2026)} 列")

    # 過濾出有現金股利或股票股利的有效列
    valid = all_2026[
        (all_2026["現金股利"].notna() & (all_2026["現金股利"] > 0)) |
        (all_2026["股票股利"].notna() & (all_2026["股票股利"] > 0))
    ].copy()
    print(f"  有股利資料的有效列: {len(valid)} 列")

    # 計算 year (除息日的年份作為 DB year)
    valid["_year"] = valid["_ex_date"].apply(
        lambda d: int(d[:4]) if pd.notna(d) else 2026  # 沒 ex_date 的也是 2026
    )

    # 按 (stock_id, year) 聚合：取最早 ex_date
    # (同 year 多筆選最早、保留所有現金/股票金額)
    agg = valid.groupby(["代號", "_year"]).agg({
        "_ex_date": "min",  # 最早的除息日
        "現金股利": "sum",
        "股票股利": "sum",
    }).reset_index()

    print(f"  聚合後 (stock_id, year): {len(agg)} 組")

    if dry:
        print("\n  🟡 Dry run — 前 10 筆預覽：")
        for _, r in agg.head(10).iterrows():
            print(f"    {r['代號']} {r['_year']}: cash={r['現金股利']:.2f}, "
                  f"stock={r['股票股利']:.2f}, ex_date={r['_ex_date']}")
        return

    # UPDATE DB：只設 ex_date，不覆寫 cash/stock
    _init_div_db(str(DB_DIV))
    conn = sqlite3.connect(str(DB_DIV))
    cur = conn.cursor()

    updated = 0
    inserted = 0
    skipped_no_exdate = 0
    for _, r in agg.iterrows():
        sid = str(r["代號"]).strip()
        yr = int(r["_year"])
        ex_date = r["_ex_date"]  # ISO 格式或 None

        # 查現有記錄
        cur.execute(
            "SELECT cash, stock, ex_date FROM dividend_history WHERE stock_id=? AND year=?",
            (sid, yr),
        )
        existing = cur.fetchone()

        if existing is None:
            # DB 沒有 → INSERT 新記錄（用 2026 檔的金額）
            if ex_date is None:
                skipped_no_exdate += 1
                continue
            cur.execute(
                """INSERT INTO dividend_history
                   (stock_id, year, cash, stock, source, ex_date, ex_date_close)
                   VALUES (?, ?, ?, ?, 'goodinfo_2026', ?, NULL)""",
                (sid, yr, float(r["現金股利"] or 0), float(r["股票股利"] or 0), ex_date),
            )
            inserted += 1
        else:
            # DB 有 → 只 UPDATE ex_date (不覆寫 cash/stock)
            if ex_date is None:
                skipped_no_exdate += 1
                continue
            cur.execute(
                """UPDATE dividend_history
                   SET ex_date = ?, fetched_at = datetime('now','localtime')
                   WHERE stock_id = ? AND year = ? AND ex_date IS NULL""",
                (ex_date, sid, yr),
            )
            if cur.rowcount > 0:
                updated += 1

    conn.commit()

    # 統計
    cur.execute("SELECT COUNT(*) FROM dividend_history WHERE ex_date IS NOT NULL")
    total_with_exdate = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dividend_history WHERE ex_date IS NULL")
    total_without_exdate = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM dividend_history WHERE source='goodinfo_2026'"
    )
    from_2026_file = cur.fetchone()[0]
    conn.close()

    print(f"\n  ✅ 更新完成：")
    print(f"     UPDATE ex_date: {updated} 筆（只補除息日、不改金額）")
    print(f"     INSERT 新記錄: {inserted} 筆（DB 沒 2026 資料才新建）")
    print(f"     略過（無除息日）: {skipped_no_exdate} 筆")
    print(f"  📊 DB 狀態：")
    print(f"     有 ex_date: {total_with_exdate} 筆")
    print(f"     缺 ex_date: {total_without_exdate} 筆")
    print(f"     source=goodinfo_2026: {from_2026_file} 筆")
    print(f"     DB 路徑: {DB_DIV}")


def mark_no_dividend_stocks(dry: bool = False):
    """把 price_df 有但 dividend DB 沒的股號 INSERT 進 DB（標記為「goodinfo 查過、無股利」）

    為什麼需要：手動選股用「_query_div_history 回傳的股號集合」對比 price_df 的股號。
    如果有股號「DB 完全沒記錄」，會被算成缺漏、但 goodinfo 其實查過了只是沒股利資料。
    標記後手動選股就不會誤報缺漏。

    使用情境：
      - 沒配息的 ETF（0057、0061、00636 等）
      - 新上市股（goodinfo 10Y 檔沒涵蓋）
      - 槓桿/反向型 ETF（00400A~00406A、006205~00646）
    """
    print("\n" + "="*70)
    print("【補充】標記「無股利股號」到 dividend_history.db")
    print("="*70)

    # 從 avg_price_history.json 拿全市場股號清單
    avg_path = TMP_DIR / "avg_price_history.json"
    if not avg_path.exists():
        print(f"  ❌ {avg_path} 不存在、請先跑 --only price 產生")
        return
    with open(avg_path, encoding="utf-8") as f:
        avg = json.load(f)
    all_codes = set(avg.keys())
    print(f"  全市場股號: {len(all_codes)} 檔")

    # 查 DB 已有的股號
    _init_div_db(str(DB_DIV))
    conn = sqlite3.connect(str(DB_DIV))
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT stock_id FROM dividend_history")
    have_codes = {r[0] for r in cur.fetchall()}
    print(f"  DB 已有股號: {len(have_codes)} 檔")

    missing = sorted(all_codes - have_codes)
    print(f"  缺漏股號: {len(missing)} 檔")

    if not missing:
        print("  ✅ 全市場股號都在 DB、無需標記")
        conn.close()
        return

    if dry:
        print(f"\n  🟡 Dry run — 前 20 檔：")
        for sid in missing[:20]:
            print(f"    {sid} 現價={avg.get(sid, {}).get('2026', '?')}")
        conn.close()
        return

    # INSERT 標記記錄（cash=0, stock=0, source='goodinfo_no_div', year=2026）
    rows = [(sid, 2026, 0.0, 0.0, "goodinfo_no_div", None, None) for sid in missing]
    cur.executemany(
        """INSERT OR IGNORE INTO dividend_history
           (stock_id, year, cash, stock, source, ex_date, ex_date_close)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM dividend_history WHERE source='goodinfo_no_div'")
    marked = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT stock_id) FROM dividend_history")
    total = cur.fetchone()[0]
    conn.close()

    print(f"\n  ✅ 標記完成：")
    print(f"     新增「無股利」標記: {len(missing)} 筆")
    print(f"     DB 累計「無股利」標記: {marked} 筆")
    print(f"     DB 股號總數: {total} 檔（= 全市場 {len(all_codes)} 檔）")


if __name__ == "__main__":
    main()
