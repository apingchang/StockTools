"""
test_dividend_year_mapping.py
驗證手動選股的「今年/去年現金股利」年份對應是否正確。

【重要修正】(V0.9.4)
FinMind `TaiwanStockDividend` 的 year 欄位是「會計年度」，
例如 year=2025 = 2025 年度盈餘的股利，在 2026 年除息發放。

台灣人說「今年現金股利」= 當年除息 = DB year=cy-1
        「去年現金股利」= 去年除息 = DB year=cy-2

之前的版本錯誤地把 DB year=cy 當「今年」，
導致 (1) DB 還沒有當年度資料 → 「今年」永遠是 None/空
         (2)「去年」抓到的是 DB year=cy-1 = 用戶口中的「今年」
            → 「去年現金殖利率」會用錯的分子算出錯誤百分比

修正後：cy-1 = 今年、cy-2 = 去年、cy-3 = 前年
"""
import os
import sys
import pandas as pd

# 讓測試可以 import source/StockTool.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _mock_finmind(codes, fake_div):
    """Mock _fetch_finmind_dividend 回傳指定 df"""
    def _fetch(codes_arg, **kwargs):
        return fake_div[fake_div["股票代號"].astype(str).isin([str(c) for c in codes_arg])].copy()
    return _fetch


def _make_input(rows):
    """產生 price_df（給 _run_manual_selection）"""
    return pd.DataFrame([
        {"股票代號": r[0], "公司名稱_來源": r[1], "股價": r[2], "成交量_張": r[3]}
        for r in rows
    ])


def _empty_revenue_eps():
    return pd.DataFrame(columns=["股票代號", "營收YoY(%)"]), \
           pd.DataFrame(columns=["股票代號", "EPS本期"])


def _no_filters():
    return {k: None for k in [
        "min_rev_yoy", "min_pe", "min_price", "min_volume",
        "min_cash_div", "min_stock_div",
        "min_last_cash_div", "min_last_stock_div",
        "min_cash_div_yld", "min_last_cash_yld",
    ]} | {"sort_by": []}


def test_3188_鑫龍騰_去年殖利率不該用今年現金股利():
    """
    3188 鑫龍騰 DB:
      year=2025 cash=3.196 (用戶: 2026 除息 = 工具的「今年」)
      year=2024 cash=1.8   (用戶: 2025 除息 = 工具的「去年」)

    修正前: 「去年現金殖利率」= 3.196/24.95 = 12.81% ← 用戶回報錯誤
    修正後: 「去年現金殖利率」= 1.8/24.95 = 7.21%
    """
    fake_div = pd.DataFrame({
        "股票代號": ["3188"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [3.196], "2025股票股利": [0.0],
        "2024現金股利": [1.8],   "2024股票股利": [0.0],
        "2023現金股利": [1.6],   "2023股票股利": [0.0],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("3188", "鑫龍騰", 24.95, 500)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金股利(元)"] == 3.196, \
        f"今年現金股利應為 3.196 (DB year=2025)，實際: {row['今年現金股利(元)']}"
    assert row["去年現金股利(元)"] == 1.8, \
        f"去年現金股利應為 1.8 (DB year=2024)，實際: {row['去年現金股利(元)']}"

    # 殖利率計算 = 股利 / 現價 * 100
    cy_yld = row["今年現金殖利率(%)"]
    ly_yld = row["去年現金殖利率(%)"]
    assert abs(cy_yld - 12.81) < 0.01, f"今年殖利率應約 12.81%，實際: {cy_yld}"
    assert abs(ly_yld - 7.21) < 0.01, f"去年殖利率應約 7.21%，實際: {ly_yld}"


def test_2408_南亞科_無DB資料時今年股利是None_不是用去年頂替():
    """
    2408 南亞科 DB 沒有 year=2024 的資料 (僅 2025=1.347、2022=2.13)
    修正前: 「去年現金股利」會錯誤抓到 DB year=2025=1.347 (其實是「今年」)
    修正後: 「去年現金股利」= DB year=cy-2=2024 = None（合理，沒資料不抓）
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None],  # ← 沒資料！
        "2024股票股利": [None],
        "2023現金股利": [None],
        "2023股票股利": [None],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金股利(元)"] == 1.347, \
        f"今年現金股利應為 1.347，實際: {row['今年現金股利(元)']}"
    # 修正前: row["去年現金股利(元)"] 會 = 1.347 (錯誤抓 year=2025)
    # 修正後: row["去年現金股利(元)"] 應該是 None (DB 沒 year=2024)
    last_div = row["去年現金股利(元)"]
    assert pd.isna(last_div), \
        f"去年現金股利應為 None (DB 沒 year=2024)，實際: {last_div}"


def test_2408_南亞科_殖利率用現價計算():
    """2408 殖利率 = 1.347/340 = 0.4% (用戶說 0.36% 是基於 374 假設價)"""
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    cy_yld = row["今年現金殖利率(%)"]
    assert abs(cy_yld - 0.4) < 0.01, f"今年殖利率應約 0.4%，實際: {cy_yld}"


def test_6171_大城地產_前年現金股利指向cy3():
    """
    6171 大城地產 DB 有 2022/2023/2024 年資料
    修正前: 前年現金股利 → DB year=cy-2=2024 (其實是「去年」)
    修正後: 前年現金股利 → DB year=cy-3=2023
    """
    fake_div = pd.DataFrame({
        "股票代號": ["6171"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [2.5],   "2024股票股利": [0.0],
        "2023現金股利": [1.5],   "2023股票股利": [0.0],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("6171", "大城地產", 24.0, 800)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 修正前: 今年=空, 去年=空, 前年=2.5 (cy-2=2024 誤抓)
    # 修正後: 今年=空 (cy-1=2025 空), 去年=2.5 (cy-2=2024), 前年=1.5 (cy-3=2023)
    assert pd.isna(row["今年現金股利(元)"]), "今年 (DB 2025) 應為空"
    assert row["去年現金股利(元)"] == 2.5, \
        f"去年現金股利應為 2.5 (DB year=2024)，實際: {row['去年現金股利(元)']}"

    # 殖利率
    ly_yld = row["去年現金殖利率(%)"]
    assert abs(ly_yld - 10.42) < 0.01, f"去年殖利率應約 10.42%，實際: {ly_yld}"


def test_year_mapping_不互相覆蓋():
    """確保今年/去年/前年現金股利三欄互不覆蓋，且來自不同年度"""
    fake_div = pd.DataFrame({
        "股票代號": ["TEST1"],
        "2026現金股利": [99.0],  # 故意填一個不合理的值，驗證不會被抓
        "2026股票股利": [None],
        "2025現金股利": [3.0],
        "2025股票股利": [0.0],
        "2024現金股利": [2.0],
        "2024股票股利": [0.0],
        "2023現金股利": [1.0],
        "2023股票股利": [0.0],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("TEST1", "測試股", 100.0, 100)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 即使 2026 有資料，今年不該抓 2026 (DB 2026 不代表 2026 除息)
    assert row["今年現金股利(元)"] == 3.0, \
        f"今年應抓 DB year=2025=3.0，不該抓 2026=99.0，實際: {row['今年現金股利(元)']}"
    assert row["去年現金股利(元)"] == 2.0, \
        f"去年應抓 DB year=2024=2.0，實際: {row['去年現金股利(元)']}"


if __name__ == "__main__":
    test_3188_鑫龍騰_去年殖利率不該用今年現金股利()
    print("✅ test_3188_鑫龍騰_去年殖利率不該用今年現金股利 passed")

    test_2408_南亞科_無DB資料時今年股利是None_不是用去年頂替()
    print("✅ test_2408_南亞科_無DB資料時今年股利是None_不是用去年頂替 passed")

    test_2408_南亞科_殖利率用現價計算()
    print("✅ test_2408_南亞科_殖利率用現價計算 passed")

    test_6171_大城地產_前年現金股利指向cy3()
    print("✅ test_6171_大城地產_前年現金股利指向cy3 passed")

    test_year_mapping_不互相覆蓋()
    print("✅ test_year_mapping_不互相覆蓋 passed")

    print("\n🎉 All tests passed!")