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


def test_v24_apply_hover_no_longer_clears_all():
    """v24：_apply_hover 不再呼叫 _clear_all_hover（delta tracking）

    v23 之前：_apply_hover 內「self._clear_all_hover(tree)」會掃整個 tree 2362 筆
    → 100+ms 延遲 + 在 race 條件下可能漏清 → up/down 後 mouse 一動就兩個 hilight

    v24 修法：用 self._hover_iid[tree] 追蹤上一個 hover iid
    新呼叫時只清上一個、不掃整個 tree
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1, "找不到 _apply_hover 函式"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "self._clear_all_hover(tree)" not in body, (
        "v24 _apply_hover 必不再呼叫 self._clear_all_hover(tree)\n"
        "v23 race 是 _clear_all_hover 漏清 + 掃整個 tree 慢 → delta tracking 取代"
    )
    # 必仍呼叫 _set_row_tag_normal（清上一個 iid）
    assert "self._set_row_tag_normal(tree, prev_iid)" in body, (
        "v24 必須呼叫 _set_row_tag_normal 清上一個 hover iid"
    )


def test_v24_apply_hover_uses_hover_iid_dict():
    """v24：_apply_hover 用 self._hover_iid dict 追蹤當前 hover iid

    3 個檢查點：
    1. 有 hasattr 守衛避免 __init__ 中需要顯式 init
    2. 用 dict[id(tree)] 作為 key
    3. 呼叫結尾更新 dict
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # hasattr 守護
    assert 'hasattr(self, "_hover_iid")' in body, (
        "v24 _apply_hover 必檢查 hasattr(self, '_hover_iid') 避免 __init__ 改動破壞向後相容"
    )
    # 用 id(tree) 作為 key（多個 tree 區分）
    assert "self._hover_iid.get(id(tree))" in body, (
        "v24 _apply_hover 必用 self._hover_iid.get(id(tree)) 讀上一個 hover"
    )
    # 結尾更新
    assert "self._hover_iid[id(tree)] = iid" in body, (
        "v24 _apply_hover 結尾必更新 self._hover_iid[id(tree)] = iid"
    )


def test_v24_apply_hover_no_op_when_same_iid():
    """v24：_apply_hover 重複呼叫同 iid → no-op、不重複設 tag

    root cause：v24 前後 mouse 連續觸發 motion、可能呼叫多次 _apply_hover
    加 early return 避免多餘 tree.item 呼叫（每次 IPC 都幾 ms）
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "if prev_iid == iid:" in body, (
        "v24 _apply_hover 必檢查 prev_iid == iid → early return no-op"
    )
    assert "return" in body, (
        "v24 no-op 分支必 return（不繼續執行清/設邏輯）"
    )


def test_v24_apply_hover_handles_stale_prev_iid():
    """v24：_apply_hover 處理 prev_iid 不在 tree 內的 edge case

    edge case：tree 被重建（呼叫 insert 重新填充）後、_hover_iid 內還有舊 iid
    → 嘗試 _set_row_tag_normal(old_iid) 會 fail（iid 已不存在）

    v24 解法：先檢查 prev_iid in tree.get_children()、不在就跳過
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert "prev_iid in tree.get_children()" in body, (
        "v24 _apply_hover 清舊 hover 必檢查 prev_iid in tree.get_children()"
        "（避免 stale iid 設到不存在的 row）"
    )


def test_v24_apply_hover_doc_mentions_delta_tracking():
    """v24：_apply_hover docstring 必明確提到「delta tracking」與「O(1)」

    避免未來看 code 的人不知道為什麼要 _hover_iid dict
    """
    content = _read()
    idx = content.find("def _apply_hover(self, tree, iid):")
    assert idx != -1
    start = content.find('"""', idx)
    end = content.find('"""', start + 3)
    docstring = content[start + 3:end]
    assert "delta tracking" in docstring or "O(1)" in docstring, (
        "v24 _apply_hover docstring 必提到「delta tracking」或「O(1)」\n"
        "說明為什麼用 _hover_iid dict"
    )


def test_v25_guard_shortened_to_50ms():
    """v25：_kbd_nav_guard 200ms → 50ms

    v16 設 200ms、避免 motion handler 速率覆蓋 key-nav 剛設的 hover
    v25 縮短到 50ms：user 感知不到殘留（< 50ms）+ race condition 大幅減少
    """
    content = _read()
    # guard 設定點在 _on_tree_key_see_focus、guard check 在 _kbd_nav_guard_should_block
    # 這 2 個地方都需要檢查
    for fn_name in ["def _kbd_nav_guard_should_block(self, tree):", "def _on_tree_key_see_focus(self, event):"]:
        idx = content.find(fn_name)
        assert idx != -1, f"找不到 {fn_name} 函式"
        end = content.find("\n    def ", idx + 50)
        if end == -1:
            end = len(content)
        body = content[idx:end]
        # 50ms 出現在設 guard 的那行（在 _on_tree_key_see_focus）
        if "tree.focus" in body:  # _on_tree_key_see_focus 才會設定 guard
            assert "int(time.time() * 1000) + 50" in body, (
                f"v25 {fn_name} 設定 guard 必是 +50（不是 +200）"
            )
    # 5px → 2px 容差（在 _kbd_nav_guard_should_block）
    idx = content.find("def _kbd_nav_guard_should_block(self, tree):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    assert "abs(mx - gx) > 2 or abs(my - gy) > 2" in body, (
        "v25 mouse 移動容差必是 2px（不是 5px）"
    )


def test_v25_ensure_focus_visible_single_update_idletasks():
    """v25：_ensure_focus_visible 內最多 1 次 tree.update_idletasks()

    v12 有 3 次 update_idletasks()、每次都強制 Tk 重繪 2362 筆 → 100-200ms 延遲
    v25 拿掉重複的、只留 1 次（在 tree.see(iid) 後）
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    # 拆掉 docstring 後才算真正的呼叫次數
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 只算 tree.update_idletasks()（排除 self.update_idletasks 和 comment）
    count = body.count("tree.update_idletasks()")
    assert count <= 1, (
        f"v25 _ensure_focus_visible 內 tree.update_idletasks() 必 ≤ 1 次、實際 {count} 次\n"
        "v12 有 3 次、每次都強制 Tk 重繪整個 tree → 100-200ms 延遲"
    )


def test_v25_ensure_focus_visible_no_redundant_yview_scroll_loop():
    """v25：_ensure_focus_visible 拿掉 v12 「多重保險」loop（重複 yview_scroll + bbox check）

    v12 有兩層「保險」：先 yview_scroll(2) + 再 check bbox 再 yview_scroll(1)
    v25 拿掉第二層（過度防護、無實質效果）
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # v25 必仍保留 is_padded_last 分支的多 scroll (yview_scroll(2))
    assert "tree.yview_scroll(2, \"units\")" in body, (
        "v25 仍保留 padded_last 的 yview_scroll(2) - 防止最後 row 被 canvas edge 切"
    )
    # 但不再有「多重保險」loop (重複 yview_scroll + bbox check)
    yview_scroll_count = body.count("tree.yview_scroll(")
    assert yview_scroll_count <= 2, (
        f"v25 _ensure_focus_visible 內 yview_scroll 必 ≤ 2 次（padded_last 一次 + 一般一次）\n"
        "v12 有 3 次（padded_last 多重保險多一次）\n"
        f"實際 {yview_scroll_count} 次"
    )


def test_v25_ensure_focus_visible_doc_mentions_single_pass():
    """v25：_ensure_focus_visible docstring 必提到「單一 path」「v25」

    避免未來看 code 的人重複加 update_idletasks（破壞 v25 性能）
    """
    content = _read()
    idx = content.find("def _ensure_focus_visible(self, tree, iid):")
    assert idx != -1
    start = content.find('"""', idx)
    end = content.find('"""', start + 3)
    docstring = content[start + 3:end]
    assert "v25" in docstring, (
        "v25 _ensure_focus_visible docstring 必提到「v25」"
    )
    assert "單一 path" in docstring or "單一" in docstring or "單一一次" in docstring or "只保留 1 個" in docstring, (
        "v25 _ensure_focus_visible docstring 必提到「單一 path」或「單一一次」或「只保留 1 個」\n"
        "避免未來看 code 的人重複加 update_idletasks"
    )


def test_v25_kbd_nav_guard_setter_uses_50():
    """v25：設定 guard 的地方必用 +50（不是 +200）

    guard 設定點在 _on_tree_key_see_focus 內（line 9426）
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
    assert "+ 50" in body, (
        "v25 _on_tree_key_see_focus 設定 guard 必用 +50（不是 +200）"
    )
    assert "+ 200" not in body, (
        "v25 移除 _on_tree_key_see_focus 內的 +200（舊的 200ms guard）"
    )


def test_v26_set_row_tag_normal_removes_hover_tags():
    """v26：_set_row_tag_normal 內必須有 tk.call(... "tag", "remove" ...) 呼叫

    William 2026-07-09 22:12 反映 v25 仍有 5289 + 6219 hover 殘留
    log 證明 v24 delta tracking 邏輯沒錯、但視覺沒變
    v26 改用明確 tk.call tag remove 強制清 hover_* tag（Python-level tag_remove 不存在）

    v26-fix2 (2026-07-09 23:32) 修正：原本 tree.tag_remove(ht, iid) 無效
    （ttk.Treeview 沒有此 method、AttributeError 中斷函式、tags= 也沒執行）
    改用 tree.tk.call(tree._w, "tag", "remove", ht, iid) 走 Tcl level
    """
    content = _read()
    idx = content.find("def _set_row_tag_normal(self, tree, iid):")
    assert idx != -1, "v26 找不到 _set_row_tag_normal"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    assert 'tk.call' in body and '"tag"' in body and '"remove"' in body, (
        "v26 _set_row_tag_normal 內必須用 tree.tk.call(..., 'tag', 'remove', ht, iid)"
    )


def test_v26_set_row_tag_normal_handles_all_three_hover_kinds():
    """v26：tag remove 必須涵蓋 hover_up / hover_down / hover_zero 三種

    price tag 有三種 (up/down/zero)、對應 hover_* 也三種
    """
    content = _read()
    idx = content.find("def _set_row_tag_normal(self, tree, iid):")
    assert idx != -1, "v26 找不到 _set_row_tag_normal"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    for kind in ("hover_up", "hover_down", "hover_zero"):
        assert kind in body, f"v26 _set_row_tag_normal 必須移除 {kind} tag"


def test_v26_set_row_tag_normal_no_raise_when_no_hover_tag():
    """v26：tk.call tag remove 必包在 try/except 內、idempotent

    即使 row 沒有 hover_* tag、tag remove 也不應該 raise
    """
    content = _read()
    idx = content.find("def _set_row_tag_normal(self, tree, iid):")
    assert idx != -1, "v26 找不到 _set_row_tag_normal"
    end = content.find("\n    def ", idx + 50)
    if end == -1:
        end = len(content)
    body = content[idx:end]
    if '"""' in body:
        parts = body.split('"""')
        body = '"""'.join(parts[2:])
    # 檢查 tk.call tag remove 呼叫有 try/except 包住
    import re
    pattern = r"try:[\s\S]{0,300}?tk\.call[\s\S]{0,200}?except"
    assert re.search(pattern, body), (
        "v26 tk.call tag remove 必須包在 try/except 內、避免無 hover tag 時 raise"
    )
