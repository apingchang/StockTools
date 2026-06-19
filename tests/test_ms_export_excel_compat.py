"""【V0.9.5-cache-savelist-fix2】「📤 匯出 Excel」的檔可以被 load_stock_list_from_excel 讀取

William 22:12 反映：「匯出 excel 可以餵回策略參數中的選股來源嗎？可以就只要這個功能」
結論：可以。匯出檔包含「股票代號」欄位、load_stock_list_from_excel 透過 find_col 讀取。
不需要另外加「存成 Excel 股票清單」按鈕。
"""
import os
import sys
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
        "PE": [22.0, 15.0, 18.0],
    })


def test_匯出Excel的檔案可以被load_stock_list_from_excel讀取(tmp_path):
    """【整合測試】匯出 Excel 的檔（含多欄）→ load_stock_list_from_excel 只讀「股票代號」"""
    out_path = str(tmp_path / "export_test.xlsx")
    df = _fake_result_df()
    df.to_excel(out_path, index=False)

    codes = st.load_stock_list_from_excel(out_path)
    assert sorted(codes) == ["2330", "2442", "3188"]
