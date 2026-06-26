"""
test_goodinfo_yield_rate.py
驗證手動選股的殖利率算法

【V0.9.5-goodinfo6+++ 改】William 2026-06-26 14:18 反映：
「2026 殖利率不能從 goodinfo 抓、要用現價去計算！」

新演算法：
  - 今年現金殖利率(%)：cash / 現價 × 100（用現價算、cash=0 = 0%）
  - 去年現金殖利率(%)：直接用 goodinfo（除息日還原價算的歷史值）
  - 股票殖利率（今年/去年）：直接用 goodinfo

為什麼去年仍用 goodinfo？
  - 去年已除息完成、殖利率是歷史事實
  - goodinfo 用「除息基準日還原價」算的、比現價算更接近實際
  - 用現價算反而會被現價偏離誤導

【V0.9.5-goodinfo3 舊版】（2026-06-17 ~ 2026-06-26）
殖利率 100% 用 goodinfo（已廢棄）
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402


def _mock_finmind(codes, fake_div):
    def _fetch(codes_arg, **kwargs):
        return fake_div[fake_div["股票代號"].astype(str).isin([str(c) for c in codes_arg])].copy()
    return _fetch


def _make_input(rows):
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


# ─────────────────────────────────────────
# 1. 今年殖利率 = cash / 現價 × 100（不用 goodinfo）
# ─────────────────────────────────────────
def test_今年殖利率用現金股利除以現價():
    """2026 殖利率 = cash / 現價 × 100，不用 goodinfo 的歷史值"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        # goodinfo 殖利率故意給很離譜的值 (6.32)、不該被採用
        "2026現金殖利率_goodinfo": [6.32],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 5.0 / 100 × 100 = 5.0%（不是 goodinfo 6.32）
    assert abs(row["今年現金殖利率(%)"] - 5.0) < 0.01, \
        f"應 = cash/現價 = 5.0%，實際: {row['今年現金殖利率(%)']}"


def test_9946_現金股利1_37現價29_殖利率4_72():
    """9946 真實情境：cash=1.37、現價=29 → 殖利率 4.72%（不是 goodinfo 6.9%）"""
    fake_div = pd.DataFrame({
        "股票代號": ["9946"],
        "2026現金股利": [1.37], "2026股票股利": [0.0],
        "2025現金股利": [1.041], "2025股票股利": [0.0],
        "2024現金股利": [0.7], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [6.9],   # goodinfo 給 6.9%（除息基準日還原價算的）
        "2025現金殖利率_goodinfo": [5.3],
        "2024現金殖利率_goodinfo": [1.97],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("9946", "三發地產", 29.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 1.37 / 29 × 100 = 4.72%（不是 goodinfo 6.9）
    assert abs(row["今年現金殖利率(%)"] - 4.72) < 0.01, \
        f"9946 應 = 1.37/29 = 4.72%，實際: {row['今年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 2. 去年殖利率仍用 goodinfo
# ─────────────────────────────────────────
def test_去年殖利率仍用goodinfo():
    """去年現金殖利率：用 goodinfo（除息日還原價算的歷史值、不用現價算）"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2025現金殖利率_goodinfo": [4.55],
        "2025除息日": ["2026-08-15"],
        "2025除息日收盤價": [1200.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 去年殖利率 = goodinfo 4.55（不用 ex_date_close 算的 0.33%、也不用現價算的 4%）
    assert row["去年現金殖利率(%)"] == 4.55, \
        f"去年殖利率應用 goodinfo 4.55，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 3. cash=0 → 殖利率 = 0.0%（不再是 None）
# ─────────────────────────────────────────
def test_今年現金股利0_殖利率為0():
    """6219 情境：cash=0 → 殖利率 = 0.0%（合理、表示該年未配息）"""
    fake_div = pd.DataFrame({
        "股票代號": ["6219"],
        "2026現金股利": [0.0], "2026股票股利": [0.0],
        "2025現金股利": [0.7], "2025股票股利": [0.5],
        "2024現金股利": [0.7], "2024股票股利": [0.5],
        "2026現金殖利率_goodinfo": [0.0],
        "2025現金殖利率_goodinfo": [3.15],
        "2024現金殖利率_goodinfo": [0.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("6219", "富旺", 13.25, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # cash=0 → 殖利率 = 0/13.25 = 0.0%
    assert row["今年現金殖利率(%)"] == 0.0, \
        f"cash=0 應顯示 0.0%，實際: {row['今年現金殖利率(%)']}"


def test_今年現金股利None_殖利率為None():
    """DB 沒 cash 資料（沒配息沒紀錄） → 殖利率 None（不是 0%）"""
    fake_div = pd.DataFrame({
        "股票代號": ["9999"],
        "2026現金股利": [None], "2026股票股利": [None],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [None], "2024股票股利": [None],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("9999", "新上市", 100.0, 500)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # cash=None → 殖利率 None（不是 0%）
    assert row["今年現金殖利率(%)"] is None or pd.isna(row["今年現金殖利率(%)"]), \
        f"cash=None 應為 None，實際: {row['今年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 4. 股票殖利率仍用 goodinfo
# ─────────────────────────────────────────
def test_今年股票殖利率用goodinfo():
    """股票殖利率直接用 goodinfo（今年現金殖利率用現價算、股票殖利率照舊）"""
    fake_div = pd.DataFrame({
        "股票代號": ["5386"],
        "2026現金股利": [0.0], "2026股票股利": [5.0],
        "2025現金股利": [0.0], "2025股票股利": [1.378],
        "2024現金股利": [0.0], "2024股票股利": [0.9],
        "2026股票殖利率_goodinfo": [1.0],
        "2025股票殖利率_goodinfo": [1.78],
        "2024股票殖利率_goodinfo": [1.07],
        "2026現金殖利率_goodinfo": [0.0],
        "2025現金殖利率_goodinfo": [0.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("5386", "捷敏", 499.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 股票殖利率 = goodinfo
    assert row["今年股票殖利率(%)"] == 1.0, \
        f"今年股票殖利率應用 goodinfo 1.0，實際: {row['今年股票殖利率(%)']}"
    assert row["去年股票殖利率(%)"] == 1.78, \
        f"去年股票殖利率應用 goodinfo 1.78，實際: {row['去年股票殖利率(%)']}"
    # 今年現金殖利率 = 0/499 = 0%
    assert row["今年現金殖利率(%)"] == 0.0, \
        f"今年現金殖利率 cash=0 應 = 0%，實際: {row['今年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 5. 10Y 平均殖利率欄位已拿掉
# ─────────────────────────────────────────
def test_10Y平均殖利率欄位已拿掉():
    """V0.9.5-goodinfo3：William 說不需要 → 欄位拿掉"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [5.0],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)

    assert "歷史平均現金殖利率(%)" not in result.columns, \
        "10Y 平均殖利率欄位應該已拿掉"


# ─────────────────────────────────────────
# 6. 真實情境：3231 緯創（去年殖利率 3.3 = goodinfo）
# ─────────────────────────────────────────
def test_3231_緯創_去年殖利率直接用goodinfo():
    """3231 去年現金殖利率 = goodinfo 3.3%（不是現價算的 3.799/158*100 = 2.40）"""
    fake_div = pd.DataFrame({
        "股票代號": ["3231"],
        "2026現金股利": [5.5], "2026股票股利": [0.0],
        "2025現金股利": [3.799], "2025股票股利": [0.0],
        "2024現金股利": [2.599], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [3.48],
        "2025現金殖利率_goodinfo": [3.3],   # ← goodinfo 提供
        "2024現金殖利率_goodinfo": [2.36],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("3231", "緯創", 158.00, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 今年殖利率 = 5.5/158*100 = 3.48%（巧合跟 goodinfo 一樣、cash/現價算法對）
    assert abs(row["今年現金殖利率(%)"] - 3.48) < 0.01, \
        f"今年殖利率應 = cash/現價 = 3.48%，實際: {row['今年現金殖利率(%)']}"
    # 去年殖利率 = goodinfo 3.3（不是 fallback 算的 2.4）
    assert row["去年現金殖利率(%)"] == 3.3, \
        f"去年殖利率應用 goodinfo 3.3，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 7. 殖利率 0.0 不該被當 None（顯示格式化）
# ─────────────────────────────────────────
def test_殖利率0_0_不該當None_應為0_00():
    """V0.9.5-goodinfo4：殖利率 = 0.0 是合法值、要顯示 '0.00'"""
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [0.0], "2026股票股利": [0.0],
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        "2026現金殖利率_goodinfo": [0.0],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 殖利率 = 0.0（cash=0、現價 340 → 0/340 = 0）
    val = row["今年現金殖利率(%)"]
    assert val == 0.0, f"殖利率 0.0 應保留為 0.0，實際: {val}"


def test_殖利率0_30_不該顯示破折號():
    """_fmt_float：0.0 → '0.00'、0.3 → '0.30'、None → '—'"""
    from StockTool import _fmt_float
    assert _fmt_float(0.0) == "0.00", f"0.0 應顯示 '0.00'，實際: '{_fmt_float(0.0)}'"
    assert _fmt_float(0.3) == "0.30", f"0.3 應顯示 '0.30'，實際: '{_fmt_float(0.3)}'"
    assert _fmt_float(None) == "—", f"None 應顯示 '—'"
    assert _fmt_float(float("nan")) == "—", f"NaN 應顯示 '—'"
    assert _fmt_float(425.0) == "425.00"