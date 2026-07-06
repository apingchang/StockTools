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
# 【V1.2.0-kb-focus-v3】2026-07-06 18:54 William 反映問題
# 1. 仍要 click 後 up/down 才會動作
# 2. click 後 highlight 變藍色（Treeview selected state 預設）
# 3. up/down 移動 scroll 不到最後一個 row
# 4. ETF / 手動選股 up/down 不會動
# 5. up/down 後 click → highlight 回到黃色、但 up/down 的藍色留在別 row
# ==========================================================


def test_no_treeview_select_binding():
    """【V1.2.0-kb-focus-v3】結果 tree（select / ms / etf / backtest）不該綁 <<TreeviewSelect>> 事件

    根因 v2：<<TreeviewSelect>> 在 Tk 是 selection 變化、不是 focus 變化、
            且對應的 selected state 預設會顯示藍色 highlight
    v3：改用 <Up>/<Down> 主動 bind、自己處理 focus 移動

    【允許 positions_tree 綁 <<TreeviewSelect>>】因為它是交易記錄 tree、不會跟 hover/focus 衝突
    """
    content = _read()
    # 找出所有 <<TreeviewSelect>> bind
    lines = content.split('\n')
    bad = []
    for i, line in enumerate(lines):
        if '<<TreeviewSelect>>' in line and '.bind(' in line:
            # 找上下文 5 行內有沒有 positions_tree（允許）vs 結果 tree（不允許）
            ctx = '\n'.join(lines[max(0, i-5):i+1])
            if '_positions_tree' in ctx or 'positions_tree' in ctx:
                continue  # 允許
            bad.append(line.strip())
    assert not bad, (
        f"❌ 結果 tree 不應該再綁 <<TreeviewSelect>>、會觸發 Treeview 預設 selected state 藍色 highlight！\n"
        f"找到 {len(bad)} 個 bind、應改用 <Up>/<Down> 主動 bind：\n" + '\n'.join(bad)
    )


def test_style_map_selected_yellow():
    """【V1.2.0-keyboard-toggle-fix】_style.map(selected → 黃色) 保留

    雖然有 selection_remove 主動移除、但 style.map 仍保留作為保險
    """
    content = _read()
    m = re.search(r'_style\.map\([^)]*Treeview[^)]*\)', content, re.DOTALL)
    assert m, "找不到 _style.map(Treeview)"
    body = m.group(0)
    assert "selected" in body and "#fff3a0" in body, (
        "❌ _style.map 應保留 selected → #fff3a0、避免任何 selected state 殘留顯示系統藍色"
    )


def test_on_tree_key_move_function_exists():
    """_on_tree_key_move 函式存在"""
    content = _read()
    assert re.search(r'def _on_tree_key_move\(self,\s*event\):', content), (
        "❌ 找不到 _on_tree_key_move(self, event) 函式！\n"
        "v3 設計：主動 bind <Up>/<Down>、自己呼叫 tree.focus() + tree.see()"
    )


def test_on_tree_key_move_returns_break():
    """_on_tree_key_move 應該 return 'break'、避免 Tk 重複處理 scroll"""
    content = _read()
    m = re.search(r'def _on_tree_key_move\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    assert m, "找不到 _on_tree_key_move"
    assert '"break"' in m.group(0), "❌ _on_tree_key_move 應 return 'break'"


def test_on_tree_key_move_calls_see():
    """_on_tree_key_move 應該呼叫 tree.see() 確保 focus row 可見"""
    content = _read()
    m = re.search(r'def _on_tree_key_move\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    body = m.group(0)
    assert "tree.see(" in body, "❌ _on_tree_key_move 應呼叫 tree.see(new_iid) 確保 scroll 到可見"


def test_on_tree_key_move_sets_hover_tag():
    """_on_tree_key_move 應該設 hover_<price> tag"""
    content = _read()
    m = re.search(r'def _on_tree_key_move\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    body = m.group(0)
    assert "hover_" in body, "❌ _on_tree_key_move 應設 hover_<price> tag"


def test_on_tree_key_move_clears_selection():
    """_on_tree_key_move 應該呼叫 selection_remove()"""
    content = _read()
    m = re.search(r'def _on_tree_key_move\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    body = m.group(0)
    assert "selection_remove" in body, (
        "❌ _on_tree_key_move 應呼叫 selection_remove、避免藍色 selected state"
    )


def test_set_row_tag_normal_function_exists():
    """_set_row_tag_normal helper 函式存在"""
    content = _read()
    assert re.search(r'def _set_row_tag_normal\(', content), (
        "❌ 找不到 _set_row_tag_normal(tree, iid) helper"
    )


def test_get_price_tag_for_tree_function_exists():
    """_get_price_tag_for_tree helper 函式存在"""
    content = _read()
    assert re.search(r'def _get_price_tag_for_tree\(', content), (
        "❌ 找不到 _get_price_tag_for_tree helper"
    )


def test_select_tree_binds_up_down():
    """results_tree (select_tree / backtest_tree 共用) 綁 <Up>/<Down>"""
    content = _read()
    assert re.search(r'results_tree\.bind\(["\']<Up>["\']', content), (
        "❌ results_tree 沒綁 <Up>！"
    )
    assert re.search(r'results_tree\.bind\(["\']<Down>["\']', content), (
        "❌ results_tree 沒綁 <Down>！"
    )


def test_ms_tree_binds_up_down():
    """_ms_tree 綁 <Up>/<Down>"""
    content = _read()
    assert re.search(r'self\._ms_tree\.bind\(["\']<Up>["\']', content), (
        "❌ _ms_tree 沒綁 <Up>！"
    )
    assert re.search(r'self\._ms_tree\.bind\(["\']<Down>["\']', content), (
        "❌ _ms_tree 沒綁 <Down>！"
    )


def test_etf_tree_binds_up_down():
    """_etf_tree 綁 <Up>/<Down>"""
    content = _read()
    assert re.search(r'self\._etf_tree\.bind\(["\']<Up>["\']', content), (
        "❌ _etf_tree 沒綁 <Up>！"
    )
    assert re.search(r'self\._etf_tree\.bind\(["\']<Down>["\']', content), (
        "❌ _etf_tree 沒綁 <Down>！"
    )


def test_click_handler_removes_selection_select_tree():
    """_on_select_tree_click 應該呼叫 selection_remove"""
    content = _read()
    m = re.search(r'def _on_select_tree_click\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    assert m, "找不到 _on_select_tree_click"
    assert "selection_remove" in m.group(0), (
        "❌ _on_select_tree_click 應呼叫 selection_remove、避免藍色 selected state"
    )


def test_click_handler_removes_selection_ms_tree():
    """_ms_toggle_check 應該呼叫 selection_remove"""
    content = _read()
    m = re.search(r'def _ms_toggle_check\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    assert m, "找不到 _ms_toggle_check"
    assert "selection_remove" in m.group(0), (
        "❌ _ms_toggle_check 應呼叫 selection_remove"
    )


def test_click_handler_removes_selection_etf_tree():
    """_etf_toggle_check 應該呼叫 selection_remove"""
    content = _read()
    m = re.search(r'def _etf_toggle_check\(self,\s*event\):.*?(?=\n    def |\Z)', content, re.DOTALL)
    assert m, "找不到 _etf_toggle_check"
    assert "selection_remove" in m.group(0), (
        "❌ _etf_toggle_check 應呼叫 selection_remove"
    )


# ==========================================================
# 行為測試：_on_tree_key_move
# ==========================================================


def test_on_tree_key_move_down_advances_focus():
    """<Down> 鍵 → focus 移到下一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    rows = ["r1", "r2", "r3"]
    items_state = {r: {"tags": ("unchecked", "price_up")} for r in rows}
    focus_calls = []
    see_calls = []
    sel_remove_calls = []

    def get_children():
        return list(rows)

    def item(iid, *args, **kwargs):
        if kwargs:
            items_state[iid].update(kwargs)
        return SimpleNamespace(**items_state[iid])

    tree = SimpleNamespace(focused_iid="r1")
    tree.focus = lambda iid=None: focus_calls.append(iid if iid else "GET") or (tree.focused_iid if iid is None else (setattr(tree, "focused_iid", iid) or iid))
    tree.see = lambda iid: see_calls.append(iid)
    tree.selection = lambda: ("r1",) if tree.focused_iid else ()
    tree.selection_remove = lambda items: sel_remove_calls.append(items)
    tree.get_children = get_children
    tree.item = item

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={r: False for r in rows},
        _ms_price_tags={r: "price_up" for r in rows},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Down")
    result = st.StrategyGUI._on_tree_key_move(app, event)

    assert result == "break", "應 return 'break'"
    # focus 應該被設到 r2
    assert tree.focused_iid == "r2", f"focus 應移到 r2、實際 {tree.focused_iid}"
    # r2 應該有 hover_up tag
    assert "hover_up" in items_state["r2"]["tags"], (
        f"r2 應有 hover_up tag、實際 {items_state['r2']['tags']}"
    )
    # r1 應該恢復成 unchecked + price_up（不再有 hover tag）
    assert "hover" not in items_state["r1"]["tags"], (
        f"r1 應取消 hover_* tag、實際 {items_state['r1']['tags']}"
    )
    # tree.see 應該被呼叫
    assert "r2" in see_calls, "tree.see(r2) 應被呼叫"


def test_on_tree_key_move_up_advances_focus():
    """<Up> 鍵 → focus 移到上一個 row"""
    from types import SimpleNamespace
    import StockTool as st

    rows = ["r1", "r2", "r3"]
    items_state = {r: {"tags": ("unchecked", "price_up")} for r in rows}

    tree = SimpleNamespace(focused_iid="r2")
    tree.focus = lambda iid=None: (setattr(tree, "focused_iid", iid) if iid is not None else None) or (tree.focused_iid if iid is None else iid)
    tree.see = lambda iid: None
    tree.selection = lambda: ()
    tree.selection_remove = lambda x: None
    tree.get_children = lambda: list(rows)
    tree.item = lambda iid, **kw: (
        items_state[iid].update(kw) if kw else SimpleNamespace(**items_state[iid])
    )

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={r: False for r in rows},
        _ms_price_tags={r: "price_up" for r in rows},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Up")
    st.StrategyGUI._on_tree_key_move(app, event)

    assert tree.focused_iid == "r1", f"focus 應移到 r1、實際 {tree.focused_iid}"


def test_on_tree_key_move_no_focus_starts_at_first():
    """沒 focus row 時 <Down> 從第一個 row 開始"""
    from types import SimpleNamespace
    import StockTool as st

    rows = ["r1", "r2"]
    items_state = {r: {"tags": ("unchecked", "price_up")} for r in rows}

    tree = SimpleNamespace(focused_iid="")
    tree.focus = lambda iid=None: (setattr(tree, "focused_iid", iid) if iid is not None else None) or (tree.focused_iid if iid is None else iid)
    tree.see = lambda iid: None
    tree.selection = lambda: ()
    tree.selection_remove = lambda x: None
    tree.get_children = lambda: list(rows)
    tree.item = lambda iid, **kw: (
        items_state[iid].update(kw) if kw else SimpleNamespace(**items_state[iid])
    )

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={r: False for r in rows},
        _ms_price_tags={r: "price_up" for r in rows},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Down")
    st.StrategyGUI._on_tree_key_move(app, event)

    assert tree.focused_iid == "r1", f"應從 r1 開始、實際 {tree.focused_iid}"


def test_on_tree_key_move_stops_at_last():
    """<Down> 在最後一個 row 不應往下超出"""
    from types import SimpleNamespace
    import StockTool as st

    rows = ["r1", "r2"]
    items_state = {r: {"tags": ("unchecked", "price_up")} for r in rows}

    tree = SimpleNamespace(focused_iid="r2")
    tree.focus = lambda iid=None: (setattr(tree, "focused_iid", iid) if iid is not None else None) or (tree.focused_iid if iid is None else iid)
    tree.see = lambda iid: None
    tree.selection = lambda: ()
    tree.selection_remove = lambda x: None
    tree.get_children = lambda: list(rows)
    tree.item = lambda iid, **kw: (
        items_state[iid].update(kw) if kw else SimpleNamespace(**items_state[iid])
    )

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={r: False for r in rows},
        _ms_price_tags={r: "price_up" for r in rows},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Down")
    st.StrategyGUI._on_tree_key_move(app, event)

    assert tree.focused_iid == "r2", f"在最後一個 row 不應超出、實際 {tree.focused_iid}"


def test_on_tree_key_move_stops_at_first():
    """<Up> 在第一個 row 不應往上超出"""
    from types import SimpleNamespace
    import StockTool as st

    rows = ["r1", "r2"]
    items_state = {r: {"tags": ("unchecked", "price_up")} for r in rows}

    tree = SimpleNamespace(focused_iid="r1")
    tree.focus = lambda iid=None: (setattr(tree, "focused_iid", iid) if iid is not None else None) or (tree.focused_iid if iid is None else iid)
    tree.see = lambda iid: None
    tree.selection = lambda: ()
    tree.selection_remove = lambda x: None
    tree.get_children = lambda: list(rows)
    tree.item = lambda iid, **kw: (
        items_state[iid].update(kw) if kw else SimpleNamespace(**items_state[iid])
    )

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={r: False for r in rows},
        _ms_price_tags={r: "price_up" for r in rows},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Up")
    st.StrategyGUI._on_tree_key_move(app, event)

    assert tree.focused_iid == "r1", f"在第一個 row 不應超出、實際 {tree.focused_iid}"


def test_on_tree_key_move_empty_tree():
    """空 tree 按 <Down> 不應爆"""
    from types import SimpleNamespace
    import StockTool as st

    tree = SimpleNamespace(focused_iid="")
    tree.focus = lambda: ""
    tree.get_children = lambda: []
    tree.item = lambda *a, **kw: SimpleNamespace()

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
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(iid, tags=("checked" if app._ms_checked.get(iid, False) else "unchecked", app._ms_price_tags.get(iid, "price_zero")))

    event = SimpleNamespace(widget=tree, keysym="Down")
    # 不應該爆
    result = st.StrategyGUI._on_tree_key_move(app, event)
    assert result == "break"
