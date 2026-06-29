"""【V1.1-popup-col-shift】加「漲跌價」欄後、popup 觸發 column 改為 #6 / #7

2026-06-29 19:44 William 反映：
- 加了漲跌價後 pop up window 的位置錯了
- 在漲跌價處 pop up ETF 持有股票名稱、在 etf 數處 pop up 異動 details
- 應該要往右移動一欄

【修法】
- column 重新對應：
  - 原本：#1=勾選, #2=代號, #3=名稱, #4=收盤價, #5=ETF數, #6=今日異動
  - 現在：#1=勾選, #2=代號, #3=名稱, #4=收盤價, #5=漲跌價, #6=ETF數, #7=今日異動
- _show_etf_popup 觸發條件：#5 → #6（ETF數）、#6 → #7（今日異動）
- 2 處都要改（_etf_tree_hover_combined + _on_etf_tree_hover 雖然後者沒被 bind、仍同步修）
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_etf_hover_uses_new_column_numbers():
    """_etf_tree_hover_combined 必須用 #6 (ETF數) + #7 (今日異動)"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _etf_tree_hover_combined\(self, event\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _etf_tree_hover_combined"
    body = m.group(1)
    # 必須有 #6 (ETF數 → etf_list mode)
    assert 'column == "#6"' in body, (
        "❌ _etf_tree_hover_combined 沒用 #6 (ETF數)!\n"
        "  V1.1-add-change-col 加了「漲跌價」欄 → 原本 #5 變 #6"
    )
    # 必須有 #7 (今日異動 → changes mode)
    assert 'column == "#7"' in body, (
        "❌ _etf_tree_hover_combined 沒用 #7 (今日異動)!\n"
        "  原本 #6 變 #7"
    )
    # 不能還有舊的 #5 觸發
    assert 'column == "#5"' not in body, (
        "❌ _etf_tree_hover_combined 還有舊的 #5 觸發! (已過時、會跟漲跌價欄衝突)"
    )


def test_old_etf_hover_also_updated():
    """_on_etf_tree_hover (未 bind 但保留) 也要同步更新"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _on_etf_tree_hover\(self, event\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_etf_tree_hover"
    body = m.group(1)
    # 也要改
    if "column ==" in body:
        assert 'column == "#6"' in body, "_on_etf_tree_hover 沒更新到 #6"
        assert 'column == "#7"' in body, "_on_etf_tree_hover 沒更新到 #7"
        assert 'column == "#5"' not in body, "_on_etf_tree_hover 還有舊 #5"


def test_etf_tree_has_7_columns():
    """_etf_tree 必須是 7 欄（加漲跌價後）"""
    content = _read(STOCKTOOL_PY)
    m_tree = content.find("self._etf_tree = ttk.Treeview")
    if m_tree < 0:
        pytest.skip("找不到 self._etf_tree")
    before = content[:m_tree]
    cols_start = before.rfind("cols = (")
    paren_start = before.find("(", cols_start)
    depth = 1
    i = paren_start + 1
    while i < len(before) and depth > 0:
        ch = before[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < len(before) and before[i] != quote:
                if before[i] == "\\":
                    i += 1
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    cols_body = before[paren_start + 1 : i - 1]
    n = len(re.findall(r'"[^"]*"|\'[^\']*\'', cols_body))
    assert n == 7, (
        f"❌ _etf_tree cols 應該 7 欄（加漲跌價）、實際 {n} 欄\n"
        f"  cols body: {cols_body[:300]}"
    )
