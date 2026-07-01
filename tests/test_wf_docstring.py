"""V1.1.3-wf-docstring: 守住 run_walk_forward 有完整 docstring

驗證：
- run_walk_forward 函式必須有 docstring
- docstring 必須提到：演算法、參數、回傳 DataFrame 欄位、限制
- 不能太短（< 200 字元）

背景（v1.0 改版 TODO 2026-06-09 P1）：
- 原本 run_walk_forward 完全沒 docstring（line 1297-1385）
- v1.1 重構後搬到 source/stocktool/backtest.py
- 修法：補完整 docstring（演算法/Args/Returns/Note）
"""
import os
import ast

BACKTEST_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "backtest.py"
)


def test_run_walk_forward_has_docstring():
    """run_walk_forward 必須有 docstring"""
    assert os.path.exists(BACKTEST_PY), f"❌ 找不到 {BACKTEST_PY}"
    with open(BACKTEST_PY, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # 找 run_walk_forward 函式
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_walk_forward":
            func = node
            break

    assert func is not None, "❌ 找不到 run_walk_forward 函式"
    doc = ast.get_docstring(func)
    assert doc is not None, (
        "❌ run_walk_forward 沒有 docstring！\n"
        "V1.1.3-wf-docstring 修法：補完整 docstring（演算法/Args/Returns/Note）"
    )
    print(f"✅ run_walk_forward 有 docstring（{len(doc)} 字元）")


def test_run_walk_forward_docstring_length():
    """docstring 不能太短（< 200 字元）— 守住詳細度"""
    with open(BACKTEST_PY, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_walk_forward"),
        None,
    )
    assert func is not None
    doc = ast.get_docstring(func) or ""

    assert len(doc) >= 200, (
        f"❌ run_walk_forward docstring 太短（{len(doc)} < 200 字元）\n"
        f"應包含演算法/參數/回傳值/限制"
    )
    print(f"✅ docstring 長度 {len(doc)} 字元（≥ 200）")


def test_run_walk_forward_docstring_sections():
    """docstring 必須有這些段落：演算法、Args、Returns"""
    with open(BACKTEST_PY, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_walk_forward"),
        None,
    )
    assert func is not None
    doc = ast.get_docstring(func) or ""

    required_sections = [
        ("演算法", "演算法"),  # 演算法說明
        ("Args", "Args"),     # 參數
        ("Returns", "Returns"),  # 回傳
    ]

    missing = [name for name, marker in required_sections if marker not in doc]
    assert not missing, (
        f"❌ run_walk_forward docstring 缺這些段落：{missing}\n"
        f"應包含：演算法、Args、Returns"
    )
    print(f"✅ docstring 包含必要段落：{[n for n, _ in required_sections]}")


def test_run_walk_forward_docstring_mentions_wf_params():
    """docstring 必須提到關鍵參數：wf_train_years、wf_test_years、wf_step_years"""
    with open(BACKTEST_PY, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_walk_forward"),
        None,
    )
    assert func is not None
    doc = ast.get_docstring(func) or ""

    required_params = ["wf_train_years", "wf_test_years", "wf_step_years"]
    missing = [p for p in required_params if p not in doc]
    assert not missing, (
        f"❌ run_walk_forward docstring 缺這些參數：{missing}\n"
        f"應提及 wf_train_years / wf_test_years / wf_step_years 三個 WF 參數"
    )
    print(f"✅ docstring 提及 WF 參數：{required_params}")


def test_run_walk_forward_docstring_mentions_return_columns():
    """docstring 必須列出回傳 DataFrame 的所有欄位"""
    with open(BACKTEST_PY, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_walk_forward"),
        None,
    )
    assert func is not None
    doc = ast.get_docstring(func) or ""

    # 從 code 看回傳的欄位（line 425-435）
    required_columns = ["window", "train_period", "test_period", "test_cagr", "test_sharpe", "test_mdd", "test_trades"]
    missing = [c for c in required_columns if c not in doc]
    assert not missing, (
        f"❌ run_walk_forward docstring 缺這些欄位：{missing}\n"
        f"應列出回傳 DataFrame 的所有 7 個欄位"
    )
    print(f"✅ docstring 列出回傳欄位：{required_columns}")
