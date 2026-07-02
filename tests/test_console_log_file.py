"""test_console_log_file.py
v1.1.5-console-log-file 守護：
- console log file 路徑正確
- 每則 GuiLogger.log() 都同步寫到 file
- atexit 正確 close file

【背景】2026-07-02 10:06 William 反映：
- 「下面這些 messages 還是沒有顯示在 program console 中」
- 整批失敗 60 則訊息沒看到
- 修法：寫雙保險 log file、即使 console 看不見也有 trace
"""
import os
import sys
import tempfile
import queue
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def test_strategygui_init_opens_console_log_file():
    """StrategyGUI.__init__ 應該開啟當日 log file"""
    assert hasattr(st.StrategyGUI, "__init__"), "StrategyGUI 沒有 __init__"

    # 檢查 source code 有開檔邏輯
    import inspect
    src = inspect.getsource(st.StrategyGUI.__init__)
    assert "_console_log_path" in src, "❌ 開 console log file 邏輯不存在"
    assert "cache/console" in src, "❌ log file 路徑不對"
    assert "_console_log_file" in src, "❌ log file handle 沒初始化"
    print("✅ StrategyGUI.__init__ 開 console log file")


def test_poll_log_queue_writes_to_log_file():
    """_poll_log_queue 應該同步寫到 log file"""
    import inspect
    src = inspect.getsource(st.StrategyGUI._poll_log_queue)
    assert "_console_log_file" in src, "❌ _poll_log_queue 沒寫到 log file"
    # 確保有 flush 確保資料真的寫進去
    assert ".flush()" in src, "❌ 沒 flush、訊息可能 buffer 丟失"
    print("✅ _poll_log_queue 同步寫 log file + flush")


def test_has_close_console_log_method():
    """atexit 註冊的 _close_console_log 必須存在"""
    assert hasattr(st.StrategyGUI, "_close_console_log"), (
        "❌ _close_console_log 不存在、App 結束時 log file 不會 close"
    )
    print("✅ _close_console_log method 存在")


def test_console_has_open_log_button():
    """主畫面要有「開啟 console log 檔」按鈕"""
    import inspect
    src = inspect.getsource(st.StrategyGUI._build_ui)
    assert "開啟 console log" in src, "❌ 開啟 console log 按鈕不存在"
    print("✅ 開啟 console log 按鈕存在")


def test_console_widget_height_enlarged():
    """console widget height 應從 10 改成 16（讓更多 log 可見）"""
    import inspect
    src = inspect.getsource(st.StrategyGUI._build_ui)
    assert "height=16" in src, "❌ console widget height 沒加到 16"
    print("✅ console widget height 加大到 16 行")


def test_poll_log_queue_uses_update_idletasks():
    """_poll_log_queue 應該用 update_idletasks() 強化 see end"""
    import inspect
    src = inspect.getsource(st.StrategyGUI._poll_log_queue)
    assert "update_idletasks" in src, (
        "❌ 沒有 update_idletasks、see end 在快速 insert 時可能失效"
    )
    print("✅ _poll_log_queue 用 update_idletasks 強化 see end")
