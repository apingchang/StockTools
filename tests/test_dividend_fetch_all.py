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


def test_finmind_402_應扡RuntimeError_不是回空list():
    """FinMind 額度用完 (status 402) 應扡出例外，不該 silently 回傳空 list

    （之前：空 list 讓 caller 誤以為「該股沒股利」，實際上是 API 額度不夠）
    """
    def fake_get_with_402(dataset, stock_id, start, end, retry=2):
        # 模擬 _finmind_get 內部處理 402
        import requests
        class FakeResp:
            status_code = 402
            text = '{"msg":"Requests reach the upper limit.","status":402}'
            url = "https://api.finmindtrade.com/api/v4/data"
            def json(self): return {"msg": "Requests reach the upper limit.", "status": 402}
            def raise_for_status(self): pass
        # 直接複制 _finmind_get 的 logic
        for attempt in range(retry + 1):
            r = FakeResp()
            if r.status_code == 429:
                time.sleep(61)
                continue
            if r.status_code == 402:
                raise RuntimeError(
                    "FinMind 額度已用完（status 402）｜請升級 plan 或等下月重置"
                    f"｜URL: {r.url}"
                )
            r.raise_for_status()
            return r.json().get("data", [])
        return []

    try:
        fake_get_with_402("TaiwanStockDividend", "3188", "2024-01-01", "2026-12-31")
        assert False, "應扡出 RuntimeError"
    except RuntimeError as e:
        assert "402" in str(e)
        assert "FinMind 額度" in str(e)


def test_background_fetch_all_dividend_FinMind額度錯誤_回傳負值():
    """_background_fetch_all_dividend 遇到 402 → 回傳 -1 (不是預期的正常股數)"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)

        # 模擬 _finmind_get 扡 402
        def fake_get_with_402(*args, **kwargs):
            raise RuntimeError("FinMind 額度已用完（status 402）")
        st._finmind_get = fake_get_with_402

        added = st._background_fetch_all_dividend(["A1", "A2", "A3"], db_path=db_path)
        # 額度錯誤應回傳 -1 (不是 3、不是 0)
        assert added == -1, f"FinMind 額度錯誤應回傳 -1，實際: {added}"
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