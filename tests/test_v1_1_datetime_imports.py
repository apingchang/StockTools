"""
test_v1_1_datetime_imports.py
==============================

【背景】v1.1 重構時把 datetime 用法從 StockTool.py 搬到各個新 module，
但 import 沒跟著搬，造成 `name 'datetime' is not defined` 錯誤
（2026-06-24 05:52 William 執行 v1.0 跑回測時炸掉，所有股票抓不到歷史日K）

【本測試守住】
- export_excel.update_stock_history
- backtest.py line 351 datetime.now()
- technical.calc_enhanced_tech_indicators

【修法】3 個檔案各自加 `from datetime import datetime`

【驗證】每個 function 應該可以 mock 環境下被呼叫，不會 NameError
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 確保 source/ 在 path
sys.path.insert(0, str(Path(__file__).parent.parent / "source"))


class TestDatetimeImportPresence:
    """守住 3 個 module 都有 `from datetime import datetime` import"""

    def test_export_excel_has_datetime_import(self):
        from stocktool import export_excel
        assert "datetime" in dir(export_excel), (
            "stocktool/export_excel.py 漏 `from datetime import datetime` — "
            "update_stock_history 用 datetime.today() 會 NameError"
        )
        import datetime as _dt
        assert export_excel.datetime is _dt.datetime

    def test_backtest_has_datetime_import(self):
        from stocktool import backtest
        assert "datetime" in dir(backtest), (
            "stocktool/backtest.py 漏 `from datetime import datetime` — "
            "datetime.now() 會 NameError"
        )
        import datetime as _dt
        assert backtest.datetime is _dt.datetime

    def test_technical_has_datetime_import(self):
        from stocktool import technical
        assert "datetime" in dir(technical), (
            "stocktool/technical.py 漏 `from datetime import datetime` — "
            "calc_enhanced_tech_indicators 用 datetime.today() 會 NameError"
        )
        import datetime as _dt
        assert technical.datetime is _dt.datetime


class TestUpdateStockHistoryCallable:
    """守住 update_stock_history 真的可以跑（不會 NameError）"""

    def test_update_stock_history_no_name_error_on_existing_cache(self, tmp_path):
        """
        場景：歷史檔已存在 → 走 update 分支 → 會執行 datetime.today()
        不該 NameError
        """
        from stocktool import export_excel
        from stocktool.config import StrategyConfig

        # 建立假的 history 檔（讓 os.path.exists 回 True）
        import pandas as pd
        history_file = tmp_path / "9999_60m.xlsx"
        df_old = pd.DataFrame({
            "Date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "股票代號": ["9999", "9999"],
            "Close": [10.0, 11.0],
            "Volume": [1000, 2000],
        })
        df_old.to_excel(history_file, index=False)

        # Monkey-patch HISTORY_DIR + fetch_twse_stock_day_month
        import stocktool.export_excel as ee
        ee.HISTORY_DIR = str(tmp_path)
        ee.fetch_twse_stock_day_month = MagicMock(return_value=pd.DataFrame())

        cfg = MagicMock(spec=StrategyConfig)
        session = MagicMock()
        logger = MagicMock()

        # 這裡如果 datetime 沒 import 會 NameError
        result = ee.update_stock_history(session, cfg, "9999", df_old)
        # fetch_twse 回空 → 應回傳原 df_old
        assert result is df_old


class TestDatetimeUsageLint:
    """
    結構性 lint：掃所有 stocktool module，
    如果有「用 datetime.XXX 但沒 import datetime」就 fail
    """

    def test_no_module_uses_datetime_without_import(self):
        import re
        from pathlib import Path

        stocktool_dir = Path(__file__).parent.parent / "source" / "stocktool"
        failures = []

        for py_file in stocktool_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            # 有用 datetime.X 或 date.today() / date.now()
            uses = re.findall(r"\bdatetime\.\w+|\bdate\.(today|now)\(\)", text)
            if not uses:
                continue
            # 有 import datetime 或 from datetime
            has_import = bool(
                re.search(r"^import datetime\b", text, re.MULTILINE)
                or re.search(r"^from datetime import\b", text, re.MULTILINE)
            )
            if not has_import:
                failures.append(
                    f"{py_file.relative_to(stocktool_dir.parent.parent)}: "
                    f"用 {uses[:3]} 但沒 import datetime"
                )

        assert not failures, (
            "以下檔案用 datetime 但沒 import（v1.1 重構漏）:\n"
            + "\n".join(failures)
        )
