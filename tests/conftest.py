"""
conftest.py
全專案 pytest 設定。

【V0.9.5-cache-time 新增】autouse fixture 防止 _fetch_finmind_dividend 測試污染
- 歷史背景：很多測試（test_dividend_year_mapping、test_dividend_3decimal_xxx、
  test_filter_last_yld_unbound、test_filter_b_logic 等）直接
  `st._fetch_finmind_dividend = lambda ...` 來 mock、但沒還原
- 結果：test_dividend_yield_fix 在後面跑時、st._fetch_finmind_dividend 還是被 mock 的版本
  → 3 個 test fail（assert 0 == 2 / IndexError）
- 修法：autouse fixture 在每個 test 後把 _fetch_finmind_dividend 還原成原始函式

【V0.9.5-tab-split-phase3 + v1.1 重構】
- 多個測試改 monkeypatch st_fetch_market._fetch_finmind_dividend
- conftest 同步改為 monitor 並 restore stocktool.fetch_market._fetch_finmind_dividend
"""
import pytest
import sys
import os

# 把 source/ 加入 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


@pytest.fixture(autouse=True)
def _restore_finmind_fetch():
    """【V0.9.5-cache-time 修測試隔離 + v1.1 重構】確保每個 test 後 _fetch_finmind_dividend 還原

    雖然只對 test_dividend_yield_fix 有影響、但 autouse 整套 test 都套用最安全。
    """
    # 確保 StockTool 已 import
    if "StockTool" not in sys.modules:
        import StockTool as st  # noqa: F401
    if "stocktool.fetch_market" not in sys.modules:
        from stocktool import fetch_market  # noqa: F401

    from stocktool import fetch_market as fm
    original = fm._fetch_finmind_dividend
    yield
    fm._fetch_finmind_dividend = original