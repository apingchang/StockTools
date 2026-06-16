#!/usr/bin/env python3
"""
import_goodinfo_history.py
============================
一次性把 goodinfo 匯出的 xls 歷史資料寫入 StockTools DB。

【來源檔案】放在 .tmp/goodinfo_export/ 下：
  dividend/  P50UpDividend10Y.xls  → 現金股利（高價股，2017~2026）
            P20-50Dividend10Y.xls  → 現金股利（中價股）
            P20LDividend10Y.xls    → 現金股利（低價股）
            P50UShare10Y.xls       → 股票股利（高價股）
            P20-50Share10Y.xls     → 股票股利（中價股）
            P20LShare10Y.xls       → 股票股利（低價股）
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
  dividend_history.db  → 現金股利 + 股票股利（加總年度）
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

【用法】
  cd /home/aping/MyProjects/StockTools/source
  python ../scripts/import_goodinfo_history.py          # 全部
  python ../scripts/import_goodinfo_history.py --only div   # 只跑股利
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

    # 合併（cash + stock 同一張表）
    all_agg: dict = defaultdict(lambda: {"cash": 0.0, "stock": 0.0})
    for (sid, yr), vals in {**dict(cash_agg), **dict(share_agg)}.items():
        all_agg[(sid, yr)]["cash"] += vals.get("cash", 0.0)
        all_agg[(sid, yr)]["stock"] += vals.get("stock", 0.0)

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


def _init_div_db(db_path: str):
    """初始化 dividend_history.db schema"""
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
            PRIMARY KEY (stock_id, year)
        )""")
    conn.commit()
    conn.close()


def _upsert_div_history(db_path: str, rows: list):
    """rows: [(stock_id, year, cash, stock, source, ex_date, ex_date_close), ...]"""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        """INSERT OR REPLACE INTO dividend_history
           (stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close)
           VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?)""",
        rows,
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
    parser.add_argument("--only", choices=["div", "eps", "price"], help="只跑指定類型")
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

    if args.only in [None, "eps"]:
        import_eps(dry=args.dry)

    if args.only in [None, "price"]:
        import_avg_price(dry=args.dry)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n🎉 全部完成！耗時 {elapsed:.1f} 秒")


if __name__ == "__main__":
    main()
