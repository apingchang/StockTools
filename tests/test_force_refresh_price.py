"""
test_force_refresh_price.py
驗證 V0.9.5-goodinfo4.3「即時抓股價」checkbox 真的會走 FinMind（不再被 cache 命中吃掉）。

【動機】
William 2026-06-18 07:08 反映：
- 勾「即時抓股價」checkbox、點開始選股
- 不到一秒結果就出來了、實際根本沒打 FinMind
- 現價還是啟動時背景抓的 cache 版本

【根因】
- _fetch_finmind_prices_batch 用 module-level _FINMIND_PRICE_CACHE
- App 啟動時 _startup_bg_fetch_price 抓過一次、cache 已滿
- 第二次呼叫全部 cache 命中、1 秒 return
- 「即時抓股價」checkbox 形同虛設

【修法】
- _fetch_finmind_prices_batch 加 force_refresh: bool = False 參數
- True → 先清空 _FINMIND_PRICE_CACHE 再走實際抓取
- False → 用 cache（默認、背景抓取場景）

【測試目標】
1. force_refresh=True → 確實走 _finmind_get（cache 被清）
2. force_refresh=False → 確實用 cache（不 _finmind_get）
3. 進度 callback 在抓取中真的被呼叫
4. _FINMIND_PRICE_CACHE 是 module-level（不是 function-level）
5. 清空 cache 後重抓、新值會寫入 cache
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def test_force_refresh_參數存在():
    """【API 守護】_fetch_finmind_prices_batch 必須有 force_refresh 參數"""
    import inspect
    sig = inspect.signature(st._fetch_finmind_prices_batch)
    assert "force_refresh" in sig.parameters, \
        "_fetch_finmind_prices_batch 缺 force_refresh 參數"
    # 預設值應為 False
    assert sig.parameters["force_refresh"].default is False, \
        f"force_refresh 預設應為 False、實際: {sig.parameters['force_refresh'].default}"


def test_force_refresh_true_清cache():
    """【核心】force_refresh=True 時 _FINMIND_PRICE_CACHE 必須被清空"""
    # 預先填入假 cache
    st._FINMIND_PRICE_CACHE["3188"] = {"close": 999.0, "Trading_Volume": 50000}
    st._FINMIND_PRICE_CACHE["2330"] = {"close": 500.0, "Trading_Volume": 100000}
    assert len(st._FINMIND_PRICE_CACHE) == 2

    # Mock _finmind_get、記錄呼叫次數
    call_log = []
    def fake_finmind_get(dataset, stock_id, start, end, retry=2):
        call_log.append((dataset, stock_id))
        return [{"date": "1150617", "close": 100.0, "Trading_Volume": 1000}]

    st._finmind_get = fake_finmind_get

    # 呼叫 force_refresh=True
    result = st._fetch_finmind_prices_batch(
        ["3188", "2330"], force_refresh=True
    )

    # 【關鍵】cache 必須被清空（不是用舊值）
    # 雖然之後會回填、但中間一定有「被清空過」這一步
    # 我們驗證：呼叫 _finmind_get 兩次、表示走實際抓取路徑
    assert len(call_log) == 2, \
        f"force_refresh=True 應打 2 次 _finmind_get，實際: {len(call_log)}"
    assert call_log[0][1] == "3188", f"第一個應抓 3188，實際: {call_log[0]}"
    assert call_log[1][1] == "2330", f"第二個應抓 2330，實際: {call_log[1]}"
    # 結果是新抓的 100.0（不是舊 cache 的 999.0 / 500.0）
    assert result.iloc[0]["現價"] == 100.0, \
        f"3188 現價應為 100.0（新抓），實際: {result.iloc[0]['現價']}"


def test_force_refresh_false_走cache():
    """【核心】force_refresh=False（默認）時用 cache、不打 FinMind"""
    # 清空 cache 然後填入
    st._FINMIND_PRICE_CACHE.clear()
    st._FINMIND_PRICE_CACHE["3188"] = {"close": 50.0, "Trading_Volume": 20000}

    # Mock _finmind_get、記錄呼叫次數（不該被呼叫）
    call_log = []
    def fake_finmind_get(dataset, stock_id, start, end, retry=2):
        call_log.append((dataset, stock_id))
        return []

    st._finmind_get = fake_finmind_get

    result = st._fetch_finmind_prices_batch(["3188"], force_refresh=False)

    # 【關鍵】cache 命中、不打 FinMind
    assert len(call_log) == 0, \
        f"force_refresh=False 應用 cache 不打 _finmind_get，實際: {len(call_log)}"
    # 結果是 cache 的 50.0
    assert result.iloc[0]["現價"] == 50.0, \
        f"3188 現價應為 cache 50.0，實際: {result.iloc[0]['現價']}"


def test_force_refresh_預設為False_不破壞既有行為():
    """【向後相容】不傳 force_refresh 應等同於 force_refresh=False"""
    st._FINMIND_PRICE_CACHE.clear()
    st._FINMIND_PRICE_CACHE["3188"] = {"close": 50.0, "Trading_Volume": 20000}

    call_log = []
    def fake_finmind_get(dataset, stock_id, start, end, retry=2):
        call_log.append((dataset, stock_id))
        return []

    st._finmind_get = fake_finmind_get

    # 不傳 force_refresh（用默認值）
    result = st._fetch_finmind_prices_batch(["3188"])
    assert len(call_log) == 0, \
        f"不傳 force_refresh 應用 cache，實際: {len(call_log)}"


def test_force_refresh_進度callback_被呼叫():
    """【UI 守護】force_refresh=True 時 progress_callback 真的被觸發"""
    st._FINMIND_PRICE_CACHE.clear()

    call_log = []
    def fake_finmind_get(dataset, stock_id, start, end, retry=2):
        return [{"date": "1150617", "close": 100.0, "Trading_Volume": 1000}]

    def progress_cb(n_done, n_total):
        call_log.append((n_done, n_total))

    st._finmind_get = fake_finmind_get

    # 12 檔、每 10 檔 callback 一次 → 應觸發 1 次（第 10 檔）
    st._fetch_finmind_prices_batch(
        [str(i) for i in range(12)],
        progress_callback=progress_cb,
        force_refresh=True,
    )
    # callback 觸發條件是 (i + 1) % 10 == 0
    # i = 9 (第 10 檔) → 觸發 (10, 12)
    assert (10, 12) in call_log, f"進度 callback 應在第 10 檔觸發 (10, 12)，實際: {call_log}"


def test_force_refresh_清空邏輯():
    """【白箱】force_refresh=True 必須清空 cache（不是用新值覆蓋）"""
    # 先清空再填入 5 檔
    st._FINMIND_PRICE_CACHE.clear()
    for i in range(5):
        st._FINMIND_PRICE_CACHE[str(i)] = {"close": 999.0, "Trading_Volume": 0}
    n_before = len(st._FINMIND_PRICE_CACHE)
    assert n_before == 5

    # Mock _finmind_get 回傳空
    st._finmind_get = lambda *a, **kw: []

    # 呼叫 force_refresh=True、傳 3 檔
    st._fetch_finmind_prices_batch(["a", "b", "c"], force_refresh=True)

    # 清空後只有 3 筆 None（被抓但沒資料）寫入
    n_after = len(st._FINMIND_PRICE_CACHE)
    assert n_after == 3, \
        f"清空後 cache 應剩 3 筆（被寫 None），實際: {n_after}"


def test_FINMIND_PRICE_CACHE_是module_level():
    """【架構守護】_FINMIND_PRICE_CACHE 必須在 module 層級、不在 function 內"""
    # 取 import 後的模組
    import StockTool
    # 必須能從 module 拿到（不是 function local）
    assert hasattr(StockTool, "_FINMIND_PRICE_CACHE"), \
        "_FINMIND_PRICE_CACHE 不在 module 層級、無法被 _ms_run_selection 清空"


if __name__ == "__main__":
    test_force_refresh_參數存在()
    print("✅ test_force_refresh_參數存在 passed")
    test_force_refresh_true_清cache()
    print("✅ test_force_refresh_true_清cache passed")
    test_force_refresh_false_走cache()
    print("✅ test_force_refresh_false_走cache passed")
    test_force_refresh_預設為False_不破壞既有行為()
    print("✅ test_force_refresh_預設為False_不破壞既有行為 passed")
    test_force_refresh_進度callback_被呼叫()
    print("✅ test_force_refresh_進度callback_被呼叫 passed")
    test_force_refresh_清空邏輯()
    print("✅ test_force_refresh_清空邏輯 passed")
    test_FINMIND_PRICE_CACHE_是module_level()
    print("✅ test_FINMIND_PRICE_CACHE_是module_level passed")
    print("\n🎉 All force-refresh-price tests passed!")
