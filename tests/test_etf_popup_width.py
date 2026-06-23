"""【V0.9.5-etf-popup-width】popup 寬度對中文計算守護

2026-06-20 11:50 William 反映 v0.9.5-etf-popup-spacing 截圖：
- popup 後面有好幾個字被截斷、看不到完整 ETF 列表

【根因】
- Text widget 的 width 是「平均字元寬度」單位
- 我用 max(len(line) for line in lines) 算 width
- 但中文實際寬度 ≈ 2× ASCII 寬度
- 結果：width 計算偏小、中文字超出 width、後面被截斷

【修法】新加 _display_width helper
- 中文（CJK + 全形 + 平假名/片假名）算 2 字元
- 其他（ASCII、半形標點）算 1 字元
- popup width 改用 _display_width(line) 計算
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_display_width_helper_exists():
    """【核心守護】StockTool.py 必須有 _display_width helper

    【v1.1 重構】已搬到 stocktool/etf.py
    """
    ETF_PY = os.path.join(
        os.path.dirname(__file__), "..", "source", "stocktool", "etf.py"
    )
    target = ETF_PY if os.path.exists(ETF_PY) else STOCKTOOL_PY
    with open(target, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"def _display_width\(s:\s*str\)\s*->\s*int:", content)
    assert match, (
        f"❌ {target} 找不到 _display_width helper！\n"
        "popup 需要它來計算 Text widget 寬度（中文字算 2、其他算 1）。"
    )


def test_display_width_counts_cjk_as_double():
    """【核心守護】_display_width 必須把 CJK 算 2、ASCII 算 1
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    from StockTool import _display_width

    # ASCII 算 1
    assert _display_width("ABC") == 3, f"ASCII 'ABC' 應該是 3、實際 {_display_width('ABC')}"
    assert _display_width("12345") == 5, f"ASCII '12345' 應該是 5"

    # 中文算 2
    assert _display_width("台積電") == 6, f"中文「台積電」應該是 6（3×2）、實際 {_display_width('台積電')}"
    assert _display_width("中") == 2, f"「中」應該是 2"

    # 混合
    # "2330 台積電" = 4 (ASCII) + 1 (空格) + 6 (中文) = 11
    assert _display_width("2330 台積電") == 11, (
        f"「2330 台積電」應該是 11、實際 {_display_width('2330 台積電')}"
    )
    # "00980A 主動野村臺灣優選" = 6 (ASCII) + 1 (空格) + 16 (中文×8) = 23
    s = "00980A 主動野村臺灣優選"
    expected = 6 + 1 + 8 * 2
    assert _display_width(s) == expected, (
        f"「{s}」應該是 {expected}、實際 {_display_width(s)}"
    )

    # 全形標點也算 2
    # 「（」= U+FF08 = 0xFF08 → in range 0xFF00-0xFFEF → 算 2
    assert _display_width("（") == 2, f"全形「（」應該是 2"


def test_popup_uses_display_width_for_width():
    """【核心守護】_show_etf_popup 的 width 計算必須用 _display_width、不是 len()
    → 避免中文被截斷
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _show_etf_popup method 內 width 計算那段
    match = re.search(
        r"max_line_len\s*=\s*max\(([^)]+)\)\s*for\s+line\s+in\s+lines",
        content,
    )
    assert match, "❌ 找不到 max_line_len = max(...) for line in lines"
    expr = match.group(1)

    # 必須用 _display_width、不是 len
    assert "_display_width" in expr, (
        f"❌ popup width 計算沒用 _display_width！\n"
        f"目前是 max({expr.strip()})、會讓中文被截斷。\n"
        f"改成 max(_display_width(line) for line in lines)"
    )
    assert "len(line)" not in expr and "len(" not in expr, (
        f"❌ popup width 不該用 len(line)！中文會被截斷。\n"
        f"目前是 max({expr.strip()})"
    )


def test_popup_method_compiles():
    """【語法守護】_show_etf_popup 改完沒漏逗號 / indent 錯誤
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")