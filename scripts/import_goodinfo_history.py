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
    parser.add_argument("--only", choices=["div", "eps", "price", "2026exdate"], help="只跑指定類型")
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

    if args.only in [None, "2026exdate"]:
        import_dividend_2026_exdate(dry=args.dry)

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


if __name__ == "__main__":
    main()
