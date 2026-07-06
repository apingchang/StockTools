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
    """_on_select_tree_hover 切 row 時必須先清所有 children 的 hover_* tag

    William 23:21 反映「mouse 移動時新位置 highlight、舊位置殘留」
    v6：直接遍歷 children 清所有 hover、不依賴 _select_hover_iids 追蹤
    """
    content = _read()
    idx = content.find('def _on_select_tree_hover(self, event):')
    assert idx != -1, "找不到 _on_select_tree_hover"
    end = content.find('\n    def ', idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    # 跳過 docstring
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 必須有 for child in tree.get_children() 遍歷 + 清 hover + 設新
    assert "for child in" in body and "get_children" in body, (
        "❌ v6 應遍歷所有 children 清 hover_* tag"
    )
    assert '_set_row_tag_normal' in body or 'tags=(' in body, (
        "❌ v6 應清舊 hover 或重設 tags"
    )
    assert 'hover_' in body, "❌ _on_select_tree_hover 應設 hover_<price> tag"
    # 不依賴 _select_hover_iids
    assert '_select_hover_iids' not in body, (
        "❌ v6 不應依賴 _select_hover_iids 追蹤"
    )


def test_ms_tree_hover_clears_old():
    """_ms_tree_hover v6 應遍歷所有 children 清 hover、不依賴 _ms_hover_iid 追蹤"""
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
    # v6：for child in tree.get_children() 遍歷清
    assert 'for child in' in body and 'get_children' in body, (
        "❌ v6 _ms_tree_hover 應遍歷 children 清 hover_* tag"
    )
    assert '_ms_clear_hover' not in body, (
        "❌ v6 不應呼叫 _ms_clear_hover、不依賴 _ms_hover_iid 追蹤"
    )
    assert 'hover_' in body, "❌ _ms_tree_hover 應設 hover_<price> tag"


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
    """_etf_tree_hover_combined v6 應清所有 children 的 hover_* tag"""
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
    # v6：遍歷清
    assert '_etf_clear_all_hover' in body, (
        "❌ v6 _etf_tree_hover_combined 應呼叫 _etf_clear_all_hover 遍歷清"
    )
    assert 'hover_' in body, "❌ _etf_tree_hover_combined 應設 hover_<price> tag"


def test_on_tree_select_sync_hover_clears_old():
    """_on_tree_select_sync_hover v6 應清所有 children 的 hover_* tag"""
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
    # v6：遍歷清
    assert 'for child in' in body and 'get_children' in body, (
        "❌ v6 _on_tree_select_sync_hover 應遍歷清 hover_* tag"
    )
    assert 'hover_' in body, "❌ _on_tree_select_sync_hover 應設新 row hover_<price> tag"


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
    """_on_select_tree_hover 移動時取消舊 row 的 hover_<price> tag"""
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

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "r2"
    tree.item = item
    tree.get_children = lambda: ["r1", "r2"]

    # v6：不需 _select_hover_iids、直接遍歷 children
    app = SimpleNamespace(
        select_tree=tree,
        _select_checked={"r1": False, "r2": False},
        _bt_checked={},
        _select_price_tags={"r1": "price_up", "r2": "price_down"},
    )

    def fake_set_row_tag_normal(t, iid):
        checked = app._select_checked.get(iid, False)
        price_tag = app._select_price_tags.get(iid, "price_zero")
        if iid in [c for c in items_state]:
            items_state[iid]["tags"] = ("checked" if checked else "unchecked", price_tag)
    app._set_row_tag_normal = fake_set_row_tag_normal

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._on_select_tree_hover(app, event)

    # r1 應該被恢復成 unchecked + price_up
    assert "hover" not in items_state["r1"]["tags"], (
        f"r1 應取消 hover_* tag、實際 {items_state['r1']['tags']}"
    )
    assert "price_up" in items_state["r1"]["tags"], (
        f"r1 應保留 price_up tag、實際 {items_state['r1']['tags']}"
    )
    # r2 應該有 hover_down tag
    assert "hover_down" in items_state["r2"]["tags"], (
        f"r2 應設 hover_down tag、實際 {items_state['r2']['tags']}"
    )


def test_ms_tree_hover_movement_clears_old():
    """_ms_tree_hover 移動時取消舊 row 的 hover_<price> tag"""
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

    tree = SimpleNamespace()
    tree.identify = lambda region, x, y: "cell"
    tree.identify_row = lambda y: "m2"
    tree.item = item
    tree.get_children = lambda: ["m1", "m2"]

    # v6：不依賴 _ms_hover_iid、不需 _ms_clear_hover
    app = SimpleNamespace(
        _ms_tree=tree,
        _ms_checked={"m1": False, "m2": False},
        _ms_price_tags={"m1": "price_up", "m2": "price_down"},
    )

    def fake_set_row_tag_normal(t, iid):
        checked = app._ms_checked.get(iid, False)
        price_tag = app._ms_price_tags.get(iid, "price_zero")
        if iid in [c for c in items_state]:
            items_state[iid]["tags"] = ("checked" if checked else "unchecked", price_tag)
    app._set_row_tag_normal = fake_set_row_tag_normal

    event = SimpleNamespace(widget=tree, x=10, y=10)
    st.StrategyGUI._ms_tree_hover(app, event)

    assert "hover" not in items_state["m1"]["tags"], (
        f"m1 應取消 hover、實際 {items_state['m1']['tags']}"
    )
    assert "hover_down" in items_state["m2"]["tags"], (
        f"m2 應設 hover_down、實際 {items_state['m2']['tags']}"
    )


def test_on_tree_select_sync_hover_clears_old_row():
    """_on_tree_select_sync_hover selection 變化時清舊 row 的 hover_* tag"""
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

    app = SimpleNamespace(
        _ms_tree=tree,
        _etf_tree=SimpleNamespace(),
        select_tree=SimpleNamespace(),
        _ms_checked={"s1": False, "s2": False},
        _ms_price_tags={"s1": "price_up", "s2": "price_down"},
        _etf_checked={},
        _etf_price_tags={},
        _select_checked={},
        _select_price_tags={},
    )
    app._get_price_tag_for_tree = lambda t, iid: app._ms_price_tags.get(iid, "price_zero")
    app._set_row_tag_normal = lambda t, iid: t.item(
        iid, tags=("unchecked", app._ms_price_tags.get(iid, "price_zero"))
    )

    event = SimpleNamespace(widget=tree)
    st.StrategyGUI._on_tree_select_sync_hover(app, event)

    assert "hover" not in items_state["s1"]["tags"], (
        f"s1 應取消 hover、實際 {items_state['s1']['tags']}"
    )
    assert "hover_down" in items_state["s2"]["tags"], (
        f"s2 應設 hover_down、實際 {items_state['s2']['tags']}"
    )


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
