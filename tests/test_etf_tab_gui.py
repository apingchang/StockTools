"""【V0.9.5-etf】主動式 ETF Tab GUI 行為測試

測試 ETF Tab 的關鍵 method（不啟動完整 Tk）：
- _etf_toggle_check / _etf_select_all / _etf_select_none：勾選狀態管理
- _etf_display_results：套用篩選 + populate Treeview
- _etf_export_excel：匯出 Excel（mock 寫檔）
- _show_etf_popup / _close_etf_popup：popup 行為

策略：mock tk.Tk() 父類別、用 `unittest.mock.MagicMock` 模擬 widget。
重點驗「邏輯」、不驗 widget 繪製。
"""
import os
import sys
from unittest.mock import MagicMock, patch, mock_open

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 工具：mock Tk 環境 + 建構 self 物件
# ==========================================================

def _make_self():
    """建立一個像 StockToolGUI 的 self 物件、給 method 呼叫用"""
    s = MagicMock()  # 不用 spec=、保留彈性

    # Treeview 模擬
    tree = MagicMock()
    tree.get_children.return_value = ["2330", "2327", "2454"]
    tree.item.side_effect = lambda *args, **kw: {
        "2330": {"values": ("☐", "2330", "台積電", "950.0", "3")},
        "2327": {"values": ("☐", "2327", "國巨", "580.0", "2")},
        "2454": {"values": ("☐", "2454", "聯發科", "1200.0", "1")},
    }[args[0]]

    # TkVar
    s._etf_min_count_var.get.return_value = 1
    s._etf_only_with_price_var.get.return_value = False
    s._etf_limit_var.get.return_value = 500

    s._etf_tree = tree
    s._etf_checked = {}
    s._etf_hover_iid = None
    s._etf_agg_df = pd.DataFrame({
        "股票代號": ["2330", "2327", "2454"],
        "股票名稱": ["台積電", "國巨", "聯發科"],
        "etf_count": [3, 2, 1],
        "etf_list": [
            "00980A 主動野村臺灣優選(9.37%) | 00982A 主動群益台灣強棒(8.71%) | 00981A 主動統一台股增長(9.68%)",
            "00981A 主動統一台股增長(8.67%) | 00403A 主動統一升級50(7.50%)",
            "00984A 主動安聯台灣高息(7.17%)",
        ],
    })
    # 補 close_etf_popup / clear_etf_hover 用的方法
    s._close_etf_popup = MagicMock()
    s._clear_etf_hover = MagicMock()
    s._etf_long_df = pd.DataFrame()
    s._etf_status = MagicMock()
    s._etf_data_status = MagicMock()
    return s


# ==========================================================
# 勾選狀態管理
# ==========================================================

def test_etf_toggle_check_第一次點擊變勾選():
    """【核心守護】點擊第一欄 → toggle 勾選狀態"""
    s = _make_self()
    # 模擬 event
    event = MagicMock()
    event.x = 10
    event.y = 10
    s._etf_tree.identify.return_value = "cell"
    s._etf_tree.identify_row.return_value = "2330"
    s._etf_tree.identify_column.return_value = "#1"

    st.StrategyGUI._etf_toggle_check(s, event)

    assert s._etf_checked["2330"] is True


def test_etf_toggle_check_第二次點擊取消勾選():
    """【邊界】已勾選 → 再點 → 取消"""
    s = _make_self()
    s._etf_checked["2330"] = True  # 已勾選
    event = MagicMock()
    event.x = 10
    event.y = 10
    s._etf_tree.identify.return_value = "cell"
    s._etf_tree.identify_row.return_value = "2330"
    s._etf_tree.identify_column.return_value = "#1"

    st.StrategyGUI._etf_toggle_check(s, event)
    assert s._etf_checked["2330"] is False


def test_etf_toggle_check_點非勾選欄不生效():
    """【邊界】點非第 1 欄 → 不切換"""
    s = _make_self()
    event = MagicMock()
    event.x = 200  # 在「代號」或「收盤價」欄
    event.y = 10
    s._etf_tree.identify.return_value = "cell"
    s._etf_tree.identify_row.return_value = "2330"
    s._etf_tree.identify_column.return_value = "#3"  # 名稱欄

    st.StrategyGUI._etf_toggle_check(s, event)

    assert "2330" not in s._etf_checked


def test_etf_select_all_全部勾選():
    s = _make_self()
    st.StrategyGUI._etf_select_all(s)
    assert all(s._etf_checked.values())
    assert len(s._etf_checked) == 3


def test_etf_select_none_全部取消():
    s = _make_self()
    s._etf_checked["2330"] = True
    s._etf_checked["2327"] = True
    st.StrategyGUI._etf_select_none(s)
    assert all(v is False for v in s._etf_checked.values())


# ==========================================================
# 套用篩選 + 顯示
# ==========================================================

def test_etf_display_results_插入所有列():
    """【核心守護】呼叫 → Treeview 清空 + 插入每一列"""
    s = _make_self()
    st.StrategyGUI._etf_display_results(s, s._etf_agg_df)
    # Treeview 應該 delete 過舊的、insert 過新的
    assert s._etf_tree.delete.called
    assert s._etf_tree.insert.call_count == 3


def test_etf_display_results_etfcount_門檻過濾():
    """【核心守護】min_count=2 → 只插入 etf_count >= 2 的列"""
    s = _make_self()
    s._etf_min_count_var.get.return_value = 2
    st.StrategyGUI._etf_display_results(s, s._etf_agg_df)
    # 3 筆 → 只剩 2 筆 (2330 etf_count=3, 2327 etf_count=2)
    assert s._etf_tree.insert.call_count == 2


def test_etf_display_results_限制上限():
    """【邊界】limit=1 → 只插入 1 列"""
    s = _make_self()
    s._etf_limit_var.get.return_value = 1
    st.StrategyGUI._etf_display_results(s, s._etf_agg_df)
    assert s._etf_tree.insert.call_count == 1


def test_etf_display_results_收盤價過濾():
    """【邊界】only_with_price=True → 過濾沒收盤價的"""
    s = _make_self()
    s._etf_only_with_price_var.get.return_value = True
    # 改 agg_df：3 筆只 2 筆有收盤價
    s._etf_agg_df = pd.DataFrame({
        "股票代號": ["2330", "2327", "2454"],
        "股票名稱": ["台積電", "國巨", "聯發科"],
        "etf_count": [3, 2, 1],
        "etf_list": ["x", "y", "z"],
        "收盤價": [950.0, None, 1200.0],
    })
    st.StrategyGUI._etf_display_results(s, s._etf_agg_df)
    # 應該過濾掉 2327（收盤價 None）
    assert s._etf_tree.insert.call_count == 2


# ==========================================================
# 匯出 Excel
# ==========================================================

def test_etf_export_excel_無資料_跳警告():
    """【邊界】_etf_agg_df 沒資料 → messagebox.showwarning"""
    s = _make_self()
    s._etf_agg_df = pd.DataFrame()  # 空
    with patch.object(st.messagebox, "showwarning") as mock_warn:
        st.StrategyGUI._etf_export_excel(s)
        mock_warn.assert_called_once()
        args = mock_warn.call_args.args
        assert "無資料" in args[0] or "無資料" in args[1]


def test_etf_export_excel_未勾選_跳警告():
    """【邊界】_etf_checked 空白 → 警告「請先勾選」"""
    s = _make_self()
    with patch.object(st.messagebox, "showwarning") as mock_warn:
        st.StrategyGUI._etf_export_excel(s)
        mock_warn.assert_called_once()
        args = mock_warn.call_args.args
        assert "未勾選" in args[0] or "未勾選" in args[1]
    s._etf_tree.delete.assert_not_called()


# ==========================================================
# Popup 行為
# ==========================================================

def test_etf_show_popup_正常顯示():
    """【核心守護】給 iid + 座標 → 建立 Toplevel、顯示 etf_list"""
    s = _make_self()
    s._etf_popup = None  # 一開始沒 popup
    # mock Toplevel
    with patch.object(st.tk, "Toplevel") as MockToplevel, \
         patch.object(st.tk, "Label") as MockLabel:
        toplevel_instance = MagicMock()
        toplevel_instance.winfo_exists.return_value = True
        toplevel_instance.winfo_reqwidth.return_value = 400
        toplevel_instance.winfo_reqheight.return_value = 200
        toplevel_instance.winfo_screenwidth.return_value = 1920
        toplevel_instance.winfo_screenheight.return_value = 1080
        MockToplevel.return_value = toplevel_instance

        st.StrategyGUI._show_etf_popup(s, "2330", 500, 300)

        # 應該建立 Toplevel
        MockToplevel.assert_called_once()
        # 應該 config text 含「2330 台積電」與「被 3 檔 ETF 持有」
        call_args = MockLabel.return_value.config.call_args
        text = call_args.kwargs.get("text", "")
        assert "2330" in text
        assert "台積電" in text
        assert "3" in text  # etf_count


def test_etf_show_popup_找不到iid_不顯示():
    """【邊界】iid 不在 agg_df → 關閉 popup（不開新）"""
    s = _make_self()
    s._etf_popup = None
    with patch.object(st.tk, "Toplevel") as MockToplevel:
        st.StrategyGUI._show_etf_popup(s, "9999", 500, 300)
        MockToplevel.assert_not_called()


def test_etf_close_popup_destroy():
    """【邊界】有 popup → close 後 destroy"""
    s = _make_self()
    popup = MagicMock()
    popup.winfo_exists.return_value = True
    s._etf_popup = popup
    st.StrategyGUI._close_etf_popup(s)
    popup.destroy.assert_called_once()
    assert s._etf_popup is None


def test_etf_close_popup_本來就None_不報錯():
    """【邊界】一開始就沒 popup → close 不報錯"""
    s = _make_self()
    s._etf_popup = None
    st.StrategyGUI._close_etf_popup(s)  # 不應 raise
    assert s._etf_popup is None