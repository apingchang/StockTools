"""
test_ms_display_div_columns.py
驗證 V0.9.5+ Phase 8 修 Bug：手動選股 Treeview 正確顯示今年/去年股利金額。

【Bug 描述】2026-06-15 William 11:02 反映
- 「手動選股結果」看不到今年/去年現金股利金額、無法驗算殖利率是否正確
- 根因：_ms_display_results 內 row.get 完全沒讀「今年現金股利(元)」、「去年現金股利(元)」
  → 雖然 DataFrame 結果有這些欄位、但 Treeview 沒顯示
- 進一步：Treeview 沒有「今現金」、「去年現金」column

【修法】
- 加 2 個 column：「今現金」、「去年現金」
- _ms_display_results 加 row.get 讀「今年現金股利(元)」、「去年現金股利(元)」
- 注意 key 要帶「(元)」：_run_manual_selection final rename 把欄位改成「(元)」結尾

【為什麼要這個 test】
- 守護「欄位名稱正確性」：未來改欄位名時、test 會第一時間跳出來
- 守護「key 對應」：_ms_display_results 用的 key 必須跟 _run_manual_selection 產出的欄位一致
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


CY = datetime.now().year  # 2026


# ==========================================================
# 【整合測試】_run_manual_selection 產出的 df 真的包含「(元)」結尾的欄位
# ==========================================================

def test_run_manual_selection_產出含元後綴股利欄位():
    """【核心整合守護】_run_manual_selection 產出的 df 必須含「(元)」後綴欄位
    這是 _ms_display_results 跟 _run_manual_selection 的契約測試
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "2330",
            f"{CY}現金股利": None,
            f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 2.5,
            f"{CY - 1}股票股利": 0.5,
            f"{CY - 2}現金股利": 1.8,
            f"{CY - 2}股票股利": 0.0,
        }
    ])

    price_df = pd.DataFrame([
        {"股票代號": "2330", "股票名稱": "台積電", "現價": 60.0,
         "營收YoY(%)": 25.0, "成交量_張": 5000.0, "PE": 15.0, "EPS本期": 4.0},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "2330", "營收YoY(%)": 25.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)

    # 必有的欄位（_ms_display_results 會用，**帶「(元)」**）
    required_cols = [
        "今年現金股利(元)",       # ← V0.9.5+ Phase 8 新增顯示
        "今年股票股利(元)",       # ← 原本就有
        "今年現金殖利率(%)",
        "去年現金股利(元)",       # ← V0.9.5+ Phase 8 新增顯示
        "去年股票股利(元)",       # ← 原本就有
        "去年現金殖利率(%)",
    ]
    for col in required_cols:
        assert col in result.columns, \
            f"result 缺少必要欄位「{col}」、_ms_display_results 會顯示錯誤。實際欄位: {result.columns.tolist()}"

    # 驗證值正確
    row = result.iloc[0]
    assert row["今年現金股利(元)"] == 2.5
    assert row["今年股票股利(元)"] == 0.5
    assert row["去年現金股利(元)"] == 1.8
    assert row["去年股票股利(元)"] == 0.0
    # 殖利率 4.17% = 2.5 / 60.0 * 100
    assert abs(row["今年現金殖利率(%)"] - 4.17) < 0.01


# ==========================================================
# 【格式化測試】驗證「_ms_display_results 用的 key 對應正確」
# ==========================================================

def test_股票股利格式化_用對的key():
    """【V0.9.5+ Phase 8 守護】格式化用「今年股票股利(元)」（帶元）"""
    # 模擬 _run_manual_selection 產出的 row
    result_df = pd.DataFrame([{
        "今年股票股利(元)": 0.5,
        "今年現金股利(元)": 2.5,
        "今年現金殖利率(%)": 4.17,
        "去年股票股利(元)": 0.0,
        "去年現金股利(元)": 1.8,
        "去年現金殖利率(%)": 3.0,
    }])
    row = result_df.iloc[0]

    # 模擬 _ms_display_results 的格式化
    stock_div = row.get("今年股票股利(元)", "—")
    stock_str = f"{stock_div:.2f}" if isinstance(stock_div, float) and str(stock_div) not in ("nan", "None") else "—"
    assert stock_str == "0.50", f"應顯示「0.50」、實際: {stock_str}"


def test_現金股利格式化_用對的key():
    """【V0.9.5+ Phase 8 守護】現金股利也要格式化（這是原本缺失的）"""
    result_df = pd.DataFrame([{
        "今年股票股利(元)": 0.5,
        "今年現金股利(元)": 2.5,
        "今年現金殖利率(%)": 4.17,
        "去年股票股利(元)": 0.0,
        "去年現金股利(元)": 1.8,
        "去年現金殖利率(%)": 3.0,
    }])
    row = result_df.iloc[0]

    cash_div = row.get("今年現金股利(元)", "—")
    cash_div_str = f"{cash_div:.2f}" if isinstance(cash_div, float) and str(cash_div) not in ("nan", "None") else "—"
    assert cash_div_str == "2.50", f"應顯示「2.50」、實際: {cash_div_str}"

    last_cash_div = row.get("去年現金股利(元)", "—")
    last_cash_div_str = f"{last_cash_div:.2f}" if isinstance(last_cash_div, float) and str(last_cash_div) not in ("nan", "None") else "—"
    assert last_cash_div_str == "1.80", f"應顯示「1.80」、實際: {last_cash_div_str}"


def test_殖利率None時_格式化為橫線():
    """殖利率 None（DB 缺漏）時應顯示 "—"，不該是 0 或 NaN"""
    result_df = pd.DataFrame([{
        "今年股票股利(元)": None,
        "今年現金股利(元)": None,
        "今年現金殖利率(%)": None,
        "去年股票股利(元)": None,
        "去年現金股利(元)": None,
        "去年現金殖利率(%)": None,
    }])
    row = result_df.iloc[0]

    cash_yld = row.get("今年現金殖利率(%)")
    cash_str = f"{cash_yld:.2f}" if cash_yld and str(cash_yld) not in ("nan", "None") else "—"
    assert cash_str == "—", f"殖利率 None 應顯示「—」、實際: {cash_str}"

    # 股利金額 None 也應顯示 "—"
    cash_div = row.get("今年現金股利(元)", "—")
    cash_div_str = f"{cash_div:.2f}" if isinstance(cash_div, float) and str(cash_div) not in ("nan", "None") else "—"
    assert cash_div_str == "—", f"現金股利 None 應顯示「—」、實際: {cash_div_str}"


def test_股利為0時_現金殖利率應為None():
    """【邊界】現金股利 = 0（公司該年未配息）→ 現金殖利率應為 None、不該是 0%
    這是 _run_manual_selection 計算殖利率時的既有邏輯
    """
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {
            "股票代號": "9999",
            f"{CY}現金股利": None,
            f"{CY}股票股利": None,
            f"{CY - 1}現金股利": 0.0,    # 不配息
            f"{CY - 1}股票股利": 0.0,
            f"{CY - 2}現金股利": 1.0,
            f"{CY - 2}股票股利": 0.0,
        }
    ])

    price_df = pd.DataFrame([
        {"股票代號": "9999", "股票名稱": "測試", "現價": 50.0,
         "營收YoY(%)": 10.0, "成交量_張": 1000.0, "PE": 20.0, "EPS本期": 2.5},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "9999", "營收YoY(%)": 10.0}])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    row = result.iloc[0]

    # 現金股利是 0（合理）
    assert row["今年現金股利(元)"] == 0.0
    # 但殖利率應為 None（不是 0%）→ 避免誤導為「殖利率 0%」
    assert pd.isna(row["今年現金殖利率(%)"]), \
        f"現金股利 = 0 時殖利率應為 None，實際: {row['今年現金殖利率(%)']}"
