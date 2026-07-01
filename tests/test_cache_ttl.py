"""V1.1.3-cache-ttl: 守住快取 TTL 分層邏輯

驗證：
- _CACHE_TTL 字典存在且有正確的 TTL 設定
- revenue cache 在 7 天內 → 用 cache
- revenue cache 超過 7 天 → 重抓
- eps cache 在 30 天內 → 用 cache
- eps cache 超過 30 天 → 重抓
- price cache 不走 TTL（盤中/收盤時間判斷更精準）
- stock_list cache 在 7 天內 → 用 cache

背景（v1.0 改版 TODO 2026-06-09 P1）：
- 原本 revenue/eps/stock_list 都用 last_update == today 判斷、每天重抓
- 改成：根據資料特性給不同 TTL、節省 API 額度
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# 把 source/ 加到 path 確保能 import
SOURCE_DIR = os.path.join(os.path.dirname(__file__), "..", "source")
if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from stocktool.cache import get_or_fetch, save_cache, load_cache  # noqa: E402
from stocktool.config import _CACHE_TTL  # noqa: E402


# ============================================================
# 1. _CACHE_TTL 字典設定
# ============================================================

def test_cache_ttl_dict_exists():
    """_CACHE_TTL 必須存在於 config"""
    assert _CACHE_TTL is not None, "❌ config._CACHE_TTL 不存在"
    print(f"✅ _CACHE_TTL = {_CACHE_TTL}")


def test_cache_ttl_revenue_is_7_days():
    """revenue (月營收) TTL 必須 = 7 天"""
    assert "revenue" in _CACHE_TTL, "❌ _CACHE_TTL 缺 revenue"
    assert _CACHE_TTL["revenue"] == 7, f"❌ revenue TTL 應為 7 天、實際 {_CACHE_TTL['revenue']}"
    print("✅ revenue TTL = 7 天（月資料、月初有新的）")


def test_cache_ttl_eps_is_30_days():
    """eps (季 EPS) TTL 必須 = 30 天"""
    assert "eps" in _CACHE_TTL, "❌ _CACHE_TTL 缺 eps"
    assert _CACHE_TTL["eps"] == 30, f"❌ eps TTL 應為 30 天、實際 {_CACHE_TTL['eps']}"
    print("✅ eps TTL = 30 天（季資料、季初有新的）")


def test_cache_ttl_stock_list_is_7_days():
    """stock_list (股票清單) TTL 必須 = 7 天"""
    assert "stock_list" in _CACHE_TTL, "❌ _CACHE_TTL 缺 stock_list"
    assert _CACHE_TTL["stock_list"] == 7, f"❌ stock_list TTL 應為 7 天、實際 {_CACHE_TTL['stock_list']}"
    print("✅ stock_list TTL = 7 天（週/月更新）")


def test_cache_ttl_price_not_in_dict():
    """price 不該在 _CACHE_TTL（盤中/收盤時間判斷更精準）"""
    assert "price" not in _CACHE_TTL, "❌ price 不該在 _CACHE_TTL、走盤中/收盤時間判斷"
    print("✅ price 不在 _CACHE_TTL（用時間判斷更精準）")


# ============================================================
# 2. get_or_fetch TTL 行為（用 tmp_path 隔離 cache 檔）
# ============================================================

def _make_cache_file(cache_dir: str, name: str, days_ago: int) -> str:
    """建立指定 days_ago 的 cache 檔（用真實的 save_cache/load_cache 介面）"""
    file_path = os.path.join(cache_dir, f"{name}.xlsx")
    df = pd.DataFrame({"股票代號": ["2330", "2317"], "現價": [600.0, 100.0]})
    # 寫 data sheet
    os.makedirs(cache_dir, exist_ok=True)
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        # 寫 meta sheet 帶指定日期
        last_update = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        meta = pd.DataFrame({"last_update": [last_update], "last_update_time": ["13:30:00"]})
        meta.to_excel(writer, sheet_name="meta", index=False)
    return file_path


def _patch_cache_path(monkeypatch, cache_dir: str):
    """把 cache 寫入/讀取指向 tmp_path"""
    def mock_get_cache_file(name: str) -> str:
        return os.path.join(cache_dir, f"{name}.xlsx")
    monkeypatch.setattr("stocktool.cache.get_cache_file", mock_get_cache_file)


def _patch_not_market_hours(monkeypatch):
    """避免 price 觸發盤中/收盤時間判斷（讓測試專注在 TTL）"""
    # 設成週末（一定不是盤中）— 避免 _is_market_hours 為 True
    # 但 2026-07-01 是週三、會被判定為盤後；用直接 monkeypatch 比較穩
    monkeypatch.setattr("stocktool.cache._is_market_hours", lambda: False)
    monkeypatch.setattr("stocktool.cache._is_price_cache_valid", lambda d, t, now=None: False)


def test_revenue_within_ttl_uses_cache(monkeypatch, tmp_path):
    """revenue cache 3 天前（TTL=7）→ 應該用 cache、不呼叫 fetch_func"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    # 建一個 3 天前的 revenue cache
    _make_cache_file(cache_dir, "revenue", days_ago=3)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("revenue", fetch_called, logger)

    fetch_called.assert_not_called(), (
        "❌ revenue cache 3 天前（TTL=7）應該用 cache、卻呼叫 fetch_func"
    )
    assert len(df) == 2, f"❌ 應該 return cache（2 筆）、實際 {len(df)}"
    print("✅ revenue cache 3 天前（< TTL 7）→ 用 cache、fetch_func 未呼叫")


def test_revenue_beyond_ttl_refetches(monkeypatch, tmp_path):
    """revenue cache 10 天前（TTL=7）→ 應該重抓、呼叫 fetch_func"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    _make_cache_file(cache_dir, "revenue", days_ago=10)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("revenue", fetch_called, logger)

    fetch_called.assert_called_once(), (
        "❌ revenue cache 10 天前（> TTL 7）應該重抓、卻沒呼叫 fetch_func"
    )
    print("✅ revenue cache 10 天前（> TTL 7）→ 重抓、fetch_func 已呼叫")


def test_eps_within_ttl_uses_cache(monkeypatch, tmp_path):
    """eps cache 20 天前（TTL=30）→ 應該用 cache"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    _make_cache_file(cache_dir, "eps", days_ago=20)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("eps", fetch_called, logger)

    fetch_called.assert_not_called(), (
        "❌ eps cache 20 天前（TTL=30）應該用 cache、卻呼叫 fetch_func"
    )
    print("✅ eps cache 20 天前（< TTL 30）→ 用 cache、fetch_func 未呼叫")


def test_eps_beyond_ttl_refetches(monkeypatch, tmp_path):
    """eps cache 40 天前（TTL=30）→ 應該重抓"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    _make_cache_file(cache_dir, "eps", days_ago=40)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("eps", fetch_called, logger)

    fetch_called.assert_called_once(), (
        "❌ eps cache 40 天前（> TTL 30）應該重抓、卻沒呼叫 fetch_func"
    )
    print("✅ eps cache 40 天前（> TTL 30）→ 重抓、fetch_func 已呼叫")


def test_stock_list_within_ttl_uses_cache(monkeypatch, tmp_path):
    """stock_list cache 5 天前（TTL=7）→ 應該用 cache"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    _make_cache_file(cache_dir, "stock_list", days_ago=5)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("stock_list", fetch_called, logger)

    fetch_called.assert_not_called(), (
        "❌ stock_list cache 5 天前（TTL=7）應該用 cache、卻呼叫 fetch_func"
    )
    print("✅ stock_list cache 5 天前（< TTL 7）→ 用 cache、fetch_func 未呼叫")


def test_ttl_at_boundary(monkeypatch, tmp_path):
    """TTL 邊界：revenue cache 7 天前（TTL=7）→ age=7、應該重抓（age < TTL 才是有效）"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    _make_cache_file(cache_dir, "revenue", days_ago=7)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("revenue", fetch_called, logger)

    # 邊界：age_days=7, ttl=7, 條件是 age_days < ttl → 7 < 7 是 False → 應重抓
    fetch_called.assert_called_once(), (
        "❌ TTL 邊界：revenue cache 7 天前（age=7 == TTL=7）應該重抓（age < TTL 才有效）"
    )
    print("✅ TTL 邊界：revenue cache 7 天前（age=7 == TTL）→ 重抓（用 age < TTL 嚴格小於）")


def test_price_not_use_ttl(monkeypatch, tmp_path):
    """price cache 不在 _CACHE_TTL → 走原本的「盤中/收盤時間」判斷（不會因為 TTL 7 天就誤判為有效）"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)

    # 把 _is_market_hours 關掉、_is_price_cache_valid 也回 False
    # 確保 price 走「last_update == today」判斷
    monkeypatch.setattr("stocktool.cache._is_market_hours", lambda: False)
    monkeypatch.setattr("stocktool.cache._is_price_cache_valid", lambda d, t, now=None: False)

    # 建一個 30 天前的 price cache（用 30 天模擬「舊的收盤後 cache」）
    # 必須包含「成交量_張」跟「data_date」欄位才不會觸發結構檢查
    file_path = os.path.join(cache_dir, "price.xlsx")
    os.makedirs(cache_dir, exist_ok=True)
    df = pd.DataFrame({
        "股票代號": ["2330"],
        "現價": [600.0],
        "成交量_張": [100],
        "data_date": ["2026-06-01"],
    })
    last_update = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": [last_update], "last_update_time": ["13:30:00"]})
        meta.to_excel(writer, sheet_name="meta", index=False)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    df = get_or_fetch("price", fetch_called, logger)

    # price 30 天前 + 不在 _CACHE_TTL → 走「資料過期 → 重抓」
    fetch_called.assert_called_once(), (
        "❌ price cache 30 天前 + 不在 _CACHE_TTL → 應重抓、卻沒呼叫 fetch_func"
    )
    print("✅ price cache 30 天前（不在 _CACHE_TTL）→ 重抓（不受 TTL 影響）")


def test_invalid_date_falls_through(monkeypatch, tmp_path):
    """last_update 是無效日期字串 → 走「資料過期 → 重抓」、不 crash"""
    cache_dir = str(tmp_path / "cache")
    _patch_cache_path(monkeypatch, cache_dir)
    _patch_not_market_hours(monkeypatch)

    # 手動建 cache 帶無效日期
    file_path = os.path.join(cache_dir, "revenue.xlsx")
    os.makedirs(cache_dir, exist_ok=True)
    df = pd.DataFrame({"股票代號": ["2330"]})
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": ["NOT-A-DATE"], "last_update_time": ["13:30:00"]})
        meta.to_excel(writer, sheet_name="meta", index=False)

    fetch_called = MagicMock(return_value=pd.DataFrame({"股票代號": ["NEW"]}))
    logger = MagicMock()

    # 不該 crash
    df = get_or_fetch("revenue", fetch_called, logger)

    fetch_called.assert_called_once(), (
        "❌ last_update 無效時應該走「重抓」、卻沒呼叫 fetch_func"
    )
    print("✅ last_update 是無效日期 → 走「重抓」、不 crash")
