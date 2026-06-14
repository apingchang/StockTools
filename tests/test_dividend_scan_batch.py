"""
test_dividend_scan_batch.py
驗證「💰 掃描全部股票 (100檔/次)」的 batch_size 分批邏輯。

【問題】(V0.9.5+ 改版)
原本「💰 補抓全部股利」是一次性抓全部缺漏，導致 Free tier (300-1000 筆/月)
一口氣爆 2000 檔就 402 失敗。

【修正】
- _background_fetch_all_dividend 加 batch_size 參數
- 「💰 掃描全部股票」按鈕呼叫 batch_size=100
- 每次只抓缺漏中的前 100 檔，跑完停、可下次再按繼續抓下一批
- 狀態顯示「這次 +X｜剩 Y（再 N 次可補完）」
"""
import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _fake_get_factory(call_log):
    """建立一個會記錄被呼叫股號的 fake _finmind_get"""
    def fake_get(dataset, code, start, end, retry=2):
        call_log.append(code)
        return []
    return fake_get


def test_batch_size_限制_只抓前N檔():
    """batch_size=3 → 缺漏 5 檔只抓前 3 檔（剩下 2 留給下次）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # 5 檔全部不在 DB
        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3", "A4", "A5"], db_path=db_path, batch_size=3,
        )
        # 應抓 3 檔、call_log 應為前 3 個
        assert added == 3, f"應抓 3 檔，實際: {added}"
        assert call_log == ["A1", "A2", "A3"], \
            f"FinMind 應只被呼叫 A1/A2/A3，實際: {call_log}"
    finally:
        os.unlink(db_path)


def test_batch_size_None_等於全部抓():
    """batch_size=None → 缺漏全部抓（向後相容舊行為）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3", "A4", "A5"], db_path=db_path, batch_size=None,
        )
        assert added == 5, f"應抓 5 檔，實際: {added}"
        assert len(call_log) == 5, f"FinMind 應被呼叫 5 次，實際: {len(call_log)}"
    finally:
        os.unlink(db_path)


def test_batch_size_超過缺漏_等於全部抓():
    """batch_size=100 但缺漏只有 5 檔 → 5 檔全部抓（不浪費）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3", "A4", "A5"], db_path=db_path, batch_size=100,
        )
        assert added == 5, f"應抓 5 檔，實際: {added}"
        assert len(call_log) == 5
    finally:
        os.unlink(db_path)


def test_batch_size_跳過已在DB的_再切片():
    """已在 DB 的先跳過、剩下的再切片 → 確保分批是針對「缺漏」而非「總清單」"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # A1/A2 已在 DB → 應跳過；剩下 A3~A7 是缺漏 → batch=3 只抓前 3 個
        st._upsert_div_history(db_path, [("A1", 2025, 1.0, 0.0, "test")])
        st._upsert_div_history(db_path, [("A2", 2025, 1.0, 0.0, "test")])

        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3", "A4", "A5", "A6", "A7"], db_path=db_path, batch_size=3,
        )
        assert added == 3, f"應抓 3 檔（A3/A4/A5），實際: {added}"
        assert call_log == ["A3", "A4", "A5"], \
            f"應跳過 A1/A2、只抓 A3/A4/A5，實際: {call_log}"
    finally:
        os.unlink(db_path)


def test_batch_size_0或負數_等於None():
    """batch_size=0 或負數 → 視同 None（全部抓、不切片）"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        # batch_size=0
        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3"], db_path=db_path, batch_size=0,
        )
        assert added == 3, f"batch=0 應抓全部，實際: {added}"
        assert len(call_log) == 3

        # batch_size=-1
        call_log.clear()
        added = st._background_fetch_all_dividend(
            ["B1", "B2", "B3"], db_path=db_path, batch_size=-1,
        )
        assert added == 3, f"batch=-1 應抓全部，實際: {added}"
        assert len(call_log) == 3
    finally:
        os.unlink(db_path)


def test_batch_size_全部已在DB_回傳0():
    """全部已在 DB → batch_size 不影響、仍回傳 0"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        for c in ["A1", "A2", "A3"]:
            st._upsert_div_history(db_path, [(c, 2025, 1.0, 0.0, "test")])

        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3"], db_path=db_path, batch_size=2,
        )
        assert added == 0, f"應回傳 0，實際: {added}"
        assert call_log == [], "FinMind 不該被呼叫"
    finally:
        os.unlink(db_path)


def test_batch_size_402_仍回傳負值():
    """batch_size 模式下遇到 FinMind 402 → 仍回傳 -1"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        def fake_get_with_402(*args, **kwargs):
            raise RuntimeError("FinMind 額度已用完（status 402）")
        st._finmind_get = fake_get_with_402

        added = st._background_fetch_all_dividend(
            ["A1", "A2", "A3", "A4", "A5"], db_path=db_path, batch_size=3,
        )
        # 第一檔就 402 → 立刻 break → 回傳 -1
        assert added == -1, f"402 應回傳 -1，實際: {added}"
    finally:
        os.unlink(db_path)


def test_100檔_次_典型情境():
    """模擬典型 V0.9.5+ 使用情境：
    - 全市場 2374 檔
    - DB 已有 351 檔 → 缺漏 2023 檔
    - batch_size=100 → 這次抓 100 檔、剩 1923 檔（再按 20 次可補完）
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # 模擬 DB 已有 351 檔（前 351 個股號視為已在 DB）
        all_codes = [f"{i:04d}" for i in range(1000, 1000 + 2374)]
        in_db_codes = all_codes[:351]
        for c in in_db_codes:
            st._upsert_div_history(db_path, [(c, 2025, 1.0, 0.0, "test")])

        call_log = []
        st._finmind_get = _fake_get_factory(call_log)

        added = st._background_fetch_all_dividend(
            all_codes, db_path=db_path, batch_size=100,
        )
        # 應抓 100 檔
        assert added == 100, f"應抓 100 檔，實際: {added}"
        assert len(call_log) == 100
        # 抓的應是「缺漏中的前 100 個」= 從 1351 開始
        assert call_log[0] == "1351", f"第一個應為 1351，實際: {call_log[0]}"
        assert call_log[-1] == "1450", f"最後一個應為 1450，實際: {call_log[-1]}"
        # 對應「再按 20 次」可補完（(2023-100)/100 + 1 = 20.23 → 20）
        # 實際算出：剩 1923 → ceil(1923/100) = 20 次
        remaining = 2023 - 100
        runs_left = (remaining + 99) // 100  # 20
        assert runs_left == 20, f"再按次數應為 20，實際: {runs_left}"
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_batch_size_限制_只抓前N檔()
    print("✅ test_batch_size_限制_只抓前N檔 passed")
    test_batch_size_None_等於全部抓()
    print("✅ test_batch_size_None_等於全部抓 passed")
    test_batch_size_超過缺漏_等於全部抓()
    print("✅ test_batch_size_超過缺漏_等於全部抓 passed")
    test_batch_size_跳過已在DB的_再切片()
    print("✅ test_batch_size_跳過已在DB的_再切片 passed")
    test_batch_size_0或負數_等於None()
    print("✅ test_batch_size_0或負數_等於None passed")
    test_batch_size_全部已在DB_回傳0()
    print("✅ test_batch_size_全部已在DB_回傳0 passed")
    test_batch_size_402_仍回傳負值()
    print("✅ test_batch_size_402_仍回傳負值 passed")
    test_100檔_次_典型情境()
    print("✅ test_100檔_次_典型情境 passed")
    print("\n🎉 All batch tests passed!")
