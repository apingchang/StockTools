"""
stocktool.paper_scheduler - 14:00 自動排程
==========================================

【V1.2.0-paper-trading】

設計：
- App 啟動後、每分鐘檢查一次現在時間
- 過了 14:00 且今天還沒跑 → 自動觸發 catch_up_all_active
- 排程狀態寫到 console
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional, Callable

from . import paper_trading as pt
from . import paper_catchup


AUTO_RUN_HOUR = 14   # 14:00 自動跑
AUTO_RUN_MINUTE = 5  # 寬限到 14:05 才觸發（避開剛收盤資料未更新）
CHECK_INTERVAL_MS = 60_000   # 每 60 秒檢查


class PaperScheduler:
    """模擬買賣的 14:00 自動排程器

    用法（在 StockTool 主程式）：
        self.paper_scheduler = PaperScheduler(self)
        self.paper_scheduler.start()
    """

    def __init__(self, app):
        self.app = app
        self.db_path = "portfolio.db"
        self._job_id: Optional[str] = None
        self._last_auto_date: Optional[str] = None
        self._logger = logging.getLogger("paper.scheduler")
        if not self._logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
            self._logger.addHandler(h)
            self._logger.setLevel(logging.INFO)

    def start(self):
        """啟動排程（在 App 內呼叫、用 after 觸發）"""
        self._cancel()
        self._job_id = self.app.after(CHECK_INTERVAL_MS, self._tick)
        self._log("⏰ 14:00 自動排程啟動（每分鐘檢查）")

    def _cancel(self):
        if self._job_id:
            try:
                self.app.after_cancel(self._job_id)
            except Exception:
                pass
            self._job_id = None

    def _tick(self):
        """每分鐘觸發"""
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")

            # 過了 14:05 且今天還沒跑 → 觸發
            if (now.hour > AUTO_RUN_HOUR or
                (now.hour == AUTO_RUN_HOUR and now.minute >= AUTO_RUN_MINUTE)):
                if self._last_auto_date != today:
                    self._run_auto_today(today)

            # 排下一次
            self._job_id = self.app.after(CHECK_INTERVAL_MS, self._tick)
        except Exception as e:
            self._log(f"❌ 排程 tick 失敗: {e}")
            self._job_id = self.app.after(CHECK_INTERVAL_MS, self._tick)

    def _run_auto_today(self, today: str):
        self._last_auto_date = today
        self._log(f"⏰ {today} 14:00 自動觸發、開始補跑所有 active 組合")

        session = getattr(self.app, "session", None)
        cfg = getattr(self.app, "cfg", None)

        try:
            results = paper_catchup.catch_up_all_active(
                self.db_path, end_date=today,
                session=session, cfg=cfg, logger=self._logger
            )
            for r in results:
                self._log(f"  ✅ {r.portfolio_name}: BUY {r.total_buys} / SELL {r.total_sells}")
        except Exception as e:
            self._log(f"❌ 自動跑失敗: {e}")

    def stop(self):
        self._cancel()
        self._log("⏹ 14:00 自動排程停止")

    def _log(self, msg: str):
        self._logger.info(msg)
        try:
            if hasattr(self.app, "logger") and hasattr(self.app.logger, "log"):
                self.app.logger.log(msg)
        except Exception:
            pass