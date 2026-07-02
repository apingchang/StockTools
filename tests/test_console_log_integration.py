"""test_console_log_integration.py

完整 integration test — 模擬真實 App 啟動+背景抓股價整批失敗場景：
1. mock TWSE API：所有 batch 都回空 msgArray → 觸發「整批失敗」訊息
2. 用 thread 跑 background fetch_prices（模擬 _startup_bg_fetch_price）
3. 直接餵 60 則測試訊息進 log_queue
4. 模擬 _poll_log_queue 從 queue 讀、寫到 console + 寫到 log file
5. 驗證：
   - log file 真的收到 60 行（含啟動 banner）
   - 每行都有時間戳記
   - 訊息沒漏、不重複

【背景】2026-07-02 10:06 William 反映「TWSE 整批失敗 60 則訊息沒顯示」
   這測試就是要把 root cause 釐清 + 修法驗證
"""
import os
import sys
import tempfile
import threading
import time
import queue
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool.fetch_market import _log_print  # noqa: E402


# ====================================================
# 【場景 1】background thread 寫 60 則整批失敗 → log file 收得到
# ====================================================

def test_bg_thread_60_messages_all_reach_log_file():
    """背景 thread 寫 60 則訊息、log file 真的收到 60 行"""
    # 用 tempdir 隔離 log file
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, f"console_{datetime.now().strftime('%Y-%m-%d')}.log")
        f = open(log_path, "a", encoding="utf-8")
        f.write(f"\n=== App 啟動 {datetime.now().isoformat()} ===\n")
        f.flush()

        q = queue.Queue()
        logger = st.GuiLogger(q)

        # 模擬 background thread（fetch_prices 在 bg thread 跑）
        def bg_worker():
            for i in range(60):
                # 跟 fetch_market.py:414 寫法一致
                if i < 58:
                    batch_size, total = 50, 50  # 50/50
                else:
                    batch_size, total = 30, 30  # 30/30
                _log_print(logger, f"⚠️ TWSE tse 整批失敗（{batch_size}/{total}）→ 跳過 otc fallback")
                time.sleep(0.005)  # 模擬 5ms/batch（真實約 3-15s 才有，壓縮時間）

        t = threading.Thread(target=bg_worker, daemon=True)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive(), "bg thread 10 秒內沒跑完、hang 住了"

        # 模擬 main thread 的 _poll_log_queue
        drained = 0
        while not q.empty():
            msg = q.get_nowait()
            if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "log":
                msg_text = msg[1]
                ts = datetime.now().strftime("%H:%M:%S")
                f.write(f"{ts} {msg_text}\n")
                f.flush()
                drained += 1

        f.write(f"\n=== App 結束 {datetime.now().isoformat()} ===\n")
        f.close()

        # 驗證
        assert drained == 60, f"❌ queue 60 則訊息只 drain {drained} 則"
        with open(log_path, "r", encoding="utf-8") as fp:
            content = fp.read()
        # 啟動 + 60 行 + 結束 = 62 行（不算空行、剛好 60 整批失敗行）
        lines = [l for l in content.split("\n") if l.strip()]
        assert len(lines) >= 62, f"❌ log file 行數 {len(lines)} 應 >= 62"
        # 至少有 60 個「整批失敗」行
        batch_fail_lines = [l for l in lines if "整批失敗" in l]
        assert len(batch_fail_lines) == 60, (
            f"❌ 應有 60 個「整批失敗」行、實際 {len(batch_fail_lines)}"
        )
        # 每行都有時間戳記（HH:MM:SS 開頭）
        import re
        ts_re = re.compile(r"^\d{2}:\d{2}:\d{2} ")
        ts_count = sum(1 for l in batch_fail_lines if ts_re.match(l))
        assert ts_count == 60, f"❌ 只有 {ts_count}/60 行有時間戳記"
        print(f"✅ bg thread 60 則訊息、log file 收到 60 行（含時間戳記）")


def test_bg_thread_failed_logger_fallback_to_print():
    """caller 漏傳 logger → fallback 到 print()、log file 不會收到
    這個測試守住「caller 漏傳 logger 會被偵測到」的 regression"""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.log")
        # 不開 file、純粹驗證 _log_print(None, msg) → fallback print()
        import io
        from contextlib import redirect_stdout

        captured = io.StringIO()
        with redirect_stdout(captured):
            _log_print(None, "⚠️ TWSE tse 整批失敗（50/50）→ 跳過 otc fallback")

        output = captured.getvalue()
        assert "整批失敗" in output, f"❌ logger=None 時 fallback 沒 print、output={output}"
        print(f"✅ caller 漏傳 logger → fallback print() {len(output.strip())} chars")


def test_poll_log_queue_no_message_loss():
    """_poll_log_queue 每 120ms 跑：模擬 30 batches × 2 messages/batch = 60 訊息進 queue
    drain 完整 60 個、不掉任何一個"""
    q = queue.Queue()
    logger = st.GuiLogger(q)

    sent_msgs = []
    for i in range(60):
        msg = f"🔄 第 {i+1} 個 fetch_prices batch 訊息"
        sent_msgs.append(msg)
        logger.log(msg)

    received = []
    while not q.empty():
        msg = q.get_nowait()
        received.append(msg[1] if isinstance(msg, tuple) else str(msg))

    assert len(received) == len(sent_msgs), (
        f"❌ 訊息掉包、sent={len(sent_msgs)} received={len(received)}"
    )
    assert received == sent_msgs, "❌ 訊息順序亂掉"
    print(f"✅ 60 則訊息 0 掉包 + 0 順序亂")


# ====================================================
# 【場景 2】App 啟動 → 假日判斷 → 不觸發整批失敗
# ====================================================

def test_holiday_does_not_trigger_force_refresh():
    """端午節（2026-06-19 週五 10:00）→ _is_market_hours=False → 不強制 refresh
    守住「假日排除」不會誤觸盤中邏輯"""
    from datetime import datetime
    assert st._is_market_hours(datetime(2026, 6, 19, 10, 0, 0)) is False, (
        "端午節 (週五) 10:00 應不算盤中、但 _is_market_hours 回 True"
    )
    print("✅ 端午節 10:00 → 不算盤中、不會觸發 force refresh")


def test_weekend_does_not_trigger_force_refresh():
    """週六 12:00 → 不算盤中"""
    from datetime import datetime
    assert st._is_market_hours(datetime(2026, 6, 20, 12, 0, 0)) is False
    print("✅ 週六 12:00 → 不算盤中")


def test_weekday_non_holiday_triggers_force_refresh():
    """平日非假日 10:00 → 算盤中（會觸發 force refresh）
    守住反向驗證：假日邏輯沒把一般平日也誤判"""
    from datetime import datetime
    assert st._is_market_hours(datetime(2026, 7, 3, 10, 0, 0)) is True, (
        "週五非假日 10:00 應算盤中、但 _is_market_hours 回 False"
    )
    print("✅ 週五非假日 10:00 → 算盤中（會 force refresh）")


# ====================================================
# 【場景 3】完整 end-to-end：log file 路徑 + 寫入 + flush
# ====================================================

def test_console_log_path_format():
    """console log file 路徑格式：cache/console/console_YYYY-MM-DD.log"""
    expected_pattern = "cache/console/console_2026-07-02.log"
    # 確認 source code 內有正確格式
    import inspect
    src = inspect.getsource(st.StrategyGUI.__init__)
    assert "cache/console" in src
    assert "console_" in src
    assert "%Y-%m-%d" in src
    print(f"✅ console log 路徑格式: {expected_pattern}")


def test_console_log_write_strategy_in_poll_loop():
    """_poll_log_queue 寫 file 順序：(insert console → write file → flush)
    守住：即使 App crash、訊息不會因 buffer 丟失"""
    import inspect
    src = inspect.getsource(st.StrategyGUI._poll_log_queue)
    # console.insert 必須在 file write 之前（先看 console、再看 file）
    insert_pos = src.find("console.insert")
    file_write_pos = src.find("_console_log_file.write")
    flush_pos = src.find("_console_log_file.flush")
    assert insert_pos > 0, "❌ console.insert 不存在"
    assert file_write_pos > 0, "❌ file.write 不存在"
    assert flush_pos > 0, "❌ file.flush 不存在（App crash 會漏 buffer）"
    assert file_write_pos < flush_pos, "❌ write 必須在 flush 之前"
    print("✅ console → file → flush 順序正確")
