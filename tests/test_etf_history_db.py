"""【V0.9.5-etf-history】ETF 持股歷史庫 + 異動計算守護

2026-06-20 17:54 William 需求：
- ETF 成份股統計加「今日異動」欄（張）
- Hover 顯示各 ETF 異動明細
- App 啟動只抓一次、歷史存 local DB

【抓取資料源】
- etfinfo.tw `/etf/{code}` SSR 資料直接含 shares（持股股數）
  範例：`2330","台積電",57.01,519237994,"股"`
  → 0050 持有台積電 519,237,994 股 = 519,237.994 張
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


@pytest.fixture
def temp_db():
    """建立 tmp 用的 etf_history.db"""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "etf_history.db")
    yield db_path
    shutil.rmtree(tmpdir, ignore_errors=True)


# ==========================================================
# 守護 1：_init_etf_history_db + _save_etf_holding_snapshot
# ==========================================================
def test_init_etf_history_db_creates_schema(temp_db):
    """DB schema 正確建立
    """
    from StockTool import _init_etf_history_db

    _init_etf_history_db(temp_db)

    with sqlite3.connect(temp_db) as conn:
        # 確認兩張表存在
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
    assert "etf_holding_history" in tables, f"❌ etf_holding_history 表未建立：{tables}"
    assert "fetch_meta" in tables, f"❌ fetch_meta 表未建立：{tables}"

    with sqlite3.connect(temp_db) as conn:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(etf_holding_history)"
        ).fetchall()]
    expected_cols = [
        "date", "etf_code", "stock_code", "stock_name",
        "weight_pct", "shares", "shares_lots", "industry", "fetched_at",
    ]
    for col in expected_cols:
        assert col in cols, f"❌ 缺少欄位 {col}、現有：{cols}"


def test_save_etf_holding_snapshot_inserts_rows(temp_db):
    """寫入一檔 ETF 持股快照、確認資料正確
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot

    _init_etf_history_db(temp_db)

    holdings = [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01,
         "shares": 519237994, "industry": "半導體"},
        {"stock_code": "2454", "stock_name": "聯發科", "weight": 6.28,
         "shares": 31410621, "industry": "半導體"},
    ]
    count = _save_etf_holding_snapshot(temp_db, "0050", holdings, date_str="2026-06-19")
    assert count == 2, f"❌ 應寫入 2 列、實際 {count}"

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            "SELECT stock_code, shares, shares_lots, weight_pct FROM etf_holding_history WHERE etf_code = ? ORDER BY stock_code",
            ("0050",),
        ).fetchall()
    assert len(rows) == 2
    # shares_lots = shares / 1000
    assert rows[0][0] == "2330"
    assert rows[0][1] == 519237994
    assert rows[0][2] == 519237.994
    assert rows[0][3] == 57.01


def test_save_etf_holding_snapshot_upsert(temp_db):
    """寫入同一天同一檔 → INSERT OR REPLACE（覆蓋）
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot

    _init_etf_history_db(temp_db)

    holdings_v1 = [{"stock_code": "2330", "stock_name": "台積電", "weight": 57.0, "shares": 100, "industry": ""}]
    _save_etf_holding_snapshot(temp_db, "0050", holdings_v1, date_str="2026-06-19")

    holdings_v2 = [{"stock_code": "2330", "stock_name": "台積電", "weight": 60.0, "shares": 200, "industry": ""}]
    _save_etf_holding_snapshot(temp_db, "0050", holdings_v2, date_str="2026-06-19")

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            "SELECT shares FROM etf_holding_history WHERE etf_code = ? AND stock_code = ?",
            ("0050", "2330"),
        ).fetchall()
    assert len(rows) == 1, f"❌ 應該只有 1 列、實際 {len(rows)}"
    assert rows[0][0] == 200, f"❌ 應該是覆蓋後的 200、實際 {rows[0][0]}"


def test_fetch_meta_updated(temp_db):
    """寫入快照後、fetch_meta.last_etf_snapshot_date 應更新
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot

    _init_etf_history_db(temp_db)

    holdings = [{"stock_code": "2330", "stock_name": "台積電", "weight": 57.0, "shares": 100, "industry": ""}]
    _save_etf_holding_snapshot(temp_db, "0050", holdings, date_str="2026-06-19")

    with sqlite3.connect(temp_db) as conn:
        meta = conn.execute(
            "SELECT value FROM fetch_meta WHERE key = ?",
            ("last_etf_snapshot_date",),
        ).fetchall()
    assert meta, "❌ fetch_meta 未寫入"
    assert meta[0][0] == "2026-06-19"


# ==========================================================
# 守護 2：_query_latest_two_dates
# ==========================================================
def test_query_latest_two_dates_returns_recent_two(temp_db):
    """有 2 個日期 → 回傳 (today, yesterday)
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _query_latest_two_dates

    _init_etf_history_db(temp_db)

    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 57.0, "shares": 100, "industry": ""}],
        date_str="2026-06-18",
    )
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 57.0, "shares": 200, "industry": ""}],
        date_str="2026-06-19",
    )

    today, yesterday = _query_latest_two_dates(temp_db)
    assert today == "2026-06-19", f"❌ today 應該是 2026-06-19、實際 {today}"
    assert yesterday == "2026-06-18", f"❌ yesterday 應該是 2026-06-18、實際 {yesterday}"


def test_query_latest_two_dates_no_yesterday(temp_db):
    """只有 1 個日期 → 回傳 (today, None)
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _query_latest_two_dates

    _init_etf_history_db(temp_db)

    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 57.0, "shares": 100, "industry": ""}],
        date_str="2026-06-19",
    )

    today, yesterday = _query_latest_two_dates(temp_db)
    assert today == "2026-06-19"
    assert yesterday is None, f"❌ yesterday 應該是 None、實際 {yesterday}"


# ==========================================================
# 守護 3：_compute_etf_changes
# ==========================================================
def test_compute_etf_changes_basic(temp_db):
    """基本情況：today shares 變多 → +diff
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _compute_etf_changes

    _init_etf_history_db(temp_db)

    # 昨日 0050 持有台積電 100,000 股 = 100 張
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": "半導體"}],
        date_str="2026-06-18",
    )

    # 今日 0050 持有台積電 200,000 股 = 200 張 (+100 張)
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 200000, "industry": "半導體"}],
        date_str="2026-06-19",
    )

    result = _compute_etf_changes(temp_db, today_str="2026-06-19")
    assert len(result) == 1, f"❌ 應該只有 1 列、實際 {len(result)}"
    assert result.iloc[0]["stock_code"] == "2330"
    assert result.iloc[0]["today_change_lots"] == 100.0, f"❌ 應該是 +100、實際 {result.iloc[0]['today_change_lots']}"

    # etf_changes_json 應有 1 筆異動
    changes = json.loads(result.iloc[0]["etf_changes_json"])
    assert len(changes) == 1
    assert changes[0]["etf_code"] == "0050"
    assert changes[0]["change_lots"] == 100.0


def test_compute_etf_changes_no_yesterday_returns_empty(temp_db):
    """沒有昨日資料 → 回傳空 DataFrame
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _compute_etf_changes

    _init_etf_history_db(temp_db)

    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": ""}],
        date_str="2026-06-19",
    )

    result = _compute_etf_changes(temp_db)
    assert result.empty, f"❌ 沒有昨日資料應該回傳空、實際 {len(result)} 列"


def test_compute_etf_changes_new_position(temp_db):
    """新增持股：昨日沒、今日有 → 算 +today_shares_lots
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _compute_etf_changes

    _init_etf_history_db(temp_db)

    # 昨日 0050 只持有台積電
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": ""}],
        date_str="2026-06-18",
    )

    # 今日 0050 加碼台積電 + 新增聯發科
    _save_etf_holding_snapshot(temp_db, "0050",
        [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 60.0, "shares": 200000, "industry": ""},
            {"stock_code": "2454", "stock_name": "聯發科", "weight": 5.0, "shares": 50000, "industry": ""},
        ],
        date_str="2026-06-19",
    )

    result = _compute_etf_changes(temp_db, today_str="2026-06-19")
    assert len(result) == 2, f"❌ 應該 2 列（2330 + 2454）、實際 {len(result)}"

    # 2330: +100 張
    row_2330 = result[result["stock_code"] == "2330"].iloc[0]
    assert row_2330["today_change_lots"] == 100.0

    # 2454: +50 張（新增）
    row_2454 = result[result["stock_code"] == "2454"].iloc[0]
    assert row_2454["today_change_lots"] == 50.0


def test_compute_etf_changes_deleted_position(temp_db):
    """刪除持股：昨日有、今日無 → 算 -yesterday_shares_lots
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _compute_etf_changes

    _init_etf_history_db(temp_db)

    # 昨日 0050 持有台積電 + 聯發科
    _save_etf_holding_snapshot(temp_db, "0050",
        [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": ""},
            {"stock_code": "2454", "stock_name": "聯發科", "weight": 5.0, "shares": 50000, "industry": ""},
        ],
        date_str="2026-06-18",
    )

    # 今日 0050 只剩台積電（聯發科被賣掉）
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": ""}],
        date_str="2026-06-19",
    )

    result = _compute_etf_changes(temp_db, today_str="2026-06-19")
    # 2454 應該 -50 張（被刪除）
    assert len(result) == 1, f"❌ 應該只有 2454 一列（被刪）、實際 {len(result)}"
    row = result.iloc[0]
    assert row["stock_code"] == "2454"
    assert row["today_change_lots"] == -50.0


def test_compute_etf_changes_multiple_etfs_same_stock(temp_db):
    """同一個股被多檔 ETF 持有 → 異動應加總
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _compute_etf_changes

    _init_etf_history_db(temp_db)

    # 昨日：0050 持 100,000 股、006208 持 50,000 股
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": ""}],
        date_str="2026-06-18",
    )
    _save_etf_holding_snapshot(temp_db, "006208",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 50000, "industry": ""}],
        date_str="2026-06-18",
    )

    # 今日：0050 加碼到 150,000 股 (+50)、006208 減碼到 30,000 股 (-20)
    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 150000, "industry": ""}],
        date_str="2026-06-19",
    )
    _save_etf_holding_snapshot(temp_db, "006208",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 30000, "industry": ""}],
        date_str="2026-06-19",
    )

    result = _compute_etf_changes(temp_db, today_str="2026-06-19")
    assert len(result) == 1
    # 個股 2330 總異動 = +50 + (-20) = +30 張
    assert result.iloc[0]["today_change_lots"] == 30.0, f"❌ 總和應該是 +30、實際 {result.iloc[0]['today_change_lots']}"

    # popup 應有 2 筆明細
    changes = json.loads(result.iloc[0]["etf_changes_json"])
    assert len(changes) == 2


# ==========================================================
# 守護 4：_query_etf_holdings_by_date
# ==========================================================
def test_query_etf_holdings_by_date(temp_db):
    """查詢指定日期持股
    """
    from StockTool import _init_etf_history_db, _save_etf_holding_snapshot, _query_etf_holdings_by_date

    _init_etf_history_db(temp_db)

    _save_etf_holding_snapshot(temp_db, "0050",
        [{"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 100000, "industry": "半導體"}],
        date_str="2026-06-19",
    )

    df = _query_etf_holdings_by_date(temp_db, "2026-06-19")
    assert len(df) == 1
    assert df.iloc[0]["stock_code"] == "2330"
    assert df.iloc[0]["shares"] == 100000
    assert df.iloc[0]["shares_lots"] == 100.0


# ==========================================================
# 守護 5：fetch_etf_top10_holdings 應該也拿 shares + industry
# ==========================================================
def test_fetch_etf_top10_holdings_includes_shares():
    """從 etfinfo.tw SSR 抓 holdings、應該也包含 shares + industry

    修正原本 fetcher 只抓 stock_code, stock_name, weight、不抓 shares
    → 這樣 save 進 DB 時就沒有 shares 資料
    """
    import inspect
    from StockTool import fetch_etf_top10_holdings
    src = inspect.getsource(fetch_etf_top10_holdings)
    assert "shares" in src, (
        "❌ fetch_etf_top10_holdings 沒抓 shares 資料！\n"
        "etfinfo.tw SSR 內含 shares（持股股數）、需 parse 出來存進 DB。"
    )
    assert "industry" in src, (
        "❌ fetch_etf_top10_holdings 沒抓 industry 資料！\n"
        "etfinfo.tw SSR 內含 industry（產業別）。"
    )