"""V1.1.4-print-to-logger: fetch_market 子模組 print() 統一走 logger

驗證：
- _log_print helper：有 logger → 走 logger.log()、沒 logger → fallback print()
- fetch_prices / fetch_revenue_latest / fetch_eps_latest 接受 logger 參數（向後相容 None）
- pipeline.py 的 lambda 把 logger 傳給 fetch_*

背景（2026-07-02 00:09 William 反映）：
- 「把股神 APP 的 output message 改成全部都從 program console 輸出」
- 「現在有些 message 是從 terminal 輸出的！」
- 原因：子模組（fetch_market.py 等）用 print() 進 terminal、沒走 logger
- 修法：給主函式加 logger 參數、內部 print() 換成 _log_print(logger, msg)
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# 把 source/ 加到 path
SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from stocktool.fetch_market import _log_print  # noqa: E402


# ============================================================
# 1. _log_print helper 路由
# ============================================================

def test_log_print_with_logger_uses_logger():
    """有 logger → 走 logger.log()、不呼叫 print()"""
    logger = MagicMock()
    with patch("builtins.print") as mock_print:
        _log_print(logger, "hello world")
    
    logger.log.assert_called_once_with("hello world")
    mock_print.assert_not_called()
    print("✅ _log_print 有 logger → 走 logger.log()、不 print()")


def test_log_print_without_logger_falls_back_to_print():
    """沒 logger (None) → fallback 到 print()"""
    with patch("builtins.print") as mock_print:
        _log_print(None, "fallback message")
    
    mock_print.assert_called_once_with("fallback message")
    print("✅ _log_print 沒 logger → fallback print()")


def test_log_print_logger_receives_correct_message():
    """logger 收到的訊息要跟呼叫時傳的完全一樣"""
    logger = MagicMock()
    msg = "⚠️ 讀取上市股價失敗：ConnectionError"
    _log_print(logger, msg)
    
    logger.log.assert_called_once_with(msg)
    print(f"✅ logger 收到正確訊息: {msg[:30]}...")


# ============================================================
# 2. fetch_* 函式簽章接受 logger 參數
# ============================================================

def test_fetch_prices_signature_accepts_logger():
    """fetch_prices 簽章必須接受 logger 參數（預設 None）"""
    import inspect
    from stocktool.fetch_market import fetch_prices
    sig = inspect.signature(fetch_prices)
    
    assert "logger" in sig.parameters, "❌ fetch_prices 缺 logger 參數"
    assert sig.parameters["logger"].default is None, (
        "❌ fetch_prices logger 參數預設應為 None（向後相容 CLI）"
    )
    print("✅ fetch_prices 接受 logger 參數（預設 None）")


def test_fetch_revenue_latest_signature_accepts_logger():
    """fetch_revenue_latest 簽章必須接受 logger 參數"""
    import inspect
    from stocktool.fetch_market import fetch_revenue_latest
    sig = inspect.signature(fetch_revenue_latest)
    
    assert "logger" in sig.parameters, "❌ fetch_revenue_latest 缺 logger 參數"
    assert sig.parameters["logger"].default is None
    print("✅ fetch_revenue_latest 接受 logger 參數（預設 None）")


def test_fetch_eps_latest_signature_accepts_logger():
    """fetch_eps_latest 簽章必須接受 logger 參數"""
    import inspect
    from stocktool.fetch_market import fetch_eps_latest
    sig = inspect.signature(fetch_eps_latest)
    
    assert "logger" in sig.parameters, "❌ fetch_eps_latest 缺 logger 參數"
    assert sig.parameters["logger"].default is None
    print("✅ fetch_eps_latest 接受 logger 參數（預設 None）")


# ============================================================
# 3. pipeline.py lambda 把 logger 傳給 fetch_*
# ============================================================

def test_pipeline_lambda_passes_logger_to_fetch():
    """pipeline.py 的 lambda 必須把 logger 傳給 fetch_*

    原本: lambda: fetch_prices(s, cfg)         ← logger 沒傳
    修完: lambda: fetch_prices(s, cfg, logger) ← logger 傳進去
    """
    with open(os.path.join(SOURCE_DIR, "stocktool", "pipeline.py"), "r", encoding="utf-8") as f:
        content = f.read()
    
    # 6 處 lambda 都要傳 logger（2 個流程 × 3 個 fetch_*）
    import re
    lambdas = re.findall(
        r"lambda:\s*(fetch_\w+)\(s,\s*cfg(?:,\s*logger)?\),?\s*logger",
        content,
    )
    
    assert len(lambdas) >= 6, (
        f"❌ pipeline.py lambda 沒傳 logger！應有 6 處（2 流程 × 3 fetch_*）\n"
        f"找到 {len(lambdas)} 處：{lambdas}"
    )
    
    # 全部都要有 logger 參數
    no_logger = re.findall(
        r"lambda:\s*fetch_\w+\(s,\s*cfg\),\s*logger",
        content,
    )
    assert len(no_logger) == 0, (
        f"❌ 還有 {len(no_logger)} 處 lambda 沒傳 logger：{no_logger}\n"
        f"V1.1.4-print-to-logger 修法：lambda 都要傳 logger 進 fetch_*"
    )
    print(f"✅ pipeline.py 6 處 lambda 都傳 logger 給 fetch_*")


# ============================================================
# 4. 向後相容：沒 logger 也能跑（CLI 模式不破）
# ============================================================

def test_log_print_with_none_logger_does_not_crash():
    """_log_print(None, msg) 不 crash（CLI 模式可能傳 None）"""
    # 不該 raise
    _log_print(None, "test")
    print("✅ _log_print(None, msg) 不 crash")
