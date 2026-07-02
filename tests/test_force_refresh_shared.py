"""test_force_refresh_shared.py
v1.1.5c-force-refresh-shared 守護：
- 共用方法 _force_refresh_price 存在
- 系統選股 tab 加了「🔄 重新抓股價」按鈕
- 手動選股 tab 既有按鈕仍存在
- source_label 參數正確帶到 _on_bg_price_done

【背景】William 2026-07-02 22:14 要求：
- 系統選股 tab 左欄加「重新抓股價」按鈕
- 不重複打 FinMind、跟手動選股 tab 共用同一個 cache
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def test_force_refresh_price_method_exists():
    """_force_refresh_price 共用方法必須存在"""
    assert hasattr(st.StrategyGUI, "_force_refresh_price"), (
        "❌ _force_refresh_price 共用方法不存在、系統選股 tab 沒法加按鈕"
    )
    sig = inspect.signature(st.StrategyGUI._force_refresh_price)
    assert "source_label" in sig.parameters, (
        "❌ _force_refresh_price 必須有 source_label 參數"
    )
    print("✅ _force_refresh_price(source_label) 共用方法存在")


def test_ms_force_refresh_delegates_to_shared():
    """_ms_force_refresh_price 必須呼叫共用 _force_refresh_price
    守住「不要 code duplication、兩 tab 行為一致」"""
    src = inspect.getsource(st.StrategyGUI._ms_force_refresh_price)
    assert "self._force_refresh_price" in src, (
        "❌ _ms_force_refresh_price 沒呼叫 _force_refresh_price、共用邏輯沒生效"
    )
    assert '"手動重抓"' in src, "❌ 沒帶 source_label='手動重抓'"
    print("✅ _ms_force_refresh_price → 呼叫 _force_refresh_price('手動重抓')")


def test_system_tab_has_refresh_price_button():
    """系統選股 tab 的 _build_ui 必須加「🔄 重新抓股價」按鈕
    守在 left column btn_frame、呼叫 _force_refresh_price('系統重抓')"""
    src = inspect.getsource(st.StrategyGUI._build_ui)
    assert "🔄 重新抓股價" in src, "❌ 系統選股 tab 沒看到「🔄 重新抓股價」按鈕"
    assert "系統重抓" in src, "❌ 沒帶 source_label='系統重抓'"
    assert "_force_refresh_price" in src, "❌ 沒呼叫共用 _force_refresh_price"
    print("✅ 系統選股 tab「🔄 重新抓股價」按鈕存在")


def test_ms_tab_refresh_price_button_still_exists():
    """手動選股 tab 既有「🔄 重新抓股價」按鈕不能被我改壞
    守住 backward compat"""
    src = inspect.getsource(st.StrategyGUI._ms_force_refresh_price)
    # 既有方法還在
    assert "手動重抓" in src, "❌ 既有 _ms_force_refresh_price 沒保留"
    print("✅ 手動選股 tab「🔄 重新抓股價」按鈕仍存在")


def test_force_refresh_passes_source_to_done_callback():
    """_force_refresh_price 的 _on_bg_price_done 必須收到 source_label
    守住 GUI status bar 顯示正確來源"""
    src = inspect.getsource(st.StrategyGUI._force_refresh_price)
    assert "_on_bg_price_done(df, source=source_label)" in src, (
        "❌ _on_bg_price_done 沒收到 source_label、status bar 會顯示空字串"
    )
    assert "_on_bg_price_err(err, source=source_label)" in src, (
        "❌ _on_bg_price_err 沒收到 source_label"
    )
    print("✅ _on_bg_price_done/_on_bg_price_err 都收到 source_label")


def test_force_refresh_runs_in_background_thread():
    """_force_refresh_price 必須用 threading.Thread、不能 block UI"""
    src = inspect.getsource(st.StrategyGUI._force_refresh_price)
    assert "threading.Thread" in src, "❌ 沒用 threading.Thread、會 block UI"
    assert "daemon=True" in src, "❌ 沒設 daemon=True、App 關閉時不會自動 kill"
    print("✅ _force_refresh_price 走 background thread")


def test_force_refresh_checks_bg_fetching_flag():
    """_force_refresh_price 必須先檢查 _bg_price_fetching flag
    避免手動按鈕跟背景 fetcher 重複打 FinMind"""
    src = inspect.getsource(st.StrategyGUI._force_refresh_price)
    assert "_bg_price_fetching" in src, (
        "❌ 沒檢查 _bg_price_fetching、會跟背景 fetcher 重複打 FinMind"
    )
    print("✅ _force_refresh_price 檢查 _bg_price_fetching flag")
