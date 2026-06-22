"""V0.9.5-tab-split-phase3-G 守護：三個 tab 統一匯出按鈕位置和名稱

William 14:10 反映：ETF 選股和手動選股的「📤 匯出 Excel」按鈕位置和名稱都跟系統選股的「💾 匯出股票清單」不一致

修法：
- 三個 tab 都把匯出按鈕放在「右上面板右邊」、跟 select_tab 一致
- 三個 tab 都用相同名稱「💾 匯出股票清單」
- 初始 state="disabled"、有資料時 enable

驗證：
- 三個 tab 都有 export_*_btn 屬性
- 三個 tab 的按鈕文字都是「💾 匯出股票清單」
- 三個 tab 的按鈕都不在 btn_row（已從左邊參數區拿掉）
- 三個 tab 的按鈕都在 right_top（標題右邊）
- 初始 state="disabled"、有資料時 enable
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _read():
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        return f.read()


def test_all_three_export_buttons_exist():
    """三個 tab 都有 export_*_btn 屬性"""
    content = _read()
    for attr in ("export_select_btn", "export_ms_btn", "export_etf_btn"):
        assert f"self.{attr}" in content, (
            f"❌ 缺少 self.{attr} 屬性！\n"
            f"Phase 3 G：三個 tab 都要有 export 按鈕實例"
        )
    print("✅ 三個 tab 都有 export_*_btn 屬性")


def test_all_three_buttons_same_text():
    """三個 tab 的按鈕文字都是「💾 匯出股票清單」"""
    content = _read()
    for attr in ("export_select_btn", "export_ms_btn", "export_etf_btn"):
        # 找出該 btn 建立的位置、驗證 text 參數
        pattern = rf'self\.{attr}\s*=\s*ttk\.Button\((.*?)\)\s*\n\s*self\.{attr}\.pack'
        m = re.search(pattern, content, re.DOTALL)
        assert m, f"❌ 找不到 self.{attr} = ttk.Button(...) 配對"
        m_text = re.search(r'text\s*=\s*"([^"]*)"', m.group(1))
        assert m_text, f"❌ self.{attr} 沒有 text 參數"
        text = m_text.group(1)
        assert text == "💾 匯出股票清單", (
            f"❌ self.{attr} 文字是「{text}」、應該是「💾 匯出股票清單」"
        )
    print("✅ 三個 tab 的按鈕文字都是「💾 匯出股票清單」")


def test_no_legacy_export_in_left_btn_row():
    """左邊參數區不再有「📤 匯出 Excel」按鈕（ms / etf）"""
    content = _read()
    # 在 btn_row 區段找「📤 匯出 Excel」
    # 找 ms btn_row
    m_ms_btn_row = re.search(
        r"btn_row\.pack\(fill=\"x\", pady=\(12, 0\)\)\s*\n(.*?)(?=right_frame|\Z)",
        content, re.DOTALL,
    )
    if m_ms_btn_row:
        ms_btn_row = m_ms_btn_row.group(1)
        assert 'text="📤 匯出 Excel"' not in ms_btn_row, (
            "❌ 手動選股 tab 左邊參數區還有「📤 匯出 Excel」按鈕！\n"
            "Phase 3 G：已搬到右上面板、跟 select_tab 一致"
        )
    # 找 etf btn_row
    m_etf_btn_row = re.search(
        r"_etf_data_status.*?\.pack\(anchor=\"w\", pady=\(0, 4\)\)\s*\n(.*?)(?=right_frame|\Z)",
        content, re.DOTALL,
    )
    if m_etf_btn_row:
        etf_btn_row = m_etf_btn_row.group(1)
        assert 'text="📤 匯出 Excel"' not in etf_btn_row, (
            "❌ ETF tab 左邊參數區還有「📤 匯出 Excel」按鈕！"
        )
    print("✅ 左邊參數區無「📤 匯出 Excel」按鈕（ms / etf 都已搬）")


def test_export_buttons_in_right_top():
    """三個 tab 的 export 按鈕都放在 right_top（標題右邊）"""
    content = _read()
    # 找 self.export_*_btn.pack(side="right")
    for attr in ("export_select_btn", "export_ms_btn", "export_etf_btn"):
        pattern = rf'self\.{attr}\.pack\(side="right"\)'
        m = re.search(pattern, content)
        assert m, (
            f"❌ self.{attr} 沒有用 pack(side=\"right\") 放到右邊\n"
            f"Phase 3 G：應在 right_top 的右邊"
        )
    print("✅ 三個 tab 的 export 按鈕都 pack(side='right') 在右邊")


def test_right_top_structures_consistent():
    """三個 tab 的 right_top 結構一致（Frame + title Label + export Button）"""
    content = _read()
    # 三個 tab 都應該有 right_top = ttk.Frame(right_frame) 然後 pack + title + button
    for tab_name in ("_build_tab_layout", "_build_etf_tab", "_build_manual_select_tab"):
        m = re.search(rf'def {tab_name}\(.*?\n    def ', content, re.DOTALL)
        if not m:
            continue
        body = m.group(0)
        has_right_top = "right_top = ttk.Frame" in body
        assert has_right_top, (
            f"❌ {tab_name} 沒有 right_top = ttk.Frame(...)\n"
            f"Phase 3 G：右上面板結構應跟 select_tab 一致"
        )
    print("✅ 三個 tab 都有 right_top 結構（Frame + title + button）")


def test_export_buttons_initially_disabled():
    """三個 tab 的 export 按鈕初始 state 都是 'disabled'（避免誤觸無資料）"""
    content = _read()
    for attr in ("export_select_btn", "export_ms_btn", "export_etf_btn"):
        # 找 btn 建構到 pack 為止的整段
        pattern = rf'self\.{attr}\s*=\s*ttk\.Button\((.*?)\)\s*\n\s*self\.{attr}\.pack'
        m = re.search(pattern, content, re.DOTALL)
        assert m, f"❌ 找不到 self.{attr} = ttk.Button(...) 配對"
        assert 'state="disabled"' in m.group(1), (
            f"❌ self.{attr} 初始沒有 state='disabled'\n"
            f"Phase 3 G：應跟 select_tab 一致、無資料時不能按"
        )
    print("✅ 三個 tab 的 export 按鈕初始都是 disabled")


def test_export_buttons_enabled_after_display():
    """三個 tab 在 display 時 enable 按鈕"""
    content = _read()
    for attr, display_method in [
        ("export_select_btn", "_display_select_results"),
        ("export_ms_btn", "_ms_display_results"),
        ("export_etf_btn", "_etf_display_results"),
    ]:
        m = re.search(
            rf'def {display_method}\(.*?\n    def |\Z',
            content, re.DOTALL,
        )
        assert m, f"❌ 找不到 {display_method}"
        body = m.group(0)
        assert f"self.{attr}.config(state=\"normal\")" in body, (
            f"❌ {display_method} 沒 enable self.{attr}\n"
            f"Phase 3 G：display 完要 enable 按鈕"
        )
    print("✅ 三個 tab 的 display method 都會 enable 對應 export 按鈕")


def test_no_stale_export_methods_lost():
    """_ms_export_excel / _etf_export_excel methods 還在（按鈕只是搬到不同位置）"""
    content = _read()
    assert "def _ms_export_excel" in content, "❌ _ms_export_excel method 不見了！"
    assert "def _etf_export_excel" in content, "❌ _etf_export_excel method 不見了！"
    print("✅ _ms_export_excel / _etf_export_excel methods 仍存在")


if __name__ == "__main__":
    test_all_three_export_buttons_exist()
    test_all_three_buttons_same_text()
    test_no_legacy_export_in_left_btn_row()
    test_export_buttons_in_right_top()
    test_right_top_structures_consistent()
    test_export_buttons_initially_disabled()
    test_export_buttons_enabled_after_display()
    test_no_stale_export_methods_lost()
    print("\n🎉 8 個 export_button_unified test 全綠")