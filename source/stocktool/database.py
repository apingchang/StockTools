"""
stocktool.database - 3 個 SQLite 歷史 DB 的 CRUD
================================================

v1.1 重構：把 _init_*/_upsert_*/_query_* 等 DB 函數從 StockTool.py 抽出

包含 3 個歷史 DB：
- dividend_history.db  股利歷史
- eps_history.db        EPS 季報歷史
- etf_history.db        ETF 持股歷史

被依賴：fetch_market.py / etf.py / pipeline.py / gui/tab_manual.py / gui/tab_etf.py
依賴：config.py
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

import pandas as pd


# ==========================================================
# 股利歷史庫 schema
# ==========================================================

DIV_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dividend_history (
    stock_id        TEXT    NOT NULL,
    year            INTEGER NOT NULL,
    cash            REAL,
    stock           REAL,
    source          TEXT,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    ex_date         TEXT,        -- V0.9.5+ Phase 10：除息日 (YYYY-MM-DD)
    ex_date_close   REAL,        -- V0.9.5+ Phase 10：除息日收盤價（用來算 殖利率）
    cash_yield_pct  REAL,        -- V0.9.5-goodinfo：該年現金殖利率（%, goodinfo 來源）
    share_yield_pct REAL,        -- V0.9.5-goodinfo：該年股票殖利率（%, goodinfo 來源）
    PRIMARY KEY (stock_id, year)
);
CREATE INDEX IF NOT EXISTS idx_div_period ON dividend_history(year);
"""

# V0.9.5+ Phase 10：DB migration for new columns
DIV_HISTORY_MIGRATIONS = [
    "ALTER TABLE dividend_history ADD COLUMN ex_date TEXT",
    "ALTER TABLE dividend_history ADD COLUMN ex_date_close REAL",
    "ALTER TABLE dividend_history ADD COLUMN cash_yield_pct REAL",
    "ALTER TABLE dividend_history ADD COLUMN share_yield_pct REAL",
]


def _init_div_history_db(db_path: str):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript(DIV_HISTORY_SCHEMA)
        for col_sql in DIV_HISTORY_MIGRATIONS:
            try:
                conn.execute(col_sql)
            except Exception:
                pass
        conn.commit()


# ==========================================================
# ETF 持股歷史庫 schema
# ==========================================================

ETF_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS etf_holding_history (
    date          TEXT    NOT NULL,
    etf_code      TEXT    NOT NULL,
    stock_code    TEXT    NOT NULL,
    stock_name    TEXT,
    weight_pct    REAL    NOT NULL,
    shares        INTEGER NOT NULL,
    shares_lots   REAL    NOT NULL,
    industry      TEXT,
    fetched_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (date, etf_code, stock_code)
);
CREATE INDEX IF NOT EXISTS idx_etf_hist_date ON etf_holding_history(date);
CREATE INDEX IF NOT EXISTS idx_etf_hist_etf ON etf_holding_history(etf_code);
CREATE INDEX IF NOT EXISTS idx_etf_hist_stock ON etf_holding_history(stock_code);
CREATE TABLE IF NOT EXISTS fetch_meta (
    key            TEXT PRIMARY KEY,
    value          TEXT,
    updated_at     TEXT
);
"""


def _init_etf_history_db(db_path: str = "etf_history.db"):
    """【V0.9.5-etf-history】建立 ETF 持股歷史庫"""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) if os.path.dirname(db_path) else ".", exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ETF_HISTORY_SCHEMA)
        conn.commit()


def _save_etf_holding_snapshot(db_path: str, etf_code: str, holdings: list, date_str: str = None) -> int:
    """【V0.9.5-etf-history】寫入單檔 ETF 持股快照"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for h in holdings:
        shares = int(h.get("shares", 0))
        shares_lots = shares / 1000.0
        rows.append((
            date_str,
            etf_code,
            h["stock_code"],
            h["stock_name"],
            float(h.get("weight", 0)),
            shares,
            shares_lots,
            h.get("industry", ""),
        ))
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO etf_holding_history
               (date, etf_code, stock_code, stock_name, weight_pct, shares, shares_lots, industry)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            """INSERT OR REPLACE INTO fetch_meta (key, value, updated_at)
               VALUES (?, ?, datetime('now','localtime'))""",
            ("last_etf_snapshot_date", date_str),
        )
        conn.commit()
    return len(rows)


def _query_etf_holdings_by_date(db_path: str, date_str: str) -> pd.DataFrame:
    """【V0.9.5-etf-history】查詢指定日期的 ETF 持股快照"""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """SELECT date, etf_code, stock_code, stock_name,
                      weight_pct, shares, shares_lots, industry
               FROM etf_holding_history
               WHERE date = ?""",
            conn,
            params=(date_str,),
        )


def _query_latest_two_dates(db_path: str) -> Tuple[Optional[str], Optional[str]]:
    """【V0.9.5-etf-history】查詢最近兩個有資料的日期"""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM etf_holding_history ORDER BY date DESC LIMIT 2"
        ).fetchall()
    if not rows:
        return (None, None)
    today = rows[0][0]
    yesterday = rows[1][0] if len(rows) > 1 else None
    return (today, yesterday)


def _etf_dates_have_changes(db_path: str, date_a: str, date_b: str) -> bool:
    """【V0.9.5-etf-weekend-fix】判斷兩個日期的 (etf_code, stock_code, shares_lots) 是否有差異

    用途：判斷 date_a 是否為「週末/假日抓的 stale duplicate」
    - App 在週末抓 ETF 持股網頁、shares_lots 跟上一個交易日完全一樣
    - 這時 date_a 沒實質變動、應跳過、往前找
    - 任一 row 有差異就回 True（包含 A 有 B 沒 / B 有 A 沒 / shares 不同）
    """
    with sqlite3.connect(db_path) as conn:
        df_a = pd.read_sql_query(
            "SELECT etf_code, stock_code, shares_lots FROM etf_holding_history WHERE date = ?",
            conn, params=(date_a,),
        )
        df_b = pd.read_sql_query(
            "SELECT etf_code, stock_code, shares_lots FROM etf_holding_history WHERE date = ?",
            conn, params=(date_b,),
        )

    if df_a.empty and df_b.empty:
        return False
    if df_a.empty or df_b.empty:
        return True  # 一邊全空 = 大變動（全清倉 / 全新建倉）

    merged = df_a.merge(
        df_b,
        on=["etf_code", "stock_code"],
        how="outer",
        suffixes=("_a", "_b"),
    )
    merged["a"] = merged["shares_lots_a"].fillna(-1)  # -1 = 不存在
    merged["b"] = merged["shares_lots_b"].fillna(-1)
    return bool((merged["a"] != merged["b"]).any())


def _find_latest_changed_etf_pair(db_path: str, all_dates: list) -> tuple:
    """【V0.9.5-etf-weekend-fix】從 all_dates (DESC) 找「最後一個有實質變動的 (today, yesterday) 對」

    - 跳過「跟下一個日期完全一樣」的 stale date（週末/假日抓的）
    - 回傳 (today_str, yesterday_str) 或 None（找不到）
    """
    for i in range(len(all_dates) - 1):
        d_today = all_dates[i]
        d_yesterday = all_dates[i + 1]
        if _etf_dates_have_changes(db_path, d_today, d_yesterday):
            return (d_today, d_yesterday)
    return None


def _compute_etf_changes(db_path: str, today_str: str = None, yesterday_str: str = None) -> pd.DataFrame:
    """【V0.9.5-etf-history】計算個股的「今日 ETF 異動張數總和」

    算法：
    - 對每檔個股、聚合所有持有它的 ETF
    - 異動張數 = Σ (today_shares_lots - yesterday_shares_lots)
    - 若某個 ETF 今天新增（昨日無資料）→ 算 +today_shares_lots（全部增持）
    - 若某個 ETF 今天刪除（今日無資料）→ 算 -yesterday_shares_lots（全部減持）
    - 沒有 yesterday 資料的個股 → 該個股無變化（不列入結果）

    【V0.9.5-etf-weekend-fix】沒開盤的日子 fallback
    - App 在週末/假日抓 ETF 持股網頁、shares_lots 跟上一個交易日完全一樣（stale duplicate）
    - 原本用 dates[0] vs dates[1] 算 → diff 全 0 → 全部過濾 → 顯示 "--"
    - 改：用「最後一個有實質 shares 變動的日期」當 today、前一天當 yesterday
    - 例：6/28 (週日) DB 內 = [6/28, 6/27, 6/26, ...]
        6/28 vs 6/27 完全一樣 → 跳過
        6/27 vs 6/26 有 35 row 變動 → 用 6/27 當 today、6/26 當 yesterday
    """
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        # 多取幾天（週末/假日可能有 stale duplicate）
        cur = conn.execute(
            "SELECT DISTINCT date FROM etf_holding_history ORDER BY date DESC LIMIT 10"
        )
        all_dates = [r[0] for r in cur.fetchall()]
        if not all_dates:
            return pd.DataFrame()

        if today_str in all_dates:
            # caller 指定 today_str 嚴格用 caller 的（避免測試誤判）
            # 但仍要做 weekend fallback：dates[0] vs dates[1] 若完全相同、往前找
            candidate_today = all_dates[0]
            candidate_yesterday = all_dates[1] if len(all_dates) > 1 else None

            if (
                candidate_yesterday
                and not _etf_dates_have_changes(db_path, candidate_today, candidate_yesterday)
            ):
                # dates[0] 是週末/假日 stale → 往前找有變動的對
                found = _find_latest_changed_etf_pair(db_path, all_dates)
                if found:
                    candidate_today, candidate_yesterday = found
                # 找不到 → 保留原本的（會算 diff 全 0 → 過濾）

            today_str = candidate_today
            yesterday_str = candidate_yesterday
        else:
            # caller 沒指定 / today_str 是週末/假日（DB 沒這個日期）
            # → 從 all_dates 找「最後一個有實質變動的對」
            found = _find_latest_changed_etf_pair(db_path, all_dates)
            if not found:
                return pd.DataFrame()
            today_str, yesterday_str = found

        if yesterday_str is None:
            return pd.DataFrame()

        today_df = pd.read_sql_query(
            "SELECT * FROM etf_holding_history WHERE date = ?", conn, params=(today_str,)
        )
        yesterday_df = pd.read_sql_query(
            "SELECT * FROM etf_holding_history WHERE date = ?", conn, params=(yesterday_str,)
        )

    if today_df.empty and yesterday_df.empty:
        return pd.DataFrame()

    today_df["key"] = today_df["etf_code"].astype(str) + "_" + today_df["stock_code"].astype(str)
    yesterday_df["key"] = yesterday_df["etf_code"].astype(str) + "_" + yesterday_df["stock_code"].astype(str)

    merged = today_df.merge(
        yesterday_df[["key", "shares_lots", "stock_name"]].rename(
            columns={"shares_lots": "y_lots", "stock_name": "y_name"},
        ),
        on="key",
        how="outer",
    )
    if "stock_code" not in merged.columns:
        merged["stock_code"] = None
    merged["key_stock"] = merged["key"].str.split("_").str[1]
    merged["stock_code"] = merged["stock_code"].fillna(merged["key_stock"])

    merged["t_lots"] = merged["shares_lots"].fillna(0)
    merged["y_lots"] = merged["y_lots"].fillna(0)
    merged["change_lots"] = merged["t_lots"] - merged["y_lots"]

    rows = []
    for stock_code, g in merged.groupby("stock_code"):
        change_entries = []
        total_change = 0.0
        for _, r in g.iterrows():
            if r["change_lots"] != 0:
                ec = r["etf_code"]
                if pd.isna(ec):
                    ec = r["key"].split("_")[0]
                change_entries.append({
                    "etf_code": str(ec),
                    "etf_name": "",
                    "change_lots": float(r["change_lots"]),
                })
                total_change += float(r["change_lots"])
        today_name = g["stock_name"].dropna()
        y_name = g["y_name"].dropna()
        stock_name = today_name.iloc[0] if not today_name.empty else (y_name.iloc[0] if not y_name.empty else "")

        etf_count = int(g["etf_code"].notna().sum())
        if etf_count == 0:
            etf_count = int((g["y_lots"] > 0).sum())

        if not change_entries:
            continue
        rows.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "etf_count": etf_count,
            "today_change_lots": round(total_change, 3),
            "etf_changes_json": json.dumps(change_entries, ensure_ascii=False),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            by="today_change_lots",
            key=lambda s: s.abs(),
            ascending=False,
        ).reset_index(drop=True)
    return result


# ==========================================================
# 股利 DB CRUD
# ==========================================================

def _upsert_div_history(db_path: str, rows: list) -> int:
    """寫入股利資料到 dividend_history.db

    向後相容 tuple 格式：
    - 5-tuple：(stock_id, year, cash, stock, source)
    - 7-tuple：(stock_id, year, cash, stock, source, ex_date, ex_date_close)
    - 9-tuple：(stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct)
    """
    if not rows:
        return 0

    normalized = []
    for r in rows:
        n = len(r)
        if n == 5:
            normalized.append((r[0], r[1], r[2], r[3], r[4], None, None, None, None))
        elif n == 6:
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], None, None, None))
        elif n == 7:
            with sqlite3.connect(db_path) as conn:
                old = conn.execute(
                    "SELECT cash_yield_pct, share_yield_pct FROM dividend_history "
                    "WHERE stock_id=? AND year=?", (r[0], r[1])
                ).fetchone()
            old_cash_yld = old[0] if old else None
            old_share_yld = old[1] if old else None
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], old_cash_yld, old_share_yld))
        elif n == 8:
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], None))
        elif n == 9:
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
        elif n == 10:
            normalized.append((r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
        else:
            normalized.append(tuple(r[:9]))
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO dividend_history
               (stock_id, year, cash, stock, source, fetched_at, ex_date, ex_date_close,
                cash_yield_pct, share_yield_pct)
               VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?)""",
            normalized,
        )
        conn.commit()
    return len(normalized)


def _query_div_history(db_path: str, codes: list) -> dict:
    """查詢多檔股票的所有年度股利 → {code: {year: {cash, stock, ex_date}}}"""
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"SELECT stock_id, year, cash, stock, ex_date FROM dividend_history WHERE stock_id IN ({placeholders})",
            codes,
        ).fetchall()
    result: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for code, year, cash, stock, ex_date in rows:
        code = str(code).strip()
        result.setdefault(code, {})
        result[code][year] = {
            "cash": cash or 0.0,
            "stock": stock or 0.0,
            "ex_date": ex_date or "",
        }
    return result


def _query_div_history_with_fetched(db_path: str, codes: list) -> dict:
    """查詢多檔股票的股利 + fetched_at → {code: {"_fetched_at": iso_str, "years": {year: {...}}}"""
    if not codes:
        return {}
    with sqlite3.connect(db_path) as conn:
        placeholders = ",".join("?" * len(codes))
        rows = conn.execute(
            f"""SELECT stock_id, year, cash, stock, fetched_at, ex_date, ex_date_close,
                       cash_yield_pct, share_yield_pct
                FROM dividend_history WHERE stock_id IN ({placeholders})""",
            codes,
        ).fetchall()
    result: Dict[str, Dict] = {}
    for code, year, cash, stock, fetched_at, ex_date, ex_date_close, cash_yld, share_yld in rows:
        code = str(code).strip()
        if code not in result:
            result[code] = {"_fetched_at": fetched_at, "years": {}}
        result[code]["years"][year] = {
            "cash": cash or 0.0,
            "stock": stock or 0.0,
            "ex_date": ex_date or "",
            "ex_date_close": ex_date_close,
            "cash_yield_pct": cash_yld,
            "share_yield_pct": share_yld,
        }
    return result


def _div_history_stats(db_path: str) -> dict:
    if not os.path.exists(db_path):
        return {"total": 0, "stocks": 0, "years": 0}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM dividend_history").fetchone()[0]
        stocks = conn.execute("SELECT COUNT(DISTINCT stock_id) FROM dividend_history").fetchone()[0]
        years = conn.execute("SELECT COUNT(DISTINCT year) FROM dividend_history").fetchone()[0]
    return {"total": total, "stocks": stocks, "years": years}


# ==========================================================
# EPS 歷史庫 schema
# ==========================================================

EPS_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS eps_history (
    stock_id    TEXT    NOT NULL,
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    eps         REAL,
    source      TEXT,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (stock_id, year, quarter)
);
CREATE INDEX IF NOT EXISTS idx_eps_period ON eps_history(year, quarter);
"""


def _init_eps_history_db(db_path: str):
    """初始化/建立 EPS 歷史庫"""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(EPS_HISTORY_SCHEMA)
        conn.commit()


def _upsert_eps_history(db_path: str, rows: list) -> int:
    """rows: [(stock_id, year, quarter, eps, source), ...]"""
    if not rows:
        return 0
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO eps_history
               (stock_id, year, quarter, eps, source)
               VALUES (?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(rows)


def _query_eps_history(db_path: str, year: int, quarter: int) -> pd.DataFrame:
    """查詢指定 (year, quarter) 的歷史 EPS"""
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT stock_id, year, quarter, eps, source FROM eps_history WHERE year = ? AND quarter = ?",
            conn, params=(year, quarter),
        )
    if not df.empty:
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
    return df


def _eps_history_stats(db_path: str) -> dict:
    """回傳歷史庫摘要（給 GUI 狀態列用）"""
    if not os.path.exists(db_path):
        return {"total": 0, "periods": 0, "latest": None}
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM eps_history").fetchone()[0]
        periods = conn.execute("SELECT COUNT(DISTINCT year*10+quarter) FROM eps_history").fetchone()[0]
        latest = conn.execute(
            "SELECT year, quarter, COUNT(*) FROM eps_history "
            "ORDER BY year DESC, quarter DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "periods": periods,
        "latest": f"{latest[0]}Q{latest[1]} ({latest[2]}筆)" if latest else None,
    }
