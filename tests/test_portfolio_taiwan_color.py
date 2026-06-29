"""【V1.1-portfolio-taiwan-color】買賣記錄台股慣例色彩守護

2026-06-29 10:16 William 反映：
- 「買賣紀錄中顯示profit + 改用紅字, - 改用綠字」

台股慣例：派 = 紅、跌 = 綠（與西方相反）
- POSITIVE profit (贖錢) → 紅 #c00000
- NEGATIVE profit (虧錢) → 綠 #0a7d2c
- ZERO → 預設色

套用範圍：
1. summary 4 個 labels（未實現損益 / 已實現淨損益 / 總報酬率 % / 總損益）
2. _positions_tree 持倉明細 整列顏色（以未實現損益為主指標）
3. _show_position_detail dialog 3 個 stat（未實現 / 預估淨收入 / 已實現）
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)
CONFIG_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "config.py"
)


# ──────────────────── 設定檔顏色常數守護 ────────────────────

def test_config_has_taiwan_color_constants():
    """【核心守護】config.py 必須有 COLOR_PROFIT_POS / NEG / ZERO 三個常數

    台股慣例：+ 紅、- 綠
    """
    with open(CONFIG_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "COLOR_PROFIT_POS" in content, "❌ config.py 缺少 COLOR_PROFIT_POS"
    assert "COLOR_PROFIT_NEG" in content, "❌ config.py 缺少 COLOR_PROFIT_NEG"
    assert "COLOR_PROFIT_ZERO" in content, "❌ config.py 缺少 COLOR_PROFIT_ZERO"


def test_config_pos_is_red_and_neg_is_green():
    """【核心守護】正數 = 紅 (#c00000)、負數 = 綠 (#0a7d2c)"""
    with open(CONFIG_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找出 COLOR_PROFIT_POS = "#xxxxxx"
    import re
    pos_match = re.search(r'COLOR_PROFIT_POS\s*=\s*"(#[0-9a-fA-F]{6})"', content)
    neg_match = re.search(r'COLOR_PROFIT_NEG\s*=\s*"(#[0-9a-fA-F]{6})"', content)
    assert pos_match, "❌ COLOR_PROFIT_POS 應為 hex 顏色"
    assert neg_match, "❌ COLOR_PROFIT_NEG 應為 hex 顏色"

    pos_color = pos_match.group(1).lower()
    neg_color = neg_match.group(1).lower()

    assert pos_color == "#c00000", (
        f"❌ COLOR_PROFIT_POS 應該是紅色 #c00000、實際 {pos_color}\n"
        f"  台股慣例：+ 紅、- 綠"
    )
    assert neg_color == "#0a7d2c", (
        f"❌ COLOR_PROFIT_NEG 應該是綠色 #0a7d2c、實際 {neg_color}"
    )


# ──────────────────── StockTool.py 引用常數守護 ────────────────────

def test_stocktool_imports_color_constants():
    """【核心守護】StockTool.py 必須 import 顏色常數（不要 hardcode）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "COLOR_PROFIT_POS" in content, "❌ StockTool.py 沒 import COLOR_PROFIT_POS"
    assert "COLOR_PROFIT_NEG" in content, "❌ StockTool.py 沒 import COLOR_PROFIT_NEG"
    # 確認有 import block
    import re
    assert re.search(
        r"from stocktool\.config import \([^)]*COLOR_PROFIT_POS",
        content,
        re.DOTALL,
    ), "❌ COLOR_PROFIT_POS 必須從 stocktool.config import、不能 hardcode"


def test_stocktool_no_hardcoded_profit_colors():
    """【核心守護】StockTool.py 不應再有 \"#0a7d2c\" / \"#c00000\" 硬編碼損益色

    之前的 bug：直接 hardcode 顏色、改不動集中管理
    修法：統一從 config.COLOR_PROFIT_* 來
    唯一例外：calendar.py 的「週日紅字」是另一個語境、不算損益色
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 損益相關的硬編碼不應再出現
    # 允許 #0a7d2c 跟 #c00000 出現在註解中（解釋台股慣例）
    # 但不應在程式碼邏輯中（if/else、color=、foreground=）
    import re

    # 抓出所有 "#0a7d2c" / "#c00000" 出現位置
    matches = re.findall(r"['\"]#0a7d2c['\"]|['\"]#c00000['\"]", content)
    assert len(matches) == 0, (
        f"❌ StockTool.py 還有 {len(matches)} 處硬編碼損益色（{matches}）！\n"
        f"  應改用 COLOR_PROFIT_POS / COLOR_PROFIT_NEG 從 config 拿"
    )


# ──────────────────── summary labels 色彩邏輯守護 ────────────────────

def test_summary_unrealized_pl_color_uses_taiwan_convention():
    """summary 的 total_unrealized_pl 顏色：>= 0 用 POS（紅）、< 0 用 NEG（綠）"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 pl_color 定義（前面有 pl_color = COLOR_PROFIT_POS if ... >= 0 else COLOR_PROFIT_NEG）
    import re
    matches = re.findall(
        r'pl_color\s*=\s*COLOR_PROFIT_POS\s+if\s+summary\.total_unrealized_pl\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ summary 的 total_unrealized_pl 顏色邏輯不對！\n"
        "  應該是：pl_color = COLOR_PROFIT_POS if summary.total_unrealized_pl >= 0 else COLOR_PROFIT_NEG"
    )


def test_summary_net_realized_color_uses_taiwan_convention():
    """summary 的 net_realized_pl 顏色：>= 0 用 POS、< 0 用 NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'net_color\s*=\s*COLOR_PROFIT_POS\s+if\s+summary\.net_realized_pl\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ summary 的 net_realized_pl 顏色邏輯不對！\n"
        "  應該是：net_color = COLOR_PROFIT_POS if summary.net_realized_pl >= 0 else COLOR_PROFIT_NEG"
    )


def test_summary_total_return_pct_color_uses_taiwan_convention():
    """summary 的 total_return_pct 顏色：>= 0 用 POS、< 0 用 NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'ret_color\s*=\s*COLOR_PROFIT_POS\s+if\s+summary\.total_return_pct\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ summary 的 total_return_pct 顏色邏輯不對！\n"
        "  應該是：ret_color = COLOR_PROFIT_POS if summary.total_return_pct >= 0 else COLOR_PROFIT_NEG"
    )


def test_summary_total_pl_color_uses_taiwan_convention():
    """summary 的 total_pl 顏色：>= 0 用 POS、< 0 用 NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'pl_color2\s*=\s*COLOR_PROFIT_POS\s+if\s+summary\.total_pl\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ summary 的 total_pl 顏色邏輯不對！\n"
        "  應該是：pl_color2 = COLOR_PROFIT_POS if summary.total_pl >= 0 else COLOR_PROFIT_NEG"
    )


# ──────────────────── _show_position_detail dialog 色彩守護 ────────────────────

def test_position_detail_unrealized_uses_taiwan_convention():
    """交易明細 dialog 的「未實現損益」用 POS/NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'COLOR_PROFIT_POS\s+if\s+unrealized_pl\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ _show_position_detail 的未實現損益顏色邏輯不對！"
    )


def test_position_detail_realized_uses_taiwan_convention():
    """交易明細 dialog 的「已實現損益（扣費稅）」用 POS/NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'COLOR_PROFIT_POS\s+if\s+realized_pl\s*>=\s*0\s+else\s+COLOR_PROFIT_NEG',
        content,
    )
    assert len(matches) >= 1, (
        "❌ _show_position_detail 的已實現損益顏色邏輯不對！"
    )


def test_position_detail_est_net_uses_taiwan_convention():
    """交易明細 dialog 的「預估淨收入」用 POS/NEG"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    import re
    matches = re.findall(
        r'COLOR_PROFIT_POS\s+if\s+est_net\s*>=\s*cur_mv',
        content,
    )
    assert len(matches) >= 1, (
        "❌ _show_position_detail 的預估淨收入顏色邏輯不對！"
    )


# ──────────────────── _positions_tree 標籤守護 ────────────────────

def test_positions_tree_has_profit_tags():
    """_positions_tree 必須有 profit_pos / profit_neg / profit_zero 三個 tag"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert 'tag_configure("profit_pos"' in content, (
        "❌ _positions_tree 沒 tag_configure profit_pos"
    )
    assert 'tag_configure("profit_neg"' in content, (
        "❌ _positions_tree 沒 tag_configure profit_neg"
    )
    assert 'tag_configure("profit_zero"' in content, (
        "❌ _positions_tree 沒 tag_configure profit_zero"
    )


def test_positions_tree_insert_uses_profit_tag():
    """持倉明細 insert 時必須用 profit_pos / profit_neg / profit_zero tag

    主要指標：current_price > 0 → unrealized_pl、否則 realized_pl
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _positions_tree.insert( ... tags=(row_tag,) )
    import re
    matches = re.findall(
        r'_positions_tree\.insert\(""?,?\s*"end",\s*values=.*?tags=\(row_tag,\)',
        content,
        re.DOTALL,
    )
    assert len(matches) >= 1, (
        "❌ _positions_tree.insert 沒帶 tags=(row_tag,)\n"
        "  應該在 insert 時把 row_tag 帶進去（profit_pos/neg/zero）"
    )

    # 確認 row_tag 計算邏輯
    assert re.search(
        r'if\s+p\.current_price\s*>\s*0:\s*\n\s*primary_pl\s*=\s*p\.unrealized_pl',
        content,
    ), "❌ primary_pl 邏輯：current_price > 0 → unrealized_pl"


# ──────────────────── 語法守護 ────────────────────

def test_stocktool_compiles():
    """【語法守護】改完沒漏逗號 / indent 錯誤"""
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")


def test_config_compiles():
    """config.py 編譯 OK"""
    import py_compile
    try:
        py_compile.compile(CONFIG_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ config.py 編譯失敗：\n{e}")


# ──────────────────── 整合測試 ────────────────────

def test_import_color_constants_actually_works():
    """【整合測試】真的能從 config 拿顏色"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    from stocktool.config import COLOR_PROFIT_POS, COLOR_PROFIT_NEG, COLOR_PROFIT_ZERO
    assert COLOR_PROFIT_POS == "#c00000", f"❌ POS 應為 #c00000、實際 {COLOR_PROFIT_POS}"
    assert COLOR_PROFIT_NEG == "#0a7d2c", f"❌ NEG 應為 #0a7d2c、實際 {COLOR_PROFIT_NEG}"
    # ZERO 隨意顏色都行、只要是 hex
    import re
    assert re.match(r"^#[0-9a-fA-F]{6}$", COLOR_PROFIT_ZERO), (
        f"❌ ZERO 應為 hex 顏色、實際 {COLOR_PROFIT_ZERO}"
    )


def test_taiwan_color_decision_logic():
    """【整合測試】驗證台股慣例決策邏輯

    + → 紅 (POS)
    - → 綠 (NEG)
    0 → 任意（zero 標籤）
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    from stocktool.config import COLOR_PROFIT_POS, COLOR_PROFIT_NEG

    def decide_color(value):
        """模擬 summary / dialog 用的顏色決策"""
        if value >= 0:
            return COLOR_PROFIT_POS
        else:
            return COLOR_PROFIT_NEG

    assert decide_color(100) == COLOR_PROFIT_POS, "正值 100 應為紅"
    assert decide_color(0) == COLOR_PROFIT_POS, "零 0 應為紅（>= 0 走 POS）"
    assert decide_color(0.5) == COLOR_PROFIT_POS, "正值 0.5 應為紅"
    assert decide_color(-100) == COLOR_PROFIT_NEG, "負值 -100 應為綠"
    assert decide_color(-0.5) == COLOR_PROFIT_NEG, "負值 -0.5 應為綠"
