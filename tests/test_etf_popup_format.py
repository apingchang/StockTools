"""【V0.9.5-etf-popup-fix】ETF hover popup 格式守護

2026-06-20 10:21 William 反映：
- hover 到「2330 台積電 / ETF 數 18」欄 → popup 顯示「金像電子（股）公司」這種擠在一起文字
- 看不出每個 ETF 代號跟名稱、無法閱讀

【根因】
- aggregate_etf_holdings 用 " | " 把 18 個 ETF 串成一行塞進 etf_list
- popup 用 Label 顯示、Label 把整段當成一行算寬度 → 被擠壓
- 結果：一行長字串 → 被擠成「金像電子（股）公司」這種難以辨識的 column

【修法】
1. etf_list 分隔符：「 | 」→ 「\n」（每個 ETF 一行）
2. popup widget：Label → Text widget（以最長那行算寬度、不會被擠壓）
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def test_etf_list_uses_newline_separator():
    """【核心守護】aggregate_etf_holdings 產出的 etf_list 用 \\n 分隔、不再用 " | "
    → 讓 popup 可以一行一個 ETF 顯示
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # 找 etf_list 定義的那段（aggregate_etf_holdings 內）
    # 規則：找 "etf_list" : <expr> 的設定
    pattern = r'"etf_list"\s*:\s*(.+?)(?=,\s*\n\s*}|$)'
    m = re.search(pattern, content, re.DOTALL)
    assert m, "❌ 找不到 etf_list 定義"

    expr = m.group(1).strip()
    # 必須是 "\n".join(etf_entries)、不該有 " | "
    assert '" | "' not in expr, (
        f"❌ etf_list 還在用 \" | \" 分隔！\n"
        f"  這會讓 popup 顯示成一行很長的字串、被 Label 擠壓。\n"
        f"  改成 \"\\n\".join(etf_entries)、每個 ETF 一行。"
    )
    assert '"\\n"' in expr or "chr(10)" in expr or '"\\\\n"' in expr, (
        f"❌ etf_list 應該用 \\n 分隔、目前是：{expr[:80]}"
    )


def test_etf_popup_widget_is_text():
    """【核心守護】popup widget 必須是 Text、不能退回 Label
    → Label 多行會被擠成最長那行寬度、視覺擠在一起
    → Text 會以 max line width 算寬度、每行清楚顯示
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    # _etf_show_hover_popup method 內應該用 Text widget
    assert "_etf_popup_text" in content, (
        "❌ 找不到 _etf_popup_text 屬性！\n"
        "popup widget 應該從 Label 改成 Text。"
    )
    # 用 self._etf_popup_text = tk.Text(...)
    assert re.search(
        r"self\._etf_popup_text\s*=\s*tk\.Text\(",
        content,
    ), "❌ _etf_popup_text 應該是 tk.Text()"

    # 反面：_etf_popup_label 應該被移除（避免忘記切換）
    assert "_etf_popup_label" not in content, (
        "❌ _etf_popup_label 還在！應該改用 _etf_popup_text (Text widget)。"
    )


def _find_size_config_body(content: str) -> str:
    """找 _etf_popup_text.config(...) 同時含 width= 和 height= 的 config call"""
    # 先找出所有 _etf_popup_text.config(...) 的範圍（含括號平衡）
    config_calls = []
    pattern = re.compile(r"self\._etf_popup_text\.config\(")
    for m in pattern.finditer(content):
        start = m.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            if content[i] == "(":
                depth += 1
            elif content[i] == ")":
                depth -= 1
            i += 1
        body = content[start:i - 1]
        config_calls.append(body)
    # 找同時含 width= 和 height= 的
    for body in config_calls:
        if re.search(r"\bwidth\s*=", body) and re.search(r"\bheight\s*=", body):
            return body
    return ""


def test_etf_popup_text_uses_max_line_width():
    """popup Text widget 的 width 應該用 max line length、不能寫死
    → 寫死 30 對長 ETF 名稱不夠、20 個字的短 ETF 名稱又太寬
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    config_body = _find_size_config_body(content)
    assert config_body, "❌ 找不到 _etf_popup_text.config(width=, height=...)"

    assert "width=max_line_len" in config_body or "width = max_line_len" in config_body, (
        f"❌ popup width 應該用 max_line_len 自動算、目前 config：\n{config_body}\n"
        f"長 ETF 名稱需要更寬、短名稱又會太寬浪費空間。"
    )


def test_etf_popup_text_height_capped():
    """popup Text widget 的 height 應該有上限、避免太長撐爆螢幕
    → 假設 ETF 數 > 25 也要可閱讀
    """
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        content = f.read()

    config_body = _find_size_config_body(content)
    assert config_body, "❌ 找不到 _etf_popup_text.config(width=, height=...)"

    assert "height=min(total_lines, 25)" in config_body or "height = min(total_lines, 25)" in config_body, (
        f"❌ popup height 應該用 min(total_lines, 25) 限制、目前 config：\n{config_body}"
    )


def test_etf_aggregator_actually_newlines():
    """【整合測試】跑 aggregate_etf_holdings、確認 etf_list 真用 \\n 分隔
    """
    import pandas as pd

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    from StockTool import aggregate_etf_holdings

    holdings = pd.DataFrame([
        {"stock_code": "2330", "stock_name": "台積電",
         "etf_code": "00980A", "etf_name": "主動野村臺灣優選", "weight": 9.37},
        {"stock_code": "2330", "stock_name": "台積電",
         "etf_code": "00982A", "etf_name": "主動群益台灣強棒", "weight": 8.71},
        {"stock_code": "2330", "stock_name": "台積電",
         "etf_code": "00981A", "etf_name": "主動統一台股增長", "weight": 9.68},
    ])

    result = aggregate_etf_holdings(holdings, price_df=pd.DataFrame())
    assert not result.empty
    etf_list = result.iloc[0]["etf_list"]

    # 真用 \n 分隔（不是 " | "）
    assert "\n" in etf_list, f"❌ etf_list 應該用 \\n 分隔：{etf_list}"
    assert " | " not in etf_list, f"❌ 不該再用 ' | ' 分隔：{etf_list}"
    # 3 行 = 3 個 ETF
    assert len(etf_list.split("\n")) == 3, (
        f"❌ 應該 3 個 ETF 各一行、實際 {len(etf_list.split(chr(10)))} 行：{etf_list}"
    )


def test_etf_popup_method_compiles():
    """【語法守護】_etf_show_hover_popup 改完沒漏逗號 / indent 錯誤
    """
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")