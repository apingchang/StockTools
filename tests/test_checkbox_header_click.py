"""V0.9.5-tab-split-phase3-D 守護：勾選欄 header click → 全選/全不選

驗證 4 個 Treeview（select_tree / backtest_tree / ms_tree / etf_tree）的：
1. 第一欄 header 文字有 ☑ 視覺
2. <Button-1> 有綁 handler
3. Handler 內 region=="heading" and column=="#1" 會 toggle 全選
4. Handler 內 region=="cell" and column=="#1" 會 toggle 該列
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _read():
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        return f.read()


def _has_handler_for_tree(content: str, handler_name: str, tree_name: str) -> bool:
    """確認某 tree 有綁某 handler

    兼容兩種寫法：
    - 直接綁：self.tree_name.bind(...)
    - 透過 _build_tab_layout 區域變數綁：results_tree.bind(...)（之後 assign 給 self.select_tree / self.backtest_tree）
    """
    # 1. 直接綁
    direct = re.search(
        rf'{re.escape(tree_name)}\.bind\([^)]*{re.escape(handler_name)}',
        content, re.DOTALL,
    )
    if direct:
        return True
    # 2. 透過 _build_tab_layout 的 results_tree 共用綁（涵蓋 select_tree + backtest_tree）
    if tree_name in ("select_tree", "backtest_tree"):
        shared = re.search(
            rf'results_tree\.bind\([^)]*{re.escape(handler_name)}',
            content, re.DOTALL,
        )
        if shared:
            return True
    return False


def _handler_has_heading_toggle(content: str, handler_name: str) -> bool:
    """確認某 handler 內有 heading+#1 → toggle 邏輯"""
    m = re.search(
        rf'def {re.escape(handler_name)}\(.*?\n    def |\Z',
        content, re.DOTALL,
    )
    if not m:
        return False
    body = m.group(0)
    return ('region == "heading"' in body) and ('column == "#1"' in body)


import re


def test_select_tree_binds_button1():
    """select_tree 有綁 _on_select_tree_click"""
    content = _read()
    assert _has_handler_for_tree(content, "_on_select_tree_click", "select_tree"), (
        "❌ select_tree 沒綁 _on_select_tree_click！\n"
        "Heading click → toggle 全選 會失效"
    )
    print("✅ select_tree 有綁 _on_select_tree_click")


def test_backtest_tree_binds_button1():
    """backtest_tree 有綁 _on_select_tree_click（共用 handler）"""
    content = _read()
    assert _has_handler_for_tree(content, "_on_select_tree_click", "backtest_tree"), (
        "❌ backtest_tree 沒綁 _on_select_tree_click！\n"
        "Heading click → toggle 全選 會失效"
    )
    print("✅ backtest_tree 有綁 _on_select_tree_click")


def test_ms_tree_binds_button1():
    """ms_tree 有綁 _ms_toggle_check"""
    content = _read()
    assert _has_handler_for_tree(content, "_ms_toggle_check", "_ms_tree"), (
        "❌ ms_tree 沒綁 _ms_toggle_check！"
    )
    print("✅ ms_tree 有綁 _ms_toggle_check")


def test_select_click_handler_has_heading_toggle():
    """_on_select_tree_click 內有 heading+#1 → 全選/全不選"""
    content = _read()
    assert _handler_has_heading_toggle(content, "_on_select_tree_click"), (
        "❌ _on_select_tree_click 內沒 heading+#1 toggle 邏輯！\n"
        "應有：if region == \"heading\" and column == \"#1\": ..."
    )
    print("✅ _on_select_tree_click 有 heading+#1 toggle")


def test_ms_click_handler_has_heading_toggle():
    """_ms_toggle_check 內有 heading+#1 → 全選/全不選"""
    content = _read()
    assert _handler_has_heading_toggle(content, "_ms_toggle_check"), (
        "❌ _ms_toggle_check 內沒 heading+#1 toggle 邏輯！"
    )
    print("✅ _ms_toggle_check 有 heading+#1 toggle")


def test_select_tree_first_col_has_checkbox_icon():
    """select_tree 第一欄 header 文字要有 ☑（讓使用者看出可點）"""
    content = _read()
    # 找 cols = (...) 內第一個元素是 "☑"
    m = re.search(r'cols\s*=\s*\(\s*["\']☑["\']', content)
    assert m, (
        "❌ select_tree 第一欄 header 沒有 ☑！\n"
        "應為 cols = (\"☑\", \"代號\", ...)\n"
        "目前使用者看不出第一欄可以點"
    )
    print("✅ select_tree 第一欄 header 是 ☑")


def test_ms_tree_first_col_has_checkbox_label():
    """ms_tree 第一欄 header 文字要有「勾選」或 ☑（讓使用者看出可點）"""
    content = _read()
    # 找 ms_tree 之前最近的 cols tuple（含 checkbox 字樣）
    # 因為 cols 可能在 Treeview 之前定義、用「_ms_tree = ttk.Treeview」往前抓
    m_ms = re.search(
        r'cols\s*=\s*\(([^)]+勾選[^)]+)\)\s*\n[^\n]*\n[^\n]*_ms_tree\s*=',
        content, re.DOTALL,
    )
    if not m_ms:
        # fallback: 找包含「勾選」字樣的 cols tuple
        candidates = re.findall(r'cols\s*=\s*\(([^)]+)\)', content)
        m_ms = None
        for c in candidates:
            if "勾選" in c:
                m_ms = type('M', (), {'group': lambda self, n: c if n == 1 else ''})()
                break
    assert m_ms, "❌ 找不到 ms_tree 的 cols tuple（含「勾選」）"
    cols_text = m_ms.group(1)
    first_col_match = re.search(r'["\']([^"\']+)["\']', cols_text)
    assert first_col_match, f"❌ cols tuple 內第一個欄位解析失敗：{cols_text[:80]}"
    first_col = first_col_match.group(1)
    assert "勾選" in first_col or "☑" in first_col, (
        f"❌ ms_tree 第一欄 header 是「{first_col}」、應該是「勾選」或「☑」"
    )
    print(f"✅ ms_tree 第一欄 header 是「{first_col}」")


def test_etf_tree_first_col_has_checkbox_label():
    """etf_tree 第一欄 header 文字要有「勾選」"""
    content = _read()
    candidates = re.findall(r'cols\s*=\s*\(([^)]+)\)', content)
    cols_text = None
    for c in candidates:
        if "勾選" in c and "ETF" in c:
            cols_text = c
            break
    assert cols_text, "❌ 找不到 etf_tree 的 cols tuple（含「勾選」且有 ETF）"
    first_col_match = re.search(r'["\']([^"\']+)["\']', cols_text)
    assert first_col_match, f"❌ cols tuple 內第一個欄位解析失敗：{cols_text[:80]}"
    first_col = first_col_match.group(1)
    assert "勾選" in first_col or "☑" in first_col, (
        f"❌ etf_tree 第一欄 header 是「{first_col}」、應該是「勾選」或「☑」"
    )
    print(f"✅ etf_tree 第一欄 header 是「{first_col}」")


def test_etf_click_handler_has_heading_toggle():
    """【V0.9.5-tab-split-phase3-D 新增】_etf_toggle_check 也要有 heading+#1 全選"""
    content = _read()
    m = re.search(
        r'def _etf_toggle_check\(.*?\n    def |\Z',
        content, re.DOTALL,
    )
    if not m:
        assert False, (
            "❌ _etf_toggle_check 內沒有 heading click 處理！\n"
            "ETF tab 的 header 點下去沒反應\n"
            "Phase 3 D：補上 heading+#1 → 全選/全不選"
        )
    body = m.group(0)
    # 接受兩種寫法：一起判 (region == "heading" and column == "#1") 或分開判
    has_heading_check = (
        ('region == "heading"' in body and 'column == "#1"' in body)
        or ('region == "heading"' in body and 'column != "#1"' in body)
    )
    assert has_heading_check, (
        "❌ _etf_toggle_check 內沒 heading+#1 toggle 邏輯"
    )
    # 必須有「全選」或「全不選」叫用
    has_toggle_action = (
        "_etf_select_all" in body and "_etf_select_none" in body
    )
    assert has_toggle_action, (
        "❌ _etf_toggle_check header 點下去沒叫 _etf_select_all/_none"
    )
    print("✅ _etf_toggle_check 有 heading+#1 toggle")


def test_checkbox_header_dynamic_state():
    """【V0.9.5-tab-split-phase3-D 新增】checkbox header 應該會根據全選狀態動態變 ☑/☐/▣

    否則使用者點了 header、rows 都勾起來了、但 header 還是 ☑ 看不出反饋
    """
    content = _read()
    # 確認有 _update_checkbox_header_text 或類似的動態更新 method
    has_dynamic_header = (
        "_update_checkbox_header" in content
        or "_refresh_checkbox_header" in content
        or "checkbox_header_text" in content
        or "_select_all_header" in content
    )
    assert has_dynamic_header, (
        "❌ checkbox header 沒做動態 ☑/☐ 切換！\n"
        "Phase 3 D：新增動態 header 文字（依全選狀態切 ☑/☐/混和）"
    )
    print("✅ checkbox header 有動態 ☑/☐ 切換")


def test_checkbox_header_logic_states():
    """【V0.9.5-tab-split-phase3-D 新增】_update_checkbox_header 邏輯含 ☐/☑/▣ 三態 + heading 更新"""
    import ast
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_update_checkbox_header":
            method = node
            break
    assert method is not None, "❌ _update_checkbox_header method 不存在"
    body_src = ast.unparse(method)
    assert 'checked_count' in body_src, "❌ 沒統計 checked_count"
    assert '☐' in body_src, "❌ 沒寫 ☐ 字串"
    assert '☑' in body_src, "❌ 沒寫 ☑ 字串"
    assert '▣' in body_src, "❌ 沒寫 ▣ 字串（混和狀態）"
    assert 'tree.heading' in body_src, "❌ 沒呼叫 tree.heading"
    print("✅ _update_checkbox_header 邏輯包含 ☐/☑/▣ 三態 + heading 更新")


def test_all_trees_init_header_to_checkbox():
    """【V0.9.5-tab-split-phase3-D 新增】三個 Treeview 初始 header 都應該設為 ☐

    而不是預設的 col 名稱（「勾選」或「☑」）
    讓使用者看到 Treeview 就知道第一欄是個 checkbox
    """
    content = _read()
    has_select_tree_init = 'self.select_tree.heading(cols[0], text="☐")' in content
    has_ms_tree_init = 'self._ms_tree.heading(cols[0], text="☐")' in content
    has_etf_tree_init = 'self._etf_tree.heading(cols[0], text="☐")' in content
    has_results_tree_init = (
        'results_tree.heading(first_col, text="☐")' in content
        or 'results_tree.heading(cols[0], text="☐")' in content
    )
    init_count = sum([
        has_select_tree_init, has_ms_tree_init,
        has_etf_tree_init, has_results_tree_init,
    ])
    assert init_count >= 3, (
        f"❌ 只找到 {init_count} 個 Treeview 初始 header 設定（應該至少 3 個）\n"
        f"  select_tree: {has_select_tree_init}\n"
        f"  ms_tree: {has_ms_tree_init}\n"
        f"  etf_tree: {has_etf_tree_init}\n"
        f"  results_tree: {has_results_tree_init}"
    )
    print(f"✅ {init_count} 個 Treeview 初始 header 設為 ☐")


def test_select_all_calls_update_header():
    """【V0.9.5-tab-split-phase3-D】_select_all / _select_none 都要叫 _update_checkbox_header"""
    content = _read()
    m_all = re.search(r'def _select_all\(.*?\n    def |\Z', content, re.DOTALL)
    m_none = re.search(r'def _select_none\(.*?\n    def |\Z', content, re.DOTALL)
    assert m_all, "❌ 找不到 _select_all method"
    assert m_none, "❌ 找不到 _select_none method"
    assert '_update_checkbox_header' in m_all.group(0), "❌ _select_all 沒叫 _update_checkbox_header"
    assert '_update_checkbox_header' in m_none.group(0), "❌ _select_none 沒叫 _update_checkbox_header"
    print("✅ _select_all / _select_none 都會更新 header")


def test_ms_etf_select_all_calls_update_header():
    """【V0.9.5-tab-split-phase3-D】_ms_select_all / _etf_select_all 都要叫 helper"""
    content = _read()
    for fn in ("_ms_select_all", "_ms_select_none", "_etf_select_all", "_etf_select_none"):
        m = re.search(rf'def {fn}\(.*?\n    def |\Z', content, re.DOTALL)
        assert m, f"❌ 找不到 {fn}"
        assert '_update_checkbox_header' in m.group(0), (
            f"❌ {fn} 沒叫 _update_checkbox_header"
        )
    print("✅ _ms_select_all / _ms_select_none / _etf_select_all / _etf_select_none 都會更新 header")


if __name__ == "__main__":
    test_select_tree_binds_button1()
    test_backtest_tree_binds_button1()
    test_ms_tree_binds_button1()
    test_select_click_handler_has_heading_toggle()
    test_ms_click_handler_has_heading_toggle()
    test_etf_click_handler_has_heading_toggle()
    test_select_tree_first_col_has_checkbox_icon()
    test_ms_tree_first_col_has_checkbox_label()
    test_etf_tree_first_col_has_checkbox_label()
    test_checkbox_header_dynamic_state()
    test_checkbox_header_logic_states()
    test_all_trees_init_header_to_checkbox()
    test_select_all_calls_update_header()
    test_ms_etf_select_all_calls_update_header()
    print("\n🎉 14 個 checkbox header test 全綠")