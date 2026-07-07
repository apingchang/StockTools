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
# 【V1.2.0-kb-focus-v16】Linux X11 XWarpPointer 取代 Windows API
# ==========================================================

def test_v16_move_os_cursor_dispatcher_exists():
    """v16：_move_os_cursor 統一介面必存在"""
    content = _read()
    assert "def _move_os_cursor(self, target_x, target_y):" in content, (
        "v16 必新增 _move_os_cursor 統一介面"
    )


def test_v16_x11_move_cursor_exists():
    """v16：_x11_move_cursor_to 必存在（Linux X11 backend）"""
    content = _read()
    assert "def _x11_move_cursor_to(self, target_x, target_y):" in content, (
        "v16 必新增 _x11_move_cursor_to（Linux X11 backend）"
    )
    # 必用 libX11.so.6
    assert "libX11.so.6" in content, (
        "v16 _x11_move_cursor_to 必載入 libX11.so.6"
    )
    # 必呼叫 XWarpPointer
    assert "XWarpPointer" in content, (
        "v16 _x11_move_cursor_to 必呼叫 X11 XWarpPointer"
    )


def test_v16_mac_move_cursor_exists():
    """v16：_mac_move_cursor_to 必存在（macOS fallback）"""
    content = _read()
    assert "def _mac_move_cursor_to(self, target_x, target_y):" in content, (
        "v16 必新增 _mac_move_cursor_to（macOS backend）"
    )
    assert "CGWarpMouseCursorPosition" in content, (
        "v16 _mac_move_cursor_to 必呼叫 CGWarpMouseCursorPosition"
    )


def test_v16_move_os_cursor_dispatches_by_platform():
    """v16：_move_os_cursor 用 sys.platform 分派"""
    content = _read()
    idx = content.find("def _move_os_cursor(self, target_x, target_y):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "sys.platform" in body, (
        "v16 _move_os_cursor 必用 sys.platform 分派"
    )
    assert "_x11_move_cursor_to" in body, (
        "v16 _move_os_cursor Linux 分派必呼叫 _x11_move_cursor_to"
    )
    assert "_mac_move_cursor_to" in body, (
        "v16 _move_os_cursor macOS 分派必呼叫 _mac_move_cursor_to"
    )


def test_v16_move_cursor_to_row_uses_x11():
    """v16：_move_cursor_to_row 必呼叫 _move_os_cursor（跨平台）"""
    content = _read()
    idx = content.find("def _move_cursor_to_row(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v16 必呼叫 _move_os_cursor（取代 v14 的 _win_move_cursor_to）
    assert "_move_os_cursor" in body, (
        "v16 _move_cursor_to_row 必呼叫 _move_os_cursor（跨平台）"
    )
    # 不應還有 _win_move_cursor_to
    assert "_win_move_cursor_to" not in body, (
        "v16 _move_cursor_to_row 不應再有 _win_move_cursor_to（已被 _move_os_cursor 取代）"
    )


def test_v16_no_v15_sticky_logic():
    """v16：取消 v15 sticky 邏輯（def 定義 + init 初始化）"""
    content = _read()
    # def 定義必須移除
    assert "def _get_sticky_key_nav_iid" not in content, (
        "v16 不應再有 def _get_sticky_key_nav_iid"
    )
    assert "def _set_sticky_key_nav_iid" not in content, (
        "v16 不應再有 def _set_sticky_key_nav_iid"
    )
    # init 初始化也應移除（self._sticky_key_nav_iids = {}）
    assert "self._sticky_key_nav_iids" not in content, (
        "v16 __init__ 不應初始化 _sticky_key_nav_iids"
    )


def test_v16_no_windows_specific_api_in_motion_handler():
    """v16：motion handler 內不應呼叫 Windows API"""
    content = _read()
    # 找所有 motion handler（v16 標準模式）
    for handler in ("_on_select_tree_hover", "_ms_tree_hover", "_etf_tree_hover_combined"):
        idx = content.find(f"def {handler}(self, event):")
        assert idx != -1, f"找不到 {handler}"
        end = content.find("\n    def ", idx + 50)
        if end == -1:
            end = len(content)
        body = content[idx:end]
        if '"""' in body:
            parts = body.split('"""')
            body = '"""'.join(parts[2:])
        assert "windll.user32" not in body, (
            f"v16 {handler} 不應再有 windll.user32（Windows-only）"
        )
        assert "SetCursorPos" not in body, (
            f"v16 {handler} 不應再有 SetCursorPos"
        )


def test_v16_on_tree_key_see_focus_calls_move_cursor():
    """v16：_on_tree_key_see_focus 必呼叫 _move_cursor_to_row"""
    content = _read()
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_move_cursor_to_row" in body, (
        "v16 _on_tree_key_see_focus 必呼叫 _move_cursor_to_row"
    )


def test_v16_x11_with_mock_unit():
    """v16：_x11_move_cursor_to 單元測試（mock libX11）"""
    from types import SimpleNamespace
    import StockTool as st

    x11_calls = []
    x11_libs = SimpleNamespace()
    x11_libs.XOpenDisplay = lambda name: x11_calls.append(("XOpenDisplay", name)) or b"display"
    x11_libs.XWarpPointer = lambda *args: x11_calls.append(("XWarpPointer", args))
    x11_libs.XFlush = lambda d: x11_calls.append(("XFlush", d))
    x11_libs.XCloseDisplay = lambda d: x11_calls.append(("XCloseDisplay", d))

    app = SimpleNamespace()
    # Patch _x11_move_cursor_to to use our mock directly
    import ctypes as _ct
    saved_cdll = _ct.CDLL
    _ct.CDLL = lambda name: x11_libs

    try:
        result = st.StrategyGUI._x11_move_cursor_to(app, 100, 200)
        assert result is True, (
            f"_x11_move_cursor_to 應 return True、實際 {result}"
        )
    finally:
        _ct.CDLL = saved_cdll

    # 檢查 mock 被呼叫
    calls_summary = [c[0] for c in x11_calls]
    assert "XOpenDisplay" in calls_summary, "必呼叫 XOpenDisplay(None)"
    assert "XWarpPointer" in calls_summary, "必呼叫 XWarpPointer(x, y)"
    assert "XFlush" in calls_summary, "必呼叫 XFlush"
    assert "XCloseDisplay" in calls_summary, "必呼叫 XCloseDisplay"


def test_v16_move_os_cursor_dispatch_unit():
    """v16：_move_os_cursor 用 sys.platform 分派（unit test）"""
    from types import SimpleNamespace
    import StockTool as st
    import sys as _sys

    app = SimpleNamespace()
    # Track which backend was called
    call_log = []
    app._x11_move_cursor_to = lambda x, y: call_log.append(("x11", x, y)) or True
    app._mac_move_cursor_to = lambda x, y: call_log.append(("mac", x, y)) or True

    # Mock sys.platform as linux
    saved_platform = _sys.platform
    try:
        _sys.platform = "linux"
        result = st.StrategyGUI._move_os_cursor(app, 100, 200)
        assert call_log[-1][0] == "x11", (
            f"Linux 必呼叫 _x11_move_cursor_to、實際 {call_log}"
        )
    finally:
        _sys.platform = saved_platform

    call_log.clear()
    saved_platform = _sys.platform
    try:
        _sys.platform = "darwin"
        result = st.StrategyGUI._move_os_cursor(app, 300, 400)
        assert call_log[-1][0] == "mac", (
            f"macOS 必呼叫 _mac_move_cursor_to、實際 {call_log}"
        )
    finally:
        _sys.platform = saved_platform
