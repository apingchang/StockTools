"""V1.1.4c-print-to-logger: 守住 logger 連鎖傳遞

【2026-07-02 01:02 William 第三輪反映】
雖然第二階段把所有 helper 函式都加 logger 參數、print() 換成 _log_print(logger, ...)，
但 caller 還是寫成 `helper()` 沒傳 logger → 收到 logger=None → fallback print() 還是會進 PyCharm。

具體位置：
- pipeline.py 3 處 calculate_simple_score(df_sel, cfg) → 漏傳 logger
- pipeline.py 內 _fetch_market_stock_list() → 漏傳 logger
- pipeline.py 內 _load_goodinfo_12q_epsrate() → 漏傳 logger
- StockTool.py 直接呼叫 _load_goodinfo_12q_epsrate() × 2 → 漏傳 logger
- StockTool.py 直接呼叫 _fetch_market_stock_list() → 漏傳 logger

修法：所有 helper 呼叫都要傳 logger。

守護：掃 AST（不限範圍）找出所有沒傳 logger 的 helper 呼叫。
"""
import os
import ast
import sys

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")


# ============================================================
# 1. _fetch_market_stock_list / _load_goodinfo_12q_epsrate 加 logger 參數
# ============================================================

def test_fetch_market_stock_list_accepts_logger():
    """_fetch_market_stock_list 必須接受 logger 參數"""
    sys.path.insert(0, SOURCE_DIR)
    from stocktool.fetch_market import _fetch_market_stock_list
    import inspect
    sig = inspect.signature(_fetch_market_stock_list)
    assert 'logger' in sig.parameters, (
        "❌ _fetch_market_stock_list 缺 logger 參數\n"
        "V1.1.4c 修法：def _fetch_market_stock_list(logger: GuiLogger = None) -> pd.DataFrame:"
    )
    assert sig.parameters['logger'].default is None
    print("✅ _fetch_market_stock_list 接受 logger 參數（預設 None）")


def test_load_goodinfo_accepts_logger():
    """_load_goodinfo_12q_epsrate 必須接受 logger 參數"""
    from stocktool.fetch_market import _load_goodinfo_12q_epsrate
    import inspect
    sig = inspect.signature(_load_goodinfo_12q_epsrate)
    assert 'logger' in sig.parameters
    print("✅ _load_goodinfo_12q_epsrate 接受 logger 參數")


# ============================================================
# 2. 所有 helper 呼叫都傳 logger
# ============================================================

def test_all_helper_calls_pass_logger():
    """所有 helper 函式呼叫都必須傳 logger 參數

    規則：
    - _fetch_market_stock_list() 必須改 _fetch_market_stock_list(logger=...)
    - _load_goodinfo_12q_epsrate() 必須改 _load_goodinfo_12q_epsrate(logger=...)
    - calculate_simple_score(df, cfg) 必須改 calculate_simple_score(df, cfg, logger=...)
    """
    target_funcs = {
        '_fetch_market_stock_list',
        '_load_goodinfo_12q_epsrate',
        'calculate_simple_score',
    }

    source_files = [
        os.path.join(SOURCE_DIR, "StockTool.py"),
        os.path.join(SOURCE_DIR, "stocktool", "scoring.py"),
        os.path.join(SOURCE_DIR, "stocktool", "pipeline.py"),
        os.path.join(SOURCE_DIR, "stocktool", "fetch_market.py"),
    ]

    bad_calls = []
    for fn in source_files:
        with open(fn) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in target_funcs:
                    n_args = len(node.args)
                    has_logger_kw = any(
                        kw.arg == 'logger' for kw in node.keywords
                    )

                    if func_name == 'calculate_simple_score':
                        if n_args < 3 and not has_logger_kw:
                            bad_calls.append(f"{fn.split('/')[-1]}:{node.lineno} {func_name}({n_args} args, no logger kw)")

                    elif func_name in ('_fetch_market_stock_list', '_load_goodinfo_12q_epsrate'):
                        if n_args == 0 and not has_logger_kw:
                            bad_calls.append(f"{fn.split('/')[-1]}:{node.lineno} {func_name}() 漏傳 logger")

    assert not bad_calls, (
        "❌ 以下 helper 呼叫漏傳 logger（會 fallback print 進 PyCharm）：\n"
        + "\n".join(bad_calls) + "\n"
        + "\n修法：所有呼叫改成 helper_function(logger=...) 或 func(..., logger)"
    )
    print("✅ 所有 helper 呼叫都傳 logger")


# ============================================================
# 3. 主要模組內剩下的 print() 只有合法 fallback
# ============================================================

def test_only_legal_prints_remain():
    """fetch_market/scoring/pipeline 的 print() 只剩 _log_print 內的 fallback"""
    files_to_check = [
        os.path.join(SOURCE_DIR, "stocktool", "fetch_market.py"),
        os.path.join(SOURCE_DIR, "stocktool", "scoring.py"),
        os.path.join(SOURCE_DIR, "stocktool", "pipeline.py"),
    ]

    # 找所有 print()，並判斷是不是在 _log_print helper 內
    bad = []
    for fn in files_to_check:
        with open(fn) as f:
            lines = f.readlines()

        # 找 _log_print helper 範圍（def ... 到下一個 def 為止）
        in_helper_range = set()  # 行號 set
        start = None
        for i, line in enumerate(lines):
            if 'def _log_print(' in line:
                start = i
            elif start is not None and (line.startswith('def ') or line.startswith('@')) and 'def _log_print' not in line:
                for j in range(start, i):
                    in_helper_range.add(j)
                start = None
        if start is not None:
            for j in range(start, len(lines)):
                in_helper_range.add(j)

        # 找每個 print()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('print('):
                if i not in in_helper_range:
                    bad.append(f"{fn.split('/')[-1]}:{i+1}  {stripped[:80]}")

    assert not bad, (
        "❌ 主要模組還有 print() 沒被轉成 _log_print：\n" + "\n".join(bad[:10])
    )
    print("✅ 主要模組的 print() 只剩 _log_print 內的合法 fallback")
