"""V0.9.5-tab-split-phase3-E 守護：參數區的全選/全不選按鈕已拿掉

William 13:43 反映：篩選結果 console 的勾選欄 header 已可全選/全不選
所以參數區的 📋 全選 / ☐ 全不選 按鈕重複、拿掉

驗證：
- ETF tab 參數區沒「📋 全選」按鈕
- ETF tab 參數區沒「☐ 全不選」按鈕
- 手動選股 tab 參數區沒「📋 全選」按鈕
- 手動選股 tab 參數區沒「☐ 全不選」按鈕
- 但 _etf_select_all / _etf_select_none / _ms_select_all / _ms_select_none methods 仍存在（heading click 仍能觸發全選/全不選）
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


def _extract_etf_btn_row(content):
    """抓 ETF tab 的 btn_row 區段（從 _build_etf_tab 到 _etf_tree 之間的 ttk.Button 群）"""
    # 從 btn_row 開始到 _etf_tree 前的所有按鈕
    m_start = content.find("self._etf_data_status")
    m_end = content.find("self._etf_tree = ttk.Treeview")
    if m_start < 0 or m_end < 0:
        return ""
    return content[m_start:m_end]


def _extract_ms_btn_row(content):
    """抓手動選股 tab 的 btn_row 區段"""
    m_start = content.find("self._ms_dividend_status")
    m_end = content.find("self._ms_tree = ttk.Treeview")
    if m_start < 0 or m_end < 0:
        return ""
    return content[m_start:m_end]


def test_etf_btn_row_no_select_all():
    """ETF tab 參數區沒「📋 全選」按鈕"""
    content = _read()
    btn_row = _extract_etf_btn_row(content)
    assert btn_row, "❌ 找不到 ETF btn_row 區段"
    assert 'text="📋 全選"' not in btn_row, (
        "❌ ETF tab 參數區還有「📋 全選」按鈕！\n"
        "Phase 3 E：拿掉、因為 header checkbox 已能全選"
    )
    print("✅ ETF tab 參數區無「📋 全選」按鈕")


def test_etf_btn_row_no_select_none():
    """ETF tab 參數區沒「☐ 全不選」按鈕"""
    content = _read()
    btn_row = _extract_etf_btn_row(content)
    assert btn_row, "❌ 找不到 ETF btn_row 區段"
    assert 'text="☐ 全不選"' not in btn_row, (
        "❌ ETF tab 參數區還有「☐ 全不選」按鈕！"
    )
    print("✅ ETF tab 參數區無「☐ 全不選」按鈕")


def test_ms_btn_row_no_select_all():
    """手動選股 tab 參數區沒「📋 全選」按鈕"""
    content = _read()
    btn_row = _extract_ms_btn_row(content)
    assert btn_row, "❌ 找不到 ms btn_row 區段"
    assert 'text="📋 全選"' not in btn_row, (
        "❌ 手動選股 tab 參數區還有「📋 全選」按鈕！"
    )
    print("✅ 手動選股 tab 參數區無「📋 全選」按鈕")


def test_ms_btn_row_no_select_none():
    """手動選股 tab 參數區沒「☐ 全不選」按鈕"""
    content = _read()
    btn_row = _extract_ms_btn_row(content)
    assert btn_row, "❌ 找不到 ms btn_row 區段"
    assert 'text="☐ 全不選"' not in btn_row, (
        "❌ 手動選股 tab 參數區還有「☐ 全不選」按鈕！"
    )
    print("✅ 手動選股 tab 參數區無「☐ 全不選」按鈕")


def test_etf_select_methods_still_exist():
    """_etf_select_all / _etf_select_none methods 還在（heading click 仍要能觸發）"""
    content = _read()
    assert "def _etf_select_all" in content, "❌ _etf_select_all method 不見了！"
    assert "def _etf_select_none" in content, "❌ _etf_select_none method 不見了！"
    print("✅ _etf_select_all / _etf_select_none methods 仍存在")


def test_ms_select_methods_still_exist():
    """_ms_select_all / _ms_select_none methods 還在"""
    content = _read()
    assert "def _ms_select_all" in content, "❌ _ms_select_all method 不見了！"
    assert "def _ms_select_none" in content, "❌ _ms_select_none method 不見了！"
    print("✅ _ms_select_all / _ms_select_none methods 仍存在")


def test_etf_heading_click_still_works():
    """ETF heading click 仍能觸發全選/全不選（methods 留著）"""
    content = _read()
    m = re.search(r'def _etf_toggle_check\(.*?\n    def |\Z', content, re.DOTALL)
    assert m, "❌ 找不到 _etf_toggle_check"
    body = m.group(0)
    assert 'region == "heading"' in body, "❌ ETF heading click 處理沒了"
    assert "_etf_select_all" in body and "_etf_select_none" in body, (
        "❌ ETF heading click 沒呼叫 _etf_select_all/_none"
    )
    print("✅ ETF heading click → _etf_select_all/_none 仍正常")


def test_ms_heading_click_still_works():
    """ms heading click 仍能觸發全選/全不選"""
    content = _read()
    m = re.search(r'def _ms_toggle_check\(.*?\n    def |\Z', content, re.DOTALL)
    assert m, "❌ 找不到 _ms_toggle_check"
    body = m.group(0)
    assert 'region == "heading"' in body, "❌ ms heading click 處理沒了"
    assert "_ms_select_all" in body and "_ms_select_none" in body, (
        "❌ ms heading click 沒呼叫 _ms_select_all/_none"
    )
    print("✅ ms heading click → _ms_select_all/_none 仍正常")


def test_context_menu_removed():
    """【V0.9.5-tab-split-phase3-F】右鍵選單的「全選/全不選」已拿掉

    William 13:52 反映：header checkbox 已能全選/全不選、右鍵選單多一重入口多餘
    拿掉 4 個右鍵 handler + 對應 bind
    """
    content = _read()
    # 4 個右鍵 method 都不該存在
    assert "def _on_select_tree_rclick" not in content, (
        "❌ _on_select_tree_rclick 還在！Phase 3 F 應該拿掉"
    )
    assert "def _etf_tree_rclick_new" not in content, (
        "❌ _etf_tree_rclick_new 還在！Phase 3 F 應該拿掉"
    )
    assert "def _ms_tree_rclick" not in content, (
        "❌ _ms_tree_rclick 還在！Phase 3 F 應該拿掉"
    )
    assert "def _ms_show_context_menu" not in content, (
        "❌ _ms_show_context_menu 還在！Phase 3 F 應該拿掉"
    )
    # 右鍵選單內的全選/全不選 command 也不該存在
    assert 'label="☑ 全選"' not in content, "❌ 右鍵選單的「全選」還在"
    assert 'label="☐ 全不選"' not in content, "❌ 右鍵選單的「全不選」還在"
    print("✅ 4 個右鍵 handler + 全選/全不選選單項目已全部拿掉")


if __name__ == "__main__":
    test_etf_btn_row_no_select_all()
    test_etf_btn_row_no_select_none()
    test_ms_btn_row_no_select_all()
    test_ms_btn_row_no_select_none()
    test_etf_select_methods_still_exist()
    test_ms_select_methods_still_exist()
    test_etf_heading_click_still_works()
    test_ms_heading_click_still_works()
    test_context_menu_removed()
    print("\n🎉 9 個 select_buttons_removed test 全綠")