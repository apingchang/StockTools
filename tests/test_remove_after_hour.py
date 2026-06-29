"""【V1.1-remove-after-hour】盤後量欄位移除守護

2026-06-29 13:46 William 反映：
- 「手動選股結果盤後量都沒資料、取消顯示！」

【根因】
- TWSE BFT41U API 只回個位數筆個股、TPEx 上櫃無公開 API
- 絕大多數個股顯示 '—'、欄位沒實質用處

【修法】
- 拿掉 _ms_tree 的「盤後量(張)」欄位（15 欄 → 14 欄）
- 拿掉 _ms_display_results 的 after_hour_vol 邏輯
- 拿掉 scoring.py 的 price_cols / out_cols / final_cols / rename 中的「盤後量_股」
- 拿掉 fetch_market.py 的 fetch_after_hour_volumes() 函數 + Step 6 整合 + return cols
- 拿掉 cache 沒有「盤後量_股」時補 None 的防呆

【Guard 守護】本檔案只測「不要再加回來」
- fetch_after_hour_volumes 函數不存在
- 欄位「盤後量(張)」不在 _ms_tree cols
- 欄位「盤後量_股」不在 price_df / out_cols / final_cols / rename
- API URL BFT41U 不在 fetch_market.py
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
FETCH_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "fetch_market.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────── 函數移除守護 ────────────────────

def test_fetch_after_hour_volumes_function_removed():
    """【核心守護】fetch_market.py 不能再有 fetch_after_hour_volumes 函數"""
    content = _read(FETCH_PY)
    assert "def fetch_after_hour_volumes" not in content, (
        "❌ fetch_market.py 還有 fetch_after_hour_volumes 函數！\n"
        "  V1.1-remove-after-hour 已拿掉（William 反映盤後量無資料、取消顯示）\n"
        "  不應再加回來"
    )


def test_bft41u_url_removed():
    """【核心守護】BFT41U API URL 不應在程式碼中（已拿掉 fetch_after_hour_volumes）"""
    content = _read(FETCH_PY)
    # 允許出現在註解中（解釋為何拿掉）、但不能是可執行的 request URL
    code_only_lines = [
        line for line in content.split("\n")
        if line and line[0] in (" ", "\t")
        and not line.lstrip().startswith("#")
    ]
    code_only = "\n".join(code_only_lines)
    assert "BFT41U" not in code_only, (
        "❌ fetch_market.py 還有 BFT41U URL 在可執行程式碼中！\n"
        "  V1.1-remove-after-hour 已拿掉盤後量抓取"
    )


# ──────────────────── StockTool 欄位守護 ────────────────────

def test_ms_tree_no_盤後量_column():
    """【核心守護】_ms_tree cols 不該有「盤後量(張)」"""
    content = _read(STOCKTOOL_PY)
    assert '"盤後量(張)"' not in content, (
        "❌ _ms_tree 還有「盤後量(張)」欄位！\n"
        "  V1.1-remove-after-hour 已拿掉（William 反映無資料）"
    )
    assert "'盤後量(張)'" not in content, (
        "❌ _ms_tree 還有「盤後量(張)」欄位（單引號）！"
    )


def test_ms_display_results_no_after_hour_logic():
    """【核心守護】_ms_display_results code 不該有 after_hour_vol 變數邏輯"""
    content = _read(STOCKTOOL_PY)
    # 找 _ms_display_results 函數範圍
    m = re.search(r"def _ms_display_results\(.*?(?=\n    def |\Z)", content, re.DOTALL)
    assert m, "找不到 _ms_display_results 函數"
    fn_body = m.group(0)
    # 函數內不能有 after_hour_vol 變數
    code_lines = [
        line for line in fn_body.split("\n")
        if line and line[0] in (" ", "\t")
        and not line.lstrip().startswith("#")
    ]
    code_only = "\n".join(code_lines)
    assert "after_hour_vol" not in code_only, (
        "❌ _ms_display_results code 還有 after_hour_vol 邏輯！\n"
        "  應一併拿掉（欄位已拿掉）"
    )


def test_ms_tree_cols_count_14():
    """_ms_tree 應該 14 欄（拿掉 1 個後）

    用 balanced paren parser 避免被「成交量(張)」裡的 ) 誤判
    """
    content = _read(STOCKTOOL_PY)
    # 找 self._ms_tree = ttk.Treeview 之前的最後一個 cols = (...)
    m_tree = content.find("self._ms_tree = ttk.Treeview")
    if m_tree < 0:
        pytest.skip("找不到 self._ms_tree = ttk.Treeview")
    before = content[:m_tree]
    cols_start = before.rfind("cols = (")
    if cols_start < 0:
        pytest.skip("找不到 cols = (...)")
    paren_start = before.find("(", cols_start)
    # balanced paren parser、跳過字串內的 ( )
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
    n = len(re.findall(r'"[^"]*"|\'[^\']*\'', cols_body))
    assert n == 14, (
        f"❌ _ms_tree cols 應該 14 欄、實際 {n} 欄\n"
        f"  cols body: {cols_body[:300]}..."
    )


# ──────────────────── scoring.py 欄位守護 ────────────────────

def test_scoring_no_盤後量_股_in_price_cols():
    """scoring.py price_cols 不該有「盤後量_股」"""
    content = _read(SCORING_PY)
    m = re.search(r'price_cols\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert m, "找不到 price_cols = [...]"
    body = m.group(1)
    assert '"盤後量_股"' not in body, (
        f"❌ scoring.py price_cols 還有「盤後量_股」！\n"
        f"  body: {body}"
    )


def test_scoring_no_盤後量_股_in_out_cols():
    """scoring.py out_cols 不該有「盤後量_股」"""
    content = _read(SCORING_PY)
    m = re.search(r'out_cols\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert m, "找不到 out_cols = [...]"
    body = m.group(1)
    assert '"盤後量_股"' not in body, (
        f"❌ scoring.py out_cols 還有「盤後量_股」！"
    )


def test_scoring_no_盤後量_股_in_final_cols():
    """scoring.py final_cols 不該有「盤後量_股」"""
    content = _read(SCORING_PY)
    m = re.search(r'final_cols\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert m, "找不到 final_cols = [...]"
    body = m.group(1)
    assert '"盤後量_股"' not in body, (
        f"❌ scoring.py final_cols 還有「盤後量_股」！"
    )


def test_scoring_no_盤後量_rename():
    """scoring.py 不該有「盤後量_股」:「盤後量(張)」的 rename"""
    content = _read(SCORING_PY)
    assert '"盤後量_股": "盤後量(張)"' not in content, (
        "❌ scoring.py 還有「盤後量_股」:「盤後量(張)」的 rename！"
    )


# ──────────────────── 語法守護 ────────────────────

def test_all_files_compile():
    """所有改動檔案都能編譯"""
    import py_compile
    for f in [STOCKTOOL_PY, SCORING_PY, FETCH_PY]:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"❌ {f} 編譯失敗：\n{e}")
