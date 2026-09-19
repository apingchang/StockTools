"""test_twse_batch_log_summary.py

驗證 TWSE batch loop 失敗時只印一行 summary、不是每批都印 (V0.9.5-goodinfo4+6 改)

【背景】2026-08-23 09:56 William 反映
- 啟動時 console 出現 8 條「⚠️ TWSE tse 整批失敗 (50/50)」洗版
- 開盤後幾分鐘 MIS API 還在暖機、整批空是常態、不是 bug
- 原本設計 (V0.9.5-goodinfo4+5): per-batch warning -> 8 批 = 8 條 log
- 新設計 (V0.9.5-goodinfo4+6): batch loop 結束後只印 1 行 summary

測試策略：
1. test_n_batches_failed_produces_one_summary: mock TWSE 全失敗、驗證只 log 1 行 (含 batch count)
2. test_no_batches_failed_produces_no_summary: mock TWSE 全成功、驗證不印 summary
3. test_partial_batches_failed_counts_correctly: 60 個股分 2 批、第一批全失敗、第二批全成功 -> summary 顯示 1/2 批 fallback
4. test_summary_message_includes_batch_count: 驗證 summary 包含「n_batches/total 批」格式
5. test_no_per_batch_整批失敗_warning: AST 守護 source code 不再有 per-batch warning
"""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from stocktool import fetch_market


# ====================================================
# 場景 1：N 批全失敗 -> 只 log 1 行 summary
# ====================================================

def test_n_batches_failed_produces_one_summary():
    """mock TWSE 全部 batch 都回空 msgArray -> 整批失敗
    預期：log 只被呼叫 1 次 (一行 summary)、且 message 含 batch count
    守住：不能又退回 per-batch warning 洗版"""
    stock_ids = [f"{i:04d}" for i in range(150)]  # 150 檔 / 50 per batch = 3 batches

    logger = MagicMock()

    with patch.object(fetch_market, "_TWSE_REALTIME_BATCH_SIZE", 50):
        with patch("stocktool.fetch_market.requests.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.json.return_value = {"msgArray": []}  # 空 = 整批失敗
            resp_mock.raise_for_status.return_value = None
            mock_get.return_value = resp_mock

            df = fetch_market._fetch_twse_realtime_batch(
                stock_ids=stock_ids,
                logger=logger,
            )

    assert len(df) == 150, f"應回傳 150 筆 (即使全 None)、got {len(df)}"

    # 關鍵驗證：summary 只被 log 1 次
    total_log_calls = (
        logger.log.call_count
        + logger.warning.call_count
        + logger.info.call_count
        + logger.error.call_count
    )

    assert total_log_calls == 1, (
        f"❌ 整批失敗應只 log 1 行 summary、實際 {total_log_calls} 行\n"
        f"   logger.log calls: {logger.log.call_args_list}\n"
        f"   logger.warning calls: {logger.warning.call_args_list}"
    )
    print(f"✅ 3 批全失敗 -> 只 log 1 行 summary (而不是 3 條 per-batch warning)")


def test_summary_message_includes_batch_count():
    """驗證 summary message 包含「batch count 資訊」
    例：「TWSE 即時股價: 0/3 批成功、3 批 fallback」"""
    stock_ids = [f"{i:04d}" for i in range(100)]  # 100 檔 / 50 = 2 批

    logger = MagicMock()

    with patch.object(fetch_market, "_TWSE_REALTIME_BATCH_SIZE", 50):
        with patch("stocktool.fetch_market.requests.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.json.return_value = {"msgArray": []}
            resp_mock.raise_for_status.return_value = None
            mock_get.return_value = resp_mock

            fetch_market._fetch_twse_realtime_batch(
                stock_ids=stock_ids,
                logger=logger,
            )

    all_msgs = []
    for call in logger.log.call_args_list:
        if call.args:
            all_msgs.append(call.args[0])
        elif call.kwargs:
            all_msgs.append(call.kwargs.get("msg", ""))

    summary_msg = " ".join(all_msgs)
    assert "0/2" in summary_msg or "0 / 2" in summary_msg, (
        f"❌ summary 應包含「0/2 批成功」、actual msg={summary_msg!r}"
    )
    assert "2 批 fallback" in summary_msg or "2批" in summary_msg, (
        f"❌ summary 應包含「2 批 fallback」、actual msg={summary_msg!r}"
    )
    print(f"✅ summary 格式正確: {summary_msg!r}")


# ====================================================
# 場景 2：全成功 -> 不印 summary (沒 noise)
# ====================================================

def test_no_batches_failed_produces_no_summary():
    """所有 batch 都成功 -> 不應有 batch-fallback summary log
    守住：不要「沒事也印 summary」變成新的 noise"""
    stock_ids = [f"{i:04d}" for i in range(50)]  # 1 批

    logger = MagicMock()

    def fake_msg_array(*args, **kwargs):
        return {
            "msgArray": [
                {
                    "c": f"{i:04d}",
                    "z": "100.0",
                    "o": "99.0",
                    "y": "98.0",
                    "v": "1000",
                    "d": "1150823",
                }
                for i in range(50)
            ]
        }

    with patch.object(fetch_market, "_TWSE_REALTIME_BATCH_SIZE", 50):
        with patch("stocktool.fetch_market.requests.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.json.side_effect = fake_msg_array
            resp_mock.raise_for_status.return_value = None
            mock_get.return_value = resp_mock

            fetch_market._fetch_twse_realtime_batch(
                stock_ids=stock_ids,
                logger=logger,
            )

    all_msgs = []
    for call in logger.log.call_args_list + logger.warning.call_args_list:
        if call.args:
            all_msgs.append(call.args[0])

    summary_msgs = [m for m in all_msgs if "TWSE 即時股價" in m or "批 fallback" in m]
    assert len(summary_msgs) == 0, (
        f"❌ 全成功時不該印 summary log、實際 {len(summary_msgs)} 行：{summary_msgs}"
    )
    print(f"✅ 全成功 -> 0 行 summary log (沒新增 noise)")


# ====================================================
# 場景 3：部分 batch 失敗 -> summary 正確計算
# ====================================================

def test_partial_batches_failed_counts_correctly():
    """150 檔分 3 批、第 1 批全失敗、第 2+3 批全成功
    預期 summary: 2/3 批成功、1 批 fallback"""
    stock_ids = [f"{i:04d}" for i in range(150)]  # 150 / 50 = 3 batches

    logger = MagicMock()

    call_count = {"n": 0}

    def fake_msg_array(*args, **kwargs):
        # stock_ids = [f"{i:04d}" for i in range(150)]
        # batch_idx 是從 call_count 來的 (1, 2, 3)
        # Batch 1 (call 1): stock_ids 0000-0049 → 應全失敗
        # Batch 2 (call 2): stock_ids 0050-0099 → 全成功
        # Batch 3 (call 3): stock_ids 0100-0149 → 全成功
        call_count["n"] += 1
        batch_idx = call_count["n"]
        if batch_idx == 1:
            return {"msgArray": []}
        start = (batch_idx - 1) * 50  # 50, 100 (對應切出來的 50 檔起點)
        return {
            "msgArray": [
                {
                    "c": f"{start + i:04d}",
                    "z": "100.0",
                    "o": "99.0",
                    "y": "98.0",
                    "v": "1000",
                    "d": "1150823",
                }
                for i in range(50)
            ]
        }

    with patch.object(fetch_market, "_TWSE_REALTIME_BATCH_SIZE", 50):
        with patch("stocktool.fetch_market.requests.get") as mock_get:
            resp_mock = MagicMock()
            resp_mock.json.side_effect = fake_msg_array
            resp_mock.raise_for_status.return_value = None
            mock_get.return_value = resp_mock

            df = fetch_market._fetch_twse_realtime_batch(
                stock_ids=stock_ids,
                logger=logger,
            )
            print(f"[DEBUG] mock_get.call_count={mock_get.call_count}")
            print(f"[DEBUG] resp_mock.json.call_count={resp_mock.json.call_count}")
            print(f"[DEBUG] call_count={call_count}")
            print(f"[DEBUG] df non-null price count={df['現價'].notna().sum()}")

    all_msgs = []
    for call in logger.log.call_args_list:
        if call.args:
            all_msgs.append(call.args[0])

    summary_msg = " ".join(all_msgs)
    assert "2/3" in summary_msg or "2 / 3" in summary_msg, (
        f"❌ summary 應顯示 2/3 批成功、actual msg={summary_msg!r}"
    )
    assert "1 批 fallback" in summary_msg, (
        f"❌ summary 應包含「1 批 fallback」、actual msg={summary_msg!r}"
    )
    print(f"✅ 1/3 批失敗 -> summary: {summary_msg!r}")


# ====================================================
# 場景 4：守護 source code 不再有 per-batch 「整批失敗」warning
# ====================================================

def test_no_per_batch_整批失敗_warning():
    """AST 守護：fetch_market.py 的 batch loop 內不應再有「整批失敗」字串的 _log_print
    防止以後又有人加 per-batch warning 回去"""
    import ast
    import inspect

    src = inspect.getsource(fetch_market._fetch_twse_realtime_batch)
    tree = ast.parse(src)

    bad_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name == "_log_print":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if "整批失敗" in str(node.args[0].value):
                        bad_calls.append((node.lineno, node.args[0].value))

    assert not bad_calls, (
        f"❌ _fetch_twse_realtime_batch 不該再有 per-batch 「整批失敗」log：\n"
        f"   {bad_calls}\n"
        f"   修法：把 per-batch warning 拿掉、batch loop 結束後只印 1 行 summary"
    )
    print(f"✅ source code 已無 per-batch 「整批失敗」warning")
