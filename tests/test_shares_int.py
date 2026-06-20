"""【V0.9.5-shares-int】買賣紀錄頁面股數顯示整數守護

2026-06-20 14:13 William 反映：
- 買賣紀錄頁面中股數顯示不用小數點只要整數即可

【根因】
- Transaction.shares: float = 0.0（portfolio.py line 326）
- str(t.shares) 對於 float 1000.0 會顯示「1000.0」
- 對於 float 1000.5 會顯示「1000.5」

【修法】3 個 Treeview cell 股數改成 str(int(t.shares))
- 買賣記錄 mini Treeview
- 持倉 Treeview
- 交易 Treeview

【不修的地方】
- Label widget（已是 .0f 整數顯示 + 千分位）
- 計算邏輯（avg_cost、market_value 等仍用 float）
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _find_treeview_block(content: str, anchor: str, end_anchor: str) -> str:
    """找 Treeview insert 區塊"""
    start = content.find(anchor)
    if start < 0:
        return ""
    end = content.find(end_anchor, start)
    if end < 0:
        end = len(content)
    return content[start:end]


def test_mini_tree_shares_is_int():
    """【核心守護】買賣記錄 mini Treeview 股數用 str(int(t.shares))
    → 避免顯示 1000.0 小數點
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    block = _find_treeview_block(
        content,
        "mini.insert(",
        "        # ── 關閉按鈕 ──",
    )
    assert block, "❌ 找不到 mini.insert 區塊"

    # 必須有 str(int(t.shares))
    assert "str(int(t.shares))" in block, (
        f"❌ 買賣記錄 mini Treeview 股數沒用 str(int(t.shares))！\n"
        f"目前：\n{block}\n"
        f"改成 str(int(t.shares)) 強制整數顯示。"
    )
    # 不該有 str(t.shares) 沒 int() 的版本
    bare_str = re.findall(r"str\(t\.shares\)(?!\))", block)
    # 排除已經包在 int() 內的（str(int(t.shares)) 包含 str(t.shares) 字串）
    # 用 negative lookbehind 排除
    bare_str_no_int = re.findall(r"(?<!int\()str\(t\.shares\)", block)
    assert not bare_str_no_int, (
        f"❌ mini Treeview 還有 str(t.shares) 沒 int()！\n"
        f"找到：{bare_str_no_int}"
    )


def test_positions_tree_shares_is_int():
    """【核心守護】持倉 Treeview 股數用 str(int(p.shares))
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    block = _find_treeview_block(
        content,
        "self._positions_tree.insert(",
        "            # 交易明細",
    )
    assert block, "❌ 找不到 _positions_tree.insert 區塊"

    assert "str(int(p.shares))" in block, (
        f"❌ 持倉 Treeview 股數沒用 str(int(p.shares))！\n"
        f"目前：\n{block}\n"
        f"改成 str(int(p.shares)) 強制整數顯示。"
    )


def test_tx_tree_shares_is_int():
    """【核心守護】交易 Treeview 股數用 str(int(t.shares))
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    block = _find_treeview_block(
        content,
        "self._tx_tree.insert(",
        "        except Exception as e:",
    )
    assert block, "❌ 找不到 _tx_tree.insert 區塊"

    assert "str(int(t.shares))" in block, (
        f"❌ 交易 Treeview 股數沒用 str(int(t.shares))！\n"
        f"目前：\n{block}\n"
        f"改成 str(int(t.shares)) 強制整數顯示。"
    )


def test_str_int_removes_decimal_for_float():
    """【功能驗證】str(int(1000.0)) = "1000"（沒小數點）
    → 證明 int() 強制轉能解決 float 小數點問題
    """
    assert str(int(1000.0)) == "1000", "str(int(1000.0)) 應該是 '1000'"
    assert str(int(1000)) == "1000", "str(int(1000)) 應該是 '1000'"
    assert str(int(1000.5)) == "1000", "str(int(1000.5)) 應該是 '1000'（截斷）"
    assert str(int(0.0)) == "0", "str(int(0.0)) 應該是 '0'"

    # 對照組：str() 不帶 int() 會有小數點
    assert str(1000.0) == "1000.0", "str(1000.0) 會保留小數點 → 這就是 bug 來源"


def test_summary_label_shares_can_use_comma_thousands():
    """【反向守護】持倉總覽 Label 可以保留千分位 + 整數
    → Label 是純文字、不會被 Tkinter locale bug 影響
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 f"{...shares...:,.0f}" 格式
    matches = re.findall(
        r'f"\{[^}]*shares[^}]*:,\.0f\}',
        content,
    )
    assert matches, (
        "❌ 找不到 shares 用千分位整數格式！\n"
        "預期 Label 用 f\"{shares:,.0f}\" 顯示（保留千分位 + 整數）。"
    )


def test_stocktool_compiles():
    """【語法守護】_refresh_portfolio_view 改完沒漏逗號
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")