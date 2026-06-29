"""
test_filter_last_yld_unbound.py
驗證「去年現金殖利率 ≥ X%」不應拋 UnboundLocalError（V0.9.5-alpha Phase 6 修 Bug）。

【V1.1-yld-hard-filter】2026-06-29 21:59 William 反映、殖利率從軟改硬。

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

    【V1.1-yld-hard-filter】2026-06-29 21:59
    - scoring line 220 改用 goodinfo 算「去年現金殖利率(%)」(`f"{CY-1}現金殖利率_goodinfo"`)
    - mock 必須加 `last_yld` 欄位才會讓殖利率算出來
    - this_cash → f"{CY-1}現金股利"（「去年現金股利」= cy-1）
    - last_cash → f"{CY-2}現金股利」（前年）
    """
    rows = []
    for code, div in codes_with_div.items():
        this_cash = div.get("this_cash")
        last_cash = div.get("last_cash")
        # 【V1.1-yld-hard-filter】去年殖利率 = goodinfo 提供、不是 cash/現價
        # mock last_yld 讓殖利率真的有值（測試需要）
        last_yld = div.get("last_yld")
        if last_yld is None and last_cash is not None:
            # 沒指定 last_yld、但有 last_cash → 自動算（用 mock 用的 price=50 算）
            # 但這樣 mock 寫法跟 goodinfo 實際欄位名對應才好
            last_yld = (last_cash / 50.0) * 100
        rows.append({
            "股票代號": code,
            f"{CY}現金股利": None,
            f"{CY}股票股利": None,
            f"{CY}現金殖利率_goodinfo": None,
            f"{CY}股票殖利率_goodinfo": None,
            f"{CY - 1}現金股利": this_cash,
            f"{CY - 1}股票股利": div.get("this_stock", 0.0),
            f"{CY - 1}現金殖利率_goodinfo": last_yld,
            f"{CY - 1}股票殖利率_goodinfo": None,
            f"{CY - 2}現金股利": last_cash,
            f"{CY - 2}股票股利": div.get("last_stock", 0.0),
            f"{CY - 2}現金殖利率_goodinfo": None,
            f"{CY - 2}股票殖利率_goodinfo": None,
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

def test_去年殖利率硬條件_排除_v1_1_yld_hard_filter():
    """【V1.1-yld-hard-filter】去年現金殖利率 = 硬 AND

    Case: A1 去年殖利率 5%（達標）vs A2 去年殖利率 None
    期望：A1 納入、A2 排除
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
    # V1.1-yld-hard-filter：A1 去年殖利率 5% 達標 → 納入；A2 去年殖利率 None → 排除
    assert "A1" in result["股票代號"].values, f"A1 應納入（殖利率達標），實際: {result['股票代號'].tolist()}"
    assert "A2" not in result["股票代號"].values, f"A2 應排除（殖利率 None 硬過濾），實際: {result['股票代號'].tolist()}"


def test_去年殖利率有值但未達標_排除_v1_1_yld_hard_filter():
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
    # V1.1-yld-hard-filter：A1 去年殖利率 5% 達標 → 納入；A2 去年殖利率 0.5% 未達標 → 排除
    assert "A1" in result["股票代號"].values, f"A1 應納入（殖利率達標），實際: {result['股票代號'].tolist()}"
    assert "A2" not in result["股票代號"].values, f"A2 應排除（殖利率未達標），實際: {result['股票代號'].tolist()}"


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
    # 只有去年現金殖利率勾、其他硬條件都沒勾
    filters = {"min_last_cash_yld": 1.0}
    # 不應拋任何例外
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), filters, top_n=10)
    # V1.1-yld-hard-filter：A1 殖利率 1.0% 達標 → 納入；A2 殖利率 None → 排除
    assert len(result) == 1, f"預期 1 筆（A1 達標、A2 殖利率 None 排除），實際: {result['股票代號'].tolist() if len(result) > 0 else '空'}"
    assert "A1" in result["股票代號"].values
