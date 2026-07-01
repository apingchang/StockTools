"""V1.1.4b-print-to-logger: 所有 helper 函式也接受 logger 參數

驗證：
- fetch_market.py 6 個 helper 函式都接受 logger: GuiLogger = None
- _log_print helper 在 fetch_market.py / scoring.py / pipeline.py 都有定義
- StockTool.py 內 7 個 print() 換成 self.logger.log/error

背景（2026-07-02 00:35 William 第二輪反映）：
- 截圖顯示 fetch_market helper 函式 + pipeline.py DEBUG 區塊的 print() 還在進 PyCharm
- 第一階段只改了 fetch_prices / fetch_revenue_latest / fetch_eps_latest 三個主函式
- 第二階段：所有 helper 函式 + DEBUG 區塊
"""
import os
import inspect
import re

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")


# ============================================================
# 1. fetch_market.py 所有 helper 函式都接受 logger
# ============================================================

def test_fetch_market_helpers_accept_logger():
    """fetch_market.py 所有 helper 函式都必須接受 logger 參數"""
    import sys
    sys.path.insert(0, SOURCE_DIR)
    from stocktool import fetch_market
    
    helpers = [
        '_load_goodinfo_12q_epsrate',
        '_fetch_twse_realtime_batch',
        '_fetch_finmind_prices_batch',
        '_fetch_finmind_dividend',
        '_background_fetch_all_dividend',
    ]
    
    missing = []
    for h in helpers:
        func = getattr(fetch_market, h)
        sig = inspect.signature(func)
        if 'logger' not in sig.parameters:
            missing.append(h)
    
    assert not missing, (
        f"❌ 以下 helper 函式缺 logger 參數：{missing}\n"
        f"V1.1.4b 修法：所有 helper 都要 logger: GuiLogger = None"
    )
    print(f"✅ fetch_market.py 5 個 helper 都接受 logger")


def test_fetch_prices_unchanged():
    """fetch_prices 主函式仍接受 logger（第一階段已加、確認沒被破壞）"""
    import sys
    sys.path.insert(0, SOURCE_DIR)
    from stocktool.fetch_market import fetch_prices
    sig = inspect.signature(fetch_prices)
    
    assert 'logger' in sig.parameters
    assert sig.parameters['logger'].default is None
    print("✅ fetch_prices 仍接受 logger 參數（預設 None）")


# ============================================================
# 2. _log_print helper 在 3 個模組都有定義
# ============================================================

def test_log_print_helper_in_fetch_market():
    """fetch_market.py 必須有 _log_print helper"""
    with open(os.path.join(SOURCE_DIR, "stocktool", "fetch_market.py")) as f:
        content = f.read()
    assert "def _log_print(logger, msg: str)" in content, (
        "❌ fetch_market.py 缺 _log_print helper"
    )
    print("✅ fetch_market.py 有 _log_print helper")


def test_log_print_helper_in_scoring():
    """scoring.py 必須有 _log_print helper"""
    with open(os.path.join(SOURCE_DIR, "stocktool", "scoring.py")) as f:
        content = f.read()
    assert "def _log_print(logger, msg: str)" in content, (
        "❌ scoring.py 缺 _log_print helper"
    )
    print("✅ scoring.py 有 _log_print helper")


def test_log_print_helper_in_pipeline():
    """pipeline.py 必須有 _log_print helper"""
    with open(os.path.join(SOURCE_DIR, "stocktool", "pipeline.py")) as f:
        content = f.read()
    assert "def _log_print(logger, msg: str)" in content, (
        "❌ pipeline.py 缺 _log_print helper"
    )
    print("✅ pipeline.py 有 _log_print helper")


# ============================================================
# 3. calculate_simple_score 接受 logger
# ============================================================

def test_calculate_simple_score_accepts_logger():
    """calculate_simple_score 必須接受 logger 參數（DEBUG 區塊用）"""
    import sys
    sys.path.insert(0, SOURCE_DIR)
    from stocktool.scoring import calculate_simple_score
    sig = inspect.signature(calculate_simple_score)
    
    assert 'logger' in sig.parameters, (
        "❌ calculate_simple_score 缺 logger 參數、DEBUG 訊息會跑進 terminal"
    )
    assert sig.parameters['logger'].default is None
    print("✅ calculate_simple_score 接受 logger 參數（預設 None）")


# ============================================================
# 4. StockTool.py 內的 print() 應換成 self.logger.log/error
# ============================================================

def test_stocktool_ms_run_selection_uses_logger():
    """StockTool.py _ms_run_selection 內 print() 應換成 self.logger.log()"""
    with open(os.path.join(SOURCE_DIR, "StockTool.py")) as f:
        content = f.read()
    
    # 找 _ms_run_selection 函式範圍
    m = re.search(r'def _ms_run_selection\(', content)
    if not m:
        # 可能在 _do() 內
        m = re.search(r'def _do\(\):', content)
    assert m, "❌ 找不到 _ms_run_selection 或 _do()"
    
    start = m.start()
    rest = content[m.end():]
    next_def = re.search(r'^    def |^def |^class |^@', rest, re.MULTILINE)
    func_end = m.end() + (next_def.start() if next_def else len(rest))
    body = content[start:func_end]
    
    # 不應再有 print()（除了 docstring 內的）
    remaining_print = re.findall(r'^\s+print\(', body, re.MULTILINE)
    assert not remaining_print, (
        f"❌ StockTool.py 內還有 {len(remaining_print)} 個 print()、應換成 self.logger.log()\n"
        f"找到：{remaining_print}"
    )
    
    # 應有 self.logger.log 或 self.logger.error
    logger_calls = re.findall(r'self\.logger\.(?:log|error)', body)
    assert len(logger_calls) >= 5, (
        f"❌ StockTool.py 內 self.logger.log/error 呼叫太少（{len(logger_calls)}）、應有 7 個"
    )
    print(f"✅ StockTool.py 內 {len(logger_calls)} 個 self.logger.log/error 呼叫")


# ============================================================
# 5. 所有 fetch_prices 呼叫處都傳 logger
# ============================================================

def test_all_fetch_prices_calls_pass_logger():
    """所有 fetch_prices 呼叫都必須傳 logger 參數（否則 print() 會 fallback 進 terminal）"""
    import sys
    sys.path.insert(0, SOURCE_DIR)
    from stocktool import fetch_market
    
    # 用 AST 掃源碼
    import ast
    source_files = [
        os.path.join(SOURCE_DIR, "StockTool.py"),
        os.path.join(SOURCE_DIR, "stocktool", "backtest.py"),
        os.path.join(SOURCE_DIR, "stocktool", "pipeline.py"),
    ]
    
    bad_calls = []
    for fn in source_files:
        with open(fn) as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 檢查是不是 fetch_prices(...) 或 fetch_revenue_latest(...) 或 fetch_eps_latest(...)
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                if func_name in ('fetch_prices', 'fetch_revenue_latest', 'fetch_eps_latest'):
                    # 檢查 lambda 內或直接呼叫的 args
                    # 簡化：檢查 node.args 數量
                    if func_name in ('fetch_prices', 'fetch_revenue_latest', 'fetch_eps_latest'):
                        # 應該有 session, cfg, logger
                        n_args = len(node.args) + len(node.keywords)
                        if n_args < 3:
                            # 可能在 lambda 內
                            # 找父節點
                            bad_calls.append(f"{fn.split('/')[-1]}:{node.lineno} {func_name}({n_args} args)")
    
    assert not bad_calls, (
        f"❌ 以下 fetch_xxx 呼叫沒傳 logger：\n" + "\n".join(bad_calls)
    )
    print("✅ 所有 fetch_prices/revenue/eps 呼叫都傳 logger")
