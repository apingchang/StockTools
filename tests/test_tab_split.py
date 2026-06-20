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

    # console 應在 outer_paned 內
    assert "outer_paned" in content, "❌ 缺少 outer_paned（上下分割）"
    assert "outer_paned.add(console_container" in content, (
        "❌ console 沒有被加到 outer_paned"
    )

    # 關鍵守護：console_container 必須是 outer_paned 的 child、不是 self 的 child
    # 抓錯 parent 會讓 console 顯示在 root 視窗、notebook 區域變空白
    m = re.search(r"console_container = ttk\.LabelFrame\(\s*([^,]+),", content)
    assert m, "❌ 找不到 console_container 宣告"
    parent = m.group(1).strip()
    assert parent == "outer_paned", (
        f"❌ console_container 的 parent 是「{parent}」、應該是「outer_paned」！\n"
        f"若是「self」會導致 console 直接放 root 視窗、\n"
        f"outer_paned 的 notebook 區域就會被擠壓變空白（William 21:27 反映）"
    )
    print("✅ console 為全域、放在 outer_paned 底部、parent 正確")


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
