"""
test_goodinfo_yield_rate.py
驗證手動選股的殖利率算法（V0.9.5-goodinfo3）

【演算法】（William 2026-06-17 11:10 / 12:03 反映後定版）
殖利率 100% 直接用 goodinfo 提供的值、不計算、不 fallback
  - goodinfo 用「除息日前 5 日均價」算 → 比任何 fallback 都準
  - cash=0 也要用 goodinfo 值（ex: 5386 2026 cash=0 但 goodinfo cash_yield=0.30%）
  - goodinfo 殖利率 = 0 = 該年未配息 → 直接顯示 0%（不是 None）
  - goodinfo 殖利率 = None → 殖利率 None

【拿掉的東西】（William 2026-06-17 12:03 反映）
1. 10Y 平均殖利率欄位（V0.9.5-goodinfo3 拿掉）
2. fallback 路徑：cash/現價、cash/ex_date_close、現價（V0.9.5-goodinfo3 拿掉）
3. cash=0 → continue 的舊邏輯（V0.9.5-goodinfo3 修掉）

【舊版演算法】（V0.9.5-goodinfo2，2026-06-17 11:10 已廢棄）
原本：殖利率 = 現金股利 / 現價 * 100 → 偏差大
V0.9.5-goodinfo2：優先 goodinfo，fallback 到 cash/現價（後來也廢掉）
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


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
# 1. 殖利率 100% 用 goodinfo
# ─────────────────────────────────────────
def test_今年殖利率100用goodinfo_不走fallback():
    """DB 有 goodinfo 殖利率 → 直接用，不算 cash/現價"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [6.32],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # goodinfo 6.32，不是 fallback 算的 5.0%
    assert row["今年現金殖利率(%)"] == 6.32, \
        f"應直接用 goodinfo 6.32，實際: {row['今年現金殖利率(%)']}"


def test_去年殖利率100用goodinfo_不走cash_exDateClose_fallback():
    """去年殖利率：直接用 goodinfo、不用 cash/ex_date_close 或 cash/現價 fallback"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2025現金殖利率_goodinfo": [4.55],
        "2025除息日": ["2026-08-15"],
        "2025除息日收盤價": [1200.0],   # DB 有 ex_date_close
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 直接用 goodinfo 4.55，不是 ex_date_close 算的 0.33%（4/1200）也不是現價算的 4%
    assert row["去年現金殖利率(%)"] == 4.55, \
        f"應直接用 goodinfo 4.55，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 2. cash=0 但 goodinfo 有值 → 殖利率用 goodinfo
# ─────────────────────────────────────────
def test_cash0_但goodinfo有值_殖利率直接用goodinfo():
    """5386 情境：cash=0 但 goodinfo cash_yield=0.30% → 殖利率 0.30%

    V0.9.5-goodinfo3 修：原本 cash=0 → continue → 殖利率 None（錯）
    """
    fake_div = pd.DataFrame({
        "股票代號": ["5386"],
        "2026現金股利": [0.0], "2026股票股利": [5.0],   # cash=0 但有 stock
        "2025現金股利": [0.0], "2025股票股利": [1.378],
        "2024現金股利": [0.0], "2024股票股利": [0.9],
        "2026現金殖利率_goodinfo": [0.30],   # ← 關鍵：cash=0 但 yield 有值
        "2025現金殖利率_goodinfo": [0.76],
        "2024現金殖利率_goodinfo": [0.48],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("5386", "捷敏", 499.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金殖利率(%)"] == 0.30, \
        f"cash=0 但 goodinfo 0.30 → 應顯示 0.30，實際: {row['今年現金殖利率(%)']}"
    assert row["去年現金殖利率(%)"] == 0.76, \
        f"去年 cash=0 但 goodinfo 0.76 → 應顯示 0.76，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 3. goodinfo 殖利率 = 0 = 未配息 → 直接顯示 0
# ─────────────────────────────────────────
def test_goodinfo殖利率0_未配息_顯示0():
    """goodinfo 殖利率 = 0 = 該年未配息 → 殖利率 0%（合理、不是 None）"""
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [0.0], "2026股票股利": [0.0],
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        "2026現金殖利率_goodinfo": [0.0],   # 該年未配息 = 0%
        "2025現金殖利率_goodinfo": [0.4],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金殖利率(%)"] == 0.0, \
        f"goodinfo 殖利率=0 應顯示 0%，實際: {row['今年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 4. goodinfo 殖利率 None → 殖利率 None
# ─────────────────────────────────────────
def test_完全無goodinfo殖利率_殖利率None():
    """DB 沒 goodinfo 殖利率（沒匯入） → 殖利率 None（無 fallback）"""
    fake_div = pd.DataFrame({
        "股票代號": ["9999"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        # 故意不給殖利率
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("9999", "新上市股", 100.0, 500)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # V0.9.5-goodinfo3：沒 fallback 了 → 殖利率 None
    assert row["今年現金殖利率(%)"] is None or pd.isna(row["今年現金殖利率(%)"]), \
        f"無 goodinfo 殖利率應為 None，實際: {row['今年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 5. 股票殖利率直接用 goodinfo
# ─────────────────────────────────────────
def test_今年股票殖利率用goodinfo():
    """股票殖利率直接用 goodinfo（ex: 5386 2026 stock=5, share_yield=1.0）"""
    fake_div = pd.DataFrame({
        "股票代號": ["5386"],
        "2026現金股利": [0.0], "2026股票股利": [5.0],
        "2025現金股利": [0.0], "2025股票股利": [1.378],
        "2024現金股利": [0.0], "2024股票股利": [0.9],
        "2026股票殖利率_goodinfo": [1.0],
        "2025股票殖利率_goodinfo": [1.78],
        "2024股票殖利率_goodinfo": [1.07],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("5386", "捷敏", 499.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年股票殖利率(%)"] == 1.0, \
        f"應用 goodinfo 1.0，實際: {row['今年股票殖利率(%)']}"
    assert row["去年股票殖利率(%)"] == 1.78, \
        f"應用 goodinfo 1.78，實際: {row['去年股票殖利率(%)']}"


# ─────────────────────────────────────────
# 6. 10Y 平均殖利率欄位已拿掉
# ─────────────────────────────────────────
def test_10Y平均殖利率欄位已拿掉():
    """V0.9.5-goodinfo3：William 說不需要 → 欄位拿掉"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [6.32],
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
# 7. 真實情境：3231 緯創（去年現金殖利率 3.3、不是 fallback 算的 2.4）
# ─────────────────────────────────────────
def test_3231_緯創_去年殖利率直接用goodinfo():
    """3231 去年現金殖利率 = goodinfo 3.3%（不是 cash/現價 fallback 算的 2.4%）"""
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

    # 直接用 goodinfo 3.3，不是 fallback 算的 3.799/158*100 = 2.40
    assert row["去年現金殖利率(%)"] == 3.3, \
        f"去年殖利率應用 goodinfo 3.3，不是 fallback 2.4，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 8. 真實情境：5386 捷敏（cash=0 但 goodinfo 有殖利率值）
# ─────────────────────────────────────────
def test_5386_捷敏_殖利率用goodinfo_不為None():
    """5386 cash=0 但 goodinfo cash_yield=0.30% / 0.76% → 殖利率照顯示"""
    fake_div = pd.DataFrame({
        "股票代號": ["5386"],
        "2026現金股利": [0.0], "2026股票股利": [5.0],   # cash=0
        "2025現金股利": [0.0], "2025股票股利": [1.378],
        "2024現金股利": [0.0], "2024股票股利": [0.9],
        "2026現金殖利率_goodinfo": [0.30],
        "2025現金殖利率_goodinfo": [0.76],
        "2024現金殖利率_goodinfo": [0.48],
        "2026股票殖利率_goodinfo": [1.0],
        "2025股票殖利率_goodinfo": [1.78],
        "2024股票殖利率_goodinfo": [1.07],
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("5386", "捷敏", 499.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年現金殖利率(%)"] == 0.30
    assert row["去年現金殖利率(%)"] == 0.76
    assert row["今年股票殖利率(%)"] == 1.0
    assert row["去年股票殖利率(%)"] == 1.78


# ─────────────────────────────────────────
# 9. V0.9.5-goodinfo4 修：殖利率 0.0 不該被當 None
# ─────────────────────────────────────────
def test_殖利率0_0_不該當None_應為0_00():
    """V0.9.5-goodinfo4 修 Bug：William 2026-06-17 反映

    原本 _ms_display_results 用 `if cash_yld and ...` truthy 判斷
    → 0.0 是 falsy、被當 None 顯示 '—'
    → 5386 現金殖利率 0.3 會被當 0.0 顯示 '—' 看起來像無資料

    修法：殖利率 = 0.0 是合法值（該年未配息 / goodinfo 算 0%）、要顯示 '0.00'
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [0.0], "2026股票股利": [0.0],   # 沒配息
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        # goodinfo 殖利率 = 0（該年未配息）
        "2026現金殖利率_goodinfo": [0.0],   # ← 關鍵
    })
    st_fetch_market._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 殖利率 = 0.0（該年未配息）、不是 None
    val = row["今年現金殖利率(%)"]
    assert val == 0.0, f"殖利率 0.0 應保留為 0.0，實際: {val}"


def test_殖利率0_30_不該顯示破折號():
    """V0.9.5-goodinfo4：5386 現金殖利率 0.3 場景

    模擬顯示格式化：殖利率 0.3 在舊版 if cash_yld and ... 邏輯下
    因為 0.3 是 truthy → 會正確顯示 '0.30'
    但 0.0 會被當 None → 顯示 '—'
    """
    # 這是 _ms_display_results 的格式化 helper 測試
    from StockTool import _fmt_float
    assert _fmt_float(0.0) == "0.00", f"0.0 應顯示 '0.00'，實際: '{_fmt_float(0.0)}'"
    assert _fmt_float(0.3) == "0.30", f"0.3 應顯示 '0.30'，實際: '{_fmt_float(0.3)}'"
    assert _fmt_float(None) == "—", f"None 應顯示 '—'"
    assert _fmt_float(float("nan")) == "—", f"NaN 應顯示 '—'"
    assert _fmt_float(425.0) == "425.00"
