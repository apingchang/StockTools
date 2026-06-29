"""【V1.1-price-color】3 個選股 tree 漲跌價欄位染色守護

2026-06-29 14:12 William 反映：
- 「選股結果中的股價和漲跌價若是漲用紅字跌用綠字」

【修法】
- 新增 _price_tag_for(v) helper：
  - v > 0 → "price_up" (紅 #c00000)
  - v < 0 → "price_down" (綠 #0a7d2c)
  - v == 0 / None / NaN → "price_zero" (深灰 #222222)
- 3 個選股 tree 都註冊 price_up/price_down/price_zero tag (只設 foreground)
- row tags 從單 tag → tuple ("checked" / "unchecked", "price_*")
  - ttk.Treeview 支援多 tag 組合 → background 由 checked/unchecked 控、foreground 由 price_* 控
- 保留所有 hover / select 行為：price_* tag 一路跟著 row
- 新增 _select_price_tags / _ms_price_tags / _etf_price_tags dict 存每個 iid 的 price_* tag

【關鍵設計】
- 原本用 tag 同時表示「勾選 + 顏色」會衝突
- 改用 row tag tuple：「勾選狀態 tag」(背景) + 「顏色 tag」(前景) 分工
- 切換勾選 / hover 都要保留 price_* tag（否則顏色會跳回黑色）
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)
CONFIG_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "config.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────── color constants 守護 ────────────────────

def test_color_profit_constants_exist():
    """COLOR_PROFIT_POS / NEG / ZERO 必須存在"""
    content = _read(CONFIG_PY)
    assert "COLOR_PROFIT_POS = " in content, "缺少 COLOR_PROFIT_POS"
    assert "COLOR_PROFIT_NEG = " in content, "缺少 COLOR_PROFIT_NEG"
    assert "COLOR_PROFIT_ZERO = " in content, "缺少 COLOR_PROFIT_ZERO"


def test_color_profit_pos_is_red():
    """COLOR_PROFIT_POS 必須是紅色（台股慣例：+紅）"""
    content = _read(CONFIG_PY)
    m = re.search(r'COLOR_PROFIT_POS\s*=\s*"([^"]+)"', content)
    assert m, "找不到 COLOR_PROFIT_POS"
    color = m.group(1).lower()
    # 紅色特徵：R 高、G 低、B 低
    assert color.startswith("#c") or color.startswith("#d") or color.startswith("#e") or color.startswith("#f"), (
        f"COLOR_PROFIT_POS 應為紅色系、實際 {color}"
    )


def test_color_profit_neg_is_green():
    """COLOR_PROFIT_NEG 必須是綠色（台股慣例：-綠）"""
    content = _read(CONFIG_PY)
    m = re.search(r'COLOR_PROFIT_NEG\s*=\s*"([^"]+)"', content)
    assert m, "找不到 COLOR_PROFIT_NEG"
    color = m.group(1).lower()
    # 綠色特徵：G 高、R 低
    assert "0a" in color or "0b" in color or "0c" in color or "1a" in color or "2a" in color, (
        f"COLOR_PROFIT_NEG 應為綠色系、實際 {color}"
    )


# ──────────────────── _price_tag_for helper 守護 ────────────────────

def test_price_tag_for_helper_exists():
    """_price_tag_for helper 必須存在"""
    content = _read(STOCKTOOL_PY)
    assert "def _price_tag_for(" in content, "缺少 _price_tag_for helper"


def test_price_tag_for_positive():
    """正數應回傳 price_up"""
    def _price_tag_for(v):
        try:
            if v is None:
                return "price_zero"
            f = float(v)
            if f > 0:
                return "price_up"
            elif f < 0:
                return "price_down"
            else:
                return "price_zero"
        except (TypeError, ValueError):
            return "price_zero"

    assert _price_tag_for(5.0) == "price_up", "正數 5.0 → price_up"
    assert _price_tag_for(0.05) == "price_up", "小正數 0.05 → price_up"
    assert _price_tag_for(123.4) == "price_up", "正數 123.4 → price_up"


def test_price_tag_for_negative():
    """負數應回傳 price_down"""
    def _price_tag_for(v):
        try:
            if v is None:
                return "price_zero"
            f = float(v)
            if f > 0:
                return "price_up"
            elif f < 0:
                return "price_down"
            else:
                return "price_zero"
        except (TypeError, ValueError):
            return "price_zero"

    assert _price_tag_for(-3.2) == "price_down", "負數 -3.2 → price_down"
    assert _price_tag_for(-0.5) == "price_down", "小負數 -0.5 → price_down"


def test_price_tag_for_zero():
    """零 / None / NaN / 字串 → price_zero"""
    def _price_tag_for(v):
        try:
            if v is None:
                return "price_zero"
            f = float(v)
            if f > 0:
                return "price_up"
            elif f < 0:
                return "price_down"
            else:
                return "price_zero"
        except (TypeError, ValueError):
            return "price_zero"

    assert _price_tag_for(0) == "price_zero", "0 → price_zero"
    assert _price_tag_for(0.0) == "price_zero", "0.0 → price_zero"
    assert _price_tag_for(None) == "price_zero", "None → price_zero"
    assert _price_tag_for(float("nan")) == "price_zero", "NaN → price_zero"
    assert _price_tag_for("abc") == "price_zero", "字串 → price_zero"


# ──────────────────── 3 個 tree tag_configure 守護 ────────────────────

def test_select_tree_has_price_tags():
    """select_tree (系統選股) 必須有 price_up/price_down/price_zero tag"""
    content = _read(STOCKTOOL_PY)
    # 找 _build_tab_layout 內的 tag_configure（給 select_tree + ms_tree 共用）
    m = re.search(
        r'def _build_tab_layout\(self, parent\):.*?return\s+',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _build_tab_layout"
    body = m.group(0)
    assert 'tag_configure("price_up"' in body, "select_tree 缺 price_up tag"
    assert 'tag_configure("price_down"' in body, "select_tree 缺 price_down tag"
    assert 'tag_configure("price_zero"' in body, "select_tree 缺 price_zero tag"


def test_ms_tree_has_price_tags():
    """_ms_tree (手動選股) 必須有 price_up/price_down/price_zero tag"""
    content = _read(STOCKTOOL_PY)
    # 找 _ms_tree.tag_configure 區塊
    m_ms = content.find("self._ms_tree.tag_configure")
    # 往後看 200 行內有 3 個 price_* tag
    snippet = content[m_ms : m_ms + 2000]
    assert 'tag_configure("price_up"' in snippet, "_ms_tree 缺 price_up tag"
    assert 'tag_configure("price_down"' in snippet, "_ms_tree 缺 price_down tag"
    assert 'tag_configure("price_zero"' in snippet, "_ms_tree 缺 price_zero tag"


def test_etf_tree_has_price_tags():
    """_etf_tree (ETF 選股) 必須有 price_up/price_down/price_zero tag"""
    content = _read(STOCKTOOL_PY)
    m_etf = content.find("self._etf_tree.tag_configure")
    snippet = content[m_etf : m_etf + 2000]
    assert 'tag_configure("price_up"' in snippet, "_etf_tree 缺 price_up tag"
    assert 'tag_configure("price_down"' in snippet, "_etf_tree 缺 price_down tag"
    assert 'tag_configure("price_zero"' in snippet, "_etf_tree 缺 price_zero tag"


# ──────────────────── row tag tuple 守護 ────────────────────

def test_select_tree_insert_uses_price_tag():
    """_display_select_results insert 必須用 price_* tag"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _display_select_results\(self, df_sel\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _display_select_results"
    body = m.group(1)
    assert "_price_tag_for(" in body, "_display_select_results 沒用 _price_tag_for"
    assert '_select_price_tags' in body, "_display_select_results 沒存 _select_price_tags"
    assert 'tags=(tag, price_tag)' in body or "tags=(tag,price_tag)" in body, (
        "_display_select_results insert 沒用 price_* tag tuple"
    )


def test_ms_tree_insert_uses_price_tag():
    """_ms_display_results insert 必須用 price_* tag"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _ms_display_results\(self, result\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _ms_display_results"
    body = m.group(1)
    assert "_price_tag_for(" in body, "_ms_display_results 沒用 _price_tag_for"
    assert '_ms_price_tags' in body, "_ms_display_results 沒存 _ms_price_tags"
    assert "tags=(tag, price_tag)" in body or "tags=(tag,price_tag)" in body, (
        "_ms_display_results insert 沒用 price_* tag tuple"
    )


def test_etf_tree_insert_uses_price_tag():
    """_etf_display_results insert 必須用 price_* tag"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _etf_display_results\(self, agg_df, change_df=None\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _etf_display_results"
    body = m.group(1)
    assert "_price_tag_for(" in body, "_etf_display_results 沒用 _price_tag_for"
    assert '_etf_price_tags' in body, "_etf_display_results 沒存 _etf_price_tags"
    assert 'tags=("unchecked", _price_tag_for(' in body, (
        "_etf_display_results insert 沒用 price_* tag tuple"
    )


# ──────────────────── hover 保留 price tag 守護 ────────────────────

def test_select_hover_preserves_price_tag():
    """select_tree hover 進入要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _on_select_tree_hover\(self, event\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_select_tree_hover"
    body = m.group(1)
    assert "_select_price_tags" in body, "_on_select_tree_hover 沒讀 _select_price_tags"
    assert 'tags=(price_tag, "hover")' in body or 'tags=(price_tag,"hover")' in body, (
        "_on_select_tree_hover 沒保留 price_* tag"
    )


def test_ms_hover_preserves_price_tag():
    """_ms_tree hover 進入要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    # 兩個 hover 都查
    for name in ["_ms_tree_hover", "_on_tree_hover"]:
        m = re.search(
            rf'def {name}\(self, event\):(.*?)(?=\n    def |\Z)',
            content,
            re.DOTALL,
        )
        if not m:
            continue
        body = m.group(1)
        assert "_ms_price_tags" in body, f"{name} 沒讀 _ms_price_tags"
        assert 'tags=(price_tag, "hover")' in body or 'tags=(price_tag,"hover")' in body, (
            f"{name} 沒保留 price_* tag"
        )


def test_etf_hover_preserves_price_tag():
    """_etf_tree hover 進入要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    m = re.search(
        r'def _on_etf_tree_hover\(self, event\):(.*?)(?=\n    def |\Z)',
        content,
        re.DOTALL,
    )
    assert m, "找不到 _on_etf_tree_hover"
    body = m.group(1)
    assert "_etf_price_tags" in body, "_on_etf_tree_hover 沒讀 _etf_price_tags"
    assert 'tags=(price_tag, "hover")' in body or 'tags=(price_tag,"hover")' in body, (
        "_on_etf_tree_hover 沒保留 price_* tag"
    )


# ──────────────────── 勾選切換保留 price tag 守護 ────────────────────

def test_select_toggle_preserves_price_tag():
    """_select_all / _select_none / click toggle 都要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    for name in ["_select_all", "_select_none", "_on_select_tree_click"]:
        m = re.search(
            rf'def {name}\(self, event=None, tree=None\):(.*?)(?=\n    def |\Z)',
            content,
            re.DOTALL,
        )
        if not m:
            # 試其他簽名
            m = re.search(
                rf'def {name}\(self, event\):(.*?)(?=\n    def |\Z)',
                content,
                re.DOTALL,
            )
        if not m:
            m = re.search(
                rf'def {name}\(self, tree=None\):(.*?)(?=\n    def |\Z)',
                content,
                re.DOTALL,
            )
        if not m:
            continue
        body = m.group(1)
        # 三個都要讀 _select_price_tags
        if name == "_on_select_tree_click":
            assert "_select_price_tags" in body, f"{name} 沒讀 _select_price_tags"


def test_ms_toggle_preserves_price_tag():
    """_ms_select_all / _ms_select_none / _ms_toggle_check 都要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    for name in ["_ms_select_all", "_ms_select_none", "_ms_toggle_check"]:
        m = re.search(
            rf'def {name}\(self, event=None\):(.*?)(?=\n    def |\Z)',
            content,
            re.DOTALL,
        )
        if not m:
            m = re.search(
                rf'def {name}\(self\):(.*?)(?=\n    def |\Z)',
                content,
                re.DOTALL,
            )
        if not m:
            continue
        body = m.group(1)
        if "_ms_tree" in body:
            assert "_ms_price_tags" in body, f"{name} 沒讀 _ms_price_tags"


def test_etf_toggle_preserves_price_tag():
    """_etf_select_all / _etf_select_none / _etf_toggle_check 都要保留 price_* tag"""
    content = _read(STOCKTOOL_PY)
    for name in ["_etf_select_all", "_etf_select_none", "_etf_toggle_check"]:
        m = re.search(
            rf'def {name}\(self, event=None\):(.*?)(?=\n    def |\Z)',
            content,
            re.DOTALL,
        )
        if not m:
            m = re.search(
                rf'def {name}\(self\):(.*?)(?=\n    def |\Z)',
                content,
                re.DOTALL,
            )
        if not m:
            continue
        body = m.group(1)
        if "_etf_tree" in body:
            assert "_etf_price_tags" in body, f"{name} 沒讀 _etf_price_tags"


# ──────────────────── 語法守護 ────────────────────

def test_all_files_compile():
    """所有改動檔案能編譯"""
    import py_compile
    for f in [STOCKTOOL_PY, CONFIG_PY]:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"❌ {f} 編譯失敗：\n{e}")