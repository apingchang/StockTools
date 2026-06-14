"""
test_filter_b_logic.py
驗證 V0.9.5+ 「B 邏輯」篩選器：硬條件 AND + 殖利率軟條件排序。

【V0.9.5-alpha 5th commit 實作錯誤】
- 拿掉 AND mask、只用 data_score > 0 過濾
- 結果：YoY < 30 仍會出現（截圖實例：1810 和成 -7.42 卻被納入）
- 因為只要 PE/現價/成交量其中一個有過，data_score > 0 就被納入

【V0.9.5-alpha 6th commit 修正】
把篩選條件分兩類：
- 硬條件（AND mask）：YoY、PE、現價、成交量、股利金額
  - None 一律算 fail（資料缺漏不能說達標）
  - 未達門檻也算 fail
- 軟條件（不擋 mask、只算排序）：今年/去年現金殖利率
  - 殖利率 None：不擋 mask（其他硬條件過了還是納入）
  - 殖利率有值未達標：不擋 mask（其他硬條件過了還是納入）
  - 殖利率達標：拿來算排序分數（排前面）

【為什麼殖利率是「軟條件」】
- DB 缺漏的股票（2023 檔沒資料）殖利率都是 None
- 如果殖利率算硬、會誤殺很多本來該納入的股票
- 殖利率不重要到要擋下其他硬條件都過的股票
- 但殖利率資料「有」比「沒有」更有用 → 用排序表達

【測試重要提醒】
_run_manual_selection 內部邏輯：
1. price_df 參數只取「股票代號、現價、成交量_張」3 欄（其他欄位會被丟掉）
2. 用 _fetch_finmind_dividend 從 DB 拿股利 → mock 必須回傳帶年份欄位的 df
3. 用「今年現金股利 / 現價」重算「今年現金殖利率(%)」
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# 取得當前年份（測試用）
CY = datetime.now().year  # 2026


def _make_div_df(codes_with_div: dict) -> pd.DataFrame:
    """Mock _fetch_finmind_dividend 回傳的股利 df
    codes_with_div: {code: {"this_cash": float, "last_cash": float}}
    """
    rows = []
    for code, div in codes_with_div.items():
        rows.append({
            "股票代號": code,
            f"{CY}現金股利": None,        # 2026（今年除息還沒公告）
            f"{CY}股票股利": None,
            f"{CY - 1}現金股利": div.get("this_cash"),  # 2025 = 「今年」
            f"{CY - 1}股票股利": div.get("this_stock", 0.0),
            f"{CY - 2}現金股利": div.get("last_cash"),  # 2024 = 「去年」
            f"{CY - 2}股票股利": div.get("last_stock", 0.0),
        })
    return pd.DataFrame(rows)


def _setup_mock(stock_divs: dict):
    """設定 _fetch_finmind_dividend mock
    stock_divs: {code: {"this_cash": float, "last_cash": float, ...}}
    """
    st._fetch_finmind_dividend = lambda codes, **kw: _make_div_df(stock_divs)


def _build_price_df(rows: list) -> pd.DataFrame:
    """建立 price_df 模擬 pipeline 傳入的股價資料
    rows: list of dict, 至少含 "股票代號"、"現價"
    註：_run_manual_selection 只取「股票代號、現價、成交量_張」三欄
    """
    return pd.DataFrame(rows)


# ==========================================================
# 【B 邏輯核心】硬條件 AND mask
# ==========================================================

def test_硬條件YoY沒過_該股票被排除():
    """【V0.9.5-alpha 5th commit 的 bug】YoY < 30 仍被納入 → 修正
    Case: A1 YoY 50% ✓, A2 YoY 10% ✗
    其他硬條件都過的情況下，A2 仍該被排除
    """
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 0.5},
        "A2": {"this_cash": 1.0, "last_cash": 0.5},
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 50.0},
        {"股票代號": "A2", "營收YoY(%)": 10.0},
    ])
    filters = {"min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" not in result["股票代號"].values, \
        f"A2 不應納入（YoY 沒過），實際: {result['股票代號'].tolist()}"


def test_硬條件YoY為None_該股票被排除():
    """硬條件 None = 資料缺漏 → 算 fail、排除"""
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 0.5},
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": None, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    filters = {"min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), filters, top_n=10)
    assert "A1" not in result["股票代號"].values, \
        f"A1 不應納入（YoY 為 None、無法判斷），實際: {result['股票代號'].tolist()}"


# ==========================================================
# 【B 邏輯核心】殖利率軟條件不擋 mask
# ==========================================================

def test_殖利率None_但其他硬條件都過_仍納入():
    """【關鍵 case】殖利率 None 不擋 mask
    Case: A1 殖利率 5%（達標）vs A2 殖利率 None
    只要 YoY、PE、現價、成交量都過 → 兩者都納入
    """
    _setup_mock({
        "A1": {"this_cash": 2.5, "last_cash": 0.5},   # 殖利率 5%
        "A2": {"this_cash": None, "last_cash": None},  # 殖利率 None
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 30.0},
        {"股票代號": "A2", "營收YoY(%)": 30.0},
    ])
    filters = {"min_rev_yoy": 30.0, "min_cash_div_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 兩檔都應納入（殖利率是軟條件）
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" in result["股票代號"].values, \
        f"A2 應納入（殖利率軟不擋 mask），實際: {result['股票代號'].tolist()}"


def test_殖利率有值但未達標_不擋mask():
    """殖利率 0.5%（未達 1%）不擋 mask、只影響排序（排到殖利率達標後面）"""
    _setup_mock({
        "A1": {"this_cash": 2.5, "last_cash": 0.5},   # 殖利率 5%（達標）
        "A2": {"this_cash": 0.25, "last_cash": 0.5},  # 殖利率 0.5%（未達標）
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 30.0},
        {"股票代號": "A2", "營收YoY(%)": 30.0},
    ])
    filters = {"min_rev_yoy": 30.0, "min_cash_div_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 兩檔都應納入
    assert "A1" in result["股票代號"].values
    assert "A2" in result["股票代號"].values
    # A1 (5%) 排前
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (5%) 應在 A2 (0.5%) 前面，實際: A1={a1_idx}, A2={a2_idx}"


# ==========================================================
# 【B 邏輯】排序邏輯
# ==========================================================

def test_殖利率有值_排殖利率None前面():
    """殖利率有值（vs None）排前面"""
    _setup_mock({
        "A1": {"this_cash": 0.5, "last_cash": 0.0},   # 殖利率 1%（達標邊緣）
        "A2": {"this_cash": None, "last_cash": None},  # 殖利率 None
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 30.0},
        {"股票代號": "A2", "營收YoY(%)": 30.0},
    ])
    filters = {"min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (殖利率有值) 應在 A2 (殖利率 None) 前面，實際: A1={a1_idx}, A2={a2_idx}"


def test_殖利率達標_排殖利率未達標前面():
    """殖利率達標（5%）排前、殖利率未達標（0.5%）排後"""
    _setup_mock({
        "A1": {"this_cash": 2.5, "last_cash": 0.5},   # 殖利率 5%
        "A2": {"this_cash": 0.25, "last_cash": 0.5},  # 殖利率 0.5%
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 30.0},
        {"股票代號": "A2", "營收YoY(%)": 30.0},
    ])
    filters = {"min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (5%) 應在 A2 (0.5%) 前面，實際: A1={a1_idx}, A2={a2_idx}"


# ==========================================================
# 【B 邏輯】什麼都沒勾的向後相容
# ==========================================================

def test_什麼都沒勾_保留全部():
    """filters 是空 dict → 沒過濾"""
    _setup_mock({
        "A1": {"this_cash": None, "last_cash": None},
        "A2": {"this_cash": 1.0, "last_cash": 0.5},
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": None,
         "營收YoY(%)": None, "成交量_張": None, "PE": None, "EPS本期": None},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 30.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 2.0},
    ])
    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), {}, top_n=10)
    assert len(result) == 2, f"沒勾條件時應保留全部 2 檔，實際: {len(result)}"


# ==========================================================
# 【典型情境】William 22:10 截圖
# ==========================================================

def test_William截圖情境_YoY小於30不該出現():
    """【關鍵守護】模擬 William 22:10 截圖看到的問題
    - 條件：YoY >= 30
    - 應排除：YoY < 30 的股票（即使其他條件都過）
    - 简化版：只勾 YoY 條件，專注驗證「YoY 沒過就排除」這件事
    """
    _setup_mock({
        "3188": {"this_cash": 3.196, "last_cash": 1.8},   # 鑫龍騰
        "1810": {"this_cash": 0.18, "last_cash": 0.05},   # 和成
        "1817": {"this_cash": 0.99, "last_cash": 0.5},    # 凱撒衛
    })
    price_df = _build_price_df([
        # 鑫龍騰 YoY 880% → 過
        {"股票代號": "3188", "股票名稱": "鑫龍騰", "現價": 24.95,
         "營收YoY(%)": 880.0, "成交量_張": 1000.0, "PE": 10.94, "EPS本期": 2.0},
        # 和成 YoY -7.42% → 不該出現
        {"股票代號": "1810", "股票名稱": "和成", "現價": 20.55,
         "營收YoY(%)": -7.42, "成交量_張": 1000.0, "PE": 5.65, "EPS本期": 3.0},
        # 凱撒衛 YoY -7.42% → 不該出現
        {"股票代號": "1817", "股票名稱": "凱撒衛", "現價": 39.60,
         "營收YoY(%)": -7.42, "成交量_張": 1000.0, "PE": 32.73, "EPS本期": 1.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "3188", "營收YoY(%)": 880.0},
        {"股票代號": "1810", "營收YoY(%)": -7.42},
        {"股票代號": "1817", "營收YoY(%)": -7.42},
    ])
    # 简化：只勾 YoY 條件（這是問題的關鍵）
    filters = {"min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=500)
    codes = result["股票代號"].tolist()
    assert "3188" in codes, f"3188 應納入（YoY 過），實際: {codes}"
    assert "1810" not in codes, f"1810 不該納入（YoY -7.42 < 30），實際: {codes}"
    assert "1817" not in codes, f"1817 不該納入（YoY -7.42 < 30），實際: {codes}"


if __name__ == "__main__":
    test_硬條件YoY沒過_該股票被排除()
    print("✅ test_硬條件YoY沒過_該股票被排除 passed")
    test_硬條件YoY為None_該股票被排除()
    print("✅ test_硬條件YoY為None_該股票被排除 passed")
    test_殖利率None_但其他硬條件都過_仍納入()
    print("✅ test_殖利率None_但其他硬條件都過_仍納入 passed")
    test_殖利率有值但未達標_不擋mask()
    print("✅ test_殖利率有值但未達標_不擋mask passed")
    test_殖利率有值_排殖利率None前面()
    print("✅ test_殖利率有值_排殖利率None前面 passed")
    test_殖利率達標_排殖利率未達標前面()
    print("✅ test_殖利率達標_排殖利率未達標前面 passed")
    test_什麼都沒勾_保留全部()
    print("✅ test_什麼都沒勾_保留全部 passed")
    test_William截圖情境_YoY小於30不該出現()
    print("✅ test_William截圖情境_YoY小於30不該出現 passed")
    print("\n🎉 All B-logic tests passed!")
