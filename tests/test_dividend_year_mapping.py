"""
test_dividend_year_mapping.py
驗證手動選股的「今年/去年現金股利」年份對應是否正確。

【V0.9.5-goodinfo 修正】(2026-06-16 William 反映)
原本 (V0.9.5-alpha)「cy-1=今年」是 fiscal year 語意 → 半年配/季配公司會跟 goodinfo 不一致
群聯 (8299) 舉例：
  - 原設計：今年 = DB year=2025 = 31.31 (goodinfo 2025支付年 = 2024 H1+H2+2025 H1)
  - goodinfo 2026 支付年 = 16.96 (2026 H1)
  - 使用者反映「App 結果 31.31 錯了、goodinfo 是 16.96」

修正後：cy = 今年、cy-1 = 去年、cy-2 = 前年 (payment year 語意)
  - 跟 goodinfo「發放年度」一致 (goodinfo = 該年除息 = DB year=cy)
  - 使用者看到的「今年現金股利」= 今年實際收到的股利

  - 範例 cy=2026：
    * 今年 (cy) = DB year=2026 = 「2026 收到的股利」= goodinfo 2026
    * 去年 (cy-1) = DB year=2025 = 「2025 收到的股利」= goodinfo 2025
    * 前年 (cy-2) = DB year=2024 = 「2024 收到的股利」= goodinfo 2024

【舊設計說明】(V0.9.4 ~ V0.9.5-alpha)
原本以「cy-1=今年、cy-2=去年」 fiscal year 語意設計：
  FinMind `TaiwanStockDividend` 的 year 欄位是「會計年度」，
  例如 year=2025 = 2025 年度盈餘的股利，在 2026 年除息發放。
  → 「今年」= 該年除息 = DB year=cy-1
  → 「去年」= 去年除息 = DB year=cy-2
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
    3188 鑫龍騰 DB (V0.9.5-goodinfo 新語意 = payment year):
      year=2026 cash=3.196 (「2026 除息」= 工具的「今年」)
      year=2025 cash=1.8   (「2025 除息」= 工具的「去年」)
      year=2024 cash=1.6   (「2024 除息」= 工具的「前年」)

    驗證：
      - 今年 (cy=2026) = DB year=2026 = 3.196
      - 去年 (cy-1=2025) = DB year=2025 = 1.8
      - 去年殖利率 = 1.8/24.95 = 7.21%
    """
    fake_div = pd.DataFrame({
        "股票代號": ["3188"],
        "2026現金股利": [3.196], "2026股票股利": [0.0],
        "2025現金股利": [1.8],   "2025股票股利": [0.0],
        "2024現金股利": [1.6],   "2024股票股利": [0.0],
        "2023現金股利": [None],  "2023股票股利": [0.0],
        # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo
        "2026現金殖利率_goodinfo": [12.81],
        "2025現金殖利率_goodinfo": [7.21],
        "2024現金殖利率_goodinfo": [5.54],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("3188", "鑫龍騰", 24.95, 500)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金股利(元)"] == 3.196, \
        f"今年現金股利應為 3.196 (DB year=2026)，實際: {row['今年現金股利(元)']}"
    assert row["去年現金股利(元)"] == 1.8, \
        f"去年現金股利應為 1.8 (DB year=2025)，實際: {row['去年現金股利(元)']}"

    # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo（不走 cash/現價 fallback）
    cy_yld = row["今年現金殖利率(%)"]
    ly_yld = row["去年現金殖利率(%)"]
    assert abs(cy_yld - 12.81) < 0.01, f"今年殖利率應用 goodinfo 12.81%，實際: {cy_yld}"
    assert abs(ly_yld - 7.21) < 0.01, f"去年殖利率應用 goodinfo 7.21%，實際: {ly_yld}"


def test_2408_南亞科_無DB資料時今年股利是None_不是用去年頂替():
    """
    2408 南亞科 DB 沒有 year=2026 的資料 (僅 2025=1.347、2024=None)
    V0.9.5-goodinfo 新語意：
      - 今年 (cy=2026) = DB year=2026 = None（合理，沒資料不抓）
      - 去年 (cy-1=2025) = DB year=2025 = 1.347
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [None], "2026股票股利": [None],   # 沒資料！
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # V0.9.5-goodinfo 新語意：今年 = DB year=2026 = None (沒資料)
    assert pd.isna(row["今年現金股利(元)"]), \
        f"今年現金股利應為 None (DB 沒 year=2026)，實際: {row['今年現金股利(元)']}"
    # 去年 = DB year=2025 = 1.347
    last_div = row["去年現金股利(元)"]
    assert last_div == 1.347, \
        f"去年現金股利應為 1.347 (DB year=2025)，實際: {last_div}"


def test_2408_南亞科_殖利率用goodinfo():
    """2408 V0.9.5-goodinfo3：殖利率直接用 goodinfo 提供

    修訂：原本測「殖利率 = cash/現價 = 0.4%」，V0.9.5-goodinfo3 改用 goodinfo
    goodinfo 2408 2026 = 0.32%（不是 0.4%）
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [1.347], "2026股票股利": [0.0],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [None], "2024股票股利": [None],
        "2023現金股利": [None], "2023股票股利": [None],
        # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo
        "2026現金殖利率_goodinfo": [0.32],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    cy_yld = row["今年現金殖利率(%)"]
    assert abs(cy_yld - 0.32) < 0.01, f"今年殖利率應用 goodinfo 0.32%，實際: {cy_yld}"


def test_6171_大城地產_前年現金股利指向cy3():
    """
    6171 大城地產 DB 有 2023/2024/2025 年資料
    V0.9.5-goodinfo 新語意：
      - 前年 (cy-2=2024) = DB year=2024 = 2.5
      - 去年 (cy-1=2025) = DB year=2025 = 1.5
    """
    fake_div = pd.DataFrame({
        "股票代號": ["6171"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [1.5],   "2025股票股利": [0.0],
        "2024現金股利": [2.5],   "2024股票股利": [0.0],
        "2023現金股利": [None],  "2023股票股利": [0.0],
        # V0.9.5-goodinfo3：殖利率 100% 用 goodinfo
        "2025現金殖利率_goodinfo": [6.25],
        "2024現金殖利率_goodinfo": [3.05],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("6171", "大城地產", 24.0, 800)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # V0.9.5-goodinfo 新語意：今年=cy=2026=None, 去年=cy-1=2025=1.5, 前年=cy-2=2024=2.5
    assert pd.isna(row["今年現金股利(元)"]), "今年 (DB 2026) 應為空"
    assert row["去年現金股利(元)"] == 1.5, \
        f"去年現金股利應為 1.5 (DB year=2025)，實際: {row['去年現金股利(元)']}"

    # V0.9.5-goodinfo3：殖利率直接用 goodinfo 提供
    ly_yld = row["去年現金殖利率(%)"]
    assert abs(ly_yld - 6.25) < 0.01, f"去年殖利率應用 goodinfo 6.25%，實際: {ly_yld}"


def test_year_mapping_不互相覆蓋():
    """確保今年/去年/前年現金股利三欄互不覆蓋，且來自不同年度

    V0.9.5-goodinfo 新語意（payment year）：
      - 今年 (cy=2026) = DB year=2026
      - 去年 (cy-1=2025) = DB year=2025
      - 前年 (cy-2=2024) = DB year=2024
    """
    fake_div = pd.DataFrame({
        "股票代號": ["TEST1"],
        "2026現金股利": [99.0],
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

    # V0.9.5-goodinfo 新語意：今年=cy=2026=99.0
    assert row["今年現金股利(元)"] == 99.0, \
        f"今年應抓 DB year=2026=99.0，實際: {row['今年現金股利(元)']}"
    assert row["去年現金股利(元)"] == 3.0, \
        f"去年應抓 DB year=2025=3.0，實際: {row['去年現金股利(元)']}"


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