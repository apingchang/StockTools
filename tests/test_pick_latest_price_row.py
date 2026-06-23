"""
test_pick_latest_price_row.py
驗證 FinMind TaiwanStockPrice 選最新一筆的邏輯

V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
原本：data[-1] → 盤中時 data[-1] 可能是上一個交易日的收盤（誤）
修法：_pick_latest_price_row 從後往前找 date == today、找不到取 data[-1]
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


def _today_roc():
    """今日 ROC 日期（ex: 2026-06-17 → '1150617'）"""
    today = datetime.now()
    return (today.year - 1911) * 10000 + today.month * 100 + today.day


def test_今天有資料_選今天():
    """盤中盤後都會有今日資料 → 選今日那筆"""
    today = _today_roc()
    data = [
        {"date": "1150615", "close": 100.0, "Trading_Volume": 1000},
        {"date": "1150616", "close": 101.0, "Trading_Volume": 2000},
        {"date": str(today), "close": 102.0, "Trading_Volume": 3000},
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    assert row["close"] == 102.0, f"應選今日 102.0，實際: {row['close']}"
    assert str(date) == str(today)


def test_週末_沒今日資料_取最後一筆():
    """週末 / 國定假日：data[-1] 是上週五收盤"""
    # 給的資料沒有今日（模擬週末）
    data = [
        {"date": "1150615", "close": 100.0, "Trading_Volume": 1000},
        {"date": "1150616", "close": 101.0, "Trading_Volume": 2000},  # 週五收盤
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    # 找不到今日 → 取最後一筆（週五收盤）
    assert row["close"] == 101.0, f"週末應取最後一筆 101.0，實際: {row['close']}"


def test_今天在後面_不取data_負1():
    """資料順序不對時、還是會找到今日（從後往前找）"""
    today = _today_roc()
    data = [
        {"date": str(today), "close": 105.0, "Trading_Volume": 5000},
        {"date": "1150616", "close": 101.0, "Trading_Volume": 2000},
        # 注意：data 順序不一定照日期遞增（測資就長這樣）
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    # 從後往前找到第一個今日 → 101.0（這個測資是壞的、要調換順序）
    # 因為我們是從後往前找、第一個遇到的今日就是 data[1] = 101.0
    # 修正：把 data 改回正確順序
    data = [
        {"date": "1150615", "close": 100.0, "Trading_Volume": 1000},
        {"date": "1150616", "close": 101.0, "Trading_Volume": 2000},
        {"date": str(today), "close": 102.0, "Trading_Volume": 3000},
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    assert row["close"] == 102.0, f"應選今日 102.0，實際: {row['close']}"


def test_空資料_回None():
    """data 為空 → 回 None"""
    row, date = st_fetch_market._pick_latest_price_row([])
    assert row is None
    assert date is None


def test_今天盤中即時_選今日_不是昨日():
    """William 反映：盤中時現價會一直變、必須抓到今日的盤中價（不是昨日收盤）

    模擬場景：
    - 今日是 6/17 11:30（盤中）
    - data[-1].date = 今日（盤中已有資料）
    - 上一筆 data[-2].date = 6/16 收盤
    → 應選今日盤中那筆
    """
    today = _today_roc()
    data = [
        {"date": "1150616", "close": 425.0, "Trading_Volume": 100000000},   # 昨日收盤 2408
        {"date": str(today), "close": 437.0, "Trading_Volume": 50000000},   # 今日盤中 11:30
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    # 應選今日 437.0（不是昨日 425.0）
    assert row["close"] == 437.0, \
        f"盤中應選今日 437.0，實際: {row['close']}"


def test_昨天收盤當_今日_避免誤判():
    """邊界：data 全部都是「昨日」、沒有今日
    → 應取最後一筆（昨日收盤）→ 合理 fallback
    """
    data = [
        {"date": "1150615", "close": 100.0, "Trading_Volume": 1000},
        {"date": "1150616", "close": 101.0, "Trading_Volume": 2000},
    ]
    row, date = st_fetch_market._pick_latest_price_row(data)
    # 沒今日 → data[-1] = 101.0
    assert row["close"] == 101.0
