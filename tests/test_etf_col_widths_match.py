"""V0.9.5-etf-history col_widths 守護

2026-06-20 William 反映：新增「今日異動」欄後 header 沒顯示
根因：cols 6 個、col_widths 5 個、zip() 只到最短 → 第 6 個 col 沒 heading() 設定
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


def test_etf_cols_and_widths_have_same_length():
    """cols tuple 和 col_widths tuple 必須同長
    否則 zip() 會丟掉尾部的 column、heading() 沒跑到、header 空白
    """
    with open(os.path.join(os.path.dirname(__file__), "..", "source", "StockTool.py"), "r", encoding="utf-8") as f:
        content = f.read()

    # 找 ETF Tab Treeview 區塊
    # 找「cols = (」後面最近的「col_widths = (」
    m_cols = re.search(r'cols = \(([^)]+)\)\s*\n\s*self\._etf_tree = ttk\.Treeview', content)
    assert m_cols, "❌ 找不到 ETF Treeview 的 cols tuple"
    cols = [c.strip().strip('"').strip("'") for c in m_cols.group(1).split(",")]
    print(f"  cols ({len(cols)}): {cols}")

    m_widths = re.search(r'col_widths = \(([^)]+)\)\s*\n\s*for col, w in zip\(cols', content)
    assert m_widths, "❌ 找不到 col_widths tuple"
    widths = [int(w.strip()) for w in m_widths.group(1).split(",") if w.strip().isdigit()]
    print(f"  col_widths ({len(widths)}): {widths}")

    assert len(cols) == len(widths), (
        f"❌ cols 數量 ({len(cols)}) ≠ col_widths 數量 ({len(widths)})！\n"
        f"zip() 會丟掉尾部的 col、heading() 沒跑到、header 空白。\n"
        f"cols: {cols}\n"
        f"col_widths: {widths}\n"
        f"  → 補上 col_widths 缺少的寬度。"
    )

    print("  ✅ cols 和 col_widths 數量一致")


def test_etf_tree_has_今日異動_column():
    """Treeview 必須有「今日異動」欄"""
    with open(os.path.join(os.path.dirname(__file__), "..", "source", "StockTool.py"), "r", encoding="utf-8") as f:
        content = f.read()

    # 找 ETF Treeview 的 cols tuple
    m = re.search(r'self\._etf_tree = ttk\.Treeview\([^)]*columns=cols', content)
    assert m, "❌ 找不到 ETF Treeview 宣告"

    # 找 cols 定義（就在前幾行）
    start = content.rfind("cols = ", 0, m.start())
    end = content.find(")", start)
    cols_str = content[start:end]
    assert "今日異動" in cols_str, (
        f"❌ ETF Treeview 沒有「今日異動」欄！\n"
        f"  cols 定義：{cols_str}"
    )
    print("  ✅ 找到「今日異動」欄")


def test_etf_tree_all_columns_have_heading():
    """每個 col 都必須有 heading() 設定（避免「未設定的 column 不顯示 header」）

    source 中 1 個 heading() 在 for loop 內 → 跑 N 次 → 頂多 N 個 col
    關鍵守護：loop body 內的 heading() 個數 + 1 (zip 體) >= len(cols)
    最簡單的測試：loop body 內 heading() 數量 == 1
    """
    with open(os.path.join(os.path.dirname(__file__), "..", "source", "StockTool.py"), "r", encoding="utf-8") as f:
        content = f.read()

    # 找 cols tuple
    m_cols = re.search(r'cols = \(([^)]+)\)\s*\n\s*self\._etf_tree = ttk\.Treeview', content)
    cols = [c.strip().strip('"').strip("'") for c in m_cols.group(1).split(",")]

    # 找後面的 for loop body（取 for col, w in zip( 之後 500 字元）
    m_loop_start = content.find('for col, w in zip(cols, col_widths):')
    assert m_loop_start > 0, "❌ 找不到 for col, w in zip(cols, col_widths) 的 loop"
    body = content[m_loop_start:m_loop_start+500]

    # for loop 內 heading() 和 column() 各只出現 1 次（跳出前的邏輯）
    heading_count = body.count("self._etf_tree.heading(")
    column_count = body.count("self._etf_tree.column(")
    print(f"  heading() 次數: {heading_count}、column() 次數: {column_count}")
    print(f"  cols 數量: {len(cols)}")

    # 守護：for loop body 內至少要有 heading() 和 column() 呼叫
    # （不加 == 1 的嚴格檢查、避免 multi-line 拼接影響）
    assert heading_count >= 1, (
        f"❌ for loop 內沒有 heading() 呼叫！\n"
        f"  cols: {cols}"
    )
    assert column_count >= 1, (
        f"❌ for loop 內沒有 column() 呼叫！\n"
        f"  cols: {cols}"
    )

    # 真正關鍵的守護：len(cols) == len(col_widths)
    # （上面 test_etf_cols_and_widths_have_same_length 已經測了、這裡只要 body 內有 heading 就 OK）
    print("  ✅ for loop body 內有 heading() 和 column() 設定")
