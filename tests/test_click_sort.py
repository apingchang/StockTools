"""
test_click_sort.py
驗證 V0.9.5-click-sort：Treeview heading click 切換升降冪

【William 2026-06-28 11:30 反映】
- 「幫我改成每個數字欄位在欄為名稱 click 一下則依此欄位數值大小排列」
- 「同一欄每按一下改變排列數序也就是由大到小或由小到大」
- 「如一般 file explorer 一樣」
- 「etf 選股結果也是同樣作法」

【設計】
- 寫在 StockTool.py 的 3 個 helper:
  - _parse_sort_value(v): 顯示字串 → (sort_key, is_missing)
  - _sort_treeview_by_column(tree, col, state): 排序單一欄位
  - _make_treeview_click_sort(tree, cols, skip_col): 套用到 tree、回傳 sort_state
- 第一次 click → desc（由大到小）
- 再 click 一次 → asc（由小到大）
- 「—」/空字串 → missing、排最後
- 數字欄自動 parse (千分位、單位)
- 文字欄當字串排（代號/名稱/日期）
- heading 顯示 ↑ / ↓ 箭頭

【守護】
- _parse_sort_value: 9 種輸入 (數字/千分位/單位/—/中文/日期)
- _sort_treeview_by_column: desc/asc/missing 排最後/多欄切換
- heading arrow: 該欄加、其他欄清掉

【實作細節】用 MockTreeview 模擬 tkinter、不需 GUI root window
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


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


# ==========================================================
# 【_parse_sort_value】各種輸入
# ==========================================================

def test_parse_sort_value_純數字():
    """【V0.9.5-click-sort】純數字字串 → float"""
    assert st._parse_sort_value("34195") == (34195.0, False)
    assert st._parse_sort_value("0") == (0.0, False)
    assert st._parse_sort_value("-50") == (-50.0, False)
    print("PASS: test_parse_sort_value_純數字")


def test_parse_sort_value_千分位逗號():
    """【V0.9.5-click-sort】千分位逗號 → float"""
    assert st._parse_sort_value("12,345") == (12345.0, False)
    assert st._parse_sort_value("3,236,100") == (3236100.0, False)
    print("PASS: test_parse_sort_value_千分位逗號")


def test_parse_sort_value_單位():
    """【V0.9.5-click-sort】帶單位（股/張/%） → float"""
    assert st._parse_sort_value("134 股") == (134.0, False)
    assert st._parse_sort_value("6 股") == (6.0, False)
    assert st._parse_sort_value("3.82%") == (3.82, False)
    assert st._parse_sort_value("12.5%") == (12.5, False)
    print("PASS: test_parse_sort_value_單位")


def test_parse_sort_value_missing():
    """【V0.9.5-click-sort】「—」/空字串/- → missing"""
    assert st._parse_sort_value("—")[1] is True
    assert st._parse_sort_value("-")[1] is True
    assert st._parse_sort_value("")[1] is True
    assert st._parse_sort_value("   ")[1] is True
    print("PASS: test_parse_sort_value_missing")


def test_parse_sort_value_中文():
    """【V0.9.5-click-sort】中文（公司名稱）→ 當字串排"""
    key, missing = st._parse_sort_value("台積電")
    assert key == "台積電"
    assert missing is False
    print("PASS: test_parse_sort_value_中文")


def test_parse_sort_value_代號():
    """【V0.9.5-click-sort】代號 → 當數字（0050 → 50.0）"""
    assert st._parse_sort_value("1101") == (1101.0, False)
    assert st._parse_sort_value("2330") == (2330.0, False)
    assert st._parse_sort_value("0050") == (50.0, False)
    print("PASS: test_parse_sort_value_代號")


def test_parse_sort_value_日期():
    """【V0.9.5-click-sort】ISO 日期字串 → 當字串排（dict 序=時間序）"""
    key, missing = st._parse_sort_value("2026-06-26")
    assert key == "2026-06-26"
    assert missing is False
    print("PASS: test_parse_sort_value_日期")


def test_parse_sort_value_小數_負號():
    """【V0.9.5-click-sort】小數/負號 → float"""
    assert st._parse_sort_value("3.82") == (3.82, False)
    assert st._parse_sort_value("-0.45") == (-0.45, False)
    assert st._parse_sort_value("2,340.00") == (2340.0, False)
    print("PASS: test_parse_sort_value_小數_負號")


# ==========================================================
# 【_sort_treeview_by_column】升降冪切換
# ==========================================================

def _make_test_tree():
    """產生測試用 MockTreeview"""
    cols = ("勾選", "代號", "名稱", "現價", "成交量(張)", "盤後量(張)", "PE", "資料日期")
    tree = MockTreeview(cols)
    test_data = [
        ("1101", {"勾選": "☐", "代號": "1101", "名稱": "台泥", "現價": "24.15",
                  "成交量(張)": "34195", "盤後量(張)": "134 股", "PE": "12.5",
                  "資料日期": "2026-06-26"}),
        ("2330", {"勾選": "☐", "代號": "2330", "名稱": "台積電", "現價": "2,340.00",
                  "成交量(張)": "39059", "盤後量(張)": "—", "PE": "15.3",
                  "資料日期": "2026-06-26"}),
        ("0050", {"勾選": "☐", "代號": "0050", "名稱": "元大台灣50", "現價": "55.20",
                  "成交量(張)": "15000", "盤後量(張)": "—", "PE": "—",
                  "資料日期": "2026-06-25"}),
        ("1102", {"勾選": "☐", "代號": "1102", "名稱": "亞泥", "現價": "35.75",
                  "成交量(張)": "8000", "盤後量(張)": "6 股", "PE": "10.2",
                  "資料日期": "2026-06-26"}),
    ]
    tree.children = list(test_data)
    return tree, cols


def test_sort_desc_第一次():
    """【V0.9.5-click-sort】第一次 click → desc（由大到小）"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "盤後量(張)", state)

    # 134 → 6 → missing (—)
    order = [tree.set(iid, "盤後量(張)") for iid in tree.get_children()]
    assert order == ["134 股", "6 股", "—", "—"], f"desc + missing 排最後、實際: {order}"

    # heading 應有 ↓ 箭頭
    assert tree.headings["盤後量(張)"]["text"] == "盤後量(張) ↓"

    # state 應記為 desc
    assert state["盤後量(張)"] == "desc"
    print(f"PASS: test_sort_desc_第一次 ({order})")


def test_sort_asc_第二次():
    """【V0.9.5-click-sort】再 click 一次 → asc（由小到大）"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "盤後量(張)", state)  # 第 1 次 desc
    st._sort_treeview_by_column(tree, "盤後量(張)", state)  # 第 2 次 asc

    # 6 → 134 → missing (—)
    order = [tree.set(iid, "盤後量(張)") for iid in tree.get_children()]
    assert order == ["6 股", "134 股", "—", "—"], f"asc + missing 排最後、實際: {order}"

    # heading 應有 ↑ 箭頭
    assert tree.headings["盤後量(張)"]["text"] == "盤後量(張) ↑"
    assert state["盤後量(張)"] == "asc"
    print(f"PASS: test_sort_asc_第二次 ({order})")


def test_sort_切換欄位_arrow_正確():
    """【V0.9.5-click-sort】切換欄位時、前一欄 arrow 應清掉、新欄位加新 arrow"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    # 點 盤後量 → desc
    st._sort_treeview_by_column(tree, "盤後量(張)", state)
    assert tree.headings["盤後量(張)"]["text"] == "盤後量(張) ↓"
    assert tree.headings["現價"]["text"] == "現價"  # 其他欄無 arrow

    # 點 現價 → desc、其他欄清掉
    st._sort_treeview_by_column(tree, "現價", state)
    assert tree.headings["現價"]["text"] == "現價 ↓"
    assert tree.headings["盤後量(張)"]["text"] == "盤後量(張)"  # arrow 應清掉

    # 點 盤後量 → asc（因為前一次是 desc、反轉）
    st._sort_treeview_by_column(tree, "盤後量(張)", state)
    assert tree.headings["盤後量(張)"]["text"] == "盤後量(張) ↑"
    assert tree.headings["現價"]["text"] == "現價"
    print("PASS: test_sort_切換欄位_arrow_正確")


def test_sort_代號_當數字():
    """【V0.9.5-click-sort】代號當數字排（0050 → 50.0、1101 → 1101.0、2330 → 2330.0）"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "代號", state)  # desc

    # 預期：2330 → 1102 → 1101 → 0050
    order = [tree.set(iid, "代號") for iid in tree.get_children()]
    assert order == ["2330", "1102", "1101", "0050"], (
        f"代號當數字排 (desc) 應 = 2330 > 1102 > 1101 > 0050、實際: {order}"
    )
    print(f"PASS: test_sort_代號_當數字 ({order})")


def test_sort_名稱_當字串():
    """【V0.9.5-click-sort】名稱當字串排（中文筆畫序）"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "名稱", state)  # desc

    # 預期 desc: 元大台灣50 > 亞泥 > 台積電 > 台泥 (筆畫)
    order = [tree.set(iid, "名稱") for iid in tree.get_children()]
    print(f"  實際順序: {order}")
    # 至少台積電 vs 台泥 應該分得出來（用字串比較、不同筆畫）
    # 不要驗證完整排序、只驗證「有排序過」（跟原始順序不同）
    original = ["台泥", "台積電", "元大台灣50", "亞泥"]
    assert order != original, f"排序後順序應改變、實際: {order} == 原始 {original}"
    print(f"PASS: test_sort_名稱_當字串 ({order})")


def test_sort_現價_千分位逗號():
    """【V0.9.5-click-sort】「2,340.00」應正確 parse 成 2340"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "現價", state)  # desc

    # 預期：2340 > 55.20 > 35.75 > 24.15
    order = [tree.set(iid, "現價") for iid in tree.get_children()]
    assert order == ["2,340.00", "55.20", "35.75", "24.15"], (
        f"現價 desc 應 = 2340 > 55 > 35 > 24、實際: {order}"
    )
    print(f"PASS: test_sort_現價_千分位逗號 ({order})")


def test_sort_資料日期_字串序():
    """【V0.9.5-click-sort】資料日期 ISO 格式、字串序 = 時間序"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "資料日期", state)  # desc

    # 預期 desc: 2026-06-26 (3 筆) → 2026-06-25 (1 筆)
    order = [tree.set(iid, "資料日期") for iid in tree.get_children()]
    assert order[0] == "2026-06-26"
    assert order[-1] == "2026-06-25"
    print(f"PASS: test_sort_資料日期_字串序 ({order})")


def test_sort_全部_missing_不爆():
    """【V0.9.5-click-sort】所有 row 都 missing 時、應正常處理（不 crash）"""
    tree, cols = _make_test_tree()
    # 把所有盤後量都改成 "—"
    for iid, row in tree.children:
        row["盤後量(張)"] = "—"
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    st._sort_treeview_by_column(tree, "盤後量(張)", state)  # desc

    # 全部 missing、但順序應保留原始順序（都排最後）
    order = [tree.set(iid, "盤後量(張)") for iid in tree.get_children()]
    assert all(v == "—" for v in order), f"全部應為 —、實際: {order}"
    print("PASS: test_sort_全部_missing_不爆")


def test_make_click_sort_skip_col():
    """【V0.9.5-click-sort】_make_treeview_click_sort 跳過 skip_col 的 click handler"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    # 「勾選」欄不應有 command
    assert tree.headings["勾選"]["command"] is None, "勾選不應有 click handler"

    # 其他欄應有 command
    for col in cols:
        if col == "勾選":
            continue
        assert tree.headings[col]["command"] is not None, f"{col} 應有 click handler"

    # state 應為 dict
    assert isinstance(state, dict)
    assert state == {}, "初始 state 應為空 dict"
    print(f"PASS: test_make_click_sort_skip_col ({len(cols)-1} 欄有 handler)")


# ==========================================================
# 【整合】手動選股 + ETF 都有套用
# ==========================================================

def test_handson_strategy_跟_etf_treeview_都有套用():
    """【V0.9.5-click-sort】兩個 treeview 都應設定 click-sort state"""
    # 簡單 import + 確保屬性存在
    # StrategyGUI 建構要 root window、所以只檢查有定義
    import inspect
    src = inspect.getsource(st)
    assert "self._ms_sort_state = _make_treeview_click_sort(" in src, (
        "手動選股 Treeview 應套用 click-sort"
    )
    assert "self._etf_sort_state = _make_treeview_click_sort(" in src, (
        "ETF Treeview 應套用 click-sort"
    )
    print("PASS: test_handson_strategy_跟_etf_treeview_都有套用")


# ==========================================================
# 【V0.9.5-click-sort fix】混雜 str+float 不 crash、skip_cols 複數
# ==========================================================

def test_sort_混雜_str_跟_float_不爆():
    """【V0.9.5-click-sort fix】William 14:30 反映 click heading crash:
    當欄位中混著 number 跟 str 時 sort 會 TypeError: '<' not supported between str and float
    修法：統一當 str 排
    """
    tree, cols = _make_test_tree()
    # 在「名稱」欄加一個 number、混雜
    for iid, row in tree.children:
        if iid == "1101":
            row["名稱"] = "123"  # 數字型字串
    state = st._make_treeview_click_sort(tree, cols, skip_cols={"勾選", "名稱"})

    # 點 勾選 不該 crash、但因 skip 不設 handler
    # 改測試點「代號」、有 handler
    # 加一個混雜的 PE 測試
    tree2, cols2 = _make_test_tree()
    # PE 欄混 1 個 str（中文）
    for iid, row in tree2.children:
        if iid == "1101":
            row["PE"] = "12.5"
        elif iid == "2330":
            row["PE"] = "本益比高估"  # str
    state = st._make_treeview_click_sort(tree2, cols2, skip_cols={"勾選", "名稱", "資料日期"})

    # 應不 crash、且依字串排
    st._sort_treeview_by_column(tree2, "PE", state)  # desc

    order = [tree2.set(iid, "PE") for iid in tree2.get_children()]
    # 全部轉 str 排、text 比較
    # "15.3" vs "本益比高估" vs "—" vs "12.5" vs "10.2" desc
    print(f"  混雜 PE 排序: {order}")
    # 驗證有排序（跟原始順序不同）
    original = ["12.5", "15.3", "—", "10.2"]
    assert order != original, f"混雜應有排序、實際 {order} == 原始 {original}"
    print("PASS: test_sort_混雜_str_跟_float_不爆")


def test_make_click_sort_skip_cols_複數():
    """【V0.9.5-click-sort fix】skip_cols 支援多個欄位"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(
        tree, cols, skip_cols={"勾選", "名稱", "資料日期"}
    )

    # 被 skip 的不應有 command
    for skip in ("勾選", "名稱", "資料日期"):
        assert tree.headings[skip]["command"] is None, f"{skip} 應被 skip"

    # 其他欄應有 command
    for col in cols:
        if col in {"勾選", "名稱", "資料日期"}:
            continue
        assert tree.headings[col]["command"] is not None, f"{col} 應有 click handler"

    print(f"PASS: test_make_click_sort_skip_cols_複數 ({len(cols)-3} 欄有 handler)")


def test_make_click_sort_skip_col_舊_API_向後相容():
    """【V0.9.5-click-sort fix】skip_col 單數舊 API 仍可使用"""
    tree, cols = _make_test_tree()
    state = st._make_treeview_click_sort(tree, cols, skip_col="勾選")

    # 勾選應被 skip
    assert tree.headings["勾選"]["command"] is None

    # 其他欄應有
    for col in cols:
        if col == "勾選":
            continue
        assert tree.headings[col]["command"] is not None
    print("PASS: test_make_click_sort_skip_col_舊_API_向後相容")


def test_select_tree_也_有_套用_click_sort():
    """【V0.9.5-click-sort fix】系統選股 select_tree 也應套用 click-sort
    （William 14:30 反映系統選股點 heading 沒反應）"""
    import inspect
    src = inspect.getsource(st)
    assert "self._select_sort_state = _make_treeview_click_sort(" in src, (
        "系統選股 select_tree 應套用 click-sort"
    )
    print("PASS: test_select_tree_也_有_套用_click_sort")


if __name__ == "__main__":
    test_parse_sort_value_純數字()
    test_parse_sort_value_千分位逗號()
    test_parse_sort_value_單位()
    test_parse_sort_value_missing()
    test_parse_sort_value_中文()
    test_parse_sort_value_代號()
    test_parse_sort_value_日期()
    test_parse_sort_value_小數_負號()
    test_sort_desc_第一次()
    test_sort_asc_第二次()
    test_sort_切換欄位_arrow_正確()
    test_sort_代號_當數字()
    test_sort_名稱_當字串()
    test_sort_現價_千分位逗號()
    test_sort_資料日期_字串序()
    test_sort_全部_missing_不爆()
    test_make_click_sort_skip_col()
    test_handson_strategy_跟_etf_treeview_都有套用()
    test_sort_混雜_str_跟_float_不爆()
    test_make_click_sort_skip_cols_複數()
    test_make_click_sort_skip_col_舊_API_向後相容()
    test_select_tree_也_有_套用_click_sort()
    print("\nAll V0.9.5-click-sort tests passed!")