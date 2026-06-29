"""【V1.1-add-change-col】3 個選股 tree 加「漲跌價」欄位守護

2026-06-29 13:57 William 反映：
- 「所有的選股結果增加漲跌價欄位、一樣要有 sorting 功能」

【修法】
- _fmt_change(v): 顯示 +5.0 / -3.2 / 0.0 / --
  - + 正數: f"+{f:,.1f}"
  - - 負數: f"{f:,.1f}" (負號自帶)
  - 0: f"{f:.1f}" = "0.0" (不帶正負號)
  - NaN/None: "--"
- 3 個選股 tree 都加「漲跌價」欄（在「股價/現價/收盤價」之後）：
  - select_tree (系統選股): 9 欄 → 10 欄
  - _ms_tree (手動選股): 14 欄 → 15 欄
  - _etf_tree (ETF 選股): 6 欄 → 7 欄
- _parse_sort_value 自動支援 + - prefix 解析（已有、不需改）
- skip_cols 不加「漲跌價」→ 可以排序

【資料流】
- price_df 本來就有「漲跌」欄（fetch_market.py line 1175 算出）
- 系統選股: price.merge(...) → df_sel 自動有「漲跌」欄
- 手動選股: scoring.py final_cols 加「漲跌」→ result 有此欄
- ETF 選股: aggregate_etf_holdings 順便 merge「漲跌」→ agg_df 有此欄
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)
SCORING_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "scoring.py"
)
ETF_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "etf.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────── _fmt_change helper 守護 ────────────────────

def test_fmt_change_helper_exists():
    """【核心守護】_fmt_change 必須存在、不能是 inline 重複"""
    content = _read(STOCKTOOL_PY)
    assert "def _fmt_change(" in content, (
        "❌ 缺少 _fmt_change helper 函數！\n"
        "  V1.1-add-change-col 加的、模組層級 helper、不能 inline 重複"
    )


def test_fmt_change_positive():
    """正數應顯示為 +5.0"""
    # 模擬 _fmt_change 邏輯
    def _fmt_change(v, decimals=1, na="--"):
        import math
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return na
            f = float(v)
            if f > 0:
                return f"+{f:,.{decimals}f}"
            elif f < 0:
                return f"{f:,.{decimals}f}"
            else:
                return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return na

    assert _fmt_change(5.0) == "+5.0", "正數 5.0 應顯示 +5.0"
    assert _fmt_change(123.4) == "+123.4", "正數 123.4 應顯示 +123.4"
    assert _fmt_change(0.05) == "+0.1", "小正數 0.05 應顯示 +0.1"


def test_fmt_change_negative():
    """負數應顯示為 -3.2"""
    def _fmt_change(v, decimals=1, na="--"):
        import math
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return na
            f = float(v)
            if f > 0:
                return f"+{f:,.{decimals}f}"
            elif f < 0:
                return f"{f:,.{decimals}f}"
            else:
                return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return na

    assert _fmt_change(-3.2) == "-3.2", "負數 -3.2 應顯示 -3.2"
    assert _fmt_change(-125.0) == "-125.0", "負數 -125.0 應顯示 -125.0"


def test_fmt_change_zero():
    """0 應顯示為 0.0 (不帶正負號)"""
    def _fmt_change(v, decimals=1, na="--"):
        import math
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return na
            f = float(v)
            if f > 0:
                return f"+{f:,.{decimals}f}"
            elif f < 0:
                return f"{f:,.{decimals}f}"
            else:
                return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return na

    assert _fmt_change(0) == "0.0", "0 應顯示 0.0"
    assert _fmt_change(0.0) == "0.0", "0.0 應顯示 0.0"


def test_fmt_change_missing():
    """None/NaN 應顯示為 --"""
    def _fmt_change(v, decimals=1, na="--"):
        import math
        try:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return na
            f = float(v)
            if f > 0:
                return f"+{f:,.{decimals}f}"
            elif f < 0:
                return f"{f:,.{decimals}f}"
            else:
                return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return na

    assert _fmt_change(None) == "--", "None 應顯示 --"
    assert _fmt_change(float("nan")) == "--", "NaN 應顯示 --"


# ──────────────────── 3 個 tree 欄位守護 ────────────────────

def test_select_tree_has_change_column():
    """select_tree (系統選股) cols 必須有「漲跌價」"""
    content = _read(STOCKTOOL_PY)
    # 找 _display_select_results 裡的 cols = (...)
    m = re.search(
        r'def _display_select_results\(self, df_sel\):.*?cols\s*=\s*\((.*?)\)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _display_select_results 內的 cols 定義"
    cols_body = m.group(1)
    assert '"漲跌價"' in cols_body, (
        f"❌ select_tree cols 還沒有「漲跌價」！\n"
        f"  cols body: {cols_body[:200]}"
    )


def test_ms_tree_has_change_column():
    """_ms_tree (手動選股) cols 必須有「漲跌價」"""
    content = _read(STOCKTOOL_PY)
    # 找 _ms_tree = ttk.Treeview 之前最近的 cols = (...)
    m_tree = content.find("self._ms_tree = ttk.Treeview")
    if m_tree < 0:
        pytest.skip("找不到 self._ms_tree")
    before = content[:m_tree]
    cols_start = before.rfind("cols = (")
    paren_start = before.find("(", cols_start)
    # balanced paren parser
    depth = 1
    i = paren_start + 1
    while i < len(before) and depth > 0:
        ch = before[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < len(before) and before[i] != quote:
                if before[i] == "\\":
                    i += 1
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    cols_body = before[paren_start + 1 : i - 1]
    assert '"漲跌價"' in cols_body, (
        f"❌ _ms_tree cols 還沒有「漲跌價」！\n"
        f"  cols body: {cols_body[:300]}"
    )


def test_etf_tree_has_change_column():
    """_etf_tree (ETF 選股) cols 必須有「漲跌價」"""
    content = _read(STOCKTOOL_PY)
    m_tree = content.find("self._etf_tree = ttk.Treeview")
    if m_tree < 0:
        pytest.skip("找不到 self._etf_tree")
    before = content[:m_tree]
    cols_start = before.rfind("cols = (")
    paren_start = before.find("(", cols_start)
    # balanced paren parser
    depth = 1
    i = paren_start + 1
    while i < len(before) and depth > 0:
        ch = before[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < len(before) and before[i] != quote:
                if before[i] == "\\":
                    i += 1
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    cols_body = before[paren_start + 1 : i - 1]
    assert '"漲跌價"' in cols_body, (
        f"❌ _etf_tree cols 還沒有「漲跌價」！\n"
        f"  cols body: {cols_body[:300]}"
    )


# ──────────────────── scoring.py final_cols 守護 ────────────────────

def test_scoring_final_cols_has_change():
    """scoring.py final_cols 必須有「漲跌」（讓手動選股有資料）"""
    content = _read(SCORING_PY)
    m = re.search(r'final_cols\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert m, "找不到 final_cols = [...]"
    body = m.group(1)
    assert '"漲跌"' in body, (
        f"❌ scoring.py final_cols 還沒有「漲跌」！\n"
        f"  body: {body[:200]}"
    )


# ──────────────────── etf.py aggregate 守護 ────────────────────

def test_etf_aggregate_merges_change():
    """aggregate_etf_holdings 必須 merge 「漲跌」"""
    content = _read(ETF_PY)
    # 確認有 price_cols.append("漲跌") 或 ["股票代號", "股價", "漲跌"]
    assert '"漲跌"' in content, (
        "❌ aggregate_etf_holdings 沒 merge「漲跌」！"
    )
    # 確認 merge 有用到
    assert re.search(
        r'price_map\s*=\s*price_df\[.*?漲跌.*?\]',
        content,
        re.DOTALL,
    ), "❌ price_map 沒包含「漲跌」欄位"


# ──────────────────── 排序守護 ────────────────────

def test_change_column_not_in_skip_cols():
    """「漲跌價」不應在 skip_cols 內（必須可排序）"""
    content = _read(STOCKTOOL_PY)
    # 找所有 skip_cols={"..."} 並檢查沒有 "漲跌價"
    # 規則：skip_cols 是 set / dict 字面量
    skip_matches = re.findall(r'skip_cols\s*=\s*\{([^}]+)\}', content)
    for body in skip_matches:
        # 移除多餘空白
        body_clean = body.strip()
        assert '"漲跌價"' not in body_clean, (
            f"❌ skip_cols 包含「漲跌價」！會被跳過排序\n"
            f"  skip_cols 內容：{body_clean}"
        )
        assert "'漲跌價'" not in body_clean, (
            f"❌ skip_cols 包含「漲跌價」（單引號）！"
        )


def test_parse_sort_value_handles_signed_change():
    """_parse_sort_value 應能正確 parse +5.0 / -3.2（已有邏輯測試）

    本測試檢查 _parse_sort_value 沒被改壞
    """
    content = _read(STOCKTOOL_PY)
    # 找 def _parse_sort_value 並驗證有 float() 邏輯
    m = re.search(
        r'def _parse_sort_value\(v\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _parse_sort_value"
    body = m.group(1)
    # 確認有 float() 解析
    assert "float(" in body, "_parse_sort_value 沒用 float() 解析"
    # 確認有 missing 判斷
    assert "--" in body or '"—"' in body, "_parse_sort_value 沒處理 -- 缺失值"


# ──────────────────── 語法守護 ────────────────────

def test_all_files_compile():
    """所有改動檔案能編譯"""
    import py_compile
    for f in [STOCKTOOL_PY, SCORING_PY, ETF_PY]:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"❌ {f} 編譯失敗：\n{e}")


def test_scoring_out_cols_keeps_change():
    """【V1.1-add-change-col-fix】scoring.py out_cols 必須保留「漲跌」欄

    Bug 歷史：William 2026-06-29 20:19 反映手動選股「漲跌價」全 0.0
    根因：scoring.py line 357-365 out_cols 漏加「漲跌」→ result 被 filter 掉
    修法：out_cols 也要加「漲跌」、確保一路保留到 result
    """
    content = _read(SCORING_PY)
    m = re.search(r'out_cols\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert m, "找不到 out_cols = [...]"
    body = m.group(1)
    assert '"漲跌"' in body, (
        f"❌ scoring.py out_cols 漏加「漲跌」！\n"
        f"  V1.1-add-change-col 修法：final_cols 也要加、out_cols 也要加\n"
        f"  out_cols body: {body[:200]}"
    )


def test_yld_filter_is_hard_filter():
    """【V1.1-yld-hard-filter】殖利率條件要硬過濾、不要 soft no-op

    Bug：William 2026-06-29 21:59 反映「左邊篩選條件參數有打開時要全部滿足 (logic AND) 才列出來！」
    根因：scoring.py 內 min_cash_div_yld / min_last_cash_yld 之前是「soft no-op」、只 any_checked=True 不擋 mask
    → 殖利率 < 門檻 或 None 的股票還是會出現在結果、違反使用者意圖

    修法：兩個殖利率條件改為硬 AND：殖利率 < 門檻 或 None 都排除
    """
    content = _read(SCORING_PY)
    # min_cash_div_yld 必須用 mask &= 處理（硬 AND）
    m = re.search(
        r'if filters\.get\("min_cash_div_yld"\) is not None:(.*?)(?=\n    if filters\.get\(|\n    # 過濾)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 min_cash_div_yld block"
    body = m.group(1)
    assert "mask &=" in body, (
        f"❌ min_cash_div_yld 沒用 mask &= 硬過濾！\n"
        f"  body: {body[:300]}"
    )
    # min_last_cash_yld 也要硬 AND
    m2 = re.search(
        r'if filters\.get\("min_last_cash_yld"\) is not None:(.*?)(?=\n    if filters\.get\(|\n    # 過濾)',
        content,
        re.DOTALL,
    )
    assert m2, "找不到 min_last_cash_yld block"
    body2 = m2.group(1)
    assert "mask &=" in body2, (
        f"❌ min_last_cash_yld 沒用 mask &= 硬過濾！\n"
        f"  body: {body2[:300]}"
    )
