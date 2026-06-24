"""
test_notebook_portfolio_tab_consistency.py
============================================

【背景】2026-06-24 09:12 William 反映：
- 開 App → 進「買賣記錄 Tab」沒 refresh
- 要先進「ETF 選股 Tab」才有資料
- root cause：_on_tab_changed 的 index 寫錯（寫 1、ETF 才會觸發；實際買賣記錄在 index 3）

【為什麼之前測試沒抓到】
- test_portfolio_refresh_loop.py 的 mock 用 current_tab=1 代表「買賣記錄」
- 但實際 notebook 結構 index 1 是 ETF、index 3 才是買賣記錄
- 測試世界觀跟程式碼世界觀不一致、雙方都通過但實際行為壞掉

【本測試守住】
1. notebook 結構（Tab 順序）跟 _on_tab_changed 用的一致
2. 切到「買賣記錄 Tab」會觸發 _refresh_portfolio_view
3. 切離「買賣記錄 Tab」會取消 refresh loop
4. 切到「ETF Tab」**不會**觸發買賣記錄 refresh（避免再次 regression）
5. 切到「其他 Tab」也都不會觸發

【做法】
- 動態抓 StockTool.py 的 notebook.add() 順序（用 AST）
- 找出「買賣記錄」tab 的 index
- 驗證 _on_tab_changed 用對的 index
- 跑 mock-based 整合測試
"""

import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "source"))


# ==========================================================
# AST 抓 notebook.add() 順序
# ==========================================================

def _parse_notebook_tab_order(stocktool_path: Path) -> list[tuple[int, str]]:
    """
    從 StockTool.py AST 抓出 notebook.add() 順序與對應的變數名 / text label

    Returns:
        list of (index, var_name, label) — 按程式碼出現順序
    """
    text = stocktool_path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    tab_order = []
    for node in ast.walk(tree):
        # 只看 Call node
        if not isinstance(node, ast.Call):
            continue
        # 抓 func 是否為 self.notebook.add
        func = node.func
        if not (isinstance(func, ast.Attribute) and
                isinstance(func.value, ast.Attribute) and
                func.value.attr == "notebook" and
                func.attr == "add"):
            continue
        # func.value.value 應該是 'self' Name
        if not (isinstance(func.value.value, ast.Name) and
                func.value.value.id == "self"):
            continue
        # 抓第一個 positional arg（frame variable name）
        # 例：self.notebook.add(self.portfolio_tab, text="...") 的第一個 arg 是
        #     Attribute 節點（self.portfolio_tab）、不是 Name
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Name):
            var_name = first_arg.id
        elif isinstance(first_arg, ast.Attribute):
            var_name = first_arg.attr  # self.select_tab → attr='select_tab'
        else:
            continue
        # 抓 text= 關鍵字
        label = ""
        for kw in node.keywords:
            if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                label = kw.value.value
        tab_order.append((var_name, label))

    # 加上 index（0-based）
    # 【避免 list comprehension bytecode bug】手動 append
    result = []
    for i, pair in enumerate(tab_order):
        var, label = pair
        result.append((i, var, label))
    return result


def _find_portfolio_tab_index(stocktool_path: Path) -> int:
    """從 notebook.add() 順序找出「買賣記錄」tab 的 index"""
    tab_order = _parse_notebook_tab_order(stocktool_path)
    for idx, var, label in tab_order:
        # portfolio_tab 是買賣記錄 frame 的變數名
        if "portfolio" in var.lower():
            return idx
        # 或 label 含「買賣記錄」
        if "買賣記錄" in label:
            return idx
    raise RuntimeError("找不到 portfolio tab — 可能是變數名稱改了、需要更新測試")


def _find_etf_tab_index(stocktool_path: Path) -> int:
    """從 notebook.add() 順序找出「主動式 ETF」tab 的 index"""
    tab_order = _parse_notebook_tab_order(stocktool_path)
    for idx, var, label in tab_order:
        if "etf" in var.lower() or "ETF" in label:
            return idx
    raise RuntimeError("找不到 ETF tab")


# ==========================================================
# 結構性 lint：_on_tab_changed 的 index 必須對應到 portfolio_tab
# ==========================================================

class TestNotebookTabOrder:
    """從 StockTool.py AST 抓 notebook 順序、驗證 index 正確"""

    def test_portfolio_tab_is_index_3(self):
        """目前 notebook 結構：買賣記錄應該在 index 3"""
        from pathlib import Path
        stocktool_path = Path(__file__).parent.parent / "source" / "StockTool.py"
        portfolio_idx = _find_portfolio_tab_index(stocktool_path)
        assert portfolio_idx == 3, (
            f"買賣記錄 Tab 應在 index 3，實際在 index {portfolio_idx}。"
            f"如果是 index 改變、需同步修 _on_tab_changed 的 index。\n"
            f"目前 notebook 順序：\n"
            + "\n".join(f"  index {i}: {var} ({label})" for i, var, label in _parse_notebook_tab_order(stocktool_path))
        )

    def test_etf_tab_is_index_1(self):
        """目前 notebook 結構：ETF Tab 應該在 index 1"""
        from pathlib import Path
        stocktool_path = Path(__file__).parent.parent / "source" / "StockTool.py"
        etf_idx = _find_etf_tab_index(stocktool_path)
        assert etf_idx == 1, (
            f"ETF Tab 應在 index 1，實際在 index {etf_idx}。"
        )

    def test_on_tab_changed_index_matches_portfolio_tab(self):
        """_on_tab_changed 內的 index 必須等於 portfolio_tab 的 index"""
        from pathlib import Path
        import StockTool as st
        stocktool_path = Path(__file__).parent.parent / "source" / "StockTool.py"
        portfolio_idx = _find_portfolio_tab_index(stocktool_path)

        # 抓 _on_tab_changed 的 source code
        method = st.StrategyGUI._on_tab_changed
        src = (method.__doc__ or "") + "\n"
        try:
            import inspect
            src += inspect.getsource(method)
        except (OSError, TypeError):
            pass

        # 找 `if current == <N>` pattern
        m = re.search(r"if\s+current\s*==\s*(\d+)", src)
        assert m, (
            "_on_tab_changed 內找不到 `if current == N` pattern — "
            "可能改寫成不一樣的形式、需更新測試"
        )
        on_tab_idx = int(m.group(1))
        assert on_tab_idx == portfolio_idx, (
            f"_on_tab_changed 用 index {on_tab_idx}，"
            f"但 portfolio tab 實際在 index {portfolio_idx}。"
            f"這就是為什麼 ETF tab 才會觸發買賣記錄 refresh。\n"
            f"修法：把 _on_tab_changed 內的 `if current == {on_tab_idx}` 改成 `if current == {portfolio_idx}`"
        )


# ==========================================================
# 整合測試：mock notebook 模擬各種 tab 切換
# ==========================================================

def _make_mock_self_with_notebook(current_tab_idx: int):
    """建 mock self、給定 current_tab_idx 模擬切到某個 tab"""
    mock = SimpleNamespace()
    mock.logger = MagicMock()
    mock.notebook = SimpleNamespace()
    mock.notebook.index = MagicMock(return_value=current_tab_idx)
    mock.notebook.select = MagicMock(return_value="fake_tab_id")
    # 用 MagicMock 追蹤呼叫
    mock._refresh_portfolio_view = MagicMock()
    mock._auto_fetch_positions_prices = MagicMock()
    mock._portfolio_refresh_job_id = None

    # after 模擬（避免真的排程）
    mock.after_calls = []
    mock.after = MagicMock(side_effect=lambda ms, cb: (
        mock.after_calls.append((ms, cb)) or f"job_{len(mock.after_calls)}"
    ))
    mock.after_cancel = MagicMock()
    return mock


class TestOnTabChangedBehavior:
    """驗證 _on_tab_changed 在切到不同 tab 時的行為"""

    @patch("StockTool._is_market_hours", return_value=False)  # 收盤、避免排 30 秒
    def test_切到買賣記錄_tab_觸發_refresh(self, _mock_market):
        """切到買賣記錄 Tab → 觸發 _refresh_portfolio_view"""
        import StockTool as st
        from pathlib import Path

        stocktool_path = Path(__file__).parent.parent / "source" / "StockTool.py"
        portfolio_idx = _find_portfolio_tab_index(stocktool_path)

        mock = _make_mock_self_with_notebook(current_tab_idx=portfolio_idx)
        mock.event = SimpleNamespace()

        st.StrategyGUI._on_tab_changed(mock, mock.event)

        mock._refresh_portfolio_view.assert_called_once(), \
            f"切到買賣記錄 Tab（index {portfolio_idx}）應觸發 _refresh_portfolio_view"
        # 應排程 100ms 抓現價
        assert any(ms == 100 for ms, _ in mock.after_calls), \
            "切到買賣記錄 Tab 應排程 after(100, _auto_fetch_positions_prices)"

    @patch("StockTool._is_market_hours", return_value=False)
    def test_切到_etf_tab_不觸發_refresh(self, _mock_market):
        """切到 ETF Tab → 不應觸發買賣記錄 refresh（避免這次 bug 再次發生）"""
        import StockTool as st
        from pathlib import Path

        stocktool_path = Path(__file__).parent.parent / "source" / "StockTool.py"
        etf_idx = _find_etf_tab_index(stocktool_path)

        mock = _make_mock_self_with_notebook(current_tab_idx=etf_idx)
        mock.event = SimpleNamespace()

        st.StrategyGUI._on_tab_changed(mock, mock.event)

        mock._refresh_portfolio_view.assert_not_called(), \
            f"切到 ETF Tab（index {etf_idx}）**不應**觸發買賣記錄 refresh — " \
            f"這是 2026-06-24 09:12 bug 的根本原因（trigger 放錯 tab）"

    @patch("StockTool._is_market_hours", return_value=False)
    def test_切到系統選股_tab_不觸發_refresh(self, _mock_market):
        """切到系統選股 Tab → 不應觸發"""
        import StockTool as st

        mock = _make_mock_self_with_notebook(current_tab_idx=0)
        mock.event = SimpleNamespace()

        st.StrategyGUI._on_tab_changed(mock, mock.event)

        mock._refresh_portfolio_view.assert_not_called()

    @patch("StockTool._is_market_hours", return_value=False)
    def test_切到回測模擬_tab_不觸發_refresh(self, _mock_market):
        """切到回測模擬 Tab → 不應觸發"""
        import StockTool as st

        mock = _make_mock_self_with_notebook(current_tab_idx=4)
        mock.event = SimpleNamespace()

        st.StrategyGUI._on_tab_changed(mock, mock.event)

        mock._refresh_portfolio_view.assert_not_called()