# test_dividend_yield_fix.py - V0.9.5-twser2
import os, sys, sqlite3, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構

CY = 2026


def insert9(db, stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yld, share_yld):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO dividend_history (stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yield_pct, share_yield_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (stock_id, year, cash, stock, source, ex_date, ex_date_close, cash_yld, share_yld)
        )
        conn.commit()


def test_bug1_fetch_returns_yield():
    db = tempfile.mktemp(suffix=".db")
    try:
        st._init_div_history_db(db)
        insert9(db, "TST1", CY, 3.5, 1.0, "goodinfo", "2026-07-15", 120.0, 2.91, 0.83)
        insert9(db, "TST1", CY - 1, 2.8, 0.5, "goodinfo", "2025-07-16", 115.0, 2.43, 0.43)

        result = st_fetch_market._fetch_finmind_dividend(["TST1"], db_path=db, skip_remote=True)
        assert not result.empty
        row = result.iloc[0]

        col_yld = f"{CY}現金殖利率_goodinfo"
        col_stk_yld = f"{CY}股票殖利率_goodinfo"
        col_last_yld = f"{CY-1}現金殖利率_goodinfo"
        col_last_stk_yld = f"{CY-1}股票殖利率_goodinfo"

        assert row.get(col_yld) is not None, f"got None for {col_yld}"
        assert row.get(col_yld) == 2.91, f"got {row.get(col_yld)}"
        assert row.get(col_last_yld) == 2.43
        assert row.get(col_stk_yld) == 0.83
        assert row.get(col_last_stk_yld) == 0.43
        assert row.get(f"{CY}現金股利") == 3.5
        assert row.get(f"{CY}股票股利") == 1.0
        print("PASS: test_bug1_fetch_returns_yield")
    finally:
        try: os.unlink(db)
        except: pass


def test_bug1_multi_stocks():
    db = tempfile.mktemp(suffix=".db")
    try:
        st._init_div_history_db(db)
        insert9(db, "M001", CY, 1.0, 0.5, "goodinfo", None, None, 1.5, 0.75)
        insert9(db, "M002", CY, 2.0, 0.0, "goodinfo", None, None, 3.2, 0.0)

        result = st_fetch_market._fetch_finmind_dividend(["M001", "M002"], db_path=db, skip_remote=True)
        assert len(result) == 2
        by_code = {row["股票代號"]: row for _, row in result.iterrows()}

        yld_key = f"{CY}現金殖利率_goodinfo"
        stk_key = f"{CY}股票殖利率_goodinfo"
        assert by_code["M001"][yld_key] == 1.5
        assert by_code["M002"][yld_key] == 3.2
        assert by_code["M001"][stk_key] == 0.75
        # stock yield=0.0 must be 0.0 (not None)
        assert by_code["M002"][stk_key] == 0.0, f"got {by_code['M002'][stk_key]}"
        print("PASS: test_bug1_multi_stocks")
    finally:
        try: os.unlink(db)
        except: pass


def test_bug2_upsert7_preserves_yield():
    db = tempfile.mktemp(suffix=".db")
    try:
        st._init_div_history_db(db)
        insert9(db, "BUG7", CY, 3.0, 1.0, "goodinfo", None, None, 2.5, 0.9)

        # 7-tuple upsert (old-style FinMind caller) - should NOT destroy yield
        st._upsert_div_history(db, [("BUG7", CY, 4.0, 0.5, "finmind", "2026-07-20", None)])

        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT cash, stock, source, cash_yield_pct, share_yield_pct FROM dividend_history WHERE stock_id='BUG7'"
            ).fetchone()
            cash, stock, source, cld, sld = row
            assert cld == 2.5, f"cash_yield_pct destroyed: got {cld}"
            assert sld == 0.9, f"share_yield_pct destroyed: got {sld}"
            assert cash == 4.0
            assert stock == 0.5
        print("PASS: test_bug2_upsert7_preserves_yield")
    finally:
        try: os.unlink(db)
        except: pass


def test_bug2_upsert9_writes_yield():
    db = tempfile.mktemp(suffix=".db")
    try:
        st._init_div_history_db(db)
        st._upsert_div_history(db, [
            ("NINE9", CY, 2.0, 0.5, "goodinfo", "2026-07-10", 80.0, 2.5, 0.6)
        ])
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT cash_yield_pct, share_yield_pct FROM dividend_history WHERE stock_id='NINE9'"
            ).fetchone()
            assert row[0] == 2.5, f"cash_yield_pct: got {row[0]}"
            assert row[1] == 0.6, f"share_yield_pct: got {row[1]}"
        print("PASS: test_bug2_upsert9_writes_yield")
    finally:
        try: os.unlink(db)
        except: pass


def test_bug2_upsert5_backward_compat():
    db = tempfile.mktemp(suffix=".db")
    try:
        st._init_div_history_db(db)
        st._upsert_div_history(db, [("OLD5T", CY - 1, 1.5, 0.0, "manual")])
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT cash, stock, cash_yield_pct, share_yield_pct FROM dividend_history WHERE stock_id='OLD5T'"
            ).fetchone()
            assert row[0] == 1.5
            assert row[1] == 0.0
            assert row[3] is None, f"share_yield_pct should be NULL for 5-tuple, got {row[3]}"
        print("PASS: test_bug2_upsert5_backward_compat")
    finally:
        try: os.unlink(db)
        except: pass


def test_skip_remote_no_finmind():
    db = tempfile.mktemp(suffix=".db")
    st._init_div_history_db(db)
    insert9(db, "SKIP1", CY, 5.0, 1.0, "goodinfo", None, None, 4.1, 0.8)
    insert9(db, "SKIP1", CY - 1, 4.0, 0.5, "goodinfo", None, None, 3.3, 0.4)
    insert9(db, "SKIP1", CY - 2, 3.5, 0.0, "goodinfo", None, None, 2.9, 0.0)

    called = []
    orig = st_fetch_market._finmind_get
    def tracker(*a, **kw):
        called.append((a, kw))
        return []
    st_fetch_market._finmind_get = tracker
    try:
        result = st_fetch_market._fetch_finmind_dividend(["SKIP1"], db_path=db, skip_remote=True)
    finally:
        st_fetch_market._finmind_get = orig

    assert len(called) == 0, f"skip_remote=True must NOT call FinMind, called {len(called)} times"
    row = result.iloc[0]
    yld_key = f"{CY}現金殖利率_goodinfo"
    assert row[yld_key] == 4.1, f"got {row[yld_key]}"
    print("PASS: test_skip_remote_no_finmind")
    try: os.unlink(db)
    except: pass


if __name__ == "__main__":
    test_bug1_fetch_returns_yield()
    test_bug1_multi_stocks()
    test_bug2_upsert7_preserves_yield()
    test_bug2_upsert9_writes_yield()
    test_bug2_upsert5_backward_compat()
    test_skip_remote_no_finmind()
    print("\nAll dividend yield fix tests passed!")
