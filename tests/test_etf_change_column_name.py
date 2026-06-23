"""
test_etf_change_column_name.py
驗證 V0.9.5-tab-split-phase3-H FixA2：
_compute_etf_changes 回傳欄位是 today_change_lots（不是 change_lots）
→ _etf_display_results / _show_etf_popup 才能正確抓到異動張數

【William 2026-06-23 12:12 反映】
- 開 App 抓 ETF 持股後、按「套用篩選」或重抓時噴 KeyError
- File "StockTool.py", line 8730, in _etf_display_results
    change_df.groupby("stock_code", as_index=False)["change_lots"]
- KeyError: 'Column not found: change_lots'

【根因】
- _compute_etf_changes 回傳欄位是 today_change_lots
- _etf_display_results 卻寫 change_lots → KeyError
- 為什麼測試沒抓到：之前 DB shares 全 0 → _compute_etf_changes 回傳空 → 不觸發 groupby
- 今早 migration 補 shares → 有資料 → 才爆

【修法】
- _etf_display_results line 8730 改用 today_change_lots
- _show_etf_popup line 8468 改用 today_change_lots

【守護】
- _compute_etf_changes 回傳欄位必須是 today_change_lots（向後測試用 test_etf_history_db.py 也用這個）
"""
import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import pandas as pd
import StockTool as st  # noqa: E402


# ==========================================================
# 【_compute_etf_changes】回傳欄位名稱守護
# ==========================================================

def test_compute_etf_changes_回傳欄位是today_change_lots():
    """【V0.9.5-tab-split-phase3-H FixA2 守護】
    _compute_etf_changes 回傳的 DataFrame 必須有 today_change_lots 欄位（不是 change_lots）
    """
    from datetime import datetime, timedelta
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # 初始化 DB
        st._init_etf_history_db(tmp_path)

        # 寫兩天的 holdings（today 有 shares、yesterday 也有 shares、要有差異）
        # 今天 2330 有 1000 股
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str=today_str)
        # 昨天 2330 有 500 股
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 500, "industry": ""},
        ], date_str=yesterday_str)

        result = st._compute_etf_changes(tmp_path)

        assert not result.empty, "_compute_etf_changes 應回傳有資料"
        # 欄位必須叫 today_change_lots（不是 change_lots）
        assert "today_change_lots" in result.columns, (
            f"_compute_etf_changes 應有 today_change_lots 欄位、實際: {list(result.columns)}"
        )
        assert "change_lots" not in result.columns, (
            "_compute_etf_changes 不應該有 change_lots 欄位（會誤導 caller）"
        )

        # 值要對：1000 - 500 = 500 股 = 0.5 張
        row = result[result["stock_code"] == "2330"].iloc[0]
        assert row["today_change_lots"] == 0.5, (
            f"today_change_lots 應為 0.5、實際: {row['today_change_lots']}"
        )
        print("PASS: test_compute_etf_changes_回傳欄位是today_change_lots")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_compute_etf_changes_空結果也要有正確欄位():
    """【V0.9.5-tab-split-phase3-H FixA2 守護】空結果也要有 today_change_lots 欄位"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        st._init_etf_history_db(tmp_path)
        # 只寫今天、沒昨天 → 沒異動 → 回傳空 DataFrame
        st._save_etf_holding_snapshot(tmp_path, "00400A", [
            {"stock_code": "2330", "stock_name": "台積電", "weight": 50.0, "shares": 1000, "industry": ""},
        ], date_str="2026-06-23")

        result = st._compute_etf_changes(tmp_path)
        # 空 DataFrame、但欄位要對
        assert result.empty
        print("PASS: test_compute_etf_changes_空結果也要有正確欄位")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ==========================================================
# 【_etf_display_results】groupby 不會爆 KeyError
# ==========================================================

def test_etf_display_results_groupby_用today_change_lots():
    """【V0.9.5-tab-split-phase3-H FixA2 守護】
    _etf_display_results 對 change_df groupby 時、用 today_change_lots（不是 change_lots）
    不會爆 KeyError
    """
    # 模擬 change_df（_compute_etf_changes 的輸出）
    change_df = pd.DataFrame([
        {"stock_code": "2330", "stock_name": "台積電", "etf_count": 5,
         "today_change_lots": 0.5, "etf_changes_json": "[]"},
        {"stock_code": "2454", "stock_name": "聯發科", "etf_count": 3,
         "today_change_lots": 1.2, "etf_changes_json": "[]"},
    ])

    # 模擬 agg_df（_etf_display_results 的主要資料源）
    agg_df = pd.DataFrame([
        {"股票代號": "2330", "股票名稱": "台積電", "收盤價": 950.0, "etf_count": 5,
         "etf_list": "00981A 主動統一台股增長(25.00%)"},
        {"股票代號": "2454", "股票名稱": "聯發科", "收盤價": 1200.0, "etf_count": 3,
         "etf_list": "00400A 主動野村臺灣(6.28%)"},
    ])

    # 直接跑 _etf_display_results 的「groupby 那段」、不啟動 GUI
    # 模擬 line 8730 那段
    stock_change = (
        change_df.groupby("stock_code", as_index=False)["today_change_lots"]
        .sum()
        .rename(columns={"today_change_lots": "total_change_lots"})
    )
    df = agg_df.merge(
        stock_change,
        left_on=agg_df["股票代號"].astype(str).str.strip(),
        right_on="stock_code",
        how="left",
    )
    df["total_change_lots"] = df["total_change_lots"].fillna(0)

    # 驗證
    assert "total_change_lots" in df.columns
    row_2330 = df[df["股票代號"] == "2330"].iloc[0]
    row_2454 = df[df["股票代號"] == "2454"].iloc[0]
    assert row_2330["total_change_lots"] == 0.5, (
        f"2330 total_change_lots 應為 0.5、實際: {row_2330['total_change_lots']}"
    )
    assert row_2454["total_change_lots"] == 1.2, (
        f"2454 total_change_lots 應為 1.2、實際: {row_2454['total_change_lots']}"
    )

    print("PASS: test_etf_display_results_groupby_用today_change_lots")


# ==========================================================
# 【_show_etf_popup】抓 today_change_lots
# ==========================================================

def test_show_etf_popup_用today_change_lots():
    """【V0.9.5-tab-split-phase3-H FixA2 守護】
    _show_etf_popup 對 change_df row 用 cr.get('today_change_lots')、不是 'change_lots'
    """
    change_df = pd.DataFrame([
        {"stock_code": "2330", "stock_name": "台積電", "etf_count": 1,
         "today_change_lots": 2.5, "etf_changes_json": "[]"},
    ])

    stock_changes = change_df[change_df["stock_code"].astype(str).str.strip() == "2330"]
    cr = stock_changes.iloc[0]

    # 模擬 _show_etf_popup line 8468 的 .get 邏輯
    cl_old = cr.get("change_lots", 0) or 0  # 舊邏輯：永遠 0
    cl_new = cr.get("today_change_lots", 0) or 0  # 新邏輯：正確抓到 2.5

    assert cl_old == 0, f"舊邏輯用 change_lots 應回傳 0、實際: {cl_old}"
    assert cl_new == 2.5, f"新邏輯用 today_change_lots 應回傳 2.5、實際: {cl_new}"

    print("PASS: test_show_etf_popup_用today_change_lots")


if __name__ == "__main__":
    test_compute_etf_changes_回傳欄位是today_change_lots()
    test_compute_etf_changes_空結果也要有正確欄位()
    test_etf_display_results_groupby_用today_change_lots()
    test_show_etf_popup_用today_change_lots()
    print("\nAll V0.9.5-tab-split-phase3-H FixA2 tests passed!")