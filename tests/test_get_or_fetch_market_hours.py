"""
test_get_or_fetch_market_hours.py
驗證 V0.9.5+ Phase 7：get_or_fetch 在盤中會強制 refresh price。

【V0.9.5+ Phase 7 規則】
- 股價 (price) 盤中 → 強制 refresh（不限次數）
- 股價 (price) 盤後/盤前/週末 → 一天只一次（last_update == today → 用 cache）
- revenue/eps → 維持原本「last_update == today」判斷（不受時段影響）

【為什麼要這個 test】
- get_or_fetch 是 price/revenue/eps 共用函式
- 盤中邏輯只對 price 生效、revenue/eps 不受影響
- 必須驗證這層「name == 'price'」的條件正確分流

【實作方式】
- patch _is_market_hours 回傳固定值（避免依賴實際時間）
- 用 tmp_path 建立 mock cache（避免污染 source/cache）
- 呼叫 get_or_fetch('price', ...) 觀察是否走 fetch_func
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import cache as st_cache  # noqa: E402  # v1.1 重構：cache 在 stocktool.cache


# ==========================================================
# 工具：建立 mock cache
# ==========================================================

def _make_fake_cache(file_path: str, last_update: str, df: pd.DataFrame):
    """建立假的 cache 檔（含 data + meta sheet）"""
    meta = pd.DataFrame({"last_update": [last_update]})
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta.to_excel(writer, sheet_name="meta", index=False)


def _fake_price_df() -> pd.DataFrame:
    """【V0.9.5-cache-vol】已加成交量_張、data_date 才能讓結構檢查測試通過"""
    return pd.DataFrame({
        "股票代號": ["2330", "2317"],
        "公司名稱_來源": ["台積電", "鴻海"],
        "股價": [600.0, 100.0],
        "漲跌": [5.0, 1.0],
        "data_date": ["2026-06-19", "2026-06-19"],
        "成交量_張": [25000.0, 5000.0],
    })


# ==========================================================
# 【price 盤中】強制 refresh
# ==========================================================

def test_price_盤中_即使cache是今天也強制refresh(tmp_path):
    """【核心守護】price 在盤中 → 強制 refresh、不論 cache 是不是今天
    情境：模擬 10:00 開 App，cache 已有今天抓的資料 → 仍要 refresh
    """
    cache_path = str(tmp_path / "price_test.xlsx")
    today = datetime.now().strftime("%Y-%m-%d")
    _make_fake_cache(cache_path, today, _fake_price_df())

    with patch.object(st_cache, "get_cache_file", return_value=cache_path), \
         patch.object(st_cache, "_is_market_hours", return_value=True), \
         patch.object(st, "datetime") as mock_dt:
        # 讓 datetime.now() 回傳盤中（避免真實時間影響）
        mock_dt.now.return_value = datetime(2026, 6, 15, 10, 0, 0)
        mock_dt.today.return_value = mock_dt.now.return_value

        mock_logger = MagicMock()
        fetch_called = []

        def fake_fetch():
            fetch_called.append(True)
            return _fake_price_df()

        result = st.get_or_fetch("price", fake_fetch, mock_logger)

    # 關鍵：盤中必須呼叫 fetch_func（即使 cache 是今天）
    assert len(fetch_called) == 1, f"盤中應強制 refresh，實際 fetch 次數: {len(fetch_called)}"
    # logger 應記錄「盤中時段 → 強制 refresh」
    log_calls = [str(c) for c in mock_logger.log.call_args_list]
    assert any("盤中" in s and "強制 refresh" in s for s in log_calls), \
        f"logger 應記錄盤中訊息，實際: {log_calls}"


def test_price_盤後_用cache不refresh(tmp_path):
    """盤後 14:00 開 App → cache 是今天 → 用 cache、不 refresh
    William 規則：「收盤（13:30）後只要 refresh 一次」
    """
    cache_path = str(tmp_path / "price_after_market.xlsx")
    today = datetime.now().strftime("%Y-%m-%d")
    _make_fake_cache(cache_path, today, _fake_price_df())

    with patch.object(st_cache, "get_cache_file", return_value=cache_path), \
         patch.object(st_cache, "_is_market_hours", return_value=False):
        mock_logger = MagicMock()
        fetch_called = []

        def fake_fetch():
            fetch_called.append(True)
            return _fake_price_df()

        result = st.get_or_fetch("price", fake_fetch, mock_logger)

    # 關鍵：盤後 cache 是今天 → 不應呼叫 fetch_func
    assert len(fetch_called) == 0, f"盤後 cache 為今日應用 cache，實際 fetch 次數: {len(fetch_called)}"
    # logger 應記錄「使用快取資料」
    log_calls = [str(c) for c in mock_logger.log.call_args_list]
    assert any("使用快取資料" in s for s in log_calls), \
        f"logger 應記錄使用快取，實際: {log_calls}"


def test_price_盤後_cache是昨天_走正常refresh路徑(tmp_path):
    """盤後 cache 是昨天 → 走原本「last_update != today」refresh 路徑
    （不是走盤中強制 refresh 路徑、但結果仍是 refresh）
    """
    cache_path = str(tmp_path / "price_yesterday.xlsx")
    yesterday = "2026-06-14"  # 假設今天是 2026-06-15
    _make_fake_cache(cache_path, yesterday, _fake_price_df())

    with patch.object(st_cache, "get_cache_file", return_value=cache_path), \
         patch.object(st_cache, "_is_market_hours", return_value=False), \
         patch.object(st, "datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 6, 15, 14, 0, 0)  # 盤後
        mock_dt.today.return_value = mock_dt.now.return_value

        mock_logger = MagicMock()
        fetch_called = []

        def fake_fetch():
            fetch_called.append(True)
            return _fake_price_df()

        result = st.get_or_fetch("price", fake_fetch, mock_logger)

    assert len(fetch_called) == 1, f"cache 過期應 refresh，實際 fetch 次數: {len(fetch_called)}"
    log_calls = [str(c) for c in mock_logger.log.call_args_list]
    assert any("資料過期" in s for s in log_calls), \
        f"logger 應記錄資料過期，實際: {log_calls}"


# ==========================================================
# 【revenue/eps 盤中】不受時段影響
# ==========================================================

def test_revenue_盤中_不強制refresh_走原本邏輯(tmp_path):
    """【關鍵守護】revenue 盤中不應被「盤中邏輯」影響
    revenue 跟 eps 是一次性的營收/EPS 快照、盤中也只抓一次
    """
    cache_path = str(tmp_path / "revenue_market_hours.xlsx")
    today = datetime.now().strftime("%Y-%m-%d")
    revenue_df = pd.DataFrame({"股票代號": ["2330"], "營收YoY(%)": [25.0]})
    _make_fake_cache(cache_path, today, revenue_df)

    with patch.object(st_cache, "get_cache_file", return_value=cache_path), \
         patch.object(st_cache, "_is_market_hours", return_value=True):
        mock_logger = MagicMock()
        fetch_called = []

        def fake_fetch():
            fetch_called.append(True)
            return revenue_df

        result = st.get_or_fetch("revenue", fake_fetch, mock_logger)

    # 關鍵：revenue 盤中、cache 是今天 → 用 cache、不 refresh
    assert len(fetch_called) == 0, \
        f"revenue 盤中 cache 為今日應用 cache，實際 fetch 次數: {len(fetch_called)}"
    log_calls = [str(c) for c in mock_logger.log.call_args_list]
    assert any("使用快取資料" in s for s in log_calls), \
        f"logger 應記錄使用快取，實際: {log_calls}"


def test_eps_盤中_不強制refresh_走原本邏輯(tmp_path):
    """eps 盤中不應被「盤中邏輯」影響"""
    cache_path = str(tmp_path / "eps_market_hours.xlsx")
    today = datetime.now().strftime("%Y-%m-%d")
    eps_df = pd.DataFrame({
        "股票代號": ["2330"], "EPS本期": [10.0],
        "EPSYoY_顯示(%)": [50.0],  # Fix11 結構檢查需要此欄
    })
    _make_fake_cache(cache_path, today, eps_df)

    with patch.object(st_cache, "get_cache_file", return_value=cache_path), \
         patch.object(st_cache, "_is_market_hours", return_value=True):
        mock_logger = MagicMock()
        fetch_called = []

        def fake_fetch():
            fetch_called.append(True)
            return eps_df

        result = st.get_or_fetch("eps", fake_fetch, mock_logger)

    assert len(fetch_called) == 0, \
        f"eps 盤中 cache 為今日應用 cache，實際 fetch 次數: {len(fetch_called)}"
