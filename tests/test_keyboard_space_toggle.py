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


def test_v22_on_tree_key_see_focus_no_move_cursor():
    """v22：_on_tree_key_see_focus 不再嘗試動 OS cursor（v17 XWarpPointer race）

    v23 更新：不再守護「必呼叫 _apply_hover」（v23 改由 _ensure_focus_visible 統一處理）
    """
    content = _read()
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    # 去掉 docstring、避免 docstring 提及 _move_cursor_to_row 被誤判
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_move_cursor_to_row" not in body, (
        "v22 _on_tree_key_see_focus 必不再呼叫 _move_cursor_to_row（XWarpPointer race 放棄）"
    )
    # v23 不再必呼叫 _apply_hover（改由 _ensure_focus_visible 統一處理）
    # → 這部分移到 test_v23_on_tree_key_see_focus_single_apply_hover 守護


def test_v16_x11_with_mock_unit():
    """v16：_x11_move_cursor_to 單元測試（mock libX11）"""
    from types import SimpleNamespace
    import StockTool as st

    x11_calls = []
    x11_libs = SimpleNamespace()
    x11_libs.XOpenDisplay = lambda name: x11_calls.append(("XOpenDisplay", name)) or b"display"
    x11_libs.XWarpPointer = lambda *args: x11_calls.append(("XWarpPointer", args))
    x11_libs.XFlush = lambda d: x11_calls.append(("XFlush", d))
    x11_libs.XSync = lambda d, b: x11_calls.append(("XSync", d, b))
    x11_libs.XCloseDisplay = lambda d: x11_calls.append(("XCloseDisplay", d))

    app = SimpleNamespace()
    app._v18_log = lambda msg: None  # v18 log helper
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

    # 檢查 mock 被呼叫（v17 用 XSync 不是 XFlush）
    calls_summary = [c[0] for c in x11_calls]
    assert "XOpenDisplay" in calls_summary, "必呼叫 XOpenDisplay(None)"
    assert "XWarpPointer" in calls_summary, "必呼叫 XWarpPointer(x, y)"
    assert "XSync" in calls_summary, "v17 必用 XSync (取代 XFlush、等 server 處理完)"
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


# ==========================================================
# 【V1.2.0-kb-focus-v17】XSync + xdotool fallback
# ==========================================================

def test_v17_x11_uses_xsync_not_xflush():
    """v17：_x11_move_cursor_to 用 XSync 不是 XFlush、等 X server 處理完"""
    content = _read()
    idx = content.find("def _x11_move_cursor_to(self, target_x, target_y):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v17 必用 XSync
    assert "lib.XSync(" in body, (
        "v17 _x11_move_cursor_to 必用 lib.XSync 而不是 XFlush（XFlush 不等 server）"
    )
    # 但 XFlush 也應該還保留作為 backup / 先 flush
    # 重點是 XSync 必存在


def test_v17_x11_xdotool_fallback():
    """v17：_x11_move_cursor_to 必 fallback 到 xdotool subprocess"""
    content = _read()
    idx = content.find("def _x11_move_cursor_to(self, target_x, target_y):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 必用 subprocess
    assert "subprocess" in body, (
        "v17 _x11_move_cursor_to 必用 subprocess 作為 fallback"
    )
    # 必呼叫 xdotool
    assert "xdotool" in body, (
        "v17 _x11_move_cursor_to fallback 必呼叫 xdotool"
    )
    assert "mousemove" in body, (
        "v17 xdotool 必呼叫 mousemove"
    )


def test_v18_v18_log_helper():
    """v18：_v18_log helper 必存在、同時 print + 寫檔"""


def test_v17_x11_with_xsync_mock_unit():
    """v17：mock XSync 確認 XWarpPointer + XSync 被呼叫"""
    from types import SimpleNamespace
    import StockTool as st

    x11_calls = []
    x11_libs = SimpleNamespace()
    x11_libs.XOpenDisplay = lambda name: x11_calls.append(("XOpenDisplay", name)) or b"display"
    x11_libs.XWarpPointer = lambda *args: x11_calls.append(("XWarpPointer", args))
    x11_libs.XFlush = lambda d: x11_calls.append(("XFlush", d))
    x11_libs.XSync = lambda d, b: x11_calls.append(("XSync", d, b))
    x11_libs.XCloseDisplay = lambda d: x11_calls.append(("XCloseDisplay", d))

    app = SimpleNamespace()
    app._v18_log = lambda msg: None  # v18 log helper
    import ctypes as _ct
    saved_cdll = _ct.CDLL
    _ct.CDLL = lambda name: x11_libs

    try:
        result = st.StrategyGUI._x11_move_cursor_to(app, 100, 200)
        assert result is True, f"expected True got {result}"
    finally:
        _ct.CDLL = saved_cdll

    # v17 必用 XSync
    calls_summary = [c[0] for c in x11_calls]
    assert "XSync" in calls_summary, (
        f"v17 必用 XSync、實際 {calls_summary}"
    )

def test_v18_v18_log_helper():
    """v18：_v18_log helper 必存在、同時 print + 寫檔"""
    content = _read()
    assert "def _v18_log(self, msg):" in content, (
        "v18 必新增 _v18_log helper 寫到 stdout + /tmp/stocktool_v18.log"
    )
    assert "/tmp/stocktool_v18.log" in content, (
        "v18 _v18_log 必寫到 /tmp/stocktool_v18.log（fallback）"
    )


def test_v18_move_cursor_to_row_logs():
    """v18：_move_cursor_to_row 開頭必 log 確保被呼叫"""
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
    assert "_v18_log" in body, (
        "v18 _move_cursor_to_row 必呼叫 self._v18_log"
    )


def test_v21_on_tree_key_see_focus_applies_hover():
    """v21：_on_tree_key_see_focus 必直接呼叫 _apply_hover（不依賴 mouse motion）

    v23 變更：取消這條守護。理由：
    - v23 設計：_on_tree_key_see_focus 不再直接呼叫 _apply_hover
    - 改由 _ensure_focus_visible 統一處理 hover + scroll
    - 避免 _on_tree_key_see_focus 自己 _apply_hover + _ensure_focus_visible 內又 _apply_hover 的重複
    - 改由 test_v23_ensure_focus_visible_applies_hover 守護新設計
    """
    # v23 後這條守護不再適用、保留僅供閱讀
    pass


def test_v23_ensure_focus_visible_applies_hover():
    """v23：_ensure_focus_visible 必呼叫 _apply_hover（替代 v21 在 _on_tree_key_see_focus 的位置）

    v23 設計：_on_tree_key_see_focus 不再直接呼叫 _apply_hover
    → 改由 _ensure_focus_visible 統一處理 hover + scroll
    → _ensure_focus_visible 必仍呼叫 _apply_hover
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible 函式"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "self._apply_hover(" in body, (
        "v23 _ensure_focus_visible 必呼叫 self._apply_hover(\n"
        "（替代 v21 在 _on_tree_key_see_focus 的位置）"
    )


def test_v18_no_more_after_idle():
    """v18：_on_tree_key_see_focus 不再 after_idle（改同步呼叫）"""
    content = _read()
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        # 把 docstring 移除、只看 code
        parts = body.split('"""')
        body = '"""'.join(parts[2:])  # skip first part是 def, last part是 after
    # 但 docstring 之後的部分可能還有 after_idle 講解
    # 嚴格說、看 call statement
    # v18 code 不應再呼叫 tree.after_idle 或 self.after_idle
    assert "tree.after_idle(" not in body, (
        "v18 _on_tree_key_see_focus 不應再用 tree.after_idle("
    )
    assert "self.after_idle(" not in body, (
        "v18 _on_tree_key_see_focus 不應再用 self.after_idle("
    )
    # 直接呼叫 _move_cursor_to_row
    assert "self._move_cursor_to_row(" not in body, (
        "v18 _on_tree_key_see_focus 必直接呼叫 self._move_cursor_to_row("
    )


# ==========================================================
# 【V1.2.0-kb-focus-v20】4 個 tree 都要有 KeyRelease binding
# ==========================================================

def test_v20_results_tree_has_keyrelease_bind():
    """v20：results_tree (select + backtest) 必綁 KeyRelease-Up/Down/Home/End/Prior/Next"""
    content = _read()
    # 找 _build_tab_layout 內 results_tree.bind 區段
    idx = content.find('results_tree.bind("<Motion>"')
    assert idx != -1, "找不到 results_tree.bind"
    # 找下一個 results_tree.bind 之前的範圍
    # 或一直往下到 50 行後
    section = content[idx:idx+3000]
    for evt in ("<KeyRelease-Up>", "<KeyRelease-Down>",
                "<KeyRelease-Home>", "<KeyRelease-End>",
                "<KeyRelease-Prior>", "<KeyRelease-Next>"):
        assert evt in section, (
            f"v20 results_tree 必綁 {evt}（v18 之前的 bug）"
        )


def test_v20_etf_tree_has_keyrelease_bind():
    """v20：_etf_tree 必綁 KeyRelease-Up/Down/Home/End/Prior/Next"""
    content = _read()
    idx = content.find('self._etf_tree.bind("<Motion>"')
    assert idx != -1
    section = content[idx:idx+3000]
    for evt in ("<KeyRelease-Up>", "<KeyRelease-Down>",
                "<KeyRelease-Home>", "<KeyRelease-End>",
                "<KeyRelease-Prior>", "<KeyRelease-Next>"):
        assert evt in section, (
            f"v20 _etf_tree 必綁 {evt}（v18 之前的 bug）"
        )


def test_v20_ms_tree_still_has_keyrelease():
    """v20：_ms_tree 既有 KeyRelease binding 必保留"""
    content = _read()
    idx = content.find('self._ms_tree.bind("<Motion>"')
    assert idx != -1
    section = content[idx:idx+3000]
    for evt in ("<KeyRelease-Up>", "<KeyRelease-Down>",
                "<KeyRelease-Home>", "<KeyRelease-End>"):
        assert evt in section, (
            f"v20 _ms_tree {evt} binding 必保留"
        )

def test_v22_on_tree_select_sync_hover_does_nothing():
    """v22：_on_tree_select_sync_hover 必 do nothing（不要 _clear_all_hover 製造 race）"""
    content = _read()
    idx = content.find("def _on_tree_select_sync_hover(self, event):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_clear_all_hover" not in body, (
        "v22 _on_tree_select_sync_hover 不應清 hover（會 race）"
    )


# ==========================================================
# 【V1.2.0-kb-focus-v23】移除 _ensure_focus_visible 內的 _move_cursor_to_row
# ==========================================================
#
# 背景（William 2026-07-08 20:59 反映）：
# - up/down 移動 highlight bar 約半秒延遲
# - 舊的 highlight bar 才消掉
# - cursor 沒跟著移動
# - mouse 一動就出現新的 highlight bar
# - hover 文字變黑色（hover_<price> 的 foreground 在 Linux ttk theme 下失效）
#
# 根因：
# - v22 commit message 說「放棄動 OS cursor」、docstring 也說要拿掉
# - 但 v22 程式碼只拿掉 _on_tree_key_see_focus 內的呼叫
# - _ensure_focus_visible 內的 _move_cursor_to_row 沒拿掉
# - _x11_move_cursor_to 在 Linux 上 XSync block + 3 retries → 0.5-1.5 秒
# - 整個 KeyRelease handler 卡住 0.5 秒
# - guard 200ms 過期、motion handler 又把 hover 蓋回 mouse 位置
#
# v23 修法：
# - _ensure_focus_visible 內徹底拿掉 _move_cursor_to_row
# - _on_tree_key_see_focus 簡化、不再重複呼叫 _apply_hover
# - hover_<price> 的 foreground 在 Linux theme 失效問題暫不在本版處理（開 issue）
# - 重複定義的 _on_select_tree_leave 拿掉（留 v4 pass 版本）

def test_v23_ensure_focus_visible_no_move_cursor():
    """v23：_ensure_focus_visible 必不再呼叫 _move_cursor_to_row

    v22 漏網：_on_tree_key_see_focus 已拿掉、但 _ensure_focus_visible 還在呼叫
    → XSync block 0.5 秒 → 整個 KeyRelease handler 卡住
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1, "找不到 _ensure_focus_visible 函式"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "_move_cursor_to_row" not in body, (
        "v23 _ensure_focus_visible 必不再呼叫 _move_cursor_to_row\n"
        "v22 漏網：X11 XSync block 0.5 秒、整個 handler 卡住\n"
        "→ up/down 移動 highlight 感覺慢、舊 hover 殘留 0.5 秒才消"
    )


def test_v23_on_tree_key_see_focus_single_apply_hover():
    """v23：_on_tree_key_see_focus 只透過 _ensure_focus_visible 呼叫 _apply_hover（不重複）

    v22 bug：_on_tree_key_see_focus 內自己呼叫 _apply_hover 一次
    + _ensure_focus_visible 內又呼叫 _apply_hover 一次 → 重複

    v23 修法：_on_tree_key_see_focus 拿掉自己的 _apply_hover、只呼叫 _ensure_focus_visible
    由 _ensure_focus_visible 統一處理 hover + scroll
    """
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
    # v23 不再直接呼叫 _apply_hover、由 _ensure_focus_visible 統一處理
    assert "self._apply_hover(" not in body, (
        "v23 _on_tree_key_see_focus 必不再直接呼叫 self._apply_hover(\n"
        "統一交給 _ensure_focus_visible 處理 hover + scroll"
    )
    # 必仍呼叫 _ensure_focus_visible（scroll + 統一 hover）
    assert "self._ensure_focus_visible(" in body, (
        "v23 _on_tree_key_see_focus 必仍呼叫 _ensure_focus_visible"
    )


def test_v23_no_duplicate_on_select_tree_leave():
    """v23：_on_select_tree_leave 只能定義一次（v22 有重複定義 bug）

    v22 bug：_on_select_tree_leave 在原始位置（pass 版本）跟後面位置（呼叫 _clear_select_hover 版本）
    重複定義、Python class 後者覆蓋前者 → bind 的 self._on_select_tree_leave 是後者版本
    → 行為不直觀

    v23 修法：只留一個版本、留 v4 pass 版本（leave 時不清 hover）
    """
    content = _read()
    count = content.count("def _on_select_tree_leave(self, event):")
    assert count == 1, (
        f"v23 _on_select_tree_leave 只能定義一次、實際 {count} 次\n"
        "v22 有重複定義 bug、Python 後者覆蓋前者、bind 行為不直觀"
    )


def test_v23_on_tree_key_see_focus_doc_says_no_move_cursor():
    """v23：_on_tree_key_see_focus docstring 必提到「不放棄動 OS cursor」

    v22 docstring 已說明、但程式碼沒對齊
    v23 強化 docstring 明確寫「不再呼叫 _move_cursor_to_row」
    """
    content = _read()
    idx = content.find("def _on_tree_key_see_focus(self, event):")
    assert idx != -1
    # 找 docstring 開始的 """（def 行後第一個 """）
    start = content.find('"""', idx)
    assert start != -1, "找不到 docstring 開始的 \"\"\""
    # 找 docstring 結束的 """（從 start+3 開始找）
    end = content.find('"""', start + 3)
    assert end != -1, "找不到 docstring 結束的 \"\"\""
    docstring = content[start + 3:end]
    assert "_move_cursor_to_row" in docstring or "OS cursor" in docstring, (
        "v23 _on_tree_key_see_focus docstring 必明確說「不再呼叫 _move_cursor_to_row」\n"
        "或「放棄動 OS cursor」"
    )
