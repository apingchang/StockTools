"""
test_filter_b_logic.py
驗證 V0.9.5+ 「B 邏輯」篩選器：None 排後面、至少一項有資料、達標多的排前面。

【動機】
原本 V0.9.5-alpha 的篩選邏輯：
  is_na | (yld >= filters["min_cash_div_yld"])
→ 殖利率 None 的股票被視為「達標」、誤導使用者（截圖中 127 檔殖利率都是 --）
→ 應該改為「B 邏輯」：None 排後面、至少一項過、達標多的排前面

【新邏輯】
- 每個被勾選的條件：計算 pass_score (達標) 和 data_score (有資料)
- 至少要有一個條件有資料（data_score > 0）才納入結果
- 排序：pass_score 多 > data_score 多 > 殖利率有值 > 殖利率高 > ...

【測試重要提醒】
_run_manual_selection 內部邏輯：
1. price_df 參數只取「股票代號、現價、成交量_張」4 欄（其他欄位會被丟掉）
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


def test_殖利率None_不再被視為達標():
    """原本：殖利率 None 視為達標 → 誤導
    新邏輯：殖利率 None 不算 pass_score、但不排除（有其他資料的話）
    
    Case: A1 (殖利率 2% 達標) vs A2 (殖利率 None、但營收達標)
    → 兩者都應納入（data_score 都 ≥ 1）
    → A1 排前、A2 排後
    """
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 0.5},   # 殖利率 2%
        "A2": {"this_cash": None, "last_cash": None},  # 殖利率 None
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 2.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 30.0},
        {"股票代號": "A2", "營收YoY(%)": 30.0},
    ])
    # 勾兩個條件：殖利率 + 營收
    # A1: 殖利率 2% 達標 + 營收 30% 達標 → pass=2, data=2
    # A2: 殖利率 None + 營收 30% 達標 → pass=1 (營收), data=2 (兩個都有資料)
    filters = {"min_cash_div_yld": 1.0, "min_rev_yoy": 20.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 兩檔都應納入
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" in result["股票代號"].values, f"A2 應納入（data_score ≥ 1），實際: {result['股票代號'].tolist()}"
    # A1 排前面（pass=2 > A2 pass=1）
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (pass=2) 應在 A2 (pass=1) 前面，實際: A1={a1_idx}, A2={a2_idx}"


def test_至少要有一個條件有資料():
    """如果所有被勾選的條件該股票都 None → 排除（data_score = 0）"""
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": None},   # 殖利率 2%
        "A2": {"this_cash": None, "last_cash": None},  # 殖利率 None
    })
    price_df = _build_price_df([
        # A1: 殖利率有值 → 納入
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": None, "成交量_張": None, "PE": None, "EPS本期": None},
        # A2: 殖利率也 None → 排除（data_score = 0）
        {"股票代號": "A2", "股票名稱": "A2", "現價": None,
         "營收YoY(%)": None, "成交量_張": None, "PE": None, "EPS本期": None},
    ])
    filters = {"min_cash_div_yld": 1.0}  # 只勾殖利率
    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), filters, top_n=10)
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" not in result["股票代號"].values, \
        f"A2 不應納入（所有被勾選條件都 None），實際: {result['股票代號'].tolist()}"


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


def test_通過分數多_排前面():
    """A1 通過 2 個條件、A2 通過 1 個條件 → A1 排前面"""
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 0.5},   # 殖利率 2%
        "A2": {"this_cash": 1.0, "last_cash": 0.5},   # 殖利率 2%
    })
    price_df = _build_price_df([
        # A1: 殖利率 2% + 營收 50%（pass=2）
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        # A2: 殖利率 2% + 營收 10%（pass=1，營收未達標）
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "累計營收YoY(%)": 50.0},
        {"股票代號": "A2", "累計營收YoY(%)": 10.0},
    ])
    filters = {"min_rev_yoy": 30.0, "min_cash_div_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (pass=2) 應在 A2 (pass=1) 前面，實際: A1={a1_idx}, A2={a2_idx}"


def test_殖利率有值_排殖利率None前面():
    """A1 殖利率 0.5%（未達標但有值）、A2 殖利率 None
    → 需要勾另一個條件讓 A2 data_score > 0
    → 兩者都 pass=0（殖利率都未達 1%），但 A1 殖利率有值 → 排前面
    """
    _setup_mock({
        "A1": {"this_cash": 0.25, "last_cash": 0.5},  # 殖利率 0.5%
        "A2": {"this_cash": None, "last_cash": None},  # 殖利率 None
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "A1", "營收YoY(%)": 50.0},
        {"股票代號": "A2", "營收YoY(%)": 50.0},
    ])
    # 勾兩個：殖利率 + 營收
    # A1: 殖利率 0.5%（未達） + 營收 50%（達）→ pass=1, data=2
    # A2: 殖利率 None + 營收 50%（達）→ pass=1, data=1
    filters = {"min_cash_div_yld": 1.0, "min_rev_yoy": 30.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    # A1 data=2 應在 A2 data=1 前面（data_score 排序）
    assert a1_idx < a2_idx, f"A1 (data=2) 應在 A2 (data=1) 前面，實際: A1={a1_idx}, A2={a2_idx}"


def test_殖利率達標_排殖利率未達標前面():
    """A1 殖利率 5%（達標）、A2 殖利率 0.5%（有值未達標）→ A1 排前面"""
    _setup_mock({
        "A1": {"this_cash": 2.5, "last_cash": 0.5},   # 殖利率 5%
        "A2": {"this_cash": 0.25, "last_cash": 0.5},  # 殖利率 0.5%
    })
    price_df = _build_price_df([
        {"股票代號": "A1", "股票名稱": "A1", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
        {"股票代號": "A2", "股票名稱": "A2", "現價": 50.0,
         "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    filters = {"min_cash_div_yld": 1.0}
    result = st._run_manual_selection(price_df, pd.DataFrame(), pd.DataFrame(), filters, top_n=10)
    a1_idx = result.index[result["股票代號"] == "A1"][0]
    a2_idx = result.index[result["股票代號"] == "A2"][0]
    assert a1_idx < a2_idx, f"A1 (5%) 應在 A2 (0.5%) 前面，實際: A1={a1_idx}, A2={a2_idx}"


def test_典型情境_殖利率None_加營收高的會排前面():
    """模擬 William 11:28 看到的 127 檔情境：
    - 127 檔殖利率都 None（DB 缺漏）
    - 營收 YoY 都有值
    - 使用者勾選「殖利率 ≥ 1%」+「營收 YoY ≥ 30%」
    - 預期：殖利率有值的排最前，殖利率 None 排後面
    """
    divs = {
        "N0": {"this_cash": None}, "N1": {"this_cash": None},
        "N2": {"this_cash": None}, "N3": {"this_cash": None}, "N4": {"this_cash": None},
        "Y1": {"this_cash": 2.5},    # 殖利率 5%（達標）
        "Y2": {"this_cash": 0.25},   # 殖利率 0.5%（有值未達標、避免被 line 989 的 >0 mask 排成 None）
    }
    _setup_mock(divs)
    rows = []
    # 5 檔殖利率 None 但營收達標
    for i in range(5):
        rows.append({
            "股票代號": f"N{i}", "股票名稱": f"None{i}", "現價": 50.0,
            "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0,
        })
    rows.append({"股票代號": "Y1", "股票名稱": "Y1", "現價": 50.0,
                 "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0})
    rows.append({"股票代號": "Y2", "股票名稱": "Y2", "現價": 50.0,
                 "營收YoY(%)": 50.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0})
    price_df = _build_price_df(rows)
    revenue_df = pd.DataFrame([{"股票代號": r["股票代號"], "營收YoY(%)": 50.0} for r in rows])
    filters = {"min_rev_yoy": 30.0, "min_cash_div_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 全部 7 檔都應納入（都有營收資料）
    assert len(result) == 7, f"應納入 7 檔，實際: {len(result)}"
    # Y1 應在最前（殖利率 5% 達標）
    y1_idx = result.index[result["股票代號"] == "Y1"][0]
    assert y1_idx == 0, f"Y1 應排第 1，實際: {y1_idx}"
    # N0..N4 應在 Y1、Y2 後面（殖利率 None）
    n0_idx = result.index[result["股票代號"] == "N0"][0]
    y2_idx = result.index[result["股票代號"] == "Y2"][0]
    assert y1_idx < y2_idx < n0_idx, \
        f"排序應為 Y1 < Y2 < N0，實際: Y1={y1_idx}, Y2={y2_idx}, N0={n0_idx}"


if __name__ == "__main__":
    test_殖利率None_不再被視為達標()
    print("✅ test_殖利率None_不再被視為達標 passed")
    test_至少要有一個條件有資料()
    print("✅ test_至少要有一個條件有資料 passed")
    test_什麼都沒勾_保留全部()
    print("✅ test_什麼都沒勾_保留全部 passed")
    test_通過分數多_排前面()
    print("✅ test_通過分數多_排前面 passed")
    test_殖利率有值_排殖利率None前面()
    print("✅ test_殖利率有值_排殖利率None前面 passed")
    test_殖利率達標_排殖利率未達標前面()
    print("✅ test_殖利率達標_排殖利率未達標前面 passed")
    test_典型情境_殖利率None_加營收高的會排前面()
    print("✅ test_典型情境_殖利率None_加營收高的會排前面 passed")
    print("\n🎉 All B-logic tests passed!")
