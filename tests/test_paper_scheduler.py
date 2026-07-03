"""
【V1.2.0-paper-trading stage 6】PaperScheduler 測試

William 2026-07-04 00:54 反映：
- 「[paper.scheduler] ⏰ 14:00 自動排程啟動」沒從 program console 顯示
- 實際只有 stderr (Python logging) 跑出來、沒進 GUI console

修法：scheduler 不再用 Python logging、只走 self.app.logger.log()
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import pytest


# ==========================================================
# Fake App / Fake GuiLogger
# ==========================================================

class _FakeGuiLogger:
    def __init__(self):
        self.msgs = []

    def log(self, msg):
        self.msgs.append(msg)

    def error(self, msg):
        self.msgs.append(f"ERROR: {msg}")


class _FakeApp:
    def __init__(self):
        self.logger = _FakeGuiLogger()
        self.session = None
        self.cfg = None
        self.after_calls = []

    def after(self, ms, fn):
        self.after_calls.append((ms, fn))
        return f"job_{len(self.after_calls)}"

    def after_cancel(self, job_id):
        pass


# ==========================================================
# 測試：訊息必須進 GUI logger、不用 Python logging
# ==========================================================

def test_scheduler_logs_to_gui_logger():
    """scheduler._log() 必須把訊息推進 GUI logger（進 console）"""
    from stocktool.paper_scheduler import PaperScheduler

    app = _FakeApp()
    sched = PaperScheduler(app)

    sched._log("⏰ 14:00 自動排程啟動")

    assert any("14:00 自動排程啟動" in m for m in app.logger.msgs), \
        f"❌ scheduler._log 沒把訊息推進 GUI logger、got {app.logger.msgs}"


def test_scheduler_does_not_use_python_logging():
    """【stage 6 關鍵】scheduler 不該再用 Python logging
    （否則訊息會從 stderr 出、不進 GUI console）
    """
    import inspect
    from stocktool.paper_scheduler import PaperScheduler

    src = inspect.getsource(PaperScheduler)
    # 確保 class 內沒有 import logging 或 self._logger.info 等
    assert "import logging" not in src, \
        "❌ PaperScheduler 不該 import logging"
    assert "logging.getLogger" not in src, \
        "❌ PaperScheduler 不該用 logging.getLogger"


def test_scheduler_logger_adapter_info():
    """【stage 6】傳給 catch_up 的 logger adapter.info() 進 GUI"""
    from stocktool.paper_scheduler import PaperScheduler

    app = _FakeApp()
    sched = PaperScheduler(app)
    adapter = sched._logger()

    adapter.info("hello")
    assert any("hello" in m for m in app.logger.msgs)


def test_scheduler_logger_adapter_warning():
    """adapter.warning() 加 ⚠️ 前綴"""
    from stocktool.paper_scheduler import PaperScheduler

    app = _FakeApp()
    sched = PaperScheduler(app)
    adapter = sched._logger()

    adapter.warning("careful")
    assert any("⚠️ careful" in m for m in app.logger.msgs)


def test_scheduler_logger_adapter_error():
    """adapter.error() 加 ❌ 前綴"""
    from stocktool.paper_scheduler import PaperScheduler

    app = _FakeApp()
    sched = PaperScheduler(app)
    adapter = sched._logger()

    adapter.error("boom")
    assert any("❌ boom" in m for m in app.logger.msgs)


def test_scheduler_start_schedules_tick():
    """start() 必須呼叫 app.after 排定 tick"""
    from stocktool.paper_scheduler import PaperScheduler, CHECK_INTERVAL_MS

    app = _FakeApp()
    sched = PaperScheduler(app)
    sched.start()

    assert any(ms == CHECK_INTERVAL_MS for ms, _ in app.after_calls)
    # 也必須 log 啟動訊息
    assert any("14:00 自動排程啟動" in m for m in app.logger.msgs)


def test_scheduler_safe_when_app_logger_missing():
    """防呆：app 沒 logger 時 scheduler._log 不應 crash"""
    from stocktool.paper_scheduler import PaperScheduler

    class _BareApp:
        pass  # 沒 logger

    app = _BareApp()
    sched = PaperScheduler(app)
    # 不應 raise
    sched._log("這訊息應該被吃掉、不 crash")
