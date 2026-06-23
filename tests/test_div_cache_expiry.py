"""
test_div_cache_expiry.py
驗證 V0.9.5+ DB cache 過期 → 自動重抓 FinMind 的邏輯。

【情境】
William 11:38 說：
「DB cache 若沒補或者已經過期則要去Finmind抓！
 這樣應該就知道握額度不夠爾且資料還沒refresh」

【改法】
- _fetch_finmind_dividend 加 cache_max_age_days 參數（預設 30 天）
- DB 資料超過 N 天 → 視為過期 → 加入 to_fetch（重抓 FinMind）
- DB 資料未過期 → 跳過（不打 API）

【為什麼要這個】
原本邏輯：DB 有資料 → 永遠不重抓
問題：DB 資料可能是 6 個月前抓的 → 配息公告後 DB 沒更新 → 使用者誤以為「資料正確」
改後：DB 過期 → 自動重抓 → 使用者會看到 402 額度錯誤 → 知道「要等下月」
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


def test_查詢DB_含fetched_at_新加函數():
    """_query_div_history_with_fetched 應回傳 fetched_at 欄位"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "test")])

        result = st._query_div_history_with_fetched(db_path, ["3188"])
        assert "3188" in result
        assert "_fetched_at" in result["3188"], "應有 _fetched_at 欄位"
        assert 2025 in result["3188"]["years"]
        assert result["3188"]["years"][2025]["cash"] == 3.196
        # fetched_at 應為 ISO 格式字串
        assert isinstance(result["3188"]["_fetched_at"], str)
    finally:
        os.unlink(db_path)


def test_DB空_cache_全部要抓():
    """DB 完全沒資料 → 全部要抓"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        result_df = st_fetch_market._fetch_finmind_dividend(
            ["A1", "A2", "A3"], db_path=db_path,
        )
        assert isinstance(result_df, pd.DataFrame)
        assert call_log == ["A1", "A2", "A3"]
    finally:
        os.unlink(db_path)


def test_DB有資料_新鮮_不重抓():
    """DB 資料 1 天前抓的（沒過期）→ 不重抓"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # 模擬 1 天前抓的資料
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "finmind")])
        # 把 fetched_at 改成 1 天前
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE dividend_history SET fetched_at = ? WHERE stock_id = '3188'",
                (one_day_ago,),
            )
            conn.commit()

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["3188"], db_path=db_path, cache_max_age_days=30,
        )
        # 1 天前抓的，沒過期 → 不打 FinMind
        assert call_log == [], f"不該打 FinMind，實際: {call_log}"
    finally:
        os.unlink(db_path)


def test_DB有資料_過期_重抓():
    """DB 資料 60 天前抓的（超過 30 天 cache 期限）→ 重抓 FinMind"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "finmind")])
        # 把 fetched_at 改成 60 天前
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE dividend_history SET fetched_at = ? WHERE stock_id = '3188'",
                (sixty_days_ago,),
            )
            conn.commit()

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["3188"], db_path=db_path, cache_max_age_days=30,
        )
        # 60 天前抓的，過期 → 重抓
        assert call_log == ["3188"]
    finally:
        os.unlink(db_path)


def test_部分過期_只重抓過期的():
    """3 檔中 1 檔過期、2 檔新鮮 → 只重抓過期那 1 檔"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # 3 檔都先寫入
        for c in ["A1", "A2", "A3"]:
            st._upsert_div_history(db_path, [(c, 2025, 1.0, 0.0, "finmind")])
        # 把 A2 改成 60 天前（過期）、A1/A3 保持新鮮
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE dividend_history SET fetched_at = ? WHERE stock_id = 'A2'",
                (sixty_days_ago,),
            )
            conn.commit()

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["A1", "A2", "A3"], db_path=db_path, cache_max_age_days=30,
        )
        assert call_log == ["A2"], f"應只抓 A2，實際: {call_log}"
    finally:
        os.unlink(db_path)


def test_cache_max_age_days_0_全部視為過期():
    """cache_max_age_days=0 → 所有有資料的股票都視為過期（強制重抓）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "finmind")])

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["3188"], db_path=db_path, cache_max_age_days=0,
        )
        # cache=0 天 → 剛抓的也算過期 → 重抓
        assert call_log == ["3188"]
    finally:
        os.unlink(db_path)


def test_cache_max_age_days_負數_視為無限大():
    """cache_max_age_days=-1 → 視為無限大（永不過期、保持原本行為）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "finmind")])
        # 把 fetched_at 改成 5 年前（超級舊）
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            five_years_ago = (datetime.now() - timedelta(days=1825)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE dividend_history SET fetched_at = ? WHERE stock_id = '3188'",
                (five_years_ago,),
            )
            conn.commit()

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["3188"], db_path=db_path, cache_max_age_days=-1,
        )
        # cache=-1 → 永不過期 → 不打 FinMind
        assert call_log == []
    finally:
        os.unlink(db_path)


def test_skip_remote_仍跳過FinMind():
    """skip_remote=True → 不打 FinMind（無論是否過期）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "finmind")])
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE dividend_history SET fetched_at = ? WHERE stock_id = '3188'",
                (sixty_days_ago,),
            )
            conn.commit()

        call_log = []
        def fake_get(dataset, code, start, end, retry=2):
            call_log.append(code)
            return []
        st_fetch_market._finmind_get = fake_get

        st_fetch_market._fetch_finmind_dividend(
            ["3188"], db_path=db_path, cache_max_age_days=30, skip_remote=True,
        )
        # skip_remote=True → 不打 FinMind
        assert call_log == []
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_查詢DB_含fetched_at_新加函數()
    print("✅ test_查詢DB_含fetched_at_新加函數 passed")
    test_DB空_cache_全部要抓()
    print("✅ test_DB空_cache_全部要抓 passed")
    test_DB有資料_新鮮_不重抓()
    print("✅ test_DB有資料_新鮮_不重抓 passed")
    test_DB有資料_過期_重抓()
    print("✅ test_DB有資料_過期_重抓 passed")
    test_部分過期_只重抓過期的()
    print("✅ test_部分過期_只重抓過期的 passed")
    test_cache_max_age_days_0_全部視為過期()
    print("✅ test_cache_max_age_days_0_全部視為過期 passed")
    test_cache_max_age_days_負數_視為無限大()
    print("✅ test_cache_max_age_days_負數_視為無限大 passed")
    test_skip_remote_仍跳過FinMind()
    print("✅ test_skip_remote_仍跳過FinMind passed")
    print("\n🎉 All cache expiry tests passed!")
