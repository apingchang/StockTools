"""【v1.1.2 ETF 漲跌價欄 click-sort】驗證 ETF 選股「漲跌價」欄可點選排序

2026-06-30 23:36 William 反映：
- 「ETF 選股結果請增加"漲跌價"欄位也要可以點選欄位名稱重新排序」
- 不確定是否已有？或 click-sort 沒套到該欄？

【驗證】
- ETF _etf_tree 必須有「漲跌價」欄（cols 第 5 個、index 4）
- _make_treeview_click_sort 必須套用到「漲跌價」
- 點 click heading → 必須正確排序（_parse_sort_value 處理 _fmt_change 格式）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


ETF_COLS = ("勾選", "代號", "名稱", "收盤價", "漲跌價", "ETF數", "今日異動")


class MockTreeview:
    """模擬 ttk.Treeview 用於單元測試"""

    def __init__(self, columns):
        self.columns = columns
        self.children = []  # list of (iid, {col: display_value})
        self.headings = {c: {"text": c, "command": None} for c in columns}

    def __getitem__(self, key):
        if key == "columns":
            return self.columns
        raise KeyError(key)

    def get_children(self, parent=""):
        return [iid for iid, _ in self.children]

    def set(self, iid, col):
        for k, v in self.children:
            if k == iid:
                return v.get(col, "")
        return ""

    def heading(self, col, text=None, command=None):
        if text is not None:
            self.headings[col]["text"] = text
            return None
        if command is not None:
            self.headings[col]["command"] = command
            return None
        return self.headings[col]

    def move(self, iid, parent, index):
        for i, (k, v) in enumerate(self.children):
            if k == iid:
                row = self.children.pop(i)
                self.children.insert(index, row)
                return


def test_etf_tree_has_change_col():
    """ETF 選股 Treeview 必須有「漲跌價」欄"""
    assert "漲跌價" in ETF_COLS, "❌ ETF cols 內找不到「漲跌價」欄位"
    # 漲跌價應該在「收盤價」之後、「ETF數」之前
    idx_change = ETF_COLS.index("漲跌價")
    idx_close = ETF_COLS.index("收盤價")
    idx_etf_count = ETF_COLS.index("ETF數")
    assert idx_change > idx_close, "❌ 「漲跌價」應在「收盤價」之後"
    assert idx_change < idx_etf_count, "❌ 「漲跌價」應在「ETF數」之前"


def test_click_sort_set_command_on_change_col():
    """click-sort helper 必須對「漲跌價」欄設 heading command"""
    tree = MockTreeview(list(ETF_COLS))
    st._make_treeview_click_sort(tree, ETF_COLS, skip_cols={"勾選", "名稱"})

    # 漲跌價的 heading 必須有 command
    info = tree.heading("漲跌價")
    assert info["command"] is not None, "❌ 「漲跌價」欄沒設 heading command、無法 click-sort"

    # 勾選、名稱 不應有 command
    for skip in ("勾選", "名稱"):
        info = tree.heading(skip)
        assert info["command"] is None, f"❌ 「{skip}」被設定為可排序（應 skip）"


def test_change_col_sort_desc():
    """模擬點擊「漲跌價」heading → 必須按 _fmt_change 的格式正確排序"""

    # 模擬 _etf_display_results 插入的 values ("收盤價", "漲跌價")
    # _fmt_change 格式：
    #   正數：+5.0、+3.2
    #   負數：-1.0、-2.5
    #   零：0.0（或 -- 看實作）
    #   None：--
    rows = [
        ("2330", {"代號": "2330", "收盤價": "2410.00", "漲跌價": "+40.00", "ETF數": "18", "今日異動": "--"}),
        ("2454", {"代號": "2454", "收盤價": "4245.00", "漲跌價": "-335.00", "ETF數": "8", "今日異動": "+5.0"}),
        ("0050", {"代號": "0050", "收盤價": "45.20", "漲跌價": "+0.50", "ETF數": "12", "今日異動": "+1.2"}),
        ("0056", {"代號": "0056", "收盤價": "30.15", "漲跌價": "0.00", "ETF數": "10", "今日異動": "--"}),
        ("2884", {"代號": "2884", "收盤價": "0.00", "漲跌價": "--", "ETF數": "5", "今日異動": "--"}),  # missing
    ]

    tree = MockTreeview(list(ETF_COLS))
    for iid, vals in rows:
        tree.children.append((iid, vals))

    # 執行 click-sort on 漲跌價
    sort_state = {}
    st._sort_treeview_by_column(tree, "漲跌價", sort_state)

    # 取得排序後的 iid 順序
    sorted_iids = [iid for iid, _ in tree.children]
    # 預期順序 (desc by 漲跌價 + missing 排最後)：
    #   +40.00 (2330) > +0.50 (0050) > 0.00 (0056) > -335.00 (2454) > -- (2884)
    expected = ["2330", "0050", "0056", "2454", "2884"]
    assert sorted_iids == expected, (
        f"❌ desc 排序錯！\n"
        f"   預期: {expected}\n"
        f"   實際: {sorted_iids}"
    )
    # 確認 state 已存（下次再 click 會用 asc）
    assert sort_state.get("漲跌價") == "desc"

    # 再 click 一次 → asc
    st._sort_treeview_by_column(tree, "漲跌價", sort_state)
    sorted_iids2 = [iid for iid, _ in tree.children]
    expected2 = ["2454", "0056", "0050", "2330", "2884"]  # 缺 missing
    assert sorted_iids2 == expected2, (
        f"❌ asc 排序錯！\n"
        f"   預期: {expected2}\n"
        f"   實際: {sorted_iids2}"
    )
    assert sort_state.get("漲跌價") == "asc"


def test_change_col_handles_negative_change():
    """_parse_sort_value 對負數字串的處理"""
    # _fmt_change(負數) → "-335.00"
    # _parse_sort_value 看到 prefix "-" → 視為 number
    sort_key, is_missing = st._parse_sort_value("-335.00")
    assert is_missing is False
    assert isinstance(sort_key, (int, float))
    assert float(sort_key) == -335.0, f"❌ 負數 parse 錯: {sort_key}"


def test_change_col_handles_positive_change():
    """_parse_sort_value 對正數字串 "+40.00" 的處理"""
    sort_key, is_missing = st._parse_sort_value("+40.00")
    assert is_missing is False
    assert float(sort_key) == 40.0, f"❌ 正數 parse 錯: {sort_key}"


def test_change_col_handles_zero_change():
    """_parse_sort_value 對零字串 "0.00" 的處理"""
    sort_key, is_missing = st._parse_sort_value("0.00")
    assert is_missing is False
    assert float(sort_key) == 0.0, f"❌ 零 parse 錯: {sort_key}"


def test_change_col_handles_missing():
    """_parse_sort_value 對 "--" 的處理"""
    sort_key, is_missing = st._parse_sort_value("--")
    assert is_missing is True, f"❌ '--' 應視為 missing, 但 is_missing={is_missing}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])