"""
test_pe_filter.py
驗證手動選股的「PE 過濾」邏輯。

【問題】(V0.9.5-alpha)
EPS 接近 0（例如 0.001 元）時，PE = 現價/EPS = 24/0.001 = 24000 → 顯示怪數字
6171 大城地產截圖中就顯示 PE=300（EPS 接近 0 造成）

【修正】
EPS 本期 < 0.05 元時，PE 設為 None（顯示 --）而非計算出來。
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構


def _mock_finmind(codes, fake_div):
    def _fetch(codes_arg, **kwargs):
        return fake_div[fake_div["股票代號"].astype(str).isin([str(c) for c in codes_arg])].copy()
    return _fetch


def _make_input(rows):
    return pd.DataFrame([
        {"股票代號": r[0], "公司名稱_來源": r[1], "股價": r[2], "成交量_張": r[3]}
        for r in rows
    ])


def _no_filters():
    return {k: None for k in [
        "min_rev_yoy", "min_pe", "min_price", "min_volume",
        "min_cash_div", "min_stock_div",
        "min_last_cash_div", "min_last_stock_div",
        "min_cash_div_yld", "min_last_cash_yld",
    ]} | {"sort_by": []}


def test_PE_接近零時_應為None():
    """EPS = 0.01、股價 24 → 原本算 PE = 2400（不合理）"""
    fake_div = pd.DataFrame({
        "股票代號": ["6171"], "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [2.5], "2024股票股利": [0.0],
        "2023現金股利": [1.5], "2023股票股利": [0.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("6171", "大城地產", 24.0, 800)])
    rev = pd.DataFrame({"股票代號": ["6171"], "營收YoY(%)": [None]})
    eps = pd.DataFrame({"股票代號": ["6171"], "EPS本期": [0.01]})  # ← 接近 0

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    pe = result.iloc[0]["PE"]
    assert pd.isna(pe), f"EPS=0.01 應設 PE=None，實際: {pe}"


def test_PE_負值時_應為None():
    """EPS 為負（公司虧損）時 PE 無意義，設 None"""
    fake_div = pd.DataFrame({
        "股票代號": ["LOSE1"], "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("LOSE1", "虧損股", 20.0, 100)])
    rev = pd.DataFrame({"股票代號": ["LOSE1"], "營收YoY(%)": [None]})
    eps = pd.DataFrame({"股票代號": ["LOSE1"], "EPS本期": [-0.5]})

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    pe = result.iloc[0]["PE"]
    assert pd.isna(pe), f"EPS=-0.5 應設 PE=None，實際: {pe}"


def test_PE_正常值_應正確計算():
    """EPS = 2.5、股價 50 → PE = 20"""
    fake_div = pd.DataFrame({
        "股票代號": ["OK1"], "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [1.5], "2025股票股利": [0.0],
        "2024現金股利": [1.0], "2024股票股利": [0.0],
        "2023現金股利": [0.8], "2023股票股利": [0.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("OK1", "正常股", 50.0, 500)])
    rev = pd.DataFrame({"股票代號": ["OK1"], "營收YoY(%)": [None]})
    eps = pd.DataFrame({"股票代號": ["OK1"], "EPS本期": [2.5]})

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    pe = result.iloc[0]["PE"]
    assert pe == 20.0, f"EPS=2.5、股價=50 應 PE=20.0，實際: {pe}"


def test_PE_邊界值_EPS_等於0_05時_應計算():
    """EPS 剛好 0.05（門檻值）→ 應該計算 PE（>= 0.05）"""
    fake_div = pd.DataFrame({
        "股票代號": ["BORDER"], "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("BORDER", "邊界股", 10.0, 100)])
    rev = pd.DataFrame({"股票代號": ["BORDER"], "營收YoY(%)": [None]})
    eps = pd.DataFrame({"股票代號": ["BORDER"], "EPS本期": [0.05]})

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    pe = result.iloc[0]["PE"]
    # 0.05 應 >= 0.05 → 計算 PE = 10/0.05 = 200
    assert pe == 200.0, f"EPS=0.05、股價=10 應 PE=200.0，實際: {pe}"


def test_PE_邊界值_EPS_略低於0_05時_應為None():
    """EPS = 0.04（< 0.05）→ 應 None"""
    fake_div = pd.DataFrame({
        "股票代號": ["BORDER2"], "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("BORDER2", "邊界股2", 10.0, 100)])
    rev = pd.DataFrame({"股票代號": ["BORDER2"], "營收YoY(%)": [None]})
    eps = pd.DataFrame({"股票代號": ["BORDER2"], "EPS本期": [0.04]})

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    pe = result.iloc[0]["PE"]
    assert pd.isna(pe), f"EPS=0.04 (< 0.05) 應設 PE=None，實際: {pe}"


if __name__ == "__main__":
    test_PE_接近零時_應為None()
    print("✅ test_PE_接近零時_應為None passed")
    test_PE_負值時_應為None()
    print("✅ test_PE_負值時_應為None passed")
    test_PE_正常值_應正確計算()
    print("✅ test_PE_正常值_應正確計算 passed")
    test_PE_邊界值_EPS_等於0_05時_應計算()
    print("✅ test_PE_邊界值_EPS_等於0_05時_應計算 passed")
    test_PE_邊界值_EPS_略低於0_05時_應為None()
    print("✅ test_PE_邊界值_EPS_略低於0_05時_應為None passed")
    print("\n🎉 All tests passed!")