"""
test_v1_1_imports_lint.py
==========================

【背景】v1.1 重構把 StockTool.py 拆成多個 stocktool/ 子模組、但 import 沒跟著搬
已發生 2 次：
1. 2026-06-24 05:52 — datetime 漏（export_excel / backtest / technical）
2. 2026-06-24 06:45 — get_column_letter 漏（pipeline.py，跑回測時炸）

【本測試】結構性 lint 掃所有 stocktool/ 模組：
- 若用到「常見第三方名字」（openpyxl / datetime / requests / pandas / numpy / tkinter）
- 但檔案 import 區塊沒 import 該名字
- → fail

【目的】未來任何重構若又漏 import、CI / pytest 立刻抓出來、不用到 William 實際跑才炸

【精準度】只列舉「特異性高、不可能是 local var / function arg」的名字
（get_column_letter / Font / Alignment / PatternFill / CellIsRule / datetime / date / timedelta）
- pd / np / tk / ttk / requests 不列（這些常被用 as alias、誤判率高）
"""

import re
import sys
from pathlib import Path

import pytest

# 確保 source/ 在 path
sys.path.insert(0, str(Path(__file__).parent.parent / "source"))


# 已知「特異第三方名字」：(regex pattern, 預期 source module)
STRICT_LINT_TARGETS = {
    "openpyxl": [
        r"\bget_column_letter\b",
        r"\bFont\b",
        r"\bAlignment\b",
        r"\bPatternFill\b",
        r"\bCellIsRule\b",
    ],
    "datetime": [
        r"\bdatetime\.(today|now|utcnow|fromtimestamp|strptime)\b",
        r"\bdate\.today\b",
        r"\bdate\.now\b",
        r"\btimedelta\(",
    ],
}


def _parse_imports(text: str) -> set[str]:
    """收集所有 import 進來的名字（含 `as` alias）"""
    names = set()
    # import X / import X as Y / import X.Y
    for m in re.finditer(r"^import\s+(\S+)(?:\s+as\s+(\S+))?", text, re.MULTILINE):
        module_or_name = m.group(1)
        alias = m.group(2)
        if alias:
            names.add(alias)
        else:
            # import pandas → 名字是 'pandas'；import pandas as pd → alias 'pd'（上面已加）
            names.add(module_or_name.split(".")[0])
    # from X import Y / from X import Y as Z
    for m in re.finditer(r"^from\s+(\S+)\s+import\s+([^\n#]+)", text, re.MULTILINE):
        for n in m.group(2).split(","):
            n = n.strip()
            if not n or n == "*":
                continue
            # Y as Z
            if " as " in n:
                _, alias = n.split(" as ")
                names.add(alias.strip())
            else:
                names.add(n.strip())
    return names


class TestExternalImportLint:
    """結構性 lint：掃所有 stocktool/ 模組的 import 完整性"""

    def test_no_openpyxl_usage_without_import(self):
        stocktool_dir = Path(__file__).parent.parent / "source" / "stocktool"
        failures = []
        for py_file in stocktool_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            imports = _parse_imports(text)
            for pattern in STRICT_LINT_TARGETS["openpyxl"]:
                if not re.search(pattern, text):
                    continue
                # 找到目標名字（取 pattern 第一個 \bXXX\b）
                target = re.search(r"\\b(\w+)\\b", pattern).group(1)
                if target not in imports:
                    failures.append(
                        f"{py_file.relative_to(stocktool_dir.parent.parent)}: "
                        f"用 {target} (openpyxl) 但沒 import"
                    )
        assert not failures, (
            "以下檔案用 openpyxl 名字但沒 import（v1.1 重構漏）:\n"
            + "\n".join(failures)
        )

    def test_no_datetime_usage_without_import(self):
        stocktool_dir = Path(__file__).parent.parent / "source" / "stocktool"
        failures = []
        for py_file in stocktool_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            imports = _parse_imports(text)
            for pattern in STRICT_LINT_TARGETS["datetime"]:
                if not re.search(pattern, text):
                    continue
                # 找該 pattern 對應的目標名字
                if "datetime" in pattern:
                    target = "datetime"
                elif "date." in pattern:
                    target = "date"
                elif "timedelta" in pattern:
                    target = "timedelta"
                else:
                    continue
                if target not in imports:
                    failures.append(
                        f"{py_file.relative_to(stocktool_dir.parent.parent)}: "
                        f"用 {target} (datetime) 但沒 import"
                    )
        assert not failures, (
            "以下檔案用 datetime 名字但沒 import（v1.1 重構漏）:\n"
            + "\n".join(failures)
        )


class TestPipelineGetColumnLetter:
    """守住 pipeline.py 有 import get_column_letter"""

    def test_pipeline_imports_get_column_letter(self):
        from stocktool import pipeline
        assert "get_column_letter" in dir(pipeline), (
            "stocktool/pipeline.py 漏 `from openpyxl.utils import get_column_letter` — "
            "run_pipeline 內 `get_column_letter(ws_buy.max_column)` 會 NameError"
        )


class TestNoNameErrorAtImport:
    """實際 import 全部 stocktool/ 模組、確保 module-level 沒有 NameError"""

    @pytest.mark.parametrize("module_name", [
        "stocktool.backtest",
        "stocktool.cache",
        "stocktool.config",
        "stocktool.database",
        "stocktool.etf",
        "stocktool.export_excel",
        "stocktool.fetch_market",
        "stocktool.pipeline",
        "stocktool.scoring",
        "stocktool.technical",
        "stocktool.gui.calendar",
    ])
    def test_module_imports_cleanly(self, module_name):
        import importlib
        try:
            importlib.import_module(module_name)
        except NameError as e:
            pytest.fail(f"❌ {module_name} import 時 NameError: {e}（v1.1 重構 import 漏）")
