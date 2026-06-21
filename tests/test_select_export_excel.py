"""
【V0.9.5-tab-split-phase3-B3】系統選股「💾 匯出股票清單」按鈕 test

【測試範圍】
1. _export_select_results_excel method 存在
2. 沒 _last_select_df → 跳 warning、不存檔
3. 有 df → 真的寫出 .xlsx
4. 預設檔名含 系統選股_ 跟時間戳
5. 匯出檔含股票代號欄位
6. 按鈕存在、初始 disabled
7. _display_select_results 後按鈕 enable
8. 匯出格式可被 load_stock_list_from_excel 讀

【驗證】
- pytest tests/test_select_export_excel.py → 8 個全綠
"""
import os
import sys
import inspect
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# 跟其他 test 一樣、把 source/ 加到 sys.path 才能 import StockTool
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


def _make_app_mock(last_select_df=None):
    """建一個 SimpleNamespace 模擬 GUI instance

    StrategyGUI 是 Tkinter widget、__getattr__ 會遞迴呼叫 self.tk
    → 用 SimpleNamespace 繞過 Tk、只給 _export_select_results_excel 需要的屬性
    """
    return SimpleNamespace(
        _last_select_df=last_select_df,
        _select_checked={},  # 【V0.9.5-tab-split-phase3-C】新屬性
        logger=MagicMock(),  # logger.log 是 mock、不會做事
    )


# ============================================================
# Test 1: _export_select_results_excel method 存在
# ============================================================
def test_export_method_exists():
    """_export_select_results_excel method 在 StockTool.py 內定義"""
    from source.StockTool import StrategyGUI  # type: ignore

    assert hasattr(StrategyGUI, "_export_select_results_excel")
    method = getattr(StrategyGUI, "_export_select_results_excel")
    assert callable(method)
    print("✅ _export_select_results_excel method 已定義")


# ============================================================
# Test 2: 沒 _last_select_df → 跳 warning、不存檔
# ============================================================
def test_export_no_data_warning():
    """沒 _last_select_df → messagebox.showwarning、不存檔"""
    from source.StockTool import StrategyGUI  # type: ignore

    warnings_caught = []
    save_called = []

    def fake_showwarning(title, msg, **kwargs):
        warnings_caught.append((title, msg))

    def fake_save(*a, **kw):
        save_called.append(True)
        return "/tmp/should_not_be_called.xlsx"

    # 沒設 _last_select_df
    app = _make_app_mock(last_select_df=None)

    with patch("tkinter.messagebox.showwarning", fake_showwarning), \
         patch("tkinter.filedialog.asksaveasfilename", fake_save):
        StrategyGUI._export_select_results_excel(app)

    assert len(warnings_caught) == 1, f"應跳 1 個 warning、實際 {len(warnings_caught)}"
    assert "無資料" in warnings_caught[0][0]
    assert save_called == [], f"不應呼叫 asksaveasfilename、實際 {save_called}"
    print("✅ 沒資料 → 跳 warning、不存檔")


# ============================================================
# Test 3: 有 df → 真的寫出 .xlsx
# ============================================================
def test_export_writes_xlsx(tmp_path):
    """有 _last_select_df + 已勾選 → 真的寫出 .xlsx"""
    from source.StockTool import StrategyGUI  # type: ignore
    from openpyxl import load_workbook

    df = pd.DataFrame({
        "股票代號": ["2330", "2317", "2454"],
        "股票名稱": ["台積電", "鴻海", "聯發科"],
        "股價": [1080.0, 215.0, 1485.0],
        "Score": [0.95, 0.88, 0.85],
    })
    app = _make_app_mock(last_select_df=df)
    app._select_checked = {"2330": True, "2317": True, "2454": True}  # 模擬已勾選

    out_path = tmp_path / "test_export.xlsx"
    out_path_str = str(out_path)

    with patch("tkinter.filedialog.asksaveasfilename", return_value=out_path_str), \
         patch("tkinter.messagebox.showinfo"), \
         patch("tkinter.messagebox.showerror"):
        StrategyGUI._export_select_results_excel(app)

    # 驗證檔案存在
    assert out_path.exists(), f"xlsx 沒被建立: {out_path}"

    # 驗證內容
    wb = load_workbook(out_path_str)
    ws = wb.active
    rows = list(ws.values)
    assert len(rows) == 4, f"應 4 列（1 header + 3 data）、實際 {len(rows)}"
    assert rows[0][0] == "股票代號"
    assert rows[1][0] == "2330"
    assert rows[1][1] == "台積電"
    print(f"✅ xlsx 寫出成功：{out_path}（4 rows: 1 header + 3 data）")


# ============================================================
# Test 4: 預設檔名含 系統選股_ 跟時間戳
# ============================================================
def test_export_filename_default():
    """filedialog 的 initialfile 預設是 系統選股_YYYYMMDD_HHMM.xlsx"""
    from datetime import datetime
    from source.StockTool import StrategyGUI  # type: ignore

    src = Path(__file__).parent.parent / "source" / "StockTool.py"
    content = src.read_text(encoding="utf-8")

    # 沒那麼嚴格：只檢查 initialfile 包含 系統選股_ + .xlsx
    assert "initialfile=f\"系統選股_" in content, "initialfile 應為 系統選股_XXX.xlsx"
    assert ".xlsx\"" in content
    # 進一步：時間格式 %Y%m%d_%H%M
    assert "%Y%m%d_%H%M" in content
    print("✅ 預設檔名格式：系統選股_YYYYMMDD_HHMM.xlsx")


# ============================================================
# Test 5: 匯出檔含股票代號欄位
# ============================================================
def test_export_xlsx_contains_stock_codes(tmp_path):
    """匯出 xlsx 的第一欄 header 必須是 股票代號（load_stock_list_from_excel 識別用）"""
    from source.StockTool import StrategyGUI  # type: ignore
    from openpyxl import load_workbook

    df = pd.DataFrame({
        "股票代號": ["2330", "6669"],
        "股票名稱": ["台積電", "緯穎"],
        "股價": [1080.0, 5130.0],
    })
    app = _make_app_mock(last_select_df=df)
    app._select_checked = {"2330": True, "6669": True}  # 模擬已勾選

    out_path = tmp_path / "test_codes.xlsx"

    with patch("tkinter.filedialog.asksaveasfilename", return_value=str(out_path)), \
         patch("tkinter.messagebox.showinfo"), \
         patch("tkinter.messagebox.showerror"):
        StrategyGUI._export_select_results_excel(app)

    wb = load_workbook(str(out_path))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert "股票代號" in headers, f"第一欄應為「股票代號」、實際：{headers}"
    # 驗證 2 筆資料
    assert ws.cell(row=2, column=1).value == "2330"
    assert ws.cell(row=3, column=1).value == "6669"
    print(f"✅ xlsx 包含「股票代號」欄：{headers}")


# ============================================================
# Test 6: 按鈕存在、初始 disabled
# ============================================================
def test_export_button_exists_initially_disabled():
    """export_select_btn 存在且初始 state='disabled'"""
    from source.StockTool import StrategyGUI  # type: ignore

    src = Path(__file__).parent.parent / "source" / "StockTool.py"
    content = src.read_text(encoding="utf-8")

    # 檢查 _build_ui 內 export_select_btn 初始是 disabled
    assert "self.export_select_btn" in content
    # 找 _build_ui 那段、按鈕 config 區塊（跨行）
    m = re.search(
        r"self\.export_select_btn\s*=\s*ttk\.Button\(.*?state\s*=\s*[\"']disabled[\"']",
        content,
        re.DOTALL,
    )
    assert m is not None, "export_select_btn 初始應為 state='disabled'"
    print("✅ export_select_btn 存在、初始 state='disabled'")


# ============================================================
# Test 7: _display_select_results 後按鈕 enable
# ============================================================
def test_export_button_enabled_after_display():
    """_display_select_results 結尾會 enable 按鈕"""
    from source.StockTool import StrategyGUI  # type: ignore

    src = Path(__file__).parent.parent / "source" / "StockTool.py"
    content = src.read_text(encoding="utf-8")

    # 找 _display_select_results method 內有 enable 按鈕的 code
    assert 'self.export_select_btn.config(state="normal")' in content
    # 並且這段 code 在 _display_select_results 內（不在 _export_ 內）
    display_idx = content.find("def _display_select_results")
    export_idx = content.find("def _export_select_results_excel")
    btn_enable_idx = content.find('self.export_select_btn.config(state="normal")')
    assert display_idx < btn_enable_idx < export_idx, \
        f"btn enable 應在 _display_select_results 內、在 _export_ 之前"
    print("✅ _display_select_results 結尾會 enable 按鈕")


# ============================================================
# Test 8: 匯出格式可被 load_stock_list_from_excel 讀
# ============================================================
def test_format_compat_with_load_stock_list(tmp_path):
    """匯出的 xlsx 格式可被既有 load_stock_list_from_excel 邏輯讀取（向下相容）"""
    from source.StockTool import StrategyGUI  # type: ignore
    from openpyxl import load_workbook

    df = pd.DataFrame({
        "股票代號": ["2330", "2317", "2454", "6669"],
        "股票名稱": ["台積電", "鴻海", "聯發科", "緯穎"],
        "股價": [1080.0, 215.0, 1485.0, 5130.0],
        "Score": [0.95, 0.88, 0.85, 0.80],
    })
    app = _make_app_mock(last_select_df=df)
    app._select_checked = {"2330": True, "2317": True, "2454": True, "6669": True}  # 模擬全勾選

    out_path = tmp_path / "compat_test.xlsx"

    with patch("tkinter.filedialog.asksaveasfilename", return_value=str(out_path)), \
         patch("tkinter.messagebox.showinfo"), \
         patch("tkinter.messagebox.showerror"):
        StrategyGUI._export_select_results_excel(app)

    # 模擬 load_stock_list_from_excel 的核心邏輯：找「股票代號」欄、讀代號
    wb = load_workbook(str(out_path))
    ws = wb.active

    # 找欄位 index
    headers = [c.value for c in ws[1]]
    code_col_idx = headers.index("股票代號")
    codes = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = row[code_col_idx]
        if code is not None and str(code).strip():
            codes.append(str(code).strip())

    assert codes == ["2330", "2317", "2454", "6669"], f"代號讀取錯誤: {codes}"
    print(f"✅ 匯出格式向下相容：load_stock_list 讀得到 {codes}")


if __name__ == "__main__":
    # 單跑測試時方便（只跑不需 mock 的）
    test_export_method_exists()
    test_export_filename_default()
    test_export_button_exists_initially_disabled()
    test_export_button_enabled_after_display()
    print("\n(其他 4 個 test 需要 mock、跑 pytest 為主)")
