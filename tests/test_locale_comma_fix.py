"""【V0.9.5-locale-comma-fix】Treeview cell 不再用千分位逗號守護

2026-06-20 12:12 William 反映：
- Windows 區域格式設定正確（中文臺灣、千位=`,`、小數=`.`）
- 但 Treeview cell 內千位分隔顯示成 `.` 不是 `,`
- 至少價格（Treeview 內）有這問題

【根因】延續 V0.9.5-goodinfo4+5 教訓：
- Tkinter Treeview + locale=zh_TW.UTF-8 會把 cell 字串的 `,` 當成歐洲小數點
- 成交量已解：用 str(int(vol)) 不千分位
- 但其他 Treeview cell（價格、市值、手續費、股數、損益）仍用 f"{x:,.2f}"
  → 一樣被轉成歐洲格式顯示

【修法】4 個 Treeview cell 全改不加千分位：
1. ETF Treeview price_str
2. 買賣記錄 mini Treeview
3. 持倉 Treeview
4. 交易 Treeview

【不改的地方】
- Label widget（持倉總覽、預估視窗 stat()）：純文字、不會被 Tkinter locale bug 影響
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
    """找 Treeview insert 區塊（從 anchor 到 end_anchor 之間的內容）
    - 確保只 grep 那段、不波及 Label / stat() 區塊
    """
    start = content.find(anchor)
    if start < 0:
        return ""
    end = content.find(end_anchor, start)
    if end < 0:
        end = len(content)
    return content[start:end]


# 千分位格式 regex（f"{x:,.2f}" → ",.2f"）
COMMA_THOUSANDS_PATTERN = r":,\.[0-9]*f"


def test_etf_tree_price_no_comma_thousands():
    """【核心守護】ETF Treeview 收盤價不該用千分位
    → Tkinter Treeview 會把 , 轉成歐洲小數點
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _etf_tree.insert 區塊
    block = _find_treeview_block(
        content,
        'self._etf_tree.insert(',
        "        self._etf_status.set(",
    )
    assert block, "❌ 找不到 _etf_tree.insert 區塊"

    # 不該有 :,2f 或 :,0f 千分位
    comma_format = re.findall(COMMA_THOUSANDS_PATTERN, block)
    assert not comma_format, (
        f"❌ ETF Treeview 還有用千分位的格式化！\n"
        f"找到：{comma_format}\n"
        f"Tkinter Treeview 會把 , 轉成歐洲小數點（zh_TW locale 問題）。\n"
        f"改成 f\"{{x:.2f}}\" 或 str(x)。"
    )


def test_mini_tree_no_comma_thousands():
    """【核心守護】買賣記錄 mini Treeview 不該用千分位
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 mini.insert 區塊
    block = _find_treeview_block(
        content,
        "mini.insert(",
        "        # ── 關閉按鈕 ──",
    )
    assert block, "❌ 找不到 mini.insert 區塊"

    comma_format = re.findall(COMMA_THOUSANDS_PATTERN, block)
    assert not comma_format, (
        f"❌ 買賣記錄 mini Treeview 還有用千分位的格式化！\n"
        f"找到：{comma_format}\n"
        f"改成 f\"{{x:.2f}}\" 或 str(x)。"
    )


def test_positions_tree_no_comma_thousands():
    """【核心守護】持倉 Treeview 不該用千分位
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    block = _find_treeview_block(
        content,
        "self._positions_tree.insert(",
        "            # 交易明細",
    )
    assert block, "❌ 找不到 _positions_tree.insert 區塊"

    comma_format = re.findall(COMMA_THOUSANDS_PATTERN, block)
    assert not comma_format, (
        f"❌ 持倉 Treeview 還有用千分位的格式化！\n"
        f"找到：{comma_format}\n"
        f"改成 f\"{{x:.2f}}\" 或 str(x)。"
    )


def test_tx_tree_no_comma_thousands():
    """【核心守護】交易 Treeview 不該用千分位
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    block = _find_treeview_block(
        content,
        "self._tx_tree.insert(",
        "        except Exception as e:",
    )
    assert block, "❌ 找不到 _tx_tree.insert 區塊"

    comma_format = re.findall(COMMA_THOUSANDS_PATTERN, block)
    assert not comma_format, (
        f"❌ 交易 Treeview 還有用千分位的格式化！\n"
        f"找到：{comma_format}\n"
        f"改成 f\"{{x:.2f}}\" 或 str(x)。"
    )


def test_summary_labels_can_use_comma_thousands():
    """【反向守護】Summary Label（_summary_labels.config）可以用千分位
    → Label 是純文字、不會被 Tkinter locale bug 影響
    → 保留千分位顯示讓總覽數字易讀
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _summary_labels["..."].config(text=...) 區塊
    matches = re.findall(
        r'_summary_labels\["[^"]+"\]\.config\(text=f"[^"]*' + COMMA_THOUSANDS_PATTERN,
        content,
    )
    assert matches, (
        "❌ 找不到 _summary_labels.config(text=f\"...:,...f\") 用千分位的格式！\n"
        "預期 Label widget 應該保留千分位顯示（純文字、不會被 Tkinter locale bug 影響）。"
    )


def test_popup_text_can_use_comma_thousands():
    """【反向守護】popup Text widget 內的 stat() / label 可以用千分位
    → Text widget 不是 Treeview、沒有 locale bug
    → 保留千分位顯示讓數字易讀
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 stat(cf, ...) 用千分位的區塊
    matches = re.findall(r'stat\(cf,\s*"[^"]*",\s*f"[^"]*' + COMMA_THOUSANDS_PATTERN, content)
    assert matches, (
        "❌ 找不到 stat() 用千分位的格式！\n"
        "預期 Label-based 預估視窗保留千分位。"
    )


def test_stocktool_compiles():
    """【語法守護】_show_etf_popup / _refresh_portfolio_view 改完沒漏逗號
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")