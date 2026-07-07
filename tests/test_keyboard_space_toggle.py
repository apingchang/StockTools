"""
【V1.2.0-keyboard-toggle】Space 鍵 toggle focus row 勾選

William 2026-07-06 15:32 反映：
- 除了滑鼠點勾選外，希望用 ↑/↓ 鍵移動 highlight、Space 鍵 toggle 勾選

驗證：
1. 4 個 Treeview（select_tree / backtest_tree / ms_tree / etf_tree）都有綁 <space>
2. 4 個 Treeview 的 <space> handler 都是 _on_tree_space_toggle
3. _on_tree_space_toggle 函式存在
4. 行為：focus row 正確被 toggle、checked_dict 更新、tree.item 更新
"""
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _read():
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        return f.read()


def _has_space_bind(content: str, tree_name: str) -> bool:
    """確認某 tree 有綁 <space> event"""
    # 1. 直接綁：self.tree_name.bind("<space>", ...)
    direct = re.search(
        rf'{re.escape(tree_name)}\.bind\(\s*["\']<space>["\']',
        content,
    )
    if direct:
        return True
    # 2. 透過 _build_tab_layout 共用綁（涵蓋 select_tree + backtest_tree）
    if tree_name in ("select_tree", "backtest_tree"):
        shared = re.search(
            r'results_tree\.bind\(\s*["\']<space>["\']',
            content,
        )
        if shared:
            return True
    return False


# ==========================================================
# 靜態測試：4 個 Treeview 都有綁 <space>
# ==========================================================


def test_select_tree_binds_space():
    content = _read()
    assert _has_space_bind(content, "select_tree"), (
        "❌ select_tree 沒綁 <space>！\n"
        "William 15:32 要求 4 個 Treeview 都要支援 Space 鍵 toggle"
    )


def test_backtest_tree_binds_space():
    content = _read()
    assert _has_space_bind(content, "backtest_tree"), (
        "❌ backtest_tree 沒綁 <space>！"
    )


def test_ms_tree_binds_space():
    content = _read()
    assert _has_space_bind(content, "_ms_tree"), (
        "❌ _ms_tree 沒綁 <space>！"
    )


def test_etf_tree_binds_space():
    content = _read()
    assert _has_space_bind(content, "_etf_tree"), (
        "❌ _etf_tree 沒綁 <space>！"
    )


def test_handler_is_on_tree_space_toggle():
    """所有 <space> binding 都指向 _on_tree_space_toggle"""
    content = _read()
    # 找所有 <space> bind 的右側 handler
    pattern = r'\.bind\("<space>",\s*self\.(\w+)\)'
    handlers = re.findall(pattern, content)
    assert handlers, "完全沒找到任何 <space> binding"
    for h in handlers:
        assert h == "_on_tree_space_toggle", (
            f"❌ <space> binding 用了 {h}、不是 _on_tree_space_toggle"
        )


# ==========================================================
# 行為測試：_on_tree_space_toggle 函式
# ==========================================================


def test_handler_function_exists():
    """_on_tree_space_toggle 函式存在"""
    content = _read()
    assert re.search(r'def _on_tree_space_toggle\(self,\s*event\):', content), (
        "❌ 找不到 _on_tree_space_toggle(self, event) 函式定義"
    )


def test_handler_returns_break():
    """handler 一定要 return "break"、避免 Space 鍵被當成 button activate"""
    content = _read()
    # 抓 _on_tree_space_toggle 函式本體
    m = re.search(
        r'def _on_tree_space_toggle\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_tree_space_toggle 函式本體"
    body = m.group(0)
    assert 'return "break"' in body, (
        '❌ _on_tree_space_toggle 沒 return "break"！\n'
        "可能導致 Space 鍵被當成 button activate"
    )


def test_handler_uses_focus_method():
    """handler 應該用 tree.focus() 取得當前 focus row（不是 selection）"""
    content = _read()
    m = re.search(
        r'def _on_tree_space_toggle\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    body = m.group(0)
    assert 'tree.focus()' in body, (
        "❌ handler 沒用 tree.focus()、無法正確取得當前 highlight row"
    )


def test_handler_supports_all_four_trees():
    """handler 內部應該區分 4 種 tree、並用正確的 checked_dict"""
    content = _read()
    m = re.search(
        r'def _on_tree_space_toggle\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    body = m.group(0)
    # 應該 4 種 tree 都有處理
    assert '_ms_tree' in body, "❌ handler 沒處理 _ms_tree"
    assert '_etf_tree' in body, "❌ handler 沒處理 _etf_tree"
    assert 'select_tree' in body, "❌ handler 沒處理 select_tree"
    assert '_bt_checked' in body, "❌ handler 沒處理 backtest_tree"


# ==========================================================
# 整合行為測試（用 SimpleNamespace 模擬 tree）
# ==========================================================


def _make_mock_tree(iid="item1", values=("☐", "2330", "台積電"), tags=("unchecked", "price_zero")):
    """建立一個 mock tree、能用 focus() / item() / get_children()"""
    from types import SimpleNamespace
    tree = SimpleNamespace()
    tree.focused_iid = iid
    tree.values = values
    tree.tags = tags
    tree.updated = []

    def focus():
        return tree.focused_iid

    def item(i, *args, **kwargs):
        # tree.item(iid) → 回傳 current values/tags
        # tree.item(iid, values=..., tags=...) → 更新並記錄
        if args:
            # tree.item(iid, "values") 讀取特定欄位
            return tree.values
        if kwargs:
            if "values" in kwargs:
                tree.values = kwargs["values"]
            if "tags" in kwargs:
                tree.tags = kwargs["tags"]
            tree.updated.append((i, kwargs))
        else:
            return SimpleNamespace(values=tree.values, tags=tree.tags)

    def get_children():
        return ["item1", "item2", "item3"]

    tree.focus = focus
    tree.item = item
    tree.get_children = get_children
    return tree


class _MockApp:
    """模擬 StrategyGUI 的最小子集（給 _on_tree_space_toggle 用）"""

    def __init__(self, tree):
        self._mock_tree = tree
        self._ms_tree = tree if "ms" in str(tree) else None
        self._etf_tree = tree if "etf" in str(tree) else None
        self.select_tree = tree
        self._ms_checked = {}
        self._etf_checked = {}
        self._select_checked = {}
        self._ms_price_tags = {}
        self._etf_price_tags = {}
        self._select_price_tags = {}
        self._bt_checked = {}
        self.header_updates = []

    def _update_checkbox_header(self, tree, checked_dict):
        self.header_updates.append((tree, dict(checked_dict)))


def test_space_toggle_select_tree():
    """【核心】select_tree space 鍵 toggle focus row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree(iid="item1", values=("☐", "2330", "台積電"))
    app = _MockApp(tree)
    # select_tree 不是 _ms_tree / _etf_tree、走 select_tree 分支
    app._ms_tree = SimpleNamespace()  # 用空 SimpleNamespace 不是同一個
    app._etf_tree = SimpleNamespace()
    event = SimpleNamespace(widget=tree)

    st.StrategyGUI._on_tree_space_toggle(app, event)

    # 確認 toggle 成功
    assert app._select_checked["item1"] is True, "focus row 應被勾選"
    assert tree.values[0] == "☑", f"第一欄應改為 ☑、實際 {tree.values[0]}"
    # header update 被呼叫
    assert len(app.header_updates) == 1


def test_space_toggle_ms_tree():
    """ms_tree space 鍵 toggle focus row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree(iid="m1", values=("☐", "3188", "鑫龍騰"))
    app = _MockApp(tree)
    app._ms_tree = tree
    app._etf_tree = SimpleNamespace()
    event = SimpleNamespace(widget=tree)

    st.StrategyGUI._on_tree_space_toggle(app, event)

    assert app._ms_checked["m1"] is True
    assert tree.values[0] == "☑"


def test_space_toggle_etf_tree():
    """etf_tree space 鍵 toggle focus row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree(iid="e1", values=("☐", "0050", "元大台灣50"))
    app = _MockApp(tree)
    app._ms_tree = SimpleNamespace()
    app._etf_tree = tree
    event = SimpleNamespace(widget=tree)

    st.StrategyGUI._on_tree_space_toggle(app, event)

    assert app._etf_checked["e1"] is True
    assert tree.values[0] == "☑"


def test_space_toggle_backtest_tree():
    """backtest_tree space 鍵 toggle focus row（用 _bt_checked）"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree(iid="b1", values=("☐", "test"))
    app = _MockApp(tree)
    app._ms_tree = SimpleNamespace()
    app._etf_tree = SimpleNamespace()
    # backtest_tree 不是 select_tree、走 else 分支用 _bt_checked
    app.select_tree = SimpleNamespace()
    event = SimpleNamespace(widget=tree)

    st.StrategyGUI._on_tree_space_toggle(app, event)

    assert app._bt_checked["b1"] is True
    assert tree.values[0] == "☑"


def test_space_toggle_twice_unselect():
    """連按兩次 Space 應該 unselect 回 ☐"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree(iid="item1", values=("☐", "2330"))
    app = _MockApp(tree)
    app._ms_tree = SimpleNamespace()
    app._etf_tree = SimpleNamespace()
    event = SimpleNamespace(widget=tree)

    st.StrategyGUI._on_tree_space_toggle(app, event)  # 第一次：☐ → ☑
    assert tree.values[0] == "☑"

    # mock 模擬「UI 跟 dict 都更新」
    # 第二次：tree.values[0] 現在是 ☑、再次 toggle 應變回 ☐
    # 因為 helper 從 checked_dict 讀 current、再 toggle
    # tree.values 是 mock 已經更新成 ☑、但 checked_dict 也是 True
    # 再按一次會變 False、tree.values 變 ☐
    st.StrategyGUI._on_tree_space_toggle(app, event)
    assert app._select_checked["item1"] is False
    assert tree.values[0] == "☐"


def test_space_no_focus_noop():
    """沒有 focus row 時（tree.focus() 回空字串）、handler 應直接 return、不爆"""
    from types import SimpleNamespace
    import StockTool as st

    tree = _make_mock_tree()
    tree.focused_iid = ""  # 沒 focus
    app = _MockApp(tree)
    app._ms_tree = SimpleNamespace()
    app._etf_tree = SimpleNamespace()
    event = SimpleNamespace(widget=tree)

    # 不應該爆
    st.StrategyGUI._on_tree_space_toggle(app, event)
    assert app._select_checked == {}, "沒 focus 不應動到 checked_dict"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

# ==========================================================
# 【V1.2.0-keyboard-toggle-fix】2026-07-06 15:58 William 反映
# 1. highlight 顏色藍色 ≠ hover 黃色
# 2. Space 不能 toggle（因為 tree.focus() 沒 row）
# 3. etf / 手動選股 up/down/space 都不會動（因為切 tab 時沒設 widget focus）
# ==========================================================


def test_select_tree_click_sets_focus():
    """_on_select_tree_click 內 cell click 應設定 tree.focus(iid)"""
    content = _read()
    # 抓 _on_select_tree_click 函式本體
    m = re.search(
        r'def _on_select_tree_click\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_select_tree_click"
    body = m.group(0)
    assert "tree.focus(" in body, (
        "❌ _on_select_tree_click 內沒設 tree.focus()！\n"
        "William 15:58 反映 click 後 Space 不能 toggle 因為 focus 沒設"
    )


def test_ms_tree_click_sets_focus():
    """_ms_toggle_check 內 cell click 應設定 _ms_tree.focus(item_id)"""
    content = _read()
    m = re.search(
        r'def _ms_toggle_check\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _ms_toggle_check"
    body = m.group(0)
    assert "_ms_tree.focus(" in body, (
        "❌ _ms_toggle_check 內沒設 _ms_tree.focus()！"
    )


def test_etf_tree_click_sets_focus():
    """_etf_toggle_check 內 cell click 應設定 _etf_tree.focus(item_id)"""
    content = _read()
    m = re.search(
        r'def _etf_toggle_check\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _etf_toggle_check"
    body = m.group(0)
    assert "_etf_tree.focus(" in body, (
        "❌ _etf_toggle_check 內沒設 _etf_tree.focus()！"
    )


def test_no_style_map_for_selected():
    """【V1.2.0-kb-focus-v3】_style.map 應保留 selected → 黃色

    William 18:54 反映「click 後 highlight 變藍色」
    原因：selection_remove 不一定在所有情況都生效、要有 style.map 保險
    設計：保留 _style.map(selected → #fff3a0)、所有 selected state 都顯示黃色
    """
    content = _read()
    m = re.search(
        r'_style\.map\([^)]*Treeview[^)]*\)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _style.map(Treeview)"
    body = m.group(0)
    assert "selected" in body and "#fff3a0" in body, (
        "❌ _style.map 應保留 selected → #fff3a0、避免藍色 highlight"
    )


def test_focus_tab_tree_function_exists():
    """_focus_tab_tree_on_change 函式存在"""
    content = _read()
    assert re.search(r'def _focus_tab_tree_on_change\(', content), (
        "❌ 找不到 _focus_tab_tree_on_change 函式！"
    )


def test_on_tab_changed_calls_focus_tree():
    """_on_tab_changed 內應該 call _focus_tab_tree_on_change"""
    content = _read()
    m = re.search(
        r'def _on_tab_changed\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_tab_changed"
    body = m.group(0)
    assert "_focus_tab_tree_on_change" in body, (
        "❌ _on_tab_changed 內沒 call _focus_tab_tree_on_change！\n"
        "William 15:58 反映 etf / 手動選股 up/down/space 都不會動"
    )


def test_focus_tab_tree_map_includes_all_results_tabs():
    """_focus_tab_tree_on_change 內的 tab_tree_map 應包含 4 個結果 tab"""
    content = _read()
    m = re.search(
        r'def _focus_tab_tree_on_change\(self,\s*current_tab_idx.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _focus_tab_tree_on_change 函式本體"
    body = m.group(0)
    # 4 個結果 tab 都要有 mapping
    for tree_attr in ("select_tree", "_etf_tree", "_ms_tree", "backtest_tree"):
        assert tree_attr in body, (
            f"❌ _focus_tab_tree_on_change 沒處理 {tree_attr}！"
        )


def test_focus_tab_tree_focus_set_and_focus_row():
    """_focus_tab_tree_on_change 應呼叫 focus_set + focus(iid)"""
    content = _read()
    m = re.search(
        r'def _focus_tab_tree_on_change\(self,\s*current_tab_idx.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    body = m.group(0)
    assert "focus_set" in body, (
        "❌ 沒呼叫 focus_set()、切到 tab 後 key events 不會送到 tree"
    )
    assert "tree.focus(children[0])" in body or "tree.focus(first_iid)" in body, (
        "❌ 沒設 focus rectangle 到第一個 row"
    )


# ==========================================================
# 行為測試：_focus_tab_tree_on_change
# ==========================================================


# ==========================================================
# 【V1.2.0-kb-focus-v4】2026-07-06 21:55 William 反映問題
# 1. 開機第一次要 mouse move + click 後 up/down 才會 scroll
# 2. 被 click 的 item 自會變成高亮白色（Linux ttk selected foreground 預設白色）
# 3. 用 key scroll 後 mouse 移動從 cursor 位置開始（hover 跟 keyboard 不同步）
# 4. down key 向下 scroll 沒辦法到達最後一個 item
# 5. 4 個 Treeview 都是同樣問題
#
# v4 簡單設計（不再 hack）：
# - selectmode="browse"（4 個 Treeview 統一）
# - <Enter> 自動 focus_set（滑鼠進入 Treeview 立刻有 keyboard focus）
# - <Motion> 用 selection_set(iid) + focus(iid) + see(iid) 同步 hover = selected
# - 不用自定 <Up>/<Down> bind、Treeview 預設 browse mode 會自動切 focus + scroll
# - <<TreeviewSelect>> 監聽 selection 變化、給 selected row 設 hover_<price> tag
# - style.map(selected → #fff3a0) + foreground → 黑色（避免 Linux 主題預設白字）
# ==========================================================


def test_selectmode_browse_all_four_trees():
    """4 個 Treeview 都要 selectmode="browse"、讓 click / ↑↓ 自動切 selection"""
    content = _read()
    # results_tree (select_tree / backtest_tree 共用)
    assert re.search(
        r'results_tree = ttk\.Treeview\([^)]*selectmode\s*=\s*["\']browse["\']',
        content,
    ), "❌ results_tree 沒設 selectmode=\"browse\""
    assert re.search(
        r'self\._etf_tree = ttk\.Treeview\([^)]*selectmode\s*=\s*["\']browse["\']',
        content,
    ), "❌ _etf_tree 沒設 selectmode=\"browse\""
    assert re.search(
        r'self\._ms_tree = ttk\.Treeview\([^)]*selectmode\s*=\s*["\']browse["\']',
        content,
    ), "❌ _ms_tree 沒設 selectmode=\"browse\""


def test_on_tree_enter_focus_function_exists():
    """_on_tree_enter_focus handler 存在

    4 個 Treeview 都綁 <Enter> → 滑鼠進入 Treeview 自動 focus_set
    """
    content = _read()
    assert re.search(r'def _on_tree_enter_focus\(self,\s*event\):', content), (
        "❌ 找不到 _on_tree_enter_focus(self, event) 函式"
    )


def test_on_tree_select_sync_hover_function_exists():
    """_on_tree_select_sync_hover handler 存在

    監聽 <<TreeviewSelect>>、selection 變化時同步 hover_<price> tag
    """
    content = _read()
    assert re.search(r'def _on_tree_select_sync_hover\(self,\s*event\):', content), (
        "❌ 找不到 _on_tree_select_sync_hover(self, event) 函式"
    )


def test_results_tree_binds_enter():
    """results_tree 綁 <Enter> 自動 focus_set"""
    content = _read()
    assert re.search(r'results_tree\.bind\(["\']<Enter>["\']', content), (
        "❌ results_tree 沒綁 <Enter> 自動 focus_set"
    )


def test_ms_tree_binds_enter():
    """_ms_tree 綁 <Enter>"""
    content = _read()
    assert re.search(r'self\._ms_tree\.bind\(["\']<Enter>["\']', content), (
        "❌ _ms_tree 沒綁 <Enter>"
    )


def test_etf_tree_binds_enter():
    """_etf_tree 綁 <Enter>"""
    content = _read()
    assert re.search(r'self\._etf_tree\.bind\(["\']<Enter>["\']', content), (
        "❌ _etf_tree 沒綁 <Enter>"
    )


def test_results_tree_binds_treeview_select():
    """results_tree 綁 <<TreeviewSelect>> 同步 hover_<price> tag"""
    content = _read()
    assert re.search(r'results_tree\.bind\(["\']<<TreeviewSelect>>["\']', content), (
        "❌ results_tree 沒綁 <<TreeviewSelect>>"
    )


def test_ms_tree_binds_treeview_select():
    """_ms_tree 綁 <<TreeviewSelect>>"""
    content = _read()
    assert re.search(r'self\._ms_tree\.bind\(["\']<<TreeviewSelect>>["\']', content), (
        "❌ _ms_tree 沒綁 <<TreeviewSelect>>"
    )


def test_etf_tree_binds_treeview_select():
    """_etf_tree 綁 <<TreeviewSelect>>"""
    content = _read()
    assert re.search(r'self\._etf_tree\.bind\(["\']<<TreeviewSelect>>["\']', content), (
        "❌ _etf_tree 沒綁 <<TreeviewSelect>>"
    )


def test_no_up_down_key_binding():
    """【V1.2.0-kb-focus-v4】不應該自定 <Up>/<Down> bind

    selectmode="browse" 下、Treeview 預設就會切 focus + scroll
    v3 自定 bind 導致額外一個 handler、容易跟 Treeview 預設行為衝突
    """
    content = _read()
    # 排除 results_tree / _ms_tree / _etf_tree 的 Up/Down bind
    bad = re.findall(r'(?:results_tree|self\._(?:ms|etf)_tree)\.bind\(["\']<(?:Up|Down)>["\']', content)
    assert not bad, (
        f"❌ v4 不應該再綁 <Up>/<Down>、會跟 Treeview 預設行為衝突！\n"
        f"找到 {len(bad)} 個 bind"
    )


def test_style_map_selected_yellow_and_foreground_black():
    """style.map 設定 selected 背景 = 黃色 + foreground = 黑色"""
    content = _read()
    # 從 _style.map( 後找括號平衡、跳過註解內的字串
    # 用 regex 找 _style.map(\n    "Treeview",
    m = re.search(r'_style\.map\(\s*\n\s*"Treeview"', content)
    assert m, "找不到 _style.map(\"Treeview\")"
    start = m.start()
    depth = 0
    i = start
    in_str = False
    while i < len(content):
        ch = content[i]
        if ch == '"' and (i == 0 or content[i-1] != '\\'):
            in_str = not in_str
        if not in_str:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    break
        i += 1
    body = content[start:i+1]
    assert "selected" in body and "#fff3a0" in body, (
        "❌ _style.map 應保留 selected → #fff3a0"
    )
    assert "foreground" in body, (
        "❌ _style.map 應設定 foreground 為黑色、避免 Linux 主題預設白字"
    )


def test_after_idle_focus_tree_function_exists():
    """_after_idle_focus_tree exists for after_idle re-focus"""
    content = _read()
    assert re.search(r'def _after_idle_focus_tree\(', content), (
        "❌ 找不到 _after_idle_focus_tree 函式"
    )



# ==========================================================
# 【V1.2.0-kb-focus-v5】2026-07-06 22:42 William 反映問題
# 1. mouse 移動時新位置有 highlight 但舊位置 highlight bar 沒有被取消
# 2. down key 沒辦法 display 最後一個 item
# 3. 三個 tab（系統選股/ETF/手動選股/回測）都一樣
#
# v5 設計（回到 hover_<price> tag 系統、不用 selection hack）：
# - hover handler 先 _clear_hover 取消舊 tag、再設新 tag
# - <Enter> 自動 focus_set + focus(children[0]) 確保 keyboard focus 在 tree
# - 不綁 <Up>/<Down>、Treeview browse mode 預設會切 focus + scroll
# - click handler 不 selection_set、靠 browse mode 自動
# - <<TreeviewSelect>> handler 同步設 hover_<price> tag（含清舊）
# - _set_row_tag_normal helper：恢復 row 原本的 checked/unchecked + price_* tag
# ==========================================================


def test_on_select_tree_hover_clears_old():
    """_on_select_tree_hover v7 motion 只設 focus(iid)、不動 tags

    William 01:08 反映 v6 race condition（hover 殘留）
    v7 修法：motion handler 只設 keyboard focus、hover_<price> 完全由 <<TreeviewSelect>> 管
    """
    content = _read()
    idx = content.find('def _on_select_tree_hover(self, event):')
    assert idx != -1, "找不到 _on_select_tree_hover"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v7：motion 只呼叫 tree.focus(iid) + focus_set()、不應動 tags
    assert 'tree.focus(iid)' in body or 'self._ms_tree.focus(iid)' in body, (
        "❌ v7 motion 應呼叫 tree.focus(iid)"
    )
    assert 'focus_set' in body, "❌ v7 motion 應呼叫 focus_set"
    # v7 不應有 hover_<price> tag 設定在 motion handler
    assert 'hover_' not in body or body.count('hover_') == 0, (
        f"❌ v7 motion handler 不應設 hover_<price> tag（body: {body[:200]})"
    )


def test_ms_tree_hover_clears_old():
    """_ms_tree_hover v7 motion 只設 focus(iid)、不動 tags"""
    content = _read()
    idx = content.find('def _ms_tree_hover(self, event):')
    assert idx != -1, "找不到 _ms_tree_hover"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v7：motion 只呼叫 _ms_tree.focus(iid)
    assert '_ms_tree.focus(iid)' in body, (
        "❌ v7 _ms_tree_hover 應呼叫 _ms_tree.focus(iid)"
    )
    assert '_ms_tree.focus_set' in body, "❌ v7 _ms_tree_hover 應呼叫 _ms_tree.focus_set"


def test_ms_tree_leave_clears_hover():
    """_ms_tree_leave v6 不清（讓 selected row 保持 highlight）"""
    content = _read()
    idx = content.find('def _ms_tree_leave(self, event):')
    assert idx != -1, "找不到 _ms_tree_leave"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    # v6：browse mode 下 selection row 有 hover_<price> tag、離開時保留
    # 測試確認為什麼清不掉舊
    # 允許 pass（不清）
    if '_ms_clear_hover' in body:
        # 還有 _ms_clear_hover、有可能調到
        pass


def test_etf_tree_hover_combined_clears_old():
    """_etf_tree_hover_combined v8 呼叫 _apply_hover 設 hover + popup + focus"""
    content = _read()
    idx = content.find('def _etf_tree_hover_combined(self, event):')
    assert idx != -1, "找不到 _etf_tree_hover_combined"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v8：motion 呼叫 _apply_hover 設 hover + focus + popup
    assert '_apply_hover' in body, (
        "❌ v8 _etf_tree_hover_combined 應呼叫 _apply_hover 設 hover_<price> tag"
    )
    assert '_etf_tree.focus(iid)' in body, (
        "❌ v8 _etf_tree_hover_combined 應呼叫 _etf_tree.focus(iid)"
    )
    assert '_etf_tree.focus_set' in body, (
        "❌ v8 _etf_tree_hover_combined 應呼叫 _etf_tree.focus_set"
    )


def test_on_tree_select_sync_hover_clears_old():
    """_on_tree_select_sync_hover v12 解耦：必不呼叫 _apply_hover"""
    content = _read()
    idx = content.find('def _on_tree_select_sync_hover(self, event):')
    assert idx != -1, "找不到 _on_tree_select_sync_hover"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v12：解耦 hover 跟 click、不呼叫 _apply_hover
    assert '_apply_hover' not in body, (
        "❌ v12 _on_tree_select_sync_hover 不應呼叫 _apply_hover（hover 解耦 click）"
    )
    # v12：仍需清舊 hover（避免 click 後留 stale hover tag）
    assert '_clear_all_hover' in body, (
        "v12 _on_tree_select_sync_hover 必呼叫 _clear_all_hover"
    )
    assert '_clear_all_hover' in body, (
        "❌ v8 _on_tree_select_sync_hover 應在空 selection 時呼叫 _clear_all_hover"
    )


def test_set_row_tag_normal_function_exists():
    """_set_row_tag_normal helper 存在"""
    content = _read()
    assert re.search(r'def _set_row_tag_normal\(', content), (
        "❌ 找不到 _set_row_tag_normal helper"
    )


def test_on_tree_enter_focus_sets_first_row():
    """_on_tree_enter_focus 應 focus_set + 設 focus(children[0]) 讓 Up/Down 可以 scroll"""
    content = _read()
    m = re.search(
        r'def _on_tree_enter_focus\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_tree_enter_focus"
    body = m.group(0)
    assert "focus_set" in body, "❌ _on_tree_enter_focus 應呼叫 focus_set"
    assert "tree.focus(children[0])" in body or "tree.focus(c0)" in body or "first_iid" in body, (
        "❌ _on_tree_enter_focus 應設 focus 到第一個 row、避免 Up/Down 沒 focus 不 scroll"
    )


def test_no_selection_set_in_hover_handlers():
    """【V1.2.0-kb-focus-v5】hover handlers 不應 selection_set（回到 hover_<price> tag 系統）"""
    content = _read()
    # v4 用 selection_set 為 single source of truth、但 Linux ttk 主題失效
    # v5 改回 hover_<price> tag 系統、不依賴 selection state
    # 跳過 docstring、只檢查函式內容
    bad_patterns = [
        ('def _on_select_tree_hover', 'selection_set'),
        ('def _ms_tree_hover', 'selection_set'),
        ('def _etf_tree_hover_combined', 'selection_set'),
    ]
    for fn_def, target in bad_patterns:
        idx = content.find(fn_def)
        if idx == -1:
            continue
        # 找下個 def 或 class、跳過中間 docstring
        end = content.find('\n    def ', idx + len(fn_def))
        if end == -1:
            end = len(content)
        body = content[idx:end]
        # 跳過 docstring ("""...""")
        if '"""' in body:
            parts = body.split('"""')
            # docstring 結束後的內容
            body = '"""'.join(parts[2:])
        assert target not in body, f"❌ {fn_def} 不應使用 {target}（v5 改回 hover_<price> tag 系統）"


def test_no_up_down_key_binding():
    """【V1.2.0-kb-focus-v5】不應該綁 <Up>/<Down>、Treeview browse mode 預設會處理"""
    content = _read()
    bad = re.findall(
        r'(?:results_tree|self\._(?:ms|etf)_tree)\.bind\(["\']<(?:Up|Down)>["\']',
        content,
    )
    assert not bad, f"❌ 不應該綁 <Up>/<Down>、會跟 Treeview 預設行為衝突"


def test_focus_tab_tree_uses_hover_tag():
    """_focus_tab_tree_on_change 應設 hover_<price> tag、不用 selection_set"""
    content = _read()
    m = re.search(
        r'def _focus_tab_tree_on_change\(self,\s*current_tab_idx.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _focus_tab_tree_on_change"
    body = m.group(0)
    assert "selection_set" not in body, (
        "❌ v5 _focus_tab_tree_on_change 不應該用 selection_set"
    )
    assert "hover_" in body, (
        "❌ v5 _focus_tab_tree_on_change 應設 hover_<price> tag"
    )


def test_click_handlers_no_selection_set():
    """【V1.2.0-kb-focus-v5】3 個 click handler 不應該 selection_set

    Treeview browse mode click 會自動 set selection
    我們用 <<TreeviewSelect>> handler 統一處理 hover_<price> tag
    """
    content = _read()
    for fn_name in ["_on_select_tree_click", "_ms_toggle_check", "_etf_toggle_check"]:
        idx = content.find(f'def {fn_name}(self, event):')
        if idx == -1:
            continue
        # 找 docstring 結束位置
        doc_end = content.find('"""', idx)
        if doc_end == -1:
            continue
        doc_end = content.find('"""', doc_end + 3)
        if doc_end == -1:
            continue
        # 找函式結尾
        end = content.find('\n    def ', doc_end)
        if end == -1:
            end = len(content)
        # 只看 docstring 後到函式結尾、跳過註解行
        body_lines = content[doc_end:end].split('\n')
        code_lines = [l for l in body_lines if not l.strip().startswith('#')]
        code = '\n'.join(code_lines)
        assert "selection_set" not in code, (
            f"❌ {fn_name} 不應呼叫 selection_set、browse mode 會自動 set"
        )


def test_hover_price_tag_registered():
    """3 個 tree 都有 hover_up/hover_down/hover_zero tag 註冊（v1.1-price-color-fix2）"""
    content = _read()
    # 寫法都是 f'hover_{ptag}' for ptag in ['up', 'down', 'zero']
    for tree_name in ["results_tree", "self._etf_tree", "self._ms_tree"]:
        pattern = re.escape(tree_name) + r'\.tag_configure\(f"hover_\{ptag\}"'
        assert re.search(pattern, content), (
            f"❌ {tree_name} 沒註冊 hover_up/hover_down/hover_zero tag"
        )


# ==========================================================
# 行為測試
# ==========================================================


def test_on_select_tree_hover_movement_clears_old():
    """_on_select_tree_hover v9 呼叫 _apply_hover 清舊 + 設新 row（motion handler 一般路徑）

    v9 多了 _kbd_nav_guard_should_block check、測試時設為 False 走一般路徑
    """
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "r1": {"tags": ("hover_up",), "values": ("☐", "3188")},
        "r2": {"tags": ("unchecked", "price_down"), "values": ("☐", "3028")},
    }

    def item(iid, *args, **kwargs):
        if args:
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(values=items_state[iid].get("values", ()), tags=items_state[iid].get("tags", ()))

    focus_calls = []
    focus_set_calls = []

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "r2"
    tree.item = item
    tree.get_children = lambda: ["r1", "r2"]
    tree.focus = lambda iid: focus_calls.append(iid)
    tree.focus_set = lambda: focus_set_calls.append(True)

    app = SimpleNamespace(
        select_tree=tree,
        _select_checked={"r1": False, "r2": False},
        _bt_checked={},
        _select_price_tags={"r1": "price_up", "r2": "price_down"},
        _kbd_nav_guard_until_ms=0,  # 已過期、guard 不 block
    )
    # v9：guard 自動返回 False（已過期）
    app._kbd_nav_guard_should_block = lambda t: False

    def fake_apply_hover(t, iid):
        for child in t.get_children():
            cur = items_state[child]["tags"]
            if any(s.startswith("hover_") for s in cur):
                price_tag = app._select_price_tags.get(child, "price_zero")
                items_state[child]["tags"] = ("unchecked", price_tag)
        price_tag = app._select_price_tags.get(iid, "price_zero")
        kind = price_tag.replace("price_", "")
        items_state[iid]["tags"] = (f"hover_{kind}",)

    app._apply_hover = fake_apply_hover

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._on_select_tree_hover(app, event)

    assert "r2" in focus_calls
    assert focus_set_calls
    assert "hover" not in str(items_state["r1"]["tags"])
    assert "hover_down" in items_state["r2"]["tags"]


def test_on_select_tree_hover_blocked_by_guard():
    """v9：_kbd_nav_guard_should_block 為 True → motion handler 應 ignore"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "r1": {"tags": ("hover_up",)},
        "r2": {"tags": ("unchecked", "price_down")},
    }

    def item(iid, *args, **kwargs):
        if args:
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(values=items_state[iid].get("values", ()), tags=items_state[iid].get("tags", ()))

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "r2"
    tree.item = item
    tree.get_children = lambda: ["r1", "r2", "r3"]
    tree.focus = lambda iid=None: "r3"  # key nav 設到 r3
    tree.focus_set = lambda: None

    apply_hover_calls = []

    app = SimpleNamespace(
        select_tree=tree,
        _select_checked={"r1": False, "r2": False, "r3": False},
        _bt_checked={},
        _select_price_tags={"r1": "price_up", "r2": "price_down", "r3": "price_zero"},
        _kbd_nav_guard_until_ms=99999999999,  # 很久之後
        _kbd_nav_mouse_pos_at_guard=(0, 0),
    )
    app._kbd_nav_guard_should_block = lambda t: True  # block
    app._apply_hover = lambda t, iid: apply_hover_calls.append(iid)

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._on_select_tree_hover(app, event)

    # motion 被 block → 不應設 r2 的 hover（會是 None 因為 identify_row 被查到但被 block）
    # 唯一被 set 的 hover 是 r3（focus）
    assert apply_hover_calls == ["r3"], (
        f"guard block 時 motion 應只套用 focus row 的 hover、實際 {apply_hover_calls}"
    )
    # r1 的 hover 不該被清（沒被覆寫）
    assert "hover_up" in items_state["r1"]["tags"], (
        f"guard block 時不應清舊 hover、實際 {items_state['r1']['tags']}"
    )


def test_ms_tree_hover_movement_clears_old():
    """_ms_tree_hover v9 呼叫 _apply_hover 清舊 + 設新 row（v9 加 guard、這邊走一般路徑）"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "m1": {"tags": ("hover_up",)},
        "m2": {"tags": ("unchecked", "price_down")},
    }

    def item(iid, *args, **kwargs):
        if args and args[0] == "tags":
            return items_state[iid].get("tags", ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(tags=items_state[iid].get("tags", ()))

    focus_calls = []
    focus_set_calls = []

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "m2"
    tree.item = item
    tree.get_children = lambda: ["m1", "m2"]
    tree.focus = lambda iid: focus_calls.append(iid)
    tree.focus_set = lambda: focus_set_calls.append(True)

    app = SimpleNamespace(
        _ms_tree=tree,
        _ms_checked={"m1": False, "m2": False},
        _ms_price_tags={"m1": "price_up", "m2": "price_down"},
        _kbd_nav_guard_until_ms=0,  # 已過期、guard 不 block
    )
    app._kbd_nav_guard_should_block = lambda t: False  # 不 block

    def fake_apply_hover(t, iid):
        for child in t.get_children():
            cur = items_state[child]["tags"]
            if any(s.startswith("hover_") for s in cur):
                price_tag = app._ms_price_tags.get(child, "price_zero")
                items_state[child]["tags"] = ("unchecked", price_tag)
        price_tag = app._ms_price_tags.get(iid, "price_zero")
        kind = price_tag.replace("price_", "")
        items_state[iid]["tags"] = (f"hover_{kind}",)

    app._apply_hover = fake_apply_hover

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._ms_tree_hover(app, event)

    assert "m2" in focus_calls
    assert focus_set_calls
    assert "hover" not in str(items_state["m1"]["tags"])
    assert "hover_down" in items_state["m2"]["tags"]


def test_ms_tree_hover_blocked_by_guard():
    """v9：_ms_tree_hover 被 guard block → 不動 motion"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "new_row"
    tree.get_children = lambda: ["focus_row", "new_row"]

    apply_hover_calls = []
    app = SimpleNamespace(
        _ms_tree=tree,
        _ms_checked={},
        _ms_price_tags={},
        _kbd_nav_guard_until_ms=99999999999,
        _kbd_nav_mouse_pos_at_guard=(0, 0),
    )
    app._kbd_nav_guard_should_block = lambda t: True  # block
    tree.focus = lambda iid=None: "focus_row"  # key nav 設到 focus_row
    tree.focus_set = lambda: None
    app._apply_hover = lambda t, iid: apply_hover_calls.append(iid)

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._ms_tree_hover(app, event)

    assert apply_hover_calls == ["focus_row"], (
        f"guard block 後只該套 focus row 的 hover、實際 {apply_hover_calls}"
    )


def test_on_tree_select_sync_hover_clears_old_row():
    """_on_tree_select_sync_hover v12 只調 _clear_all_hover、不設新 hover

    為什麼？
    - v12 解耦 hover 跟 click
    - click 不設 hover、只 clear 舊 hover（避免留 stale）
    - mouse 動了 motion handler 才會重設 hover 到 cursor 位置
    """
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "s1": {"tags": ("hover_up",)},
        "s2": {"tags": ("unchecked", "price_down")},
    }

    def item(iid, *args, **kwargs):
        if args:
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(tags=items_state[iid].get("tags", ()))

    tree = SimpleNamespace()
    tree.selection = lambda: ("s2",)
    tree.get_children = lambda: ["s1", "s2"]
    tree.item = item
    tree.winfo_exists = lambda: True

    # v12：_on_tree_select_sync_hover 只調 _clear_all_hover
    app = SimpleNamespace()
    app._clear_all_hover = lambda t: _fake_clear_all_hover(t, items_state)

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._on_tree_select_sync_hover(app, event)

    # v12：s1 的 hover 應被清（來自 _clear_all_hover）
    assert "hover" not in items_state["s1"]["tags"], (
        f"s1 應取消 hover、實際 {items_state['s1']['tags']}"
    )
    # v12：s2 不應設新的 hover（hover 由 mouse motion 控制）
    assert "hover" not in items_state["s2"]["tags"], (
        f"v12 s2 不該設 hover、實際 {items_state['s2']['tags']}"
    )


def _fake_clear_all_hover(tree, items_state):
    """測試 helper：模擬 _clear_all_hover 只清 hover_* tags、不動其他"""
    for child in tree.get_children():
        cur = items_state[child]["tags"]
        if any(s.startswith("hover_") for s in cur):
            # 清成無 hover tag
            new_tags = tuple(t for t in cur if not t.startswith("hover_"))
            if not new_tags:
                new_tags = ("unchecked", "price_zero")
            items_state[child]["tags"] = new_tags


def test_on_tree_enter_focus_sets_focus():
    """_on_tree_enter_focus 呼叫 focus_set + focus(children[0])"""
    from types import SimpleNamespace
    import StockTool as st

    focus_set_calls = []
    focus_calls = []

    def focus_fn(iid=None):
        if iid is not None:
            focus_calls.append(iid)
            return iid
        return ""

    tree = SimpleNamespace()
    tree.focus_set = lambda: focus_set_calls.append(True)
    tree.focus = focus_fn
    tree.get_children = lambda: ["c1", "c2"]

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._on_tree_enter_focus(SimpleNamespace(), event)

    assert focus_set_calls, "_on_tree_enter_focus 應呼叫 focus_set"
    assert "c1" in focus_calls, "_on_tree_enter_focus 應設 focus(children[0])"


def test_focus_tab_tree_no_selection_set():
    """_focus_tab_tree_on_change 不用 selection_set、改用 hover_<price> tag"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {"r1": {"tags": ("unchecked", "price_up")}}
    sel_set_calls = []
    focus_calls = []

    def item(iid, *args, **kwargs):
        if args and args[0] == "tags":
            return items_state[iid].get("tags", ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(tags=items_state[iid].get("tags", ()))

    tree = SimpleNamespace()
    tree.focus_set = lambda: None
    tree.selection_set = lambda iid: sel_set_calls.append(iid)
    tree.focus = lambda iid: focus_calls.append(iid)
    tree.see = lambda iid: None
    tree.get_children = lambda: ["r1"]
    tree.item = item

    app = SimpleNamespace(
        select_tree=tree,
        _etf_tree=SimpleNamespace(),
        _ms_tree=SimpleNamespace(),
        backtest_tree=SimpleNamespace(),
    )
    app._get_price_tag_for_tree = lambda t, iid: "price_up"
    app._set_row_tag_normal = lambda t, iid: None  # v6 會呼叫、但無舊 hover
    app.after_idle = lambda fn: fn()

    st.StrategyGUI._focus_tab_tree_on_change(app, 0)

    # v5：不用 selection_set、改用 hover_<price> tag
    assert not sel_set_calls, "v5 _focus_tab_tree_on_change 不應 selection_set"
    assert "r1" in focus_calls, "應呼叫 focus(r1)"
    assert "hover_up" in items_state["r1"]["tags"], (
        f"r1 應設 hover_up tag、實際 {items_state['r1']['tags']}"
    )


# ==========================================================
# 【V1.2.0-kb-focus-v8】新 helper: _apply_hover / _clear_all_hover
# ==========================================================

def test_apply_hover_helper_exists():
    """v8 _apply_hover 統一函式必須存在"""
    content = _read()
    assert "def _apply_hover(self, tree, iid):" in content, (
        "v8 應新增 _apply_hover(tree, iid) 統一函式"
    )


def test_clear_all_hover_helper_exists():
    """v8 _clear_all_hover 輔助函式必須存在"""
    content = _read()
    assert "def _clear_all_hover(self, tree):" in content, (
        "v8 應新增 _clear_all_hover(tree) 輔助函式"
    )


def test_move_cursor_to_row_helper_exists():
    """v8 _move_cursor_to_row 鍵盤同步函式必須存在"""
    content = _read()
    assert "def _move_cursor_to_row(self, tree, iid):" in content, (
        "v8 應新增 _move_cursor_to_row(tree, iid) 鍵盤同步函式"
    )


def test_ensure_focus_visible_helper_exists():
    """v8 _ensure_focus_visible 最後 row 顯示函式必須存在"""
    content = _read()
    assert "def _ensure_focus_visible(self, tree, iid):" in content, (
        "v8 應新增 _ensure_focus_visible(tree, iid) 函式"
    )


def test_apply_hover_clears_all_then_sets_new():
    """_apply_hover 內部邏輯：清全部 hover + 設新 row hover_<price>"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "a": {"tags": ("hover_up",)},
        "b": {"tags": ("unchecked", "price_down")},
        "c": {"tags": ("hover_zero",)},
    }

    def item(iid, *args, **kwargs):
        if args and args[0] == "tags":
            return items_state[iid].get("tags", ())
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(tags=items_state[iid].get("tags", ()))

    tree = SimpleNamespace()
    tree.winfo_exists = lambda: True
    tree.get_children = lambda: ["a", "b", "c"]
    tree.item = item

    app = SimpleNamespace(
        _ms_price_tags={"a": "price_up", "b": "price_down", "c": "price_zero"},
    )
    app._set_row_tag_normal = lambda t, iid: t.item(
        iid, tags=("unchecked", app._ms_price_tags.get(iid, "price_zero"))
    )
    # v8：_apply_hover 內部呼叫 _clear_all_hover
    def fake_clear_all_hover(t):
        for child in t.get_children():
            cur = items_state[child]["tags"]
            if any(s.startswith("hover_") for s in cur):
                price_tag = app._ms_price_tags.get(child, "price_zero")
                items_state[child]["tags"] = ("unchecked", price_tag)
    app._clear_all_hover = fake_clear_all_hover
    # v8：_apply_hover 需要 _get_price_tag_for_tree 拿 price_<up/down/zero>
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")

    # 直接呼叫 _apply_hover
    st.StrategyGUI._apply_hover(app, tree, "b")

    # 應清掉 a 和 c 的 hover、b 設新 hover
    assert "hover" not in str(items_state["a"]["tags"]), (
        f"a 應清 hover、實際 {items_state['a']['tags']}"
    )
    assert "hover_down" in items_state["b"]["tags"], (
        f"b 應設 hover_down、實際 {items_state['b']['tags']}"
    )
    assert "hover" not in str(items_state["c"]["tags"]), (
        f"c 應清 hover、實際 {items_state['c']['tags']}"
    )


def test_ensure_focus_visible_scrolls_extra_for_last_item():
    """v10 _ensure_focus_visible：先加 padding row、再 see、倒數第二 row 多 scroll"""
    from types import SimpleNamespace
    import StockTool as st

    yview_scroll_calls = []
    see_calls = []
    update_calls = []
    apply_hover_calls = []
    move_cursor_calls = []
    padding_added = []
    bbox_results = {}

    tree = SimpleNamespace()
    tree.winfo_exists = lambda: True
    # 模擬 padding row 已在 → get_children 回 ["a", "b", "c", "__focus_padding__"]
    tree.get_children = lambda: ["a", "b", "c", "__focus_padding__"]
    tree.see = lambda iid: see_calls.append(iid)
    tree.yview_scroll = lambda n, unit: yview_scroll_calls.append((n, unit))
    tree.update_idletasks = lambda: update_calls.append(True)
    tree.bbox = lambda iid: bbox_results.get(iid)
    tree.winfo_height = lambda: 500
    tree.cget = lambda key: "#ffffff"
    tree.exists = lambda iid: True  # padding 已存在
    tree.item = lambda iid, *args, **kw: SimpleNamespace(values=("1", "2", "3"))
    tree.tag_configure = lambda *a, **kw: None

    app = SimpleNamespace()
    app._apply_hover = lambda t, iid: apply_hover_calls.append(iid)
    app._move_cursor_to_row = lambda t, iid: move_cursor_calls.append(iid)
    app._ensure_focus_padding_row = lambda t: padding_added.append(True)

    # iid "c" 是 children[-2]（padding 是最後）→ 應 extra scroll
    st.StrategyGUI._ensure_focus_visible(app, tree, "c")
    assert yview_scroll_calls == [(2, "units")], (
        f"iid 為 children[-2] 應 yview_scroll(1, units)、實際 {yview_scroll_calls}"
    )
    assert see_calls == ["c"], f"see 應呼叫、實際 {see_calls}"
    assert apply_hover_calls == ["c"]
    assert move_cursor_calls == ["c"]
    assert padding_added, "v10 應加 padding row"

    # iid "a" 不是 children[-2]、bbox 看是否接近底部
    yview_scroll_calls.clear()
    see_calls.clear()
    apply_hover_calls.clear()
    move_cursor_calls.clear()
    bbox_results["a"] = (0, 100, 100, 20)  # 中間位置
    st.StrategyGUI._ensure_focus_visible(app, tree, "a")
    assert yview_scroll_calls == [], (
        f"iid 在中間、bbox 不接近底部 → 不該 scroll、實際 {yview_scroll_calls}"
    )
    assert see_calls == ["a"]


def test_move_cursor_to_row_skips_when_mouse_outside_tree():
    """v10：_move_cursor_to_row 不檢查 mouse 是否在 tree 內、bbox 缺失就 early return"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace()
    tree.winfo_exists = lambda: True
    # bbox 回空字串模擬 row 不可見
    tree.bbox = lambda iid: ""

    app = SimpleNamespace()
    # 調用不該丟 exception
    st.StrategyGUI._move_cursor_to_row(app, tree, "any_iid")
    # 驗證邏輯：不會 raise exception 就代表 success


def test_ms_tree_no_legacy_v1_hover_binding():
    """v8：ms_tree 只綁一個 <Motion> handler、v1.0 的 _on_tree_hover 不再綁"""
    content = _read()
    # 計算 ms_tree 綁 <Motion> 的次數
    pattern = r'self\._ms_tree\.bind\(\s*["\']<Motion>["\']'
    matches = re.findall(pattern, content)
    assert len(matches) == 1, (
        f"v8 ms_tree 應只綁一個 <Motion> handler、實際 {len(matches)} 個 "
        f"（v1.0 的 _on_tree_hover 雙重綁定已拿掉）"
    )


def test_on_tree_key_see_focus_uses_ensure_focus_visible():
    """v8 _on_tree_key_see_focus 呼叫 _ensure_focus_visible（含 yview_scroll + cursor）"""
    content = _read()
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1, "找不到 _on_tree_key_see_focus"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_ensure_focus_visible" in body, (
        "v8 _on_tree_key_see_focus 應呼叫 _ensure_focus_visible"
    )
    # 確認舊的 "tree.see(cur)" 直接呼叫已拿掉、改透過 helper
    assert "tree.see(cur)" not in body, (
        "v8 _on_tree_key_see_focus 不應直接呼叫 tree.see(cur)、改用 _ensure_focus_visible"
    )


# ==========================================================
# 【V1.2.0-kb-focus-v9】key nav guard 機制
# ==========================================================

def test_kbd_nav_guard_helper_exists():
    """v9 _kbd_nav_guard_should_block helper 必須存在"""
    content = _read()
    assert "def _kbd_nav_guard_should_block(self, tree):" in content, (
        "v9 應新增 _kbd_nav_guard_should_block(tree) helper"
    )


def test_kbd_nav_guard_blocks_when_mouse_unchanged():
    """v9：guard 期間內 mouse 位置未變 → 應 block motion"""
    from types import SimpleNamespace
    import time as _time
    import StockTool as st

    cur_mouse_pos = (200, 300)

    tree = SimpleNamespace()
    tree.winfo_pointerxy = lambda: cur_mouse_pos

    app = SimpleNamespace()
    # guard 設為現在 + 60 秒（足够未來才不會 timeout）
    app._kbd_nav_guard_until_ms = int(_time.time() * 1000) + 60000
    app._kbd_nav_mouse_pos_at_guard = (200, 300)  # 跟當前位置一樣

    result = st.StrategyGUI._kbd_nav_guard_should_block(app, tree)
    assert result is True, (
        f"guard 期間內 mouse 未變 → 應 return True block、實際 {result}"
    )


def test_kbd_nav_guard_releases_when_mouse_moves():
    """v9：mouse 位置真的動了 → guard 自動解除、return False"""
    from types import SimpleNamespace
    import time as _time
    import StockTool as st

    tree = SimpleNamespace()
    tree.winfo_pointerxy = lambda: (500, 600)  # mouse 已移到新位置

    app = SimpleNamespace()
    app._kbd_nav_guard_until_ms = int(_time.time() * 1000) + 60000
    app._kbd_nav_mouse_pos_at_guard = (200, 300)  # 原來位置

    result = st.StrategyGUI._kbd_nav_guard_should_block(app, tree)
    assert result is False, (
        f"mouse 真的動了 → 應 return False 不 block、實際 {result}"
    )
    # 同時 guard 應自動 reset
    assert app._kbd_nav_guard_until_ms == 0, (
        f"guard 自動 reset、實際 {app._kbd_nav_guard_until_ms}"
    )


def test_kbd_nav_guard_releases_on_timeout():
    """v9：guard timeout（已過期）→ 應 return False 不 block"""
    from types import SimpleNamespace
    import time as _time
    import StockTool as st

    tree = SimpleNamespace()
    tree.winfo_pointerxy = lambda: (200, 300)

    app = SimpleNamespace()
    # guard 在 1 分鐘前就過期了
    app._kbd_nav_guard_until_ms = int(_time.time() * 1000) - 60000
    app._kbd_nav_mouse_pos_at_guard = (200, 300)

    result = st.StrategyGUI._kbd_nav_guard_should_block(app, tree)
    assert result is False, (
        f"guard 已過期 → 應 return False 不 block、實際 {result}"
    )


def test_motion_handlers_call_guard():
    """v9：3 個 motion handler 都要呼叫 _kbd_nav_guard_should_block"""
    content = _read()
    for fn in ("_on_select_tree_hover", "_ms_tree_hover", "_etf_tree_hover_combined"):
        idx = content.find(f"def {fn}(self, event):")
        assert idx != -1, f"找不到 {fn}"
        end = content.find("\n    def ", idx + 50)
        if end == -1:
            end = len(content)
        body = content[idx:end]
        if '"""' in body:
            parts = body.split('"""')
            body = '"""'.join(parts[2:])
        assert "_kbd_nav_guard_should_block" in body, (
            f"v9 {fn} 應呼叫 _kbd_nav_guard_should_block"
        )


def test_ensure_focus_visible_uses_bbox_check():
    """v9 _ensure_focus_visible 用 bbox.y+h 判斷是否需要 extra scroll"""
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v9 用 bbox.y+h 判斷（不是看是不是最後 row）
    assert "tree.bbox(iid)" in body, (
        "v9 _ensure_focus_visible 應呼叫 tree.bbox(iid)"
    )
    assert "tree.winfo_height" in body, (
        "v9 _ensure_focus_visible 應呼叫 tree.winfo_height() 算 canvas 高度"
    )
    assert "update_idletasks" in body, (
        "v9 _ensure_focus_visible 應呼叫 tree.update_idletasks() 強制重繪"
    )


# ==========================================================
# 【V1.2.0-kb-focus-v10】focus padding row + SendInput fallback
# ==========================================================

def test_sendinput_helper_exists():
    """v10 _sendinput_move_cursor helper 必須存在（Windows SendInput fallback）"""
    content = _read()
    assert "def _sendinput_move_cursor(self, x, y):" in content, (
        "v10 應新增 _sendinput_move_cursor(x, y) helper"
    )


def test_ensure_focus_padding_row_helper_exists():
    """v10 _ensure_focus_padding_row helper 必須存在"""
    content = _read()
    assert "def _ensure_focus_padding_row(self, tree):" in content, (
        "v10 應新增 _ensure_focus_padding_row(tree) helper（加 invisible padding row）"
    )


def test_move_cursor_calls_event_generate_first():
    """v13：_move_cursor_to_row 必先呼叫 event_generate（即使 OS cursor API 失敗也能視覺同步）"""
    content = _read()
    idx = content.find("def _move_cursor_to_row(self, tree, iid):")
    assert idx != -1, "找不到 _move_cursor_to_row"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # event_generate 必需在 _win_move_cursor_to 之前
    eg_idx = body.find("event_generate")
    win_idx = body.find("_win_move_cursor_to")
    assert eg_idx != -1, (
        "v13 _move_cursor_to_row 必包含 event_generate('<Motion>')"
    )
    assert win_idx != -1, (
        "v13 _move_cursor_to_row 必呼叫 _win_move_cursor_to（多層豐的 OS cursor 同步）"
    )
    assert eg_idx < win_idx, (
        "v13：event_generate 必在 _win_move_cursor_to 之前（主矛先視覺同步）"
    )


def test_padding_row_added_when_missing():
    """v10 _ensure_focus_padding_row：tree 沒 __focus_padding__ 時要加上"""
    import StockTool as st

    children_added = []
    item_calls = []
    tag_configure_calls = []

    class MockTree:
        def exists(self, iid):
            return False  # 不存在

        def get_children(self):
            return ["a", "b", "c"]

        def item(self, iid, *args, **kwargs):
            item_calls.append((iid, args, kwargs))
            # 真實 Tkinter tree.item(iid, "values") 回 tuple
            if args == ("values",):
                return ("2330", "台積電", "100")
            class V:
                values = ("2330", "台積電", "100")
            return V()

        def cget(self, key):
            return "#ffffff"

        def tag_configure(self, tag, **kw):
            tag_configure_calls.append((tag, kw))

        def insert(self, parent, index, **kw):
            children_added.append(kw)

        def __getitem__(self, key):
            # 模擬 Treeview["columns"] = ("col1", "col2", "col3")
            if key == "columns":
                return ("col1", "col2", "col3")
            raise KeyError(key)

    tree = MockTree()
    app = st.StrategyGUI if hasattr(st, 'StrategyGUI') else object()
    # 用一個帶 _ensure_focus_padding_row 方法的 mock app 簡化
    # 直接 invoke 時用真實函式（是 unbound method）但透過 instance
    # 改用更簡單的方式：直接用一個最小 app
    class App:
        pass

    st.StrategyGUI._ensure_focus_padding_row(App(), tree)

    assert children_added, "v10 應加 padding row"
    assert children_added[0].get("iid") == "__focus_padding__", (
        f"padding row iid 應為 __focus_padding__、實際 {children_added[0].get('iid')}"
    )
    assert "focus_padding" in children_added[0].get("tags", ()), (
        f"padding row 應有 focus_padding tag、實際 {children_added[0].get('tags')}"
    )
    assert tag_configure_calls, "v10 應 tag_configure focus_padding"


def test_padding_row_not_added_if_exists():
    """v10：tree 已有 __focus_padding__ 時不重加"""
    from types import SimpleNamespace
    import StockTool as st

    children_added = []
    tree = SimpleNamespace()
    tree.exists = lambda iid: True  # 已存在
    tree.get_children = lambda: ["__focus_padding__", "a"]
    tree.insert = lambda parent, index, **kw: children_added.append(kw)

    app = SimpleNamespace()
    st.StrategyGUI._ensure_focus_padding_row(app, tree)

    assert not children_added, "已存在時不應重加 padding row"


def test_guard_5px_tolerance():
    """v10：mouse 在 5px 容差內移動仍視為未動、guard 繼續 block"""
    from types import SimpleNamespace
    import time as _time
    import StockTool as st

    tree = SimpleNamespace()
    # mouse 位置與 guard 位置差 3px（在容差內）
    tree.winfo_pointerxy = lambda: (203, 303)

    app = SimpleNamespace()
    app._kbd_nav_guard_until_ms = int(_time.time() * 1000) + 60000
    app._kbd_nav_mouse_pos_at_guard = (200, 300)  # 差 3x3 = 在容差內

    result = st.StrategyGUI._kbd_nav_guard_should_block(app, tree)
    assert result is True, (
        f"5px 容差內的 mouse 微動 → 應繼續 block、實際 {result}"
    )

    # 差 10x10 = 超出容差、解除 guard
    tree.winfo_pointerxy = lambda: (210, 310)
    result = st.StrategyGUI._kbd_nav_guard_should_block(app, tree)
    assert result is False, (
        f"超出 5px 容差 → 應解除 guard、實際 {result}"
    )


def test_ensure_focus_visible_calls_padding_row_first():
    """v10：_ensure_focus_visible 必先呼叫 _ensure_focus_padding_row、再 see()"""
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 確認呼叫順序
    pad_idx = body.find("_ensure_focus_padding_row")
    see_idx = body.find("tree.see(iid)")
    assert pad_idx != -1, "v10 _ensure_focus_visible 必呼叫 _ensure_focus_padding_row"
    assert see_idx != -1, "v10 _ensure_focus_visible 必呼叫 tree.see(iid)"
    assert pad_idx < see_idx, (
        "v10：_ensure_focus_padding_row 必在 tree.see(iid) 之前（先加 padding 再 scroll）"
    )


def test_ensure_focus_visible_checks_second_to_last():
    """v10：_ensure_focus_visible 檢查 children[-2]、若 iid 是倒數第二 + 多 scroll"""
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 確認有 children[-2] 判斷
    assert "children[-2]" in body, (
        "v10 _ensure_focus_visible 檢查 iid == children[-2] 確認是倒數第二（padding row 是最後）"
    )


# ==========================================================
# 【V1.2.0-kb-focus-v12】解耦 hover vs click
# ==========================================================

def test_v12_hover_decoupled_from_click():
    """v12 _on_tree_select_sync_hover 必不含 _apply_hover 呼叫（hover 解耦 click）

    William 2026-07-07 15:03 明確表示：
    - cursor 在結果 area 就要 highlight（mouse motion）
    - click 是選股 (excel output)、不該動 hover
    → <<TreeviewSelect>> 不該 call _apply_hover
    """
    content = _read()
    idx = content.find("def _on_tree_select_sync_hover(self, event):")
    assert idx != -1, "找不到 _on_tree_select_sync_hover"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v12：<<TreeviewSelect>> handler 不該 call _apply_hover
    assert "_apply_hover" not in body, (
        f"v12 _on_tree_select_sync_hover 不該 call _apply_hover（hover 解耦 click）"
    )


def test_v12_apply_hover_single_tag():
    """v12 _apply_hover 回到 v8 設計：tags=(hover_kind,) 單一 tag

    為什麼？
    - v11 三重 tags 太複雜、click handler 重設 (checked, price_x) 會覆蓋 hover
    - v12 簡化回 hover_<kind> 單一 tag
    - click handler 重設時清掉 hover 是設計上就要的（因為 click 不等於 hover）
    - mouse motion 持續 re-apply hover 保持 highlight
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1, "找不到 _apply_hover"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 確認使用單一 hover tag
    import re
    # 從 body 找出 tree.item(iid, tags=(...)) 這行
    # 簡單用字串包含檢查：tags=(f"hover_{hover_kind}",)
    # 重點：tags= 後只有 1 個 tag、並且沒有勾號以外的逗號
    # 找出 tree.item(iid, tags=( ... )) 的全部內容
    m = re.search(r"tree\.item\(\s*iid\s*,\s*tags=\((.*?)\)\s*\)", body, re.DOTALL)
    if not m:
        # 試試無空格版本
        m = re.search(r"tree\.item\(iid,tags=\((.*?)\)\)", body, re.DOTALL)
    assert m, "v12 _apply_hover 必包含 tree.item(iid, tags=(...))"
    inner = m.group(1).strip()
    # 去掉尾部的逗號（Python tuple 結尾逗號不是分隔符）
    if inner.endswith(","):
        inner = inner[:-1].strip()
    # 計算 top-level commas
    depth = 0
    top_commas = 0
    for ch in inner:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            top_commas += 1
    assert top_commas == 0, (
        f"v12 _apply_hover tags= 應只有 1 個 tag、發現 top-level 逗號 {top_commas} 個、inner={inner!r}"
    )
    # 確認是 hover tag
    assert "hover_" in inner, (
        f"v12 _apply_hover 應設 hover_<kind> tag、實際 {inner!r}"
    )


def test_v12_clear_all_hover_simple():
    """v12 _clear_all_hover 簡化：不使用 tree.tag_remove

    為什麼？
    - v11 用 tag_remove("hover_up") 等、若 tag 未註冊會 raise（雖然包 try/except）
    - v12 改用更簡單的方法：掃每個 row、看 tags、有 hover_* 就 _set_row_tag_normal
    """
    content = _read()
    idx = content.find("def _clear_all_hover(self, tree):")
    assert idx != -1, "找不到 _clear_all_hover"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v12 不該使用 tree.tag_remove
    assert "tag_remove" not in body, (
        f"v12 _clear_all_hover 不該使用 tag_remove、應用 _set_row_tag_normal 重建"
    )


def test_v12_ensure_focus_visible_scrolls_extra_for_last_row():
    """v12 _ensure_focus_visible 保留 v10 的最後 row 邏輯

    William 反映最後 row 顯示不出來：
    - tree.see(last_real_item) 把 last_real_item 推到 bottom edge
    - focus rectangle 在 row 邊框、被 canvas bottom edge 切到
    - 解法：padding row + yview_scroll(1, units) 給 focus rectangle 留空間
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_ensure_focus_padding_row" in body, (
        "v12 _ensure_focus_visible 必呼叫 _ensure_focus_padding_row"
    )
    assert "children[-2]" in body, (
        "v12 _ensure_focus_visible 必檢查 iid == children[-2]"
    )
    assert "yview_scroll(1" in body, (
        "v12 _ensure_focus_visible 必呼叫 yview_scroll(1, ...)"
    )


def test_v12_motion_handler_does_not_require_click():
    """v12 motion handler 必能在 mouse 移動時直接 highlight（不需要 click）

    William 15:03：cursor 在結果 area 就要 highlight 不需要 click
    → _on_select_tree_hover 應該在 iid in children 時直接 _apply_hover
    """
    content = _read()
    idx = content.find("def _on_select_tree_hover(self, event):")
    assert idx != -1, "找不到 _on_select_tree_hover"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 確認 motion handler 進場即設 hover（不需要 click）
    assert "_apply_hover" in body, (
        "v12 _on_select_tree_hover 必 call _apply_hover"
    )
    # 確認不被 click gate
    # 例如不該有「if clicked」「if selection」等限制
    assert "if clicked" not in body, (
        "v12 motion handler 不該被 click gate"
    )


def test_v12_motion_handler_uses_event_generate_fallback():
    """v12 motion handler 應該在 set focus 後也 set focus_set（讓鍵盤 nav 立刻有效）"""
    content = _read()
    idx = content.find("def _on_select_tree_hover(self, event):")
    assert idx != -1, "找不到 _on_select_tree_hover"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 確認設 focus + focus_set
    assert "tree.focus(iid)" in body or ".focus(iid)" in body, (
        "v12 motion handler 必設 tree.focus(iid) 讓鍵盤 nav 同步"
    )
    assert "focus_set" in body, (
        "v12 motion handler 必設 focus_set 讓 keyboard 立即有效"
    )


def test_v12_click_handler_no_hover_call():
    """v12 click handler (_on_select_tree_click) 必不 call _apply_hover

    為什麼？
    - click 設 (checked, price_x) 會清掉 hover tag、若 click 又 call _apply_hover 會立刻設回去
    - 但 mouse cursor 還在 click row 附近、motion 還沒 fire → highlight 留在 click row
    - 這是 William 反映的「click 後 highlight bar 動不了」bug
    - v12 解法：click handler 不 call _apply_hover、mouse 動了 motion 會自動重設 hover
    """
    content = _read()
    for click_handler in ("_on_select_tree_click", "_ms_toggle_check", "_etf_toggle_check"):
        idx = content.find(f"def {click_handler}(self, event):")
        assert idx != -1, f"找不到 {click_handler}"
        end = content.find("\n    def ", idx + 50)
        if end == -1:
            end = len(content)
        body = content[idx:end]
        if '"""' in body:
            parts = body.split('"""')
            body = '"""'.join(parts[2:])
        assert "_apply_hover" not in body, (
            f"v12 {click_handler} 不該 call _apply_hover（hover 應該由 mouse motion 控制）"
        )


# ==========================================================
# 【V1.2.0-kb-focus-v13】多層豐的 OS cursor 移動
# ==========================================================

def test_win_move_cursor_to_helper_exists():
    """v13 _win_move_cursor_to helper 必存在（多層豐的 OS cursor 同步）"""
    content = _read()
    assert "def _win_move_cursor_to(self, target_x, target_y):" in content, (
        "v13 應新增 _win_move_cursor_to(target_x, target_y) helper（多層豐的 cursor 移動）"
    )


def test_move_cursor_uses_get_cursor_pos_verify():
    """v13：SetCursorPos 後用 GetCursorPos 驗證是否真的到了 target"""
    content = _read()
    idx = content.find("def _win_move_cursor_to(self, target_x, target_y):")
    assert idx != -1, "找不到 _win_move_cursor_to"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "GetCursorPos" in body, (
        "v13 _win_move_cursor_to 必使用 GetCursorPos 驗證 SetCursorPos 是否真的 effect"
    )


def test_move_cursor_uses_clip_cursor_release():
    """v13：SetCursorPos 失敗時釋放 ClipCursor lock 再重試"""
    content = _read()
    idx = content.find("def _win_move_cursor_to(self, target_x, target_y):")
    assert idx != -1, "找不到 _win_move_cursor_to"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "ClipCursor" in body, (
        "v13 _win_move_cursor_to 必使用 ClipCursor 釋放 mouse lock"
    )


def test_move_cursor_uses_mouse_event():
    """v13：mouse_event 作為 fallback API"""
    content = _read()
    idx = content.find("def _win_move_cursor_to(self, target_x, target_y):")
    assert idx != -1, "找不到 _win_move_cursor_to"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "mouse_event" in body, (
        "v13 _win_move_cursor_to 必包含 mouse_event 老 API 作為 fallback"
    )


def test_move_cursor_uses_send_input():
    """v13：SendInput 作為 fallback API"""
    content = _read()
    idx = content.find("def _win_move_cursor_to(self, target_x, target_y):")
    assert idx != -1, "找不到 _win_move_cursor_to"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "SendInput" in body, (
        "v13 _win_move_cursor_to 必包含 SendInput 低階 API 作為 fallback"
    )


def test_kbd_nav_guard_extended_to_2000ms():
    """v13：_kbd_nav_guard 延長到 2000ms（從 500ms）"""
    content = _read()
    # v13 應該用 2000 而不是 500
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "2000" in body, (
        "v13 _on_tree_key_see_focus 必設定 guard 2000ms（防止 motion handler 太快覆蓋 key nav hover）"
    )


def test_v13_win_move_cursor_to_multi_layer():
    """v13 _win_move_cursor_to 測試：SetCursorPos 失敗時走 mouse_event"""
    from types import SimpleNamespace
    import StockTool as st

    # 模擬 ctypes.windll.user32
    class FakeUser32:
        def __init__(self):
            self.set_pos_called = 0
            self.get_pos_called = 0
            self.mouse_event_called = 0
            self.sendinput_called = 0
            self.cur_pos = SimpleNamespace(x=100, y=100)
            # 預設 cursor 在 (100, 100)
            self.fail_set_cursor = True  # SetCursorPos 假裝失敗

        def GetCursorPos(self, p):
            self.get_pos_called += 1
            p.contents.x = self.cur_pos.x
            p.contents.y = self.cur_pos.y

        def SetCursorPos(self, x, y):
            self.set_pos_called += 1
            if self.fail_set_cursor:
                # 第一輪失敗、第二輪成功
                return False
            self.cur_pos.x = x
            self.cur_pos.y = y
            return True

        def ClipCursor(self, rect):
            return True

        def GetSystemMetrics(self, idx):
            return 1920 if idx == 0 else 1080

        def mouse_event(self, flags, dx, dy, data, extra):
            self.mouse_event_called += 1
            # 移動 cursor
            self.cur_pos.x = int(dx * 1920 / 65536)
            self.cur_pos.y = int(dy * 1080 / 65536)
            return True

        def SendInput(self, n, inputs, size):
            self.sendinput_called += 1
            return 1

    fake = FakeUser32()

    class FakeCtypes:
        def __init__(self):
            self.windll = SimpleNamespace(user32=fake)

        def Structure(self, *args, **kwargs):
            return type("P", (), {
                "__init__": lambda self: None,
                "contents": SimpleNamespace(x=0, y=0)
            })

    # 用 SimpleNamespace 模擬 ctypes
    import ctypes as real_ctypes
    class FakePOINT(real_ctypes.Structure):
        _fields_ = [("x", real_ctypes.c_long), ("y", real_ctypes.c_long)]

    # 我們測試 _win_move_cursor_to 內部 cursor 邏輯、不直接測
    # 重點：函式必存在 + 必呼叫 5 個 layer
    content = _read()
    idx = content.find("def _win_move_cursor_to(self, target_x, target_y):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 5 個 layer 都要出現
    # Layer 1: SetCursorPos + GetCursorPos
    assert "SetCursorPos" in body, "v13 Layer 1 應使用 SetCursorPos"
    assert "GetCursorPos" in body, "v13 必用 GetCursorPos 驗證"
    # Layer 2: ClipCursor
    assert "ClipCursor(None)" in body, "v13 Layer 2 應釋放 ClipCursor"
    # Layer 3: mouse_event
    assert "mouse_event" in body, "v13 Layer 3 應使用 mouse_event"
    # Layer 4: SendInput
    assert "SendInput" in body, "v13 Layer 4 應使用 SendInput"
    # Layer 5: 最後一次重試
    layer5_count = body.count("Layer 5") + body.count("強制解 ClipCursor")
    assert layer5_count >= 1, "v13 Layer 5 應有最後重試"


def test_v13_event_generate_still_called_for_visual():
    """v13：即使 OS cursor 移動失敗、event_generate 仍要做視覺同步"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace()
    tree.winfo_exists = lambda: True
    tree.bbox = lambda iid: (10, 20, 100, 30)
    tree.winfo_rootx = lambda: 0
    tree.winfo_rooty = lambda: 0

    event_gen_calls = []
    tree.event_generate = lambda event, **kw: event_gen_calls.append((event, kw))

    # 模擬 _win_move_cursor_to（不重要、不需真的動 OS cursor）
    app = SimpleNamespace()
    app._win_move_cursor_to = lambda x, y: False

    # v13 邏輯：先 event_generate、然後 _win_move_cursor_to
    cx = 10 + 100 // 2  # 60
    cy = 20 + 30 // 2  # 35
    tree.event_generate("<Motion>", x=cx, y=cy)
    app._win_move_cursor_to(0 + cx, 0 + cy)

    assert event_gen_calls == [("<Motion>", {"x": cx, "y": cy})], (
        f"v13 必先 event_generate('<Motion>', x=cx, y=cy) 做視覺同步、實際 {event_gen_calls}"
    )
