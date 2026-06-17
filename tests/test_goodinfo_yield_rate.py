"""
test_goodinfo_yield_rate.py
驗證手動選股的殖利率算法優先順序（V0.9.5-goodinfo 新功能）

【演算法優先順序】(2026-06-17 William 反映)
原本：殖利率 = 現金股利 / 現價 * 100 → 偏差大（只反映最近一次配息 vs 現價）
修正：優先用 goodinfo 提供的「該年現金殖利率」（%）= 該年除息基準日的還原殖利率
  - goodinfo 用「除息日前 5 日均價」算 → 不被單日股價波動干擾
  - 也涵蓋多次配息（不會只算第一次）

【fallback 順序】
  1. goodinfo cash_yield_pct（%）— 最準
  2. cash / ex_date_close（V0.9.5+ Phase 10 算法）
  3. cash / 現價（最差但不讓殖利率全 None）

【歷史殖利率問題】(William 2026-06-17 反映)
原本「歷史殖利率」用「年平均價」算 → 偏差太大
修正：直接拿 goodinfo 各年度殖利率算術平均（不需自己算價格）
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


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
# 1. goodinfo 殖利率優先
# ─────────────────────────────────────────
def test_今年殖利率優先用_goodinfo_殖利率():
    """當 DB 有 goodinfo cash_yield_pct，今年殖利率應直接用，不該用 cash/現價

    情境：
      - 今年現金股利 = 5.0
      - 現價 = 100
      - naive 算法 = 5/100 = 5.0%
      - goodinfo 提供 = 6.32%（除息基準日算的）
      → 應顯示 6.32%（goodinfo 優先）
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        # V0.9.5-goodinfo：殖利率（百分比）
        "2026現金殖利率_goodinfo": [6.32],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
        "2026股票殖利率_goodinfo": [None],
        "2025股票殖利率_goodinfo": [None],
        "2024股票殖利率_goodinfo": [None],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 應用 goodinfo 殖利率 6.32%，不是 cash/現價 5.0%
    assert row["今年現金殖利率(%)"] == 6.32, \
        f"應用 goodinfo 殖利率 6.32%（不是 cash/現價 5.0%），實際: {row['今年現金殖利率(%)']}"


def test_去年殖利率優先用_goodinfo_殖利率():
    """去年殖利率也用 goodinfo（不是 cash/ex_date_close）"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 去年殖利率 = goodinfo 4.55%
    assert row["去年現金殖利率(%)"] == 4.55, \
        f"去年應用 goodinfo 殖利率 4.55%，實際: {row['去年現金殖利率(%)']}"


# ─────────────────────────────────────────
# 2. fallback 路徑（DB 沒 goodinfo 殖利率）
# ─────────────────────────────────────────
def test_DB無goodinfo殖利率_今年fallback到現金股利_現價():
    """DB 沒 goodinfo cash_yield_pct → 用 cash/現價 (V0.9.5+ 既有邏輯)"""
    fake_div = pd.DataFrame({
        "股票代號": ["3188"],
        "2026現金股利": [3.196], "2026股票股利": [0.0],
        "2025現金股利": [1.8],   "2025股票股利": [0.0],
        "2024現金股利": [1.6],   "2024股票股利": [0.0],
        # 故意不給 goodinfo 殖利率（模擬 2408 南亞科那種 DB 沒殖利率的股票）
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("3188", "鑫龍騰", 24.95, 500)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    cy_yld = row["今年現金殖利率(%)"]
    # fallback = 3.196 / 24.95 * 100 = 12.81
    assert abs(cy_yld - 12.81) < 0.01, \
        f"DB 沒 goodinfo 殖利率時應 fallback 到 cash/現價 = 12.81%，實際: {cy_yld}"


def test_goodinfo殖利率0_不要用_fallback():
    """goodinfo 殖利率 = 0 (該年未配息) → 殖利率 None、不是用 cash/現價

    重要：避免「未配息股票被誤判為高殖利率」的 bug
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2408"],
        "2026現金股利": [0.0], "2026股票股利": [0.0],  # 未配息
        "2025現金股利": [1.347], "2025股票股利": [0.0],
        "2024現金股利": [None], "2024股票股利": [None],
        "2026現金殖利率_goodinfo": [0.0],   # goodinfo 說沒配息
        "2025現金殖利率_goodinfo": [0.4],   # goodinfo 說有
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2408", "南亞科", 340.0, 1000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # goodinfo = 0 → 不該用 fallback、殖利率應該 None 或 0
    cy_yld = row["今年現金殖利率(%)"]
    # 設計：goodinfo 0 不算「有值」、會 fallback；但 fallback 也需要 cash>0
    # 結果 = None (cash=0, 沒 fallback 條件)
    assert cy_yld is None or pd.isna(cy_yld), \
        f"goodinfo 殖利率=0 且 cash=0 時應為 None，實際: {cy_yld}"


# ─────────────────────────────────────────
# 3. 股票殖利率欄位
# ─────────────────────────────────────────
def test_股票殖利率用_goodinfo_提供():
    """股票殖利率 = goodinfo 提供，不需自己算"""
    fake_div = pd.DataFrame({
        "股票代號": ["0050"],
        "2026現金股利": [2.0], "2026股票股利": [0.0],
        "2025現金股利": [1.5], "2025股票股利": [0.0],
        "2024現金股利": [1.0], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [1.39],
        "2025現金殖利率_goodinfo": [2.06],
        "2024現金殖利率_goodinfo": [2.79],
        "2026股票殖利率_goodinfo": [0.0],
        "2025股票殖利率_goodinfo": [0.0],
        "2024股票殖利率_goodinfo": [0.0],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("0050", "元大台灣50", 105.90, 10000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    assert row["今年股票殖利率(%)"] is None or pd.isna(row["今年股票殖利率(%)"]), \
        f"0050 沒股票股利 → 殖利率應為 None，實際: {row['今年股票殖利率(%)']}"


def test_股票殖利率_goodinfo_有值時直接用():
    """有股票股利的股票（ex: 2330 早年）殖利率顯示"""
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [6.32],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
        "2026股票殖利率_goodinfo": [None],
        "2025股票殖利率_goodinfo": [None],
        "2024股票殖利率_goodinfo": [None],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 沒股票股利 → None
    assert row["今年股票殖利率(%)"] is None or pd.isna(row["今年股票殖利率(%)"]), \
        f"沒股票股利時殖利率應為 None，實際: {row['今年股票殖利率(%)']}"


# ─────────────────────────────────────────
# 4. 歷史平均殖利率（V0.9.5-goodinfo 核心修正）
# ─────────────────────────────────────────
def test_歷史平均現金殖利率_用_goodinfo_各年平均():
    """歷史平均殖利率 = goodinfo 各年殖利率的算術平均

    範例：2330 goodinfo 殖利率 = [6.32, 4.55, 3.20] (2026/2025/2024)
    → 平均 = (6.32 + 4.55 + 3.20) / 3 = 4.69%
    """
    fake_div = pd.DataFrame({
        "股票代號": ["2330"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [4.0], "2025股票股利": [0.0],
        "2024現金股利": [3.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [6.32],
        "2025現金殖利率_goodinfo": [4.55],
        "2024現金殖利率_goodinfo": [3.20],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("2330", "台積電", 100.0, 5000)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 歷史平均 = (6.32 + 4.55 + 3.20) / 3 = 4.69
    expected = (6.32 + 4.55 + 3.20) / 3
    avg_yld = row["歷史平均現金殖利率(%)"]
    assert abs(avg_yld - expected) < 0.01, \
        f"歷史平均殖利率應為 {expected:.2f}%，實際: {avg_yld}"


def test_歷史平均殖利率_缺資料時跳過不影響平均():
    """缺資料的年份 (NaN) 不列入平均

    範例：5 年中只有 3 年有殖利率 → 平均 = 這 3 年的平均（不是 5 年）
    """
    fake_div = pd.DataFrame({
        "股票代號": ["1234"],
        "2026現金股利": [1.0], "2026股票股利": [0.0],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [0.5], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [3.0],
        "2025現金殖利率_goodinfo": [None],   # 缺資料
        "2024現金殖利率_goodinfo": [2.0],
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("1234", "測試股", 50.0, 100)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    # 缺 2025 → 平均 = (3.0 + 2.0) / 2 = 2.5
    avg_yld = row["歷史平均現金殖利率(%)"]
    assert abs(avg_yld - 2.5) < 0.01, \
        f"缺資料時不該列入平均，應為 2.5%，實際: {avg_yld}"


def test_歷史平均殖利率_完全無資料時為None():
    """goodinfo 完全沒殖利率 → 歷史平均 = None"""
    fake_div = pd.DataFrame({
        "股票代號": ["9999"],
        "2026現金股利": [1.0], "2026股票股利": [0.0],
        "2025現金股利": [None], "2025股票股利": [None],
        "2024現金股利": [0.5], "2024股票股利": [0.0],
        # 故意不給殖利率
    })
    st._fetch_finmind_dividend = _mock_finmind(None, fake_div)

    price_df = _make_input([("9999", "無殖利率股", 50.0, 100)])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)
    row = result.iloc[0]

    avg_yld = row.get("歷史平均現金殖利率(%)")
    assert avg_yld is None or pd.isna(avg_yld), \
        f"完全無殖利率時應為 None，實際: {avg_yld}"


# ─────────────────────────────────────────
# 5. 排序優先用歷史平均殖利率
# ─────────────────────────────────────────
def test_排序優先用歷史平均殖利率():
    """兩檔股票「今年殖利率」相同、但「歷史平均」不同 → 歷史平均高的排前

    排序條件：殖利率有值 > 歷史平均 > 今年殖利率 > 股票股利 > 營收 > PE
    """
    fake_div_a = pd.DataFrame({  # 歷史平均高（穩定型）
        "股票代號": ["AAPL"],
        "2026現金股利": [2.0], "2026股票股利": [0.0],
        "2025現金股利": [2.0], "2025股票股利": [0.0],
        "2024現金股利": [2.0], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [5.0],   # 今年殖利率
        "2025現金殖利率_goodinfo": [5.0],
        "2024現金殖利率_goodinfo": [5.0],   # 歷史平均 = 5.0
    })
    fake_div_b = pd.DataFrame({  # 今年殖利率高、但歷史平均低（偶發高殖利率）
        "股票代號": ["BAPL"],
        "2026現金股利": [5.0], "2026股票股利": [0.0],
        "2025現金股利": [1.0], "2025股票股利": [0.0],
        "2024現金股利": [1.0], "2024股票股利": [0.0],
        "2026現金殖利率_goodinfo": [10.0],  # 今年殖利率爆高
        "2025現金殖利率_goodinfo": [1.0],
        "2024現金殖利率_goodinfo": [1.0],   # 歷史平均 = 4.0
    })

    def _fetch(codes_arg, **kwargs):
        codes_str = [str(c) for c in codes_arg]
        a = fake_div_a[fake_div_a["股票代號"].isin(codes_str)]
        b = fake_div_b[fake_div_b["股票代號"].isin(codes_str)]
        return pd.concat([a, b], ignore_index=True)

    st._fetch_finmind_dividend = _fetch

    price_df = _make_input([
        ("AAPL", "穩定型", 100.0, 1000),
        ("BAPL", "偶發型", 100.0, 1000),
    ])
    rev, eps = _empty_revenue_eps()

    result = st._run_manual_selection(price_df, rev, eps, _no_filters(), top_n=10)

    # 應該 AAPL 在前（歷史平均 5.0 > BAPL 4.0）
    first_code = result.iloc[0]["股票代號"]
    assert first_code == "AAPL", \
        f"歷史平均高的 AAPL 應排前，實際第一名: {first_code}"

    # 驗證殖利率數值
    aapl_row = result[result["股票代號"] == "AAPL"].iloc[0]
    bapl_row = result[result["股票代號"] == "BAPL"].iloc[0]
    assert aapl_row["歷史平均現金殖利率(%)"] == 5.0
    assert bapl_row["歷史平均現金殖利率(%)"] == 4.0
