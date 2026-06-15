"""
test_fetch_stock_info_fallback.py
驗證 V0.9.5+ Phase 9：fetch_stock_info 在 z='-' 時 fallback 到 h+l 中價。

【V0.9.5+ Phase 9 修 Bug】2026-06-15 William 11:26 反映
- 00403A 現價一直停在 10.61 不動
- 根因：TWSE 在「沒成交瞬間」 z='-' → _num('z') 轉成 0.0
       → _apply_fetched_prices price=0 跳過更新 → 保持舊值

【修法】
- z=0 時 fallback 到 h+l 中價（今日高低价中點）
  - 比 y（昨收）更接近即時
  - 標記 price_fallback='mid' 讓 UI 知道是估算
- h/l 也 0 時 fallback 到 y（昨收）
  - 標記 price_fallback='prev_close'
- 兩者都 0 → price 保持 0、price_fallback='' → 維持原本「不更新」行為

【為什麼要這個 test】
- fetch_stock_info 之前只看 z、有成交就更新、沒成交就 0
- 00403A 這種交易不活躍的標的（主動式 ETF）會一直停在舊值
- 改 fallback 後要確保其他股票的正常成交價不被影響
"""
import os
import sys
from unittest.mock import patch, MagicMock
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import portfolio as pf  # noqa: E402


# ==========================================================
# Mock TWSE 回應
# ==========================================================

def _make_twse_response(z="10.61", o="10.54", h="10.65", l="10.52", y="10.25",
                        t="11:27:24", n="主動統一升級50"):
    """模擬 TWSE 單股查詢的 JSON 結構"""
    item = {"z": z, "o": o, "h": h, "l": l, "y": y, "t": t, "n": n}
    return {"msgArray": [item]}


def _make_empty_response():
    return {"msgArray": []}


# ==========================================================
# 【核心守護】z='-' fallback 到 h+l 中價
# ==========================================================

def test_z是橫線_fallback到h_l中價():
    """【V0.9.5+ Phase 9 核心】TWSE 沒成交瞬間（z='-'）→ fallback 到 (h+l)/2
    情境：00403A 盤中、沒最新成交、h=10.65 l=10.52 → 預期 price ≈ 10.585"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="-", o="10.54", h="10.65", l="10.52", y="10.25", t="11:27:24"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("00403A", session=session)
    expected_mid = round((10.65 + 10.52) / 2, 4)
    assert info["price"] == expected_mid, \
        f"z='-' 應 fallback 到 h+l 中價，預期 {expected_mid}、實際: {info['price']}"
    assert info["price_fallback"] == "mid", \
        f"price_fallback 應標記為 mid，實際: {info['price_fallback']}"
    assert info["ok"] is True


def test_z是None_fallback到h_l中價():
    """z=None 也要 fallback"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z=None, h="10.65", l="10.52"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("00403A", session=session)
    assert info["price"] == round((10.65 + 10.52) / 2, 4)
    assert info["price_fallback"] == "mid"


def test_hl也都0_fallback到昨收():
    """h/l 為 0（連今日高低都沒資料）→ fallback 到 y（昨收）"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="-", o="0", h="0", l="0", y="10.25"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("00403A", session=session)
    assert info["price"] == 10.25, \
        f"h/l 為 0 應 fallback 到 y=10.25，實際: {info['price']}"
    assert info["price_fallback"] == "prev_close", \
        f"price_fallback 應標記為 prev_close，實際: {info['price_fallback']}"


def test_全都0_price保持0():
    """z=0, h=0, l=0, y=0 → price 保持 0（不更新）"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="-", o="0", h="0", l="0", y="0"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("00403A", session=session)
    assert info["price"] == 0.0
    assert info["price_fallback"] == ""


# ==========================================================
# 【正常情況】即時成交價不被影響
# ==========================================================

def test_z有即時成交_不fallback():
    """【守護】z 有值時（正常成交）→ price 用 z、price_fallback 空字串"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="392.00", o="391.00", h="399.00", l="382.00", y="374.00"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("2408", session=session)
    assert info["price"] == 392.0
    assert info["price_fallback"] == "", \
        f"z 有值時 price_fallback 應空，實際: {info['price_fallback']}"


def test_z有即時成交_就算接近昨收也不誤判fallback():
    """【邊界】z=10.25 = y=10.25（開盤平盤）→ 仍用 z、不 fallback"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="10.25", o="10.25", h="10.25", l="10.25", y="10.25"
    )
    session.get.return_value.raise_for_status = MagicMock()

    info = pf.fetch_stock_info("00403A", session=session)
    assert info["price"] == 10.25
    assert info["price_fallback"] == ""


# ==========================================================
# 【整合】fetch_prices_batch 行為
# ==========================================================

def test_fetch_prices_batch_00403A_fallback正常運作():
    """【整合】fetch_prices_batch 對 00403A（z='-'）應 fallback、price 不為 0"""
    session = MagicMock(spec=requests.Session)
    session.get.return_value.json.return_value = _make_twse_response(
        z="-", h="10.65", l="10.52", y="10.25"
    )
    session.get.return_value.raise_for_status = MagicMock()

    results = pf.fetch_prices_batch(["00403A"], session=session)
    assert "00403A" in results
    info = results["00403A"]
    assert info["ok"] is True
    assert info["price"] > 0, f"00403A price 應 fallback 大於 0，實際: {info['price']}"
    assert info["price_fallback"] == "mid"


# ==========================================================
# 【_apply_fetched_prices 整合】fallback 也能更新 _current_prices
# ==========================================================

def test_apply_fetched_prices_fallback也更新():
    """【V0.9.5+ Phase 9 整合】fallback 估算價仍會被 apply
    之前 price=0 → 跳過；現在 price=mid > 0 → 仍會被設進 _current_prices
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    import StockTool as st
    from types import SimpleNamespace

    mock_self = SimpleNamespace()
    mock_self.logger = MagicMock()
    mock_self._current_prices = {}
    mock_self._refresh_portfolio_view = MagicMock()
    mock_self._backfill_stock_name = MagicMock()

    # 模擬兩個股票：2330 即時成交、00403A fallback mid
    results = {
        "2330": {"ok": True, "price": 2360.0, "name": "台積電", "price_fallback": ""},
        "00403A": {"ok": True, "price": 10.585, "name": "主動統一升級50", "price_fallback": "mid"},
    }
    st.StrategyGUI._apply_fetched_prices(mock_self, results)

    # 兩個 price 都應該被更新（fallback 也能更新）
    assert mock_self._current_prices["2330"] == 2360.0
    assert mock_self._current_prices["00403A"] == 10.585, \
        f"00403A fallback mid 應被更新，實際: {mock_self._current_prices.get('00403A')}"
    # 00403A 應有 log 提示
    log_calls = [str(c) for c in mock_self.logger.log.call_args_list]
    assert any("00403A" in s and "估算" in s for s in log_calls), \
        f"00403A 應有 fallback log 提示，實際: {log_calls}"


def test_apply_fetched_prices_price為0仍然跳過():
    """【邊界】price=0（全部 fallback 都失敗）→ 仍不更新（保持舊值）"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
    import StockTool as st
    from types import SimpleNamespace

    mock_self = SimpleNamespace()
    mock_self.logger = MagicMock()
    mock_self._current_prices = {"00403A": 10.61}  # 已有舊值
    mock_self._refresh_portfolio_view = MagicMock()
    mock_self._backfill_stock_name = MagicMock()

    results = {
        "00403A": {"ok": True, "price": 0.0, "name": "主動統一升級50", "price_fallback": ""},
    }
    st.StrategyGUI._apply_fetched_prices(mock_self, results)

    # price=0 → 不更新、保持舊值
    assert mock_self._current_prices["00403A"] == 10.61, \
        f"price=0 應保持舊值 10.61，實際: {mock_self._current_prices['00403A']}"
