"""【V0.9.5-etf-popup-spacing】popup 行距 + 拿掉 icon 守護

2026-06-20 11:39 William 反映 v0.9.5-etf-popup-fix 截圖：
- 第一行最前面有 📊 icon、不要
- 行字間隔太小、太擠不好讀

【修法】
1. 拿掉 title 的 📊
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
    """【核心守護】title 不應該有 emoji（如 📊）
    → William 不要 icon
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 title = f"..." 那段
    match = re.search(r'title\s*=\s*f"([^"]*)"', content)
    assert match, "❌ 找不到 title = f\"...\""
    title_template = match.group(1)

    # 不該有 📊
    assert "📊" not in title_template, (
        f"❌ title 還有 📊 icon！\n"
        f"William 11:39 反映、不要 icon。\n"
        f"目前 title template：{title_template}"
    )

    # 也不該有其他常見 emoji（圖示類）
    other_emojis = ["📈", "📉", "📊", "💰", "📌", "⭐", "✅", "❌"]
    for emoji in other_emojis:
        assert emoji not in title_template, (
            f"❌ title 不該有 emoji「{emoji}」、目前 template：{title_template}"
        )

    # 應該有股票代號 + 名稱 + 「被 N 檔 ETF 持有」
    assert "{stock_code}" in title_template, "❌ title 應該包含 {stock_code}"
    assert "{stock_name}" in title_template, "❌ title 應該包含 {stock_name}"
    assert "{etf_count}" in title_template, "❌ title 應該包含 {etf_count}"
    assert "被" in title_template and "ETF" in title_template and "持有" in title_template, (
        f"❌ title 應該包含「被 N 檔 ETF 持有」描述、目前：{title_template}"
    )


def test_popup_text_has_spacing():
    """【核心守護】popup Text widget 必須有 spacing1 + spacing3 設定
    → 預設 spacing1=0 spacing3=0、行間太擠
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 _etf_popup_text = tk.Text(...) 設定（用括號平衡處理 nested parens）
    idx = content.find("self._etf_popup_text")
    assert idx >= 0, "❌ 找不到 _etf_popup_text"
    # 跳到第一個 (
    open_paren = content.find("(", idx)
    assert open_paren >= 0, "❌ _etf_popup_text 後面沒有 ("
    depth = 1
    i = open_paren + 1
    while i < len(content) and depth > 0:
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
        i += 1
    text_body = content[open_paren + 1:i - 1]

    # 必須有 spacing1= 跟 spacing3=
    spacing1_match = re.search(r"spacing1\s*=\s*(\d+)", text_body)
    spacing3_match = re.search(r"spacing3\s*=\s*(\d+)", text_body)

    assert spacing1_match, "❌ 找不到 spacing1 設定（行間 padding）"
    assert spacing3_match, "❌ 找不到 spacing3 設定（行間 padding）"

    spacing1_val = int(spacing1_match.group(1))
    spacing3_val = int(spacing3_match.group(1))

    # 至少要有 > 0、避免預設擠在一起
    assert spacing1_val >= 2, f"❌ spacing1={spacing1_val} 太小、看不出差異（建議 >= 2）"
    assert spacing3_val >= 2, f"❌ spacing3={spacing3_val} 太小、看不出差異（建議 >= 2）"
    # 不該太大、避免 popup 撐爆螢幕
    assert spacing1_val <= 12, f"❌ spacing1={spacing1_val} 太大、popup 會太高"
    assert spacing3_val <= 12, f"❌ spacing3={spacing3_val} 太大、popup 會太高"


def test_popup_method_compiles():
    """【語法守護】_show_etf_popup 改完沒漏逗號 / indent 錯誤
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")