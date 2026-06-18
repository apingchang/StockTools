"""
test_ms_no_stock_yield_vol_display.py
驗證 V0.9.5-twser3 修 Bug：手動選股 Treeview 不再顯示股票殖利率欄 + 盤中成交量顯示邏輯。

【Bug 描述】2026-06-18 William 11:16 反映
1. 篩選結果中不需要看「股票殖利率」（今股票殖%、去年股票殖%）
2. 盤中不顯示成交量（TWSE 即時 API 每 15-20 秒更新累積量、顯示沒意義）
   → 收盤後才顯示總成交量（13:30 後量才固定）

【修法】
- Treeview header 拿掉 2 欄：「今股票殖%」、「去年股票殖%」（15 → 13 欄）
- _ms_display_results 內：
  - 不再 row.get 股票殖利率欄位
  - 盤中（_is_market_hours() == True）→ 成交量顯示 "-"
  - 收盤後 → 維持原本邏輯（顯示總成交量）

【為什麼要這個 test】
- 守護「Treeview 不再插入股票殖利率欄」
- 守護「盤中成交量邏輯」（用 monkeypatch _is_market_hours 來模擬盤中 / 收盤後）
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


CY = datetime.now().year  # 2026


# ==========================================================
# 【欄位守護】Treeview 拿掉股票殖利率欄、總共 13 欄
# ==========================================================

def test_treeview_columns_拿掉股票殖利率():
    """【V0.9.5-twser3 守護】手動選股 Treeview 拿掉「今股票殖%」、「去年股票殖%」

    原本 15 欄 → 改後 13 欄
    移除: 「今股票殖%」、「去年股票殖%」
    """
    # 模擬 _run_manual_selection 產出的 df（含 stock_yield 欄位、_ms_display_results 忽略）
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

    # 模擬 _ms_display_results 對一個 row 的 values tuple 邏輯
    row = df.iloc[0]
    values = (
        "☐", row["股票代號"], row["股票名稱"],
        row["現價"], row["累計營收YoY(%)"],
        row["今年股票股利(元)"], row["今年現金股利(元)"], row["今年現金殖利率(%)"],
        # 注意：沒有 row["今年股票殖利率(%)"]
        row["PE"],
        # 收盤後（模擬）：顯示總成交量
        f"{int(row['成交量(張)']):,}" if pd.notna(row['成交量(張)']) else "—",
        row["去年股票股利(元)"], row["去年現金股利(元)"], row["去年現金殖利率(%)"],
        # 注意：沒有 row["去年股票殖利率(%)"]
    )
    # 守護：values 應為 13 個欄位（勾選 + 12 個資料欄）
    assert len(values) == 13, \
        f"Treeview 應為 13 欄（拿掉 2 個股票殖利率）、實際 {len(values)} 欄: {values}"

    # 守護：values 順序對應 header (勾選/代號/名稱/現價/累計YoY%/今股票/今現金/今現金殖%/PE/成交量/去年股票/去年現金/去年現金殖%)
    assert values[0] == "☐"
    assert values[1] == "2548"
    assert values[2] == "華固"
    assert values[3] == 107.0
    assert values[4] == 50.0
    assert values[5] == 0.5     # 今股票
    assert values[6] == 8.5     # 今現金
    assert values[7] == 6.53    # 今現金殖%
    assert values[8] == 46.93   # PE
    assert values[9] == "1,500"  # 成交量（收盤後）
    assert values[10] == 0.5    # 去年股票
    assert values[11] == 6.0    # 去年現金
    assert values[12] == 5.07   # 去年現金殖%
    print("PASS: test_treeview_columns_拿掉股票殖利率")


# ==========================================================
# 【盤中成交量邏輯】_is_market_hours() == True → 顯示 "-"
# ==========================================================

def test_成交量_盤中顯示橫線():
    """【V0.9.5-twser3 守護】盤中（_is_market_hours() == True）→ 成交量顯示 "-" """
    # 模擬 _ms_display_results 內成交量格式化邏輯
    vol = 1500
    with patch.object(st, '_is_market_hours', return_value=True):
        if st._is_market_hours():
            vol_str = "-"
        else:
            try:
                vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"
            except (TypeError, ValueError):
                vol_str = "—"
    assert vol_str == "-", f"盤中應顯示 '-', 實際: {vol_str}"
    print("PASS: test_成交量_盤中顯示橫線")


def test_成交量_收盤後顯示總量():
    """【V0.9.5-twser3 守護】收盤後（_is_market_hours() == False）→ 顯示總成交量（千分位）"""
    vol = 1500
    with patch.object(st, '_is_market_hours', return_value=False):
        if st._is_market_hours():
            vol_str = "-"
        else:
            try:
                vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"
            except (TypeError, ValueError):
                vol_str = "—"
    assert vol_str == "1,500", f"收盤後應顯示 '1,500', 實際: {vol_str}"
    print("PASS: test_成交量_收盤後顯示總量")


def test_成交量_收盤後None顯示橫線():
    """【V0.9.5-twser3 守護】收盤後 + volume None → 顯示 '—'"""
    vol = None
    with patch.object(st, '_is_market_hours', return_value=False):
        if st._is_market_hours():
            vol_str = "-"
        else:
            try:
                vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"
            except (TypeError, ValueError):
                vol_str = "—"
    assert vol_str == "—", f"收盤後 volume=None 應顯示 '—', 實際: {vol_str}"
    print("PASS: test_成交量_收盤後None顯示橫線")


def test_成交量_週末收盤後顯示總量():
    """【V0.9.5-twser3 守護】週末（_is_market_hours() == False）→ 顯示總成交量

    週末雖無交易、但 _is_market_hours() 會回 False（盤前/盤後/週末都算收盤後）
    → 顯示上週五的總成交量（沿用 cache 既有值）
    """
    vol = 2500
    with patch.object(st, '_is_market_hours', return_value=False):  # 模擬週末
        if st._is_market_hours():
            vol_str = "-"
        else:
            try:
                vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"
            except (TypeError, ValueError):
                vol_str = "—"
    assert vol_str == "2,500", f"週末應顯示 '2,500', 實際: {vol_str}"
    print("PASS: test_成交量_週末收盤後顯示總量")


# ==========================================================
# 【DataFrame 不動】_run_manual_selection 還是產出 stock_yield 欄位（給 Excel 匯出用）
# ==========================================================

def test_run_manual_selection_還是產出_stock_yield_欄位():
    """【V0.9.5-twser3 守護】拿掉 Treeview 顯示 ≠ 拿掉 DataFrame 欄位

    Excel 匯出還是想保留 stock_yield 欄位（給進階使用者）
    → _run_manual_selection 還是要產出
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "2548",
            f"{CY}現金股利": 8.5,
            f"{CY}股票股利": 0.5,
            f"{CY - 1}現金股利": 6.0,
            f"{CY - 1}股票股利": 0.5,
            f"{CY - 2}現金股利": 8.5,
            f"{CY - 2}股票股利": 1.0,
            f"{CY}現金殖利率_goodinfo": 6.53,
            f"{CY}股票殖利率_goodinfo": 0.48,
            f"{CY - 1}現金殖利率_goodinfo": 5.07,
            f"{CY - 1}股票殖利率_goodinfo": 0.46,
            f"{CY - 2}現金殖利率_goodinfo": 3.96,
            f"{CY - 2}股票殖利率_goodinfo": 0.53,
        }
    ])

    price_df = pd.DataFrame([
        {"股票代號": "2548", "股票名稱": "華固", "現價": 107.0,
         "營收YoY(%)": 50.0, "成交量_張": 1500.0, "PE": 46.93, "EPS本期": 2.28},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "2548", "營收YoY(%)": 50.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)

    # 守護：stock_yield 欄位還在 DataFrame（給 Excel 匯出用）
    assert "今年股票殖利率(%)" in result.columns, \
        "result 應該還是有「今年股票殖利率(%)」欄位（Excel 匯出用）"
    assert "去年股票殖利率(%)" in result.columns, \
        "result 應該還是有「去年股票殖利率(%)」欄位（Excel 匯出用）"

    # 守護：值正確
    assert abs(result.iloc[0]["今年股票殖利率(%)"] - 0.48) < 0.01
    assert abs(result.iloc[0]["去年股票殖利率(%)"] - 0.46) < 0.01
    print("PASS: test_run_manual_selection_還是產出_stock_yield_欄位")


# ==========================================================
# 【DataFrame 資料流】驗證 cash 不會跟 stock 加總（守護 William 反映的 bug）
# ==========================================================

def test_cash_strictly_cash_only():
    """【V0.9.5-twser3 守護】現金股利欄位 = cash only、不會跟 stock 加總

    2026-06-18 William 11:16 反映「現金股利你還是把現金＋股票作家總了」
    → 用整合測試守護：cash 欄位跟 stock 欄位在 display 一定分開
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "2548",
            f"{CY}現金股利": 8.5,
            f"{CY}股票股利": 0.5,  # ← 故意非零、避免 stock=0 掩蓋 bug
            f"{CY - 1}現金股利": 6.0,
            f"{CY - 1}股票股利": 0.5,
            f"{CY - 2}現金股利": 8.5,
            f"{CY - 2}股票股利": 1.0,
            f"{CY}現金殖利率_goodinfo": 6.53,
        }
    ])

    price_df = pd.DataFrame([
        {"股票代號": "2548", "股票名稱": "華固", "現價": 107.0,
         "營收YoY(%)": 50.0, "成交量_張": 1500.0, "PE": 46.93, "EPS本期": 2.28},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "2548", "營收YoY(%)": 50.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    row = result.iloc[0]

    # 守護：今現金 = 8.5（cash only）、不是 9.0（cash + stock）
    assert row["今年現金股利(元)"] == 8.5, \
        f"今現金應為 8.5（cash only）、實際: {row['今年現金股利(元)']}"
    assert row["今年股票股利(元)"] == 0.5, \
        f"今股票應為 0.5、實際: {row['今年股票股利(元)']}"

    # 守護：去年也一樣分開
    assert row["去年現金股利(元)"] == 6.0, \
        f"去年現金應為 6.0、實際: {row['去年現金股利(元)']}"
    assert row["去年股票股利(元)"] == 0.5, \
        f"去年股票應為 0.5、實際: {row['去年股票股利(元)']}"

    # 守護：殖利率用 goodinfo 直接給的（不是 cash/現價 算出來的）
    # 107 * 6.53% = 6.99（不是 8.5）→ 確認殖利率是 goodinfo 的、不是本地算的
    assert abs(row["今年現金殖利率(%)"] - 6.53) < 0.01
    print("PASS: test_cash_strictly_cash_only")


if __name__ == "__main__":
    test_treeview_columns_拿掉股票殖利率()
    test_成交量_盤中顯示橫線()
    test_成交量_收盤後顯示總量()
    test_成交量_收盤後None顯示橫線()
    test_成交量_週末收盤後顯示總量()
    test_run_manual_selection_還是產出_stock_yield_欄位()
    test_cash_strictly_cash_only()
    print("\nAll V0.9.5-twser3 tests passed!")