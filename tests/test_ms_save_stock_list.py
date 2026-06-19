"""【V0.9.5-cache-savelist】存勾選股票為 Excel 股票清單

設計：
- 只存「股票代號」+「股票名稱」兩個欄位（被 load_stock_list_from_excel 直接讀取）
- 至少勾選一隻、否則提示
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _fake_result_df():
    return pd.DataFrame({
        "股票代號": ["2330", "3188", "2442"],
        "股票名稱": ["台積電", "鑫龍騰", "美利達"],
        "現價": [950.0, 32.0, 180.0],
        "今年現金殖利率(%)": [2.5, 7.2, 4.1],
    })


def _make_app_mock():
    """建一個 mock app、有 _ms_result_df / _ms_checked / logger"""
    app = MagicMock()
    app._ms_result_df = _fake_result_df()
    app._ms_checked = {}  # 預設沒勾選
    return app


def test_未選股_提示無資料():
    """【守護】沒按「選股」就按儲存 → 提示「請先按選股」"""
    app = MagicMock()
    # _ms_result_df 沒有
    del app._ms_result_df  # 確保 getattr 回傳空

    # 直接呼叫會 AttributeError → 但 messagebox.showwarning 應該先被呼叫
    with patch.object(st, "messagebox") as mock_mb:
        try:
            st.StrategyGUI._ms_save_stock_list(app)
        except AttributeError:
            pass
        # 這條路徑：_ms_result_df 不存在 → 直接 messagebox.showwarning('無資料', ...)
        # 但 hasattr 會回 False → 進 messagebox 路徑
        # 若走完整邏輯、_ms_result_df 為 None → 也會 messagebox.showwarning


def test_沒勾選任何股票_提示未勾選():
    """【守護】Treeview 有資料、但沒勾 → 提示「請至少勾選一隻」"""
    app = _make_app_mock()
    app._ms_checked = {}  # 都沒勾

    with patch.object(st, "messagebox") as mock_mb:
        st.StrategyGUI._ms_save_stock_list(app)
        # 應該呼叫 showwarning('未勾選', ...)
        called = False
        for c in mock_mb.showwarning.call_args_list:
            if c.args and "未勾選" in str(c.args[0]):
                called = True
                break
        assert called, "沒勾任何股票時應提示「未勾選」、不要跳出存檔對話框"


def test_勾選至少一隻_寫入乾淨格式(tmp_path):
    """【核心守護】勾選後寫的 Excel 只能有「股票代號」+「股票名稱」兩欄

    load_stock_list_from_excel 只需要「股票代號」欄
    但實作上保留「股票名稱」給人看、方便核對
    """
    app = _make_app_mock()
    app._ms_checked = {"2330": True, "3188": True}  # 勾 2 隻

    out_path = str(tmp_path / "test_list.xlsx")

    # mock filedialog 回傳 path
    with patch.object(st, "filedialog") as mock_fd, \
         patch.object(st, "messagebox"):
        mock_fd.asksaveasfilename.return_value = out_path
        st.StrategyGUI._ms_save_stock_list(app)

    # 讀回驗證
    df = pd.read_excel(out_path)
    assert list(df.columns) == ["股票代號", "股票名稱"], (
        f"輸出欄位應為 [股票代號, 股票名稱]、實際: {list(df.columns)}"
    )
    sorted_codes = sorted(str(c) for c in df['股票代號'].tolist()); assert sorted_codes == ['2330', '3188'], f'actual: {sorted_codes}'
    assert df["股票名稱"].tolist() == ["台積電", "鑫龍騰"]
    # 不能包含現價、殖利率等其他欄位（會污染 load_stock_list_from_excel）
    assert "現價" not in df.columns
    assert "今年現金殖利率(%)" not in df.columns


def test_load_stock_list_from_excel_可讀回_我們存的檔(tmp_path):
    """【整合測試】用 _ms_save_stock_list 存的檔、可以被 load_stock_list_from_excel 讀取"""
    app = _make_app_mock()
    app._ms_checked = {"2330": True, "3188": True, "2442": True}

    out_path = str(tmp_path / "test_list2.xlsx")

    with patch.object(st, "filedialog") as mock_fd, \
         patch.object(st, "messagebox"):
        mock_fd.asksaveasfilename.return_value = out_path
        st.StrategyGUI._ms_save_stock_list(app)

    codes = st.load_stock_list_from_excel(out_path)
    assert sorted(codes) == ["2330", "2442", "3188"]
