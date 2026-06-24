"""
test_portfolio_refresh_loop.py
驗證 V0.9.5+ Phase 8：買賣記錄 Tab 開盤時段（09:00~13:30）每 30 秒 refresh 持倉現價。

【V0.9.5+ Phase 8 規則】William 2026-06-15 11:02 設定
- 點進買賣記錄 Tab、且在開盤時段（09:00~13:30）→ 每 30 秒 refresh 一次
- 收盤後、週末、或切離買賣記錄 Tab → 停止

【為什麼要這個 test】
- _schedule_portfolio_refresh / _portfolio_refresh_loop 是 GUI method、需 mock
- 但底層邏輯是純函式化（用 _is_market_hours 判斷、用 self.after 排程）
- 用 mock self 測核心分支決策、確保邏輯正確

【實作】
- 用 SimpleNamespace 建 mock self（有 after、after_cancel、notebook、logger 等）
- 用 patch.object(st, '_is_market_hours') 控制時段
- 呼叫 _schedule_portfolio_refresh / _portfolio_refresh_loop、觀察 after 次數
"""
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# Mock self
# ==========================================================

def _make_mock_self(current_tab: int = 1):
    """建一個 mock self 給 portfolio refresh method 用

    current_tab: 模擬目前選中的 tab index（0=策略, 1=ETF, 2=手動選股, 3=買賣記錄）
    """
    mock = SimpleNamespace()
    mock.logger = MagicMock()
    # after 模擬：記錄每次呼叫
    mock.after_calls = []
    mock._after_id_counter = 0
    def fake_after(ms, callback):
        mock._after_id_counter += 1
        job_id = f"job_{mock._after_id_counter}"
        mock.after_calls.append((ms, callback, job_id))
        return job_id
    mock.after = fake_after
    def fake_after_cancel(job_id):
        for i, (_, _, jid) in enumerate(mock.after_calls):
            if jid == job_id:
                mock.after_calls.pop(i)
                return
    mock.after_cancel = fake_after_cancel
    # notebook 模擬
    mock.notebook = SimpleNamespace()
    mock.notebook.index = MagicMock(return_value=current_tab)
    mock.notebook.select = MagicMock(return_value="fake_tab_id")
    # _auto_fetch_positions_prices 模擬
    mock._auto_fetch_positions_prices = MagicMock()
    mock._portfolio_refresh_job_id = None
    # 補上其他 method、綁定到真實 method（避免 mock 缺漏）
    mock._cancel_portfolio_refresh = lambda: st.StrategyGUI._cancel_portfolio_refresh(mock)
    mock._schedule_portfolio_refresh = lambda: st.StrategyGUI._schedule_portfolio_refresh(mock)
    # 重要：_portfolio_refresh_loop 要 bind 完才能傳給 after
    mock._portfolio_refresh_loop = None  # placeholder
    mock._portfolio_refresh_loop = lambda: st.StrategyGUI._portfolio_refresh_loop(mock)
    mock._refresh_portfolio_view = MagicMock()
    return mock


# ==========================================================
# 【盤中】_schedule_portfolio_refresh 排程下一次
# ==========================================================

def test_盤中_排程下一次refresh():
    """【核心守護】盤中時 _schedule_portfolio_refresh 應排程 30 秒後的 job"""
    mock = _make_mock_self(current_tab=3)
    with patch.object(st, "_is_market_hours", return_value=True):
        st.StrategyGUI._schedule_portfolio_refresh(mock)

    # 應呼叫 after(30000, ...) 一次
    assert len(mock.after_calls) == 1, \
        f"盤中應排程 1 次 after，實際: {len(mock.after_calls)} 次"
    ms, callback, job_id = mock.after_calls[0]
    assert ms == 30000, f"應排程 30 秒，實際: {ms} ms"
    assert job_id == "job_1"
    # job_id 應被存到 self
    assert mock._portfolio_refresh_job_id == "job_1"
    # logger 應記錄啟動訊息
    log_calls = [str(c) for c in mock.logger.log.call_args_list]
    assert any("啟動" in s and "30 秒" in s for s in log_calls), \
        f"logger 應記錄啟動訊息，實際: {log_calls}"


def test_盤後_不排程():
    """盤後時 _schedule_portfolio_refresh 不應排程（但要 log 訊息）"""
    mock = _make_mock_self(current_tab=3)
    with patch.object(st, "_is_market_hours", return_value=False):
        st.StrategyGUI._schedule_portfolio_refresh(mock)

    # 應 0 次 after 呼叫
    assert len(mock.after_calls) == 0, \
        f"盤後不應排程 after，實際: {len(mock.after_calls)} 次"
    # job_id 應為 None
    assert mock._portfolio_refresh_job_id is None
    # logger 應記錄停止訊息
    log_calls = [str(c) for c in mock.logger.log.call_args_list]
    assert any("收盤" in s and "停止" in s for s in log_calls), \
        f"logger 應記錄收盤停止訊息，實際: {log_calls}"


# ==========================================================
# 【重複排程】呼叫多次時應取消上次的、避免重複
# ==========================================================

def test_重複排程_取消上次的():
    """【守護】_schedule_portfolio_refresh 內部會先 cancel 上次的
    避免重複排程導致多個 job 同時跑"""
    mock = _make_mock_self(current_tab=3)
    with patch.object(st, "_is_market_hours", return_value=True):
        # 第一次
        st.StrategyGUI._schedule_portfolio_refresh(mock)
        first_id = mock._portfolio_refresh_job_id
        assert first_id == "job_1"
        # 第二次（模擬下一次排程時）
        st.StrategyGUI._schedule_portfolio_refresh(mock)
        second_id = mock._portfolio_refresh_job_id
        assert second_id == "job_2"
        # 第二次呼叫時、第一次的 job 應被 cancel（從 after_calls 移除）
        remaining_ids = [jid for _, _, jid in mock.after_calls]
        assert first_id not in remaining_ids, \
            f"第一次的 job 應被 cancel，實際仍在: {remaining_ids}"
        assert second_id in remaining_ids


# ==========================================================
# 【refresh loop】盤中時刷新一次、再排程下一次
# ==========================================================

def test_盤中_refresh_loop_刷新並排程下一次():
    """【核心】refresh loop 本體：刷新一次後、應再排程下一次"""
    mock = _make_mock_self(current_tab=3)
    with patch.object(st, "_is_market_hours", return_value=True):
        st.StrategyGUI._portfolio_refresh_loop(mock)

    # 應呼叫 _auto_fetch_positions_prices 一次
    assert mock._auto_fetch_positions_prices.call_count == 1
    # 應排程下一次（after_calls 應有 1 個）
    assert len(mock.after_calls) == 1
    ms, _, _ = mock.after_calls[0]
    assert ms == 30000


def test_refresh_loop_已切離Tab_停止loop():
    """【守護】使用者切離買賣記錄 Tab、refresh loop 應停止（不刷新、不排程）"""
    mock = _make_mock_self(current_tab=2)  # Tab 2 = 手動選股（已切離買賣記錄）
    st.StrategyGUI._portfolio_refresh_loop(mock)

    # 應不呼叫 _auto_fetch_positions_prices
    assert mock._auto_fetch_positions_prices.call_count == 0
    # 應不排程
    assert len(mock.after_calls) == 0
    # logger 應記錄停止訊息
    log_calls = [str(c) for c in mock.logger.log.call_args_list]
    assert any("切離" in s and "停止" in s for s in log_calls), \
        f"logger 應記錄切離停止訊息，實際: {log_calls}"


# ==========================================================
# 【_cancel_portfolio_refresh】取消邏輯
# ==========================================================

def test_cancel_有job時呼叫after_cancel():
    """有 job_id 時 _cancel_portfolio_refresh 應呼叫 after_cancel"""
    mock = _make_mock_self(current_tab=3)
    mock._portfolio_refresh_job_id = "test_job_123"
    after_cancel_calls = []
    mock.after_cancel = lambda jid: after_cancel_calls.append(jid)

    st.StrategyGUI._cancel_portfolio_refresh(mock)

    assert after_cancel_calls == ["test_job_123"], \
        f"after_cancel 應被呼叫且傳入 job_id，實際: {after_cancel_calls}"
    assert mock._portfolio_refresh_job_id is None


def test_cancel_沒job時不做事():
    """沒 job_id 時 _cancel_portfolio_refresh 應 silently 跳過、不報錯"""
    mock = _make_mock_self(current_tab=3)
    mock._portfolio_refresh_job_id = None
    after_cancel_calls = []
    mock.after_cancel = lambda jid: after_cancel_calls.append(jid)

    # 不應拋任何例外
    st.StrategyGUI._cancel_portfolio_refresh(mock)

    assert after_cancel_calls == [], \
        f"沒 job 時不應呼叫 after_cancel，實際: {after_cancel_calls}"


# ==========================================================
# 【時段切換邊界】盤中 → 盤後
# ==========================================================

def test_refresh_loop_盤中排程後_排程時已是盤後_就停():
    """【實戰】13:29 啟動 loop → 13:30:00 觸發 → 排程下一次 → 此時 13:30:30 已收盤 → 停
    模擬：排程時 _is_market_hours 回傳 True（盤中）、
    下一次排程時 _is_market_hours 回傳 False（盤後）"""
    mock = _make_mock_self(current_tab=3)
    # 第一次：盤中
    with patch.object(st, "_is_market_hours", return_value=True):
        st.StrategyGUI._portfolio_refresh_loop(mock)
    assert len(mock.after_calls) == 1
    # 第二次（手動呼叫 _schedule_portfolio_refresh、模擬 30 秒後）：盤後
    with patch.object(st, "_is_market_hours", return_value=False):
        st.StrategyGUI._schedule_portfolio_refresh(mock)
    # 排程應被取消（盤後不排程）
    assert len(mock.after_calls) == 0, \
        f"盤後排程應被取消，實際: {len(mock.after_calls)} 次"


# ==========================================================
# 【on_tab_changed】整合測試
# ==========================================================

def test_on_tab_changed_切到買賣記錄_啟動refresh():
    """切到買賣記錄 Tab → 啟動 refresh loop"""
    mock = _make_mock_self(current_tab=3)
    # 補上 _refresh_portfolio_view、_on_tab_changed 需要的方法
    mock._refresh_portfolio_view = MagicMock()
    mock.event = SimpleNamespace()
    with patch.object(st, "_is_market_hours", return_value=True), \
         patch.object(st, "threading") as _t:
        st.StrategyGUI._on_tab_changed(mock, mock.event)

    # 應排程 2 次：after(100, _auto_fetch_positions_prices) + after(30000, _portfolio_refresh_loop)
    assert len(mock.after_calls) == 2
    # 第一個是原本的 100ms 抓現價
    ms1, _, _ = mock.after_calls[0]
    assert ms1 == 100
    # 第二個是新增的 30 秒 refresh loop
    ms2, _, _ = mock.after_calls[1]
    assert ms2 == 30000


def test_on_tab_changed_切走_取消refresh():
    """切走買賣記錄 Tab → 取消 refresh loop"""
    mock = _make_mock_self(current_tab=2)  # 切到手動選股
    mock._portfolio_refresh_job_id = "existing_job"
    after_cancel_calls = []
    mock.after_cancel = lambda jid: after_cancel_calls.append(jid)
    mock._refresh_portfolio_view = MagicMock()
    mock.event = SimpleNamespace()

    st.StrategyGUI._on_tab_changed(mock, mock.event)

    # 應 cancel job
    assert "existing_job" in after_cancel_calls, \
        f"切走時應 cancel job，實際: {after_cancel_calls}"
    assert mock._portfolio_refresh_job_id is None
