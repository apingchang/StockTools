"""
【2026-08-20 bug fix 3】Regression test for _get_historical_prices auto-refresh stale cache

背景 (續 test_paper_catchup_history_months.py)：
- 第一次 fix：month 對應 (12 vs 60) → 解了 cache 讀不到的問題
- 第二次 fix：HISTORY_DIR 改 user home → 解了 cache 路徑解析
- 但還有第三個問題：cache 過舊時 (e.g., max=2026-07-20、ask=2026-08-01)
  → _get_historical_prices 只讀 cache 不 refresh
  → stock_data 空 → 23 天全 skip

修法：
- _get_historical_prices 偵測 cache max date < trade_date 時、呼叫 update_stock_history refresh
- 沒 session 就 graceful skip、不 crash

期望：
1. cache 過舊 + 有 session → 自動 refresh + 返回 trade_date 價格
2. cache 過舊 + 沒 session → graceful skip (return empty)
3. cache 新鮮 → 不呼叫 refresh、返回 trade_date 價格
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))


def _write_history_xlsx(path: str, df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": ["2026-07-20"], "last_update_time": ["07:00:00"]})
        meta.to_excel(writer, sheet_name="meta", index=False)


# ==========================================================
# Test 1：cache 過舊 + 有 session → 自動 refresh + 抓 trade_date 價格
# ==========================================================
def test_stale_cache_with_session_auto_refreshes(monkeypatch):
    """cache max=7/20、ask=7/21、有 session → 應自動 refresh + 抓到 7/21 價格"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(export_excel, "HISTORY_DIR", tmpdir)
        try:
            code = "2330"
            # 寫一份過舊的 cache (max=2026-07-20)
            df_stale = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-14", "2026-07-15", "2026-07-16",
                                        "2026-07-17", "2026-07-20"]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 5,
                "Close": [2420.0, 2440.0, 2470.0, 2290.0, 2320.0],
                "Volume": [10000] * 5,
            })
            fp = os.path.join(tmpdir, f"{code}_60m.xlsx")
            _write_history_xlsx(fp, df_stale)

            # Mock update_stock_history：模擬 API 回傳新資料
            df_fresh = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-20", "2026-07-21", "2026-07-22"]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 3,
                "Close": [2320.0, 2350.0, 2380.0],  # 7/21 新資料
                "Volume": [10000] * 3,
            })

            mock_logger = MagicMock()

            with patch("stocktool.export_excel.update_stock_history", return_value=df_fresh) as mock_update:
                # 模擬有 finmind session
                mock_session = MagicMock()
                result = paper_catchup._get_historical_prices(
                    session=mock_session, cfg=None, codes=[code],
                    trade_date="2026-07-21",
                    logger=mock_logger,
                )

                # 應抓到 refresh 後的 7/21 價格
                assert code in result, (
                    f"❌ cache 過舊 + 有 session 卻沒 refresh\n"
                    f"   got={result}\n"
                    f"   → 第三個 bug：_get_historical_prices 沒 auto-refresh"
                )
                assert result[code]["price"] == 2350.0

                # 確認 update_stock_history 被呼叫
                assert mock_update.called, "❌ update_stock_history 沒被呼叫"
        finally:
            pass  # monkeypatch 已自動還原 HISTORY_DIR


# ==========================================================
# Test 2：cache 過舊 + 沒 session → graceful skip (不 crash)
# ==========================================================
def test_stale_cache_no_session_graceful_skip(monkeypatch):
    """cache 過舊 + 沒 session → return empty、不 crash"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(export_excel, "HISTORY_DIR", tmpdir)
        try:
            code = "2330"
            df_stale = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-14", "2026-07-20"]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 2,
                "Close": [2420.0, 2320.0],
                "Volume": [10000] * 2,
            })
            fp = os.path.join(tmpdir, f"{code}_60m.xlsx")
            _write_history_xlsx(fp, df_stale)

            mock_logger = MagicMock()

            # 沒 session (None) → 應 graceful skip
            result = paper_catchup._get_historical_prices(
                session=None, cfg=None, codes=[code],
                trade_date="2026-07-21",
                logger=mock_logger,
            )

            # 應回空、不 crash
            assert result == {}, (
                f"❌ 沒 session + 過舊 cache 應回空 dict\n"
                f"   got={result}"
            )
        finally:
            pass  # monkeypatch 已自動還原 HISTORY_DIR


# ==========================================================
# Test 3：cache 新鮮 → 不呼叫 refresh、正常返回
# ==========================================================
def test_fresh_cache_no_refresh_needed(monkeypatch):
    """cache 已含 trade_date → 不呼叫 update、直接返回"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(export_excel, "HISTORY_DIR", tmpdir)
        try:
            code = "2330"
            df = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-14", "2026-07-15", "2026-07-20"]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 3,
                "Close": [2420.0, 2440.0, 2320.0],
                "Volume": [10000] * 3,
            })
            fp = os.path.join(tmpdir, f"{code}_60m.xlsx")
            _write_history_xlsx(fp, df)

            with patch("stocktool.export_excel.update_stock_history") as mock_update:
                mock_session = MagicMock()
                result = paper_catchup._get_historical_prices(
                    session=mock_session, cfg=None, codes=[code],
                    trade_date="2026-07-15",
                )

                # 應抓到、且沒呼叫 update (cache 已含 7/15)
                assert code in result
                assert result[code]["price"] == 2440.0
                assert not mock_update.called, "❌ cache 新鮮卻呼叫 update、不應該"
        finally:
            pass  # monkeypatch 已自動還原 HISTORY_DIR


# ==========================================================
# Test 4：完全沒 cache + 有 session → 應 init + return
# ==========================================================
def test_no_cache_with_session_init(monkeypatch):
    """完全沒 cache + 有 session → 應 init (init_stock_history) + return"""
    from stocktool import paper_catchup
    from stocktool import export_excel

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(export_excel, "HISTORY_DIR", tmpdir)
        try:
            code = "2330"
            df_init = pd.DataFrame({
                "Date": pd.to_datetime(["2026-07-14", "2026-07-21"]).strftime("%Y-%m-%d"),
                "股票代號": [code] * 2,
                "Close": [2420.0, 2350.0],
                "Volume": [10000] * 2,
            })

            with patch("stocktool.export_excel.init_stock_history", return_value=df_init) as mock_init:
                mock_session = MagicMock()
                mock_logger = MagicMock()
                result = paper_catchup._get_historical_prices(
                    session=mock_session, cfg=None, codes=[code],
                    trade_date="2026-07-21",
                    logger=mock_logger,
                )

                # 應 init + 抓到 7/21
                assert code in result, "❌ 完全沒 cache + session 卻沒抓到 " + code + " got=" + str(result)
                assert result[code]["price"] == 2350.0
                assert mock_init.called, "❌ 完全沒 cache 卻沒呼叫 init"
        finally:
            pass  # monkeypatch 已自動還原 HISTORY_DIR
