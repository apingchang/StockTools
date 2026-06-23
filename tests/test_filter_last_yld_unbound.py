"""
test_filter_last_yld_unbound.py
驗證 V0.9.5-alpha Phase 6 修 Bug：勾選「去年現金殖利率 ≥ X%」不應拋 UnboundLocalError。

【Bug 描述】2026-06-15 William 09:35 截圖
- 在「手動選股」勾選「去年現金殖利率 ≥ 0.1%」（含其他條件）
- 結果：整個手動選股崩潰、顯示「❌ 選股失敗：cannot access local variable 'data_score'」

【Bug 根因】
- Phase 4「B 邏輯」改了一半：line 1163-1166（今年現金殖利率）有改對、no-op + any_checked
- 但 line 1168-1175（去年現金殖利率）漏改、殘留舊版「data_score / pass_score 雙計分」邏輯
- 這兩個變數從未被初始化（函式內沒定義）、使用時 UnboundLocalError

【修法】
- 把 line 1168-1175 改成跟 line 1163-1166 一樣的 no-op（只設 any_checked=True）
- 排序階段用 _yld_has_data 自然處理「殖利率有資料 vs None」的排序

【為什麼要這個 test】
- 防線：避免未來 Phase 7+ 又把這個區塊寫成「死 code 計分邏輯」
- 行為驗證：確認「去年現金殖利率」是軟條件、不擋 mask
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


# 取得當前年份（測試用）
CY = datetime.now().year  # 2026


def _make_div_df(codes_with_div: dict) -> pd.DataFrame:
    """Mock _fetch_finmind_dividend 回傳的股利 df
    codes_with_div: {code: {"this_cash": float, "last_cash": float, ...}}
    """
    rows = []
    for code, div in codes_with_div.items():
        rows.append({
            "股票代號": code,
            f"{CY}現金股利": None,
            f"{CY}股票股利": None,
            f"{CY - 1}現金股利": div.get("this_cash"),
            f"{CY - 1}股票股利": div.get("this_stock", 0.0),
            f"{CY - 2}現金股利": div.get("last_cash"),
            f"{CY - 2}股票股利": div.get("last_stock", 0.0),
        })
    return pd.DataFrame(rows)


def _setup_mock(stock_divs: dict):
    """設定 _fetch_finmind_dividend mock"""
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: _make_div_df(stock_divs)


def _build_price_df(rows: list) -> pd.DataFrame:
    """建立 price_df 模擬 pipeline 傳入的股價資料"""
    return pd.DataFrame(rows)


# ==========================================================
# 【核心】修 Bug：不再 UnboundLocalError
# ==========================================================

def test_勾選去年現金殖利率_不拋UnboundLocalError():
    """【V0.9.5-alpha Phase 6 修 Bug】2026-06-15
    模擬 William 09:35 截圖情境：勾選「去年現金殖利率 ≥ 0.1%」
    修法前：UnboundLocalError（data_score 未定義）
    修法後：正常回傳結果
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
    # 關鍵：min_last_cash_yld 有值（這就是 09:35 崩潰的 trigger）
    filters = {"min_rev_yoy": 30.0, "min_last_cash_yld": 0.1}
    # 不應拋任何例外
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" not in result["股票代號"].values, \
        f"A2 不應納入（YoY 10 < 30 硬條件沒過），實際: {result['股票代號'].tolist()}"


# ==========================================================
# 【B 邏輯】去年現金殖利率是軟條件、不擋 mask
# ==========================================================

def test_去年殖利率軟條件_不擋mask():
    """【B 邏輯一致性】去年現金殖利率跟今年現金殖利率一樣是軟條件
    Case: A1 去年殖利率 5%（達標）vs A2 去年殖利率 None
    只要 YoY、PE、現價、成交量都過 → 兩者都納入
    """
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 2.5},   # 去年殖利率 5%
        "A2": {"this_cash": 1.0, "last_cash": None},  # 去年殖利率 None
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
    filters = {"min_rev_yoy": 30.0, "min_last_cash_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 兩檔都應納入（去年殖利率是軟條件）
    assert "A1" in result["股票代號"].values, f"A1 應納入，實際: {result['股票代號'].tolist()}"
    assert "A2" in result["股票代號"].values, \
        f"A2 應納入（去年殖利率軟不擋 mask），實際: {result['股票代號'].tolist()}"


def test_去年殖利率有值但未達標_不擋mask():
    """去年殖利率 0.5%（未達 1%）不擋 mask、只影響排序（排到殖利率達標後面）"""
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 2.5},   # 去年殖利率 5%（達標）
        "A2": {"this_cash": 1.0, "last_cash": 0.25},  # 去年殖利率 0.5%（未達標）
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
    filters = {"min_rev_yoy": 30.0, "min_last_cash_yld": 1.0}
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 兩檔都應納入
    assert "A1" in result["股票代號"].values
    assert "A2" in result["股票代號"].values


def test_只勾選去年現金殖利率_仍可運行():
    """【V0.9.5-alpha Phase 6 修 Bug 邊界 case】
    只有 min_last_cash_yld、沒其他硬條件 → 應回傳全部（any_checked 觸發）
    """
    _setup_mock({
        "A1": {"this_cash": 1.0, "last_cash": 0.5},
        "A2": {"this_cash": None, "last_cash": None},
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
    # 只有軟條件、無硬條件
    filters = {"min_last_cash_yld": 1.0}
    # 不應拋任何例外
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # 軟條件不擋 mask → 兩檔都納入
    assert len(result) == 2, f"只有軟條件時應保留全部 2 檔，實際: {len(result)}"
