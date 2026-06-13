"""
test_dividend_fetch_all.py
驗證「補抓全部股利」邏輯。

【問題】(V0.9.5-alpha)
股利 DB 只有 351/2374 檔，導致手動選股時 86% 的股票殖利率欄位是 "—"
（截圖中 1438/6020/2548 等都沒資料）

【修正】
加一個「💰 補抓全部股利」按鈕：
- 跑 _background_fetch_all_dividend 補抓所有缺漏
- 帶 progress_callback 讓 UI 顯示進度
- 抓完寫入 DB
"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _mock_finmind_for_6231():
    """Mock FinMind 回傳 6231 雙鴻的股利資料（用來驗證 _background_fetch_all_dividend 會正確寫入 DB）"""
    return [{
        "year": "114年",       # 民國 114 = 西元 2025
        "CashEarningsDistribution": 8.5,
        "StockEarningsDistribution": 0.0,
    }]


def test_background_fetch_all_dividend_跳過已在DB的():
    """如果股票已在 DB，不會重抓"""
    # 寫一個暫存 DB，內含 3188
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "test")])
        st._upsert_div_history(db_path, [("3188", 2024, 1.8, 0.0, "test")])

        # mock _finmind_get：記錄被呼叫幾次
        call_count = {"n": 0}
        def fake_get(dataset, code, start, end, retry=2):
            call_count["n"] += 1
            return _mock_finmind_for_6231()
        st._finmind_get = fake_get

        # 只給 3188 + 6231，3188 在 DB 應跳過、6231 應被抓
        added = st._background_fetch_all_dividend(["3188", "6231"], db_path=db_path)
        assert added == 1, f"應抓 1 檔（6231），實際: {added}"
        assert call_count["n"] == 1, f"應只 call FinMind 1 次，實際: {call_count['n']}"
    finally:
        os.unlink(db_path)


def test_background_fetch_all_dividend_progress_callback():
    """progress_callback 應在每抓一檔被呼叫"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        progress_calls = []
        def cb(done, total):
            progress_calls.append((done, total))
        st._finmind_get = lambda *args, **kwargs: []
        st._background_fetch_all_dividend(
            ["A1", "A2", "A3"], db_path=db_path, progress_callback=cb,
        )
        # 應有 3 次 callback（每檔一次）
        assert len(progress_calls) == 3, f"應 3 次 callback，實際: {len(progress_calls)}"
        assert progress_calls[-1] == (3, 3), f"最後一次應為 (3,3)，實際: {progress_calls[-1]}"
    finally:
        os.unlink(db_path)


def test_background_fetch_all_dividend_全部已在DB_回傳0():
    """全部已在 DB → 回傳 0、不 call FinMind"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "test")])

        call_count = {"n": 0}
        def fake_get(*args, **kwargs):
            call_count["n"] += 1
            return []
        st._finmind_get = fake_get

        added = st._background_fetch_all_dividend(["3188"], db_path=db_path)
        assert added == 0, f"應 0，實際: {added}"
        assert call_count["n"] == 0, f"FinMind 不該被呼叫，實際: {call_count['n']}"
    finally:
        os.unlink(db_path)


def test_background_fetch_all_dividend_寫入DB後可查詢():
    """驗證抓完後 _query_div_history 找得到"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)

        def fake_get(dataset, code, start, end, retry=2):
            if code == "6231":
                return [{
                    "year": "114年",
                    "CashEarningsDistribution": 8.5,
                    "StockEarningsDistribution": 0.0,
                }]
            return []
        st._finmind_get = fake_get

        st._background_fetch_all_dividend(["6231"], db_path=db_path)

        # 查詢
        cached = st._query_div_history(db_path, ["6231"])
        assert "6231" in cached, "6231 應在 DB"
        assert 2025 in cached["6231"], "2025 應在 6231 的年度 dict"
        assert abs(cached["6231"][2025]["cash"] - 8.5) < 0.01, \
            f"cash 應為 8.5，實際: {cached['6231'][2025]['cash']}"
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_background_fetch_all_dividend_跳過已在DB的()
    print("✅ test_background_fetch_all_dividend_跳過已在DB的 passed")
    test_background_fetch_all_dividend_progress_callback()
    print("✅ test_background_fetch_all_dividend_progress_callback passed")
    test_background_fetch_all_dividend_全部已在DB_回傳0()
    print("✅ test_background_fetch_all_dividend_全部已在DB_回傳0 passed")
    test_background_fetch_all_dividend_寫入DB後可查詢()
    print("✅ test_background_fetch_all_dividend_寫入DB後可查詢 passed")
    print("\n🎉 All tests passed!")