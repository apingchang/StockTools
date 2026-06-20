"""V0.9.5-etf-popup-spacing tests

1. 拿掉 title 的 emoji
2. Text widget 加 spacing1=4 spacing3=4（行間呼吸感）
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_popup_title_no_emoji():
    """V0.9.5-etf-history：popup_title 在 etf_list mode 中"""

    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # V0.9.5-etf-history：popup_text = etf_list_str（不含 emoji）
    # 只檢查 popup_title = f"..." 不含 📊（若有設 title 的話）
    popup_title_match = re.search(r"popup_title\s*=\s*f?\"([^\"]+)\"", content)
    if popup_title_match:
        title_template = popup_title_match.group(1)
        assert "📊" not in title_template, (
            f"❌ popup_title 還有 📊 icon！：{title_template}"
        )
    # 如果只有 popup_text = etf_list_str，也是一樣（etf_list_str 沒 emoji）


def test_popup_text_has_spacing():
    """Text widget 必須有 spacing1 + spacing3 設定"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert re.search(r"spacing1\s*=\s*4", content), (
        "❌ popup Text widget 缺少 spacing1=4"
    )
    assert re.search(r"spacing3\s*=\s*4", content), (
        "❌ popup Text widget 缺少 spacing3=4"
    )


def test_popup_text_uses_max_line_width():
    """popup width 必須用 max_line_len 自動算"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert "_display_width" in content, "❌ 缺少 _display_width helper"
    assert re.search(r"max_line_len\s*=\s*max\(_display_width", content), (
        "❌ popup width 計算沒用 max_line_len"
    )


def test_popup_text_height_capped():
    """popup height 最多 25 行"""
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    assert re.search(r"height\s*=\s*min\(total_lines,\s*25\)", content), (
        "❌ popup height 沒有限制在 25 行以內"
    )
