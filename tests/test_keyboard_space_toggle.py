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
    """【V1.2.0-kb-focus-v2】不應該覆寫 selected state 顏色

    William 16:26 反映「up/down 文字變亮白色」
    根因：Linux ttk 主題 selected state 預設會把 foreground 改白色
    上一版用 _style.map(selected → #fff3a0) 試圖同色、但沒改 foreground → 文字變白
    新設計：完全不用 selected state 表示 keyboard focus、改用 hover_* tag
    所以不應該有 _style.map("Treeview", background=[("selected", ...)]) 設定
    """
    content = _read()
    m = re.search(
        r'_style\.map\([^)]*Treeview[^)]*\)',
        content,
        re.DOTALL,
    )
    # 期望找不到、或者找到但不包含 selected
    if m and "selected" in m.group(0):
        pytest.fail(
            "❌ 還在覆寫 selected state 顏色！\n"
            "新設計：不要覆寫 selected、讓 hover_* tag 同時處理 hover + keyboard focus\n"
            "詳見 _sync_focus_to_hover()"
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


def test_focus_tab_tree_select_tree():
    """切到系統選股 tab → focus select_tree 第一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(
        children=["row1", "row2"],
        focus_set_called=[],
        focus_called=[],
    )
    tree.get_children = lambda: tree.children
    tree.focus_set = lambda: tree.focus_set_called.append(True)
    tree.focus = lambda iid: tree.focus_called.append(iid)

    app = SimpleNamespace(
        select_tree=tree,
        _etf_tree=None,
        _ms_tree=None,
        backtest_tree=None,
    )

    st.StrategyGUI._focus_tab_tree_on_change(app, 0)

    assert tree.focus_set_called, "應呼叫 focus_set"
    assert tree.focus_called == ["row1"], f"應 focus 第一個 row、實際 {tree.focus_called}"


def test_focus_tab_tree_etf_tree():
    """切到 ETF tab → focus _etf_tree 第一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(children=["e1"], focus_set_called=[], focus_called=[])
    tree.get_children = lambda: tree.children
    tree.focus_set = lambda: tree.focus_set_called.append(True)
    tree.focus = lambda iid: tree.focus_called.append(iid)

    app = SimpleNamespace(
        select_tree=None,
        _etf_tree=tree,
        _ms_tree=None,
        backtest_tree=None,
    )

    st.StrategyGUI._focus_tab_tree_on_change(app, 1)

    assert tree.focus_set_called
    assert tree.focus_called == ["e1"]


def test_focus_tab_tree_ms_tree():
    """切到手動選股 tab → focus _ms_tree 第一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(children=["m1", "m2", "m3"], focus_set_called=[], focus_called=[])
    tree.get_children = lambda: tree.children
    tree.focus_set = lambda: tree.focus_set_called.append(True)
    tree.focus = lambda iid: tree.focus_called.append(iid)

    app = SimpleNamespace(
        select_tree=None,
        _etf_tree=None,
        _ms_tree=tree,
        backtest_tree=None,
    )

    st.StrategyGUI._focus_tab_tree_on_change(app, 2)

    assert tree.focus_set_called
    assert tree.focus_called == ["m1"]


def test_focus_tab_tree_backtest_tree():
    """切到回測 tab → focus backtest_tree 第一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(children=["b1"], focus_set_called=[], focus_called=[])
    tree.get_children = lambda: tree.children
    tree.focus_set = lambda: tree.focus_set_called.append(True)
    tree.focus = lambda iid: tree.focus_called.append(iid)

    app = SimpleNamespace(
        select_tree=None,
        _etf_tree=None,
        _ms_tree=None,
        backtest_tree=tree,
    )

    st.StrategyGUI._focus_tab_tree_on_change(app, 4)

    assert tree.focus_set_called
    assert tree.focus_called == ["b1"]


def test_focus_tab_tree_empty_no_op():
    """tree 沒資料時（get_children 空）不應該 focus、不爆"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(children=[], focus_set_called=[], focus_called=[])
    tree.get_children = lambda: tree.children
    tree.focus_set = lambda: tree.focus_set_called.append(True)
    tree.focus = lambda iid: tree.focus_called.append(iid)

    app = SimpleNamespace(
        select_tree=tree,
        _etf_tree=None,
        _ms_tree=None,
        backtest_tree=None,
    )

    # 不應該爆
    st.StrategyGUI._focus_tab_tree_on_change(app, 0)

    assert not tree.focus_set_called, "空 tree 不應 focus_set"
    assert not tree.focus_called, "空 tree 不應設 focus"


def test_focus_tab_tree_unknown_tab_no_op():
    """tab index 沒對應 tree 時（買賣記錄 tab 3）不應該爆"""
    from types import SimpleNamespace
    import StockTool as st

    app = SimpleNamespace(
        select_tree=SimpleNamespace(),
        _etf_tree=SimpleNamespace(),
        _ms_tree=SimpleNamespace(),
        backtest_tree=SimpleNamespace(),
    )

    # 不應該爆
    st.StrategyGUI._focus_tab_tree_on_change(app, 3)  # 買賣記錄 tab
    st.StrategyGUI._focus_tab_tree_on_change(app, 99)  # 不存在


# ==========================================================
# 【V1.2.0-kb-focus-v2】完全不用 selected state、用 hover_* tag 同時處理
# ==========================================================


def test_sync_focus_to_hover_function_exists():
    """_sync_focus_to_hover 函式存在"""
    content = _read()
    assert re.search(r'def _sync_focus_to_hover\(self,\s*event\):', content), (
        "❌ 找不到 _sync_focus_to_hover(self, event) 函式！\n"
        "新設計：用 <<TreeviewSelect>> 把 focus 變化同步到 hover_* tag"
    )


def test_sync_focus_to_hover_supports_all_four_trees():
    """_sync_focus_to_hover 應該支援 4 種 tree"""
    content = _read()
    m = re.search(
        r'def _sync_focus_to_hover\(self,\s*event\):.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _sync_focus_to_hover"
    body = m.group(0)
    for tree_attr in ("_ms_tree", "_etf_tree", "select_tree", "_bt_checked"):
        assert tree_attr in body, (
            f"❌ _sync_focus_to_hover 沒處理 {tree_attr}！"
        )


def test_select_tree_binds_treeview_select():
    """select_tree / backtest_tree 有綁 <<TreeviewSelect>>"""
    content = _read()
    # 透過 results_tree 共用綁
    m = re.search(
        r'results_tree\.bind\(\s*["\']<<TreeviewSelect>>["\']',
        content,
    )
    assert m, (
        "❌ results_tree 沒綁 <<TreeviewSelect>>！\n"
        "William 16:26 反映 hover 跟 keyboard highlight 沒同步"
    )


def test_ms_tree_binds_treeview_select():
    """_ms_tree 有綁 <<TreeviewSelect>>"""
    content = _read()
    m = re.search(
        r'self\._ms_tree\.bind\(\s*["\']<<TreeviewSelect>>["\']',
        content,
    )
    assert m, "❌ _ms_tree 沒綁 <<TreeviewSelect>>！"


def test_etf_tree_binds_treeview_select():
    """_etf_tree 有綁 <<TreeviewSelect>>"""
    content = _read()
    m = re.search(
        r'self\._etf_tree\.bind\(\s*["\']<<TreeviewSelect>>["\']',
        content,
    )
    assert m, "❌ _etf_tree 沒綁 <<TreeviewSelect>>！"


def test_force_focus_tree_function_exists():
    """【V1.2.0-kb-focus-v2】_force_focus_tree exists for after_idle"""
    content = _read()
    assert re.search(r'def _force_focus_tree\(', content), (
        "❌ 找不到 _force_focus_tree 函式！\n"
        "after_idle 強迫 focus、避免被 notebook 內部事件覆蓋"
    )


def test_focus_tab_tree_uses_after_idle():
    """_focus_tab_tree_on_change 內應該用 after_idle"""
    content = _read()
    m = re.search(
        r'def _focus_tab_tree_on_change\(self,\s*current_tab_idx.*?(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    body = m.group(0)
    assert "after_idle" in body, (
        "❌ _focus_tab_tree_on_change 沒用 after_idle！\n"
        "William 16:26 反映 ETF / 手動選股 up/down 還是不會動 → 需要 after_idle 避開 notebook 內部事件"
    )


# ==========================================================
# 行為測試：_sync_focus_to_hover
# ==========================================================


def test_sync_focus_to_hover_ms_tree():
    """_sync_focus_to_hover：ms_tree focus 改變時把 hover tag 移到新 row"""
    from types import SimpleNamespace
    import StockTool as st

    # 模擬 tree 有兩個 rows + 一個 row 已經有 hover_zero tag
    rows = ["row1", "row2"]
    items_state = {
        "row1": {"tags": ("hover_zero",), "values": ("☐", "3188")},
        "row2": {"tags": ("unchecked", "price_up"), "values": ("☐", "3028")},
    }

    def get_children():
        return list(rows)

    def item(iid, *args, **kwargs):
        if args:
            # tree.item(iid, "tags") → 回傳該欄位值
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        s = items_state[iid]
        return SimpleNamespace(values=s.get("values", ()), tags=s.get("tags", ()))

    tree = SimpleNamespace(focused_iid="row2")
    tree.focus = lambda: tree.focused_iid
    tree.get_children = get_children
    tree.item = item

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={"row1": False, "row2": False},
        _ms_price_tags={"row1": "price_zero", "row2": "price_up"},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._sync_focus_to_hover(app, event)

    # row1 應該被恢復成 unchecked + price_zero
    assert "hover" not in items_state["row1"]["tags"], (
        f"row1 應該取消 hover_* tag、實際 tags={items_state['row1']['tags']}"
    )
    # row2 應該被設成 hover_up
    assert "hover_up" in items_state["row2"]["tags"], (
        f"row2 應該設 hover_up tag、實際 tags={items_state['row2']['tags']}"
    )


def test_sync_focus_to_hover_etf_tree():
    """_sync_focus_to_hover：etf_tree focus 改變時把 hover tag 移到新 row"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "e1": {"tags": ("unchecked", "price_down"), "values": ("☐", "0050")},
        "e2": {"tags": ("unchecked", "price_up"), "values": ("☐", "0056")},
    }

    def item(iid, *args, **kwargs):
        if args:
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        s = items_state[iid]
        return SimpleNamespace(values=s.get("values", ()), tags=s.get("tags", ()))

    tree = SimpleNamespace(focused_iid="e1")
    tree.focus = lambda: tree.focused_iid
    tree.get_children = lambda: ["e1", "e2"]
    tree.item = item

    app = SimpleNamespace(
        _ms_tree=SimpleNamespace(),
        _etf_tree=tree,
        select_tree=SimpleNamespace(),
        _ms_checked={},
        _ms_price_tags={},
        _etf_checked={"e1": False, "e2": False},
        _etf_price_tags={"e1": "price_down", "e2": "price_up"},
        _select_checked={},
        _select_price_tags={},
    )

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._sync_focus_to_hover(app, event)

    assert "hover_down" in items_state["e1"]["tags"], (
        f"e1 應設 hover_down tag、實際 tags={items_state['e1']['tags']}"
    )


def test_sync_focus_to_hover_select_tree():
    """_sync_focus_to_hover：select_tree focus 改變時把 hover tag 移到新 row"""
    from types import SimpleNamespace
    import StockTool as st

    items_state = {
        "s1": {"tags": ("unchecked", "price_up"), "values": ("☐", "2330")},
    }

    def item(iid, *args, **kwargs):
        if args:
            return items_state[iid].get(args[0], ())
        if kwargs:
            items_state[iid].update(kwargs)
        s = items_state[iid]
        return SimpleNamespace(values=s.get("values", ()), tags=s.get("tags", ()))

    tree = SimpleNamespace(focused_iid="s1")
    tree.focus = lambda: tree.focused_iid
    tree.get_children = lambda: ["s1"]
    tree.item = item

    app = SimpleNamespace(
        _ms_tree=SimpleNamespace(),
        _etf_tree=SimpleNamespace(),
        select_tree=tree,
        _ms_checked={},
        _ms_price_tags={},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={"s1": False},
        _select_price_tags={"s1": "price_up"},
    )

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._sync_focus_to_hover(app, event)

    assert "hover_up" in items_state["s1"]["tags"]


def test_sync_focus_to_hover_no_focus_no_op():
    """focus 為空時（tree.focus() 回空）不應該爆"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(focused_iid="")
    tree.focus = lambda: tree.focused_iid
    tree.get_children = lambda: ["row1"]

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={},
        _ms_price_tags={},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )

    event = SimpleNamespace(widget=tree)
    # 不應該爆
    st.StrategyGUI._sync_focus_to_hover(app, event)


def test_force_focus_tree():
    """_force_focus_tree：呼叫後應該 focus_set + focus"""
    from types import SimpleNamespace
    import StockTool as st

    calls = []

    def focus_set():
        calls.append(("focus_set",))

    def focus(iid):
        calls.append(("focus", iid))

    tree = SimpleNamespace()
    tree.focus_set = focus_set
    tree.focus = focus
    tree.get_children = lambda: ["row1"]

    st.StrategyGUI._force_focus_tree(SimpleNamespace(), tree, "row1")

    assert ("focus_set",) in calls, "應呼叫 focus_set"
    assert ("focus", "row1") in calls, "應呼叫 focus(row1)"
