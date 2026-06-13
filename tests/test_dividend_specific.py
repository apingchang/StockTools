"""
test_dividend_specific.py
驗證「指定股補抓」的股號解析邏輯（Free tier 適用）。

【情境】(V0.9.5-alpha)
William 是 FinMind Free tier (300-1000 筆/月額度)，
不能一次補抓全市場 2023 檔 → 需要「指定股補抓」UI。

【測試項目】
- 解析多種分隔格式（逗號、空格、換行、中文逗號）
- 跳過空白
- 限 100 檔（超過截斷）
"""
import os
import re
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _parse_codes(raw: str, max_n: int = 100):
    """複制 _ms_fetch_specific_dividend 內的解析邏輯"""
    _re = re.compile(r"[\s,，]+")
    codes = [c.strip() for c in _re.split(raw) if c.strip()]
    if len(codes) > max_n:
        codes = codes[:max_n]
    return codes


def test_parse_codes_逗號分隔():
    assert _parse_codes("2330,2454,2317") == ["2330", "2454", "2317"]


def test_parse_codes_空格分隔():
    assert _parse_codes("2330 2454 2317") == ["2330", "2454", "2317"]


def test_parse_codes_換行分隔():
    assert _parse_codes("2330\n2454\n2317") == ["2330", "2454", "2317"]


def test_parse_codes_中文逗號():
    """台灣使用者常打中文逗號「，」"""
    assert _parse_codes("2330，2454，2317") == ["2330", "2454", "2317"]


def test_parse_codes_混合分隔():
    assert _parse_codes("2330, 2454 2317\n2318") == ["2330", "2454", "2317", "2318"]


def test_parse_codes_跳過空白():
    assert _parse_codes("  2330 ,  , 2454  ") == ["2330", "2454"]


def test_parse_codes_超過100檔截斷():
    raw = ",".join(str(i) for i in range(150))
    codes = _parse_codes(raw, max_n=100)
    assert len(codes) == 100
    assert codes[0] == "0"
    assert codes[-1] == "99"


def test_parse_codes_空字串():
    assert _parse_codes("") == []


def test_parse_codes_只空白():
    assert _parse_codes("   ,  ,  ") == []


def test_specific_dividend_只抓缺漏的():
    """模擬 _ms_fetch_specific_dividend 跳過已在 DB 的股"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        st._init_div_history_db(db_path)
        # 3188 已在 DB
        st._upsert_div_history(db_path, [("3188", 2025, 3.196, 0.0, "test")])

        def fake_get(dataset, code, start, end, retry=2):
            if code == "2330":
                return [{
                    "year": "114年",
                    "CashEarningsDistribution": 4.0,
                    "StockEarningsDistribution": 0.0,
                }]
            return []
        st._finmind_get = fake_get

        # 用戶輸入 2330, 3188, 2317
        user_input = "2330,3188,2317"
        codes = _parse_codes(user_input)
        cached = st._query_div_history(db_path, codes)
        to_fetch = [c for c in codes if c not in cached]

        # 3188 已在 DB 跳過，2330 + 2317 應被抓
        assert "3188" not in to_fetch
        assert set(to_fetch) == {"2330", "2317"}

        added = st._background_fetch_all_dividend(to_fetch, db_path=db_path)
        assert added == 2

        # 2330 應在 DB
        cached_after = st._query_div_history(db_path, ["2330", "3188"])
        assert "2330" in cached_after
        assert "3188" in cached_after
        assert abs(cached_after["2330"][2025]["cash"] - 4.0) < 0.01
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    test_parse_codes_逗號分隔()
    print("✅ test_parse_codes_逗號分隔 passed")
    test_parse_codes_空格分隔()
    print("✅ test_parse_codes_空格分隔 passed")
    test_parse_codes_換行分隔()
    print("✅ test_parse_codes_換行分隔 passed")
    test_parse_codes_中文逗號()
    print("✅ test_parse_codes_中文逗號 passed")
    test_parse_codes_混合分隔()
    print("✅ test_parse_codes_混合分隔 passed")
    test_parse_codes_跳過空白()
    print("✅ test_parse_codes_跳過空白 passed")
    test_parse_codes_超過100檔截斷()
    print("✅ test_parse_codes_超過100檔截斷 passed")
    test_parse_codes_空字串()
    print("✅ test_parse_codes_空字串 passed")
    test_parse_codes_只空白()
    print("✅ test_parse_codes_只空白 passed")
    test_specific_dividend_只抓缺漏的()
    print("✅ test_specific_dividend_只抓缺漏的 passed")
    print("\n🎉 All tests passed!")