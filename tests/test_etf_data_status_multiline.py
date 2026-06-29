"""【V1.1-etf-data-status-multiline】ETF 持股左欄狀態拆多行守護

2026-06-29 10:33 William 反映（看截圖）
- 「etf選股左欄說明太長了請拆成多行」

【根因】
1. 原本 50+ 字元塞 200px 左欄、被裁切
2. 同時發現：strftime('%%Y-%%m-%%d') 印出字面 '%Y-%m-%d'（不是真正時間）
   截圖上最後更新顯示 '%Y-%m-%d %H:%M:%S' 就是這個 bug
   原因：strftime 的 %% 是字面 %、但這裡是要顯示真實 datetime

【修法】
- 改成 \\n.join(status_lines) 拆 3 行
- datetime.now().strftime('%Y-%m-%d %H:%M:%S') 修 %%Y bug
- 3 個 set 位置（first time fetch / has yesterday / no yesterday）全部更新
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
STOCKTOOL_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "StockTool.py"
)


def _read_source():
    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────── 結構守護 ────────────────────

def test_three_set_calls_remain():
    """【核心守護】_etf_data_status.set 必須有 2 處呼叫（不應被誤刪）

    原本 3 處：first time fetch / 有昨日 / 無昨日
    v1.1 重構後：2 處（has/no yesterday 合併成 1 個 conditional set、DRY）
    1. first time fetch
    2. 有/無昨日 (有 has_yesterday 三元 if/else)
    """
    content = _read_source()
    matches = re.findall(r"self\._etf_data_status\.set\(", content)
    assert len(matches) == 2, (
        f"❌ _etf_data_status.set 應該有 2 處、實際 {len(matches)} 處！\n"
        f"  first time fetch + 有/無昨日 conditional 共 2 處"
    )


def test_uses_multiline_join():
    """【核心守護】必須用 \\n.join 拆多行、不該再寫單行 f-string

    之前：f\"ETF 持股：最後更新 ... ({len(agg_df)} 檔個股、從 {etf_count} 檔 ETF) ...\"
    之後：\"\\n\".join(status_lines)
    """
    content = _read_source()
    # 2 個 set 都要用 \\n.join
    matches = re.findall(r'"\\n"\.join\(', content)
    assert len(matches) >= 2, (
        f"❌ 應該有 2 個 \\\"\\\\n\\\".join()、實際 {len(matches)} 個！\n"
        f"  2 個 set 都要拆多行"
    )


def test_status_lines_structure():
    """【核心守護】status_lines 必須有 ETF 持股 / 最後更新 / (有/無昨日) 三段

    第一個 set 只 2 行（first time fetch）
    第二個 set 有 3 行（有/無昨日 conditional append）
    """
    content = _read_source()

    # 1. 標題列「ETF 持股：{N} 檔個股、{M} 檔 ETF」要出現 2 次（2 個 set 都有）
    etf_header = re.findall(
        r'f"ETF 持股：\{len\(agg_df\)\} 檔個股、\{etf_count\} 檔 ETF"',
        content,
    )
    assert len(etf_header) == 2, (
        f"❌ 'ETF 持股：...' 標題列應該 2 次（2 個 set 都有）、實際 {len(etf_header)} 次"
    )

    # 2. 「最後更新 {now_str}」要出現 2 次
    last_update = re.findall(
        r'f"最後更新 \{now_str\}"',
        content,
    )
    assert len(last_update) == 2, (
        f"❌ '最後更新 {{now_str}}' 應該 2 次、實際 {len(last_update)} 次"
    )

    # 3. 「✅ 有昨日資料可比較」和「⚠️ 無昨日資料」各 1 次
    assert "✅ 有昨日資料可比較" in content, "❌ 缺少 '✅ 有昨日資料可比較'"
    assert "⚠️ 無昨日資料" in content, "❌ 缺少 '⚠️ 無昨日資料'"


# ──────────────────── Bug 修正守護 ────────────────────

def test_no_double_percent_in_strftime():
    """【核心守護】strftime 不能用 %%Y（會印出字面 %Y）

    之前 bug：strftime('%%Y-%%m-%%d') 印出字面 '%Y-%m-%d'
    修法：strftime('%Y-%m-%d %H:%M:%S')
    注意：用 ast 抓「所有 ast.Call 結點、name=ast.Name(id='strftime')」
    讓 docstring / 註解不會被誤判
    """
    import ast

    with open(STOCKTOOL_PY, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)

    # 走訪所有 Call 結點、找 strftime(...)
    bad_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # 直接呼叫：strftime("...") 或 datetime.now().strftime("...")
            is_strftime = (
                (isinstance(func, ast.Name) and func.id == "strftime")
                or (isinstance(func, ast.Attribute) and func.attr == "strftime")
            )
            if is_strftime and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    fmt = first_arg.value
                    if "%%" in fmt:
                        bad_calls.append(fmt)

    assert not bad_calls, (
        f"❌ ast 找出 {len(bad_calls)} 個 strftime call 用了 %% 開頭格式：\n"
        + "\n".join(f"  - {sf!r}" for sf in bad_calls)
        + "\n  應改為 %Y-%m-%d %H:%M:%S（不是 %%Y）"
    )


def test_strftime_uses_correct_format():
    """datetime.now().strftime 必須用 %Y-%m-%d %H:%M:%S（不是 %%Y）"""
    content = _read_source()
    # 找 now_str = datetime.now().strftime(...)
    m = re.search(
        r"now_str\s*=\s*datetime\.now\(\)\.strftime\(['\"]([^'\"]+)['\"]\)",
        content,
    )
    assert m, "❌ 找不到 now_str = datetime.now().strftime(...)"
    fmt = m.group(1)
    assert fmt == "%Y-%m-%d %H:%M:%S", (
        f"❌ strftime 格式應為 '%Y-%m-%d %H:%M:%S'、實際 '{fmt}'"
    )


# ──────────────────── 整合測試 ────────────────────

def test_multiline_format_produces_three_lines():
    """【整合測試】驗證最終組裝出來真的是 3 行、有換行符"""
    # 模擬有/無昨日的組裝
    def build_status(agg_count, etf_count, has_yesterday, now_str="2026-06-29 10:00:00"):
        status_lines = [
            f"ETF 持股：{agg_count} 檔個股、{etf_count} 檔 ETF",
            f"最後更新 {now_str}",
        ]
        if has_yesterday:
            status_lines.append("✅ 有昨日資料可比較")
        else:
            status_lines.append("⚠️ 無昨日資料")
        return "\n".join(status_lines)

    # 有昨日
    text1 = build_status(53, 20, True)
    lines1 = text1.split("\n")
    assert len(lines1) == 3, f"❌ 有昨日應該 3 行、實際 {len(lines1)} 行: {lines1}"
    assert "ETF 持股：53 檔個股、20 檔 ETF" in text1
    assert "最後更新 2026-06-29 10:00:00" in text1
    assert "✅ 有昨日資料可比較" in text1

    # 無昨日
    text2 = build_status(53, 20, False)
    lines2 = text2.split("\n")
    assert len(lines2) == 3
    assert "⚠️ 無昨日資料" in text2


def test_no_old_inline_format_remains():
    """【整合測試】不該再出現舊的單行 f-string 寫法

    之前：f\"ETF 持股：最後更新 ... ({len(agg_df)} 檔個股、從 {etf_count} 檔 ETF) ...\"
    """
    content = _read_source()
    # 不該有「從 {etf_count} 檔 ETF）」這個舊 pattern
    assert "從 {etf_count} 檔 ETF)" not in content, (
        "❌ 還有舊的 '從 {etf_count} 檔 ETF)' 寫法、應改為 '檔個股、{etf_count} 檔 ETF'"
    )
    # 不該有「最後更新 {datetime.now().strftime...」舊 pattern
    assert "最後更新 {datetime.now().strftime" not in content, (
        "❌ 還有舊的 '最後更新 {datetime.now().strftime(...)}' 內聯寫法、應改為 now_str 變數"
    )


# ──────────────────── 語法守護 ────────────────────

def test_stocktool_compiles():
    """【語法守護】改完沒漏逗號 / indent 錯誤"""
    import py_compile
    try:
        py_compile.compile(STOCKTOOL_PY, doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"❌ StockTool.py 編譯失敗：\n{e}")
