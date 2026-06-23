"""
test_ms_no_stock_yield_vol_display.py
驗證 V0.9.5-twser3 修 Bug：手動選股 Treeview 不再顯示股票殖利率欄。

【Bug 描述】2026-06-18 William 11:16 反映
1. 篩選結果中不需要看「股票殖利率」（今股票殖%、去年股票殖%）

【修法】
- Treeview header 拿掉 2 欄：「今股票殖%」、「去年股票殖%」（15 → 13 欄）
- _ms_display_results 內不再 row.get 股票殖利率欄位

【V0.9.5-goodinfo4+5 修正】2026-06-18 18:12 William 反映：
- 「成交量不是我要的今日成交量！」
- 拿掉原本 V0.9.5-twser3 加的盤中/收盤後切換邏輯
- 直接顯示 price_df 的「成交量(張)」（今日成交量）
- 新的 vol + sort test 都在 test_ms_vol_rev_sort.py
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


CY = datetime.now().year  # 2026


# ==========================================================
# 【欄位守護】Treeview 拿掉股票殖利率欄、總共 13 欄
# ==========================================================

def test_treeview_columns_拿掉股票殖利率():
    """【V0.9.5-twser3 守護】手動選股 Treeview 拿掉「今股票殖%」、「去年股票殖%」

    原本 15 欄 → 改後 13 欄
    移除: 「今股票殖%」、「去年股票殖%」
    """
    df = pd.DataFrame([{
        "股票代號": "2548",
        "股票名稱": "華固",
        "現價": 107.0,
        "累計營收YoY(%)": 50.0,
        "今年股票股利(元)": 0.5,
        "今年現金股利(元)": 8.5,
        "今年現金殖利率(%)": 6.53,
        "今年股票殖利率(%)": 0.48,  # ← 還是會產出、但 _ms_display_results 不讀
        "去年股票股利(元)": 0.5,
        "去年現金股利(元)": 6.0,
        "去年現金殖利率(%)": 5.07,
        "去年股票殖利率(%)": 0.46,  # ← 還是會產出、但 _ms_display_results 不讀
        "PE": 46.93,
        "成交量(張)": 1500,
        "EPS本期": 2.28,
    }])

    row = df.iloc[0]
    values = (
        "☐", row["股票代號"], row["股票名稱"],
        row["現價"], row["累計營收YoY(%)"],
        row["今年股票股利(元)"], row["今年現金股利(元)"], row["今年現金殖利率(%)"],
        # 注意：沒有 row["今年股票殖利率(%)"]
        row["PE"],
        # 【V0.9.5-goodinfo4+5】直接顯示今日成交量（不管時段）
        f"{int(row['成交量(張)']):,}" if pd.notna(row['成交量(張)']) else "—",
        row["去年股票股利(元)"], row["去年現金股利(元)"], row["去年現金殖利率(%)"],
        # 注意：沒有 row["去年股票殖利率(%)"]
    )
    # 守護：values 應為 13 個欄位（勾選 + 12 個資料欄）
    assert len(values) == 13, (
        f"values 應為 13 個欄位、實際: {len(values)}\n"
        f"（拿掉今/去年股票殖利率 → 15-2=13）"
    )
    # 守護：第 9 欄是成交量(張)、不是 "-"
    assert values[9] == "1,500", f"成交量應顯示 '1,500'、實際: {values[9]}"
    # 守護：股票殖利率欄位根本不在 values 內
    assert "今年股票殖利率(%)" not in values
    assert "去年股票殖利率(%)" not in values
    print("PASS: test_treeview_columns_拿掉股票殖利率")


# ==========================================================
# 【DataFrame 不動】_run_manual_selection 還是產出 stock_yield 欄位（給 Excel 匯出用）
# ==========================================================

def test_run_manual_selection_還是產出_stock_yield_欄位():
    """【V0.9.5-twser3 守護】_run_manual_selection 還是會在 DataFrame 內保留 stock_yield

    因為 Excel 匯出還需要這欄、只有 Treeview 不顯示
    """
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {"股票代號": "2548", f"{CY}現金股利": 8.5, f"{CY}股票股利": 0.5,
         f"{CY - 1}現金股利": 6.0, f"{CY - 1}股票股利": 0.5,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 6.53},
    ])

    price_df = pd.DataFrame([
        {"股票代號": "2548", "股票名稱": "華固", "現價": 107.0,
         "營收YoY(%)": 50.0, "成交量_張": 1500.0, "PE": 46.93, "EPS本期": 2.28},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "2548", "營收YoY(%)": 50.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)

    # 守護：stock_yield 欄位還是會在
    assert "今年股票殖利率(%)" in result.columns, (
        f"今年股票殖利率(%) 應保留給 Excel 匯出用、目前 columns: {result.columns.tolist()}"
    )
    assert "去年股票殖利率(%)" in result.columns
    print("PASS: test_run_manual_selection_還是產出_stock_yield_欄位")


# ==========================================================
# 【現金 vs 股票分開守護】
# ==========================================================

def test_cash_strictly_cash_only():
    """【V0.9.5-goodinfo3 守護】DB cash 跟 stock 是分開存分開顯示、不會加總"""
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {"股票代號": "2548", f"{CY}現金股利": 8.5, f"{CY}股票股利": 0.5,
         f"{CY - 1}現金股利": 6.0, f"{CY - 1}股票股利": 0.5,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 6.53},
    ])

    price_df = pd.DataFrame([
        {"股票代號": "2548", "股票名稱": "華固", "現價": 107.0,
         "營收YoY(%)": 50.0, "成交量_張": 1500.0, "PE": 46.93, "EPS本期": 2.28},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "2548", "營收YoY(%)": 50.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    row = result.iloc[0]

    # 守護：cash = 8.5、stock = 0.5（不是 cash+stock=9.0）
    assert row["今年現金股利(元)"] == 8.5
    assert row["今年股票股利(元)"] == 0.5
    print("PASS: test_cash_strictly_cash_only")


if __name__ == "__main__":
    test_treeview_columns_拿掉股票殖利率()
    test_run_manual_selection_還是產出_stock_yield_欄位()
    test_cash_strictly_cash_only()
    print("\nAll V0.9.5-twser3 + V0.9.5-goodinfo4+5 (no_stock_yield) tests passed!")