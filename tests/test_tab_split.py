"""V0.9.5-tab-split 結構守護

2026-06-20 階段 1：把舊「策略參數」tab 拆成 2 個新 tab（系統選股 + 回測模擬）
並把 console 搬到底部（全域共用）
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_no_legacy_strategy_tab():
    """不應再有舊的「策略參數」tab（已拆分為 系統選股 + 回測模擬）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "text=\"⚙️ 策略參數\"" not in content, (
        "❌ 還有「⚙️ 策略參數」tab！\n"
        "V0.9.5-tab-split：應拆分為「系統選股」+「回測模擬」"
    )
    assert "strategy_tab = ttk.Frame" not in content, (
        "❌ 還有 strategy_tab 變數！\n"
        "V0.9.5-tab-split：應改用 self.select_tab / self.backtest_tab"
    )
    print("✅ 沒有舊 strategy_tab")


def test_has_select_tab():
    """必須有「系統選股」tab"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "self.select_tab" in content, "❌ 缺少 self.select_tab"
    assert "text=\"📊 系統選股\"" in content, "❌ 缺少「系統選股」tab"
    print("✅ 有「📊 系統選股」tab")


def test_has_backtest_tab():
    """必須有「回測模擬」tab"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "self.backtest_tab" in content, "❌ 缺少 self.backtest_tab"
    assert "text=\"🧪 回測模擬\"" in content, "❌ 缺少「回測模擬」tab"
    print("✅ 有「🧪 回測模擬」tab")


def test_console_is_global_at_bottom():
    """console 應為全域、在視窗底部（有 scroll bar）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # self.console 必須在 notebook 外（沒有被加到 notebook）
    # 找 self.notebook.add( 區塊、確認沒有 console 在內
    notebook_adds = re.findall(r"self\.notebook\.add\(([^)]+)\)", content)
    for arg in notebook_adds:
        assert "console" not in arg.lower(), (
            f"❌ console 還在某個 tab 內！notebook.add({arg})\n"
            f"V0.9.5-tab-split：console 應為全域、不屬於任何 tab"
        )

    # V0.9.5-tab-split-fix2：console_container 用 side="bottom" pack
    assert 'side="bottom"' in content, (
        "❌ console_container 沒有 side='bottom'！\n"
        "V0.9.5-tab-split-fix2：用 Frame + pack、console 在底"
    )
    print("✅ console 為全域、放在 side='bottom'")


def test_use_grid_not_paned():
    """V0.9.5-tab-split-fix3：用 grid 切上下兩列、不是 PanedWindow

    PanedWindow 在 Win10/Win11 不可靠
    pack(in_=top_frame) 不會 reparent notebook
    改用 grid：root 分兩列、row 0 = top_frame（expand）、row 1 = console（固定 180px）
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 不應該有 outer_paned
    assert "outer_paned" not in content, "❌ 不應再用 PanedWindow"

    # 必須有 grid_rowconfigure
    assert "grid_rowconfigure" in content, "❌ 缺少 grid_rowconfigure（控制上下比例）"
    assert "_top_frame.grid(" in content or "self._top_frame.grid(" in content, (
        "❌ top_frame 沒有用 grid 排版"
    )
    assert "console_container.grid(" in content, (
        "❌ console_container 沒有用 grid 排版"
    )
    print("✅ 用 grid 切上下兩列（不用 PanedWindow）")


def test_notebook_master_is_top_frame():
    """notebook 必須以 _top_frame 為 master（pack(in_=...) 不可靠）

    之前犯的錯：notebook 一開始建在 self (root)、後來 pack(in_=top_frame)
    Tk 不會真的 reparent、所以 notebook 還是 root 的 child、跟 top_frame 疊在一起。
    修法：notebook 建構時就直接以 _top_frame 為 master。
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # notebook 建構必須以 _top_frame 為 parent
    m = re.search(r"self\.notebook\s*=\s*ttk\.Notebook\(\s*([^)]+)\)", content)
    assert m, "❌ 找不到 self.notebook = ttk.Notebook(...)"
    parent = m.group(1).strip()
    assert parent == "self._top_frame", (
        f"❌ notebook 的 parent 是「{parent}」、應該是「self._top_frame」！\n"
        f"用 root 或 self 會導致 notebook 跟 top_frame 疊在一起（William 21:54 反映）"
    )

    # 不應該有 pack(in_=...)
    assert "notebook.pack(in_=" not in content, (
        "❌ 不應再用 notebook.pack(in_=...)！\n"
        "Tk 的 pack(in_=...) 不會真的 reparent widget"
    )
    print("✅ notebook 直接以 _top_frame 為 master（不用 pack reparent）")


def test_console_has_vertical_and_horizontal_scrollbar():
    """console 應有 vertical + horizontal 兩種 scrollbar"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "console_scrollbar_y" in content, "❌ 缺少 vertical scrollbar (console_scrollbar_y)"
    assert "console_scrollbar_x" in content, "❌ 缺少 horizontal scrollbar (console_scrollbar_x)"
    print("✅ console 有 vertical + horizontal scrollbar")


def test_backtest_placeholder_method_exists():
    """必須有 _build_backtest_placeholder method"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "def _build_backtest_placeholder" in content, (
        "❌ 缺少 _build_backtest_placeholder method"
    )
    print("✅ 有 _build_backtest_placeholder method")


def test_existing_tabs_unchanged():
    """買賣記錄、手動選股、ETF 三個 tab 應仍存在"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    for tab_text in ["📒 買賣記錄", "🔍 手動選股", "📊 主動式 ETF"]:
        assert tab_text in content, f"❌ 缺少 {tab_text} tab"
    print("✅ 買賣記錄、手動選股、ETF 三個 tab 仍在")


def test_tabs_count_is_5():
    """應該有 5 個 tab（系統選股、回測模擬、買賣記錄、手動選股、ETF）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    notebook_adds = re.findall(r"self\.notebook\.add\(", content)
    assert len(notebook_adds) == 5, (
        f"❌ 預期 5 個 tab、實際 {len(notebook_adds)} 個\n"
        f"應為：系統選股、回測模擬、買賣記錄、手動選股、ETF"
    )
    print(f"✅ 5 個 tab 全到位")
