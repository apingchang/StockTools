"""
test_data_date_column.py
驗證 V0.9.5-cache-info：「資料日期」欄位邏輯

【背景】William 2026-06-19 14:17 設計：
- 「App 隨時要有最新的收盤個股資訊（cache）」
- 「篩選結果中增加一個欄位顯示個股資料所參考的最新日期」

【設計】
- fetch_prices 加 data_date 欄位（從 TWSE/TPEx Date 民國年轉西元）
- 民國年 1150618 → 西元 2026-06-18
- _run_manual_selection merge 時保留 data_date
- _ms_display_results 在 Treeview 最右邊加「資料日期」欄位
- 邊界：API 沒 Date 欄位 → data_date 為空字串（不 crash）

【為什麼要獨立 test 守護】
- 民國年轉西元是常見出錯點（邊界：年份數字、月份數字、日期數字）
- 萬一未來 TWSE/TPEx 改欄位名 → 這個 test 會第一時間跳出
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import requests

import StockTool as st  # noqa: E402


def _mock_session_factory(twse_data=None, tpex_data=None):
    """產生 mock session：TWSE / TPEx 回傳指定資料"""
    twse_data = twse_data or []
    tpex_data = tpex_data or []
    s = requests.Session()

    def mock_get(url, **kw):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "STOCK_DAY_ALL" in url:
            m.json = lambda: twse_data
        else:
            m.json = lambda: tpex_data
        return m

    s.get = mock_get
    return s


# ==========================================================
# 【核心】民國年 → 西元 轉換
# ==========================================================

def test_roc_to_ad_正常日期():
    """【核心】民國 115 年 6 月 18 日 → 西元 2026-06-18"""
    # 透過 fetch_prices 的 mock 來驗
    twse = [
        {"Date": "1150618", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "950.0", "Change": "+5.0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "data_date" in df.columns, f"price_df 應有 data_date 欄位、實際: {df.columns.tolist()}"
    assert df.iloc[0]["data_date"] == "2026-06-18", (
        f"民國 1150618 應轉成 2026-06-18、實際: {df.iloc[0]['data_date']}"
    )


def test_roc_to_ad_民國100年():
    """【邊界】民國 100 年 → 西元 2011（測試年數邊界）"""
    # 民國 100 = 2011（20 世紀初期）
    twse = [
        {"Date": "1000101", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "100.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == "2011-01-01", (
        f"民國 1000101 應轉成 2011-01-01、實際: {df.iloc[0]['data_date']}"
    )


def test_roc_to_ad_民國114年():
    """【邊界】民國 114 年 → 西元 2025（測試常見年份）"""
    twse = [
        {"Date": "1141231", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "100.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == "2025-12-31"


def test_roc_to_ad_格式錯誤回空字串():
    """【邊界】Date 格式不對 → data_date 為空字串（不 crash）"""
    twse = [
        {"Date": "bad_format", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "100.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == "", (
        f"錯誤格式應回空字串、實際: '{df.iloc[0]['data_date']}'"
    )


# ==========================================================
# 【API 邊界】Date 欄位不存在
# ==========================================================

def test_API無Date欄位_不crash_data_date空字串():
    """【邊界】若 TWSE API 沒 Date 欄位 → fetch_prices 不 crash、data_date 空"""
    twse = [
        # 故意不放 Date 欄位
        {"Code": "2330", "Name": "台積電", "ClosingPrice": "950.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "data_date" in df.columns
    assert df.iloc[0]["data_date"] == "", "Date 欄位不存在時應回空字串、不 crash"


# ==========================================================
# 【整合】TWSE + TPEx 都有 data_date
# ==========================================================

def test_TPEx股也帶data_date():
    """【整合】TPEx 股（6547）也要有 data_date"""
    twse = [
        {"Date": "1150618", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "950.0", "Change": "0"},
    ]
    tpex = [
        {"Date": "1150618", "SecuritiesCompanyCode": "6547",
         "CompanyName": "高端", "Close": "15.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse, tpex_data=tpex)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert len(df) == 2
    row_2330 = df[df["股票代號"] == "2330"].iloc[0]
    row_6547 = df[df["股票代號"] == "6547"].iloc[0]
    assert row_2330["data_date"] == "2026-06-18"
    assert row_6547["data_date"] == "2026-06-18"


# ==========================================================
# 【整合】_run_manual_selection 保留 data_date
# ==========================================================

def test_run_manual_selection_保留data_date():
    """【整合】_run_manual_selection merge 後 data_date 仍在 result"""
    price_df = st.pd.DataFrame([
        {"股票代號": "2330", "公司名稱_來源": "台積電", "股價": 950.0,
         "漲跌": 5.0, "data_date": "2026-06-18"},
        {"股票代號": "3188", "公司名稱_來源": "鑫龍騰", "股價": 32.0,
         "漲跌": 0.5, "data_date": "2026-06-17"},
    ])
    revenue_df = st.pd.DataFrame([
        {"股票代號": "2330", "年月": 202605, "當月營收(億元)": 2000.0, "營收YoY(%)": 30.0},
        {"股票代號": "3188", "年月": 202605, "當月營收(億元)": 5.0, "營收YoY(%)": 20.0},
    ])
    eps_df = st.pd.DataFrame()  # 沒 EPS、不影響 data_date
    result = st._run_manual_selection(
        price_df, revenue_df, eps_df,
        filters={"rev_yoy": None},  # 不篩選、全部都留
        top_n=500,
    )
    assert "data_date" in result.columns, (
        f"_run_manual_selection 結果應保留 data_date 欄位、實際: {result.columns.tolist()}"
    )
    row_2330 = result[result["股票代號"] == "2330"].iloc[0]
    row_3188 = result[result["股票代號"] == "3188"].iloc[0]
    assert row_2330["data_date"] == "2026-06-18"
    assert row_3188["data_date"] == "2026-06-17"


if __name__ == "__main__":
    test_roc_to_ad_正常日期()
    print("✅ test_roc_to_ad_正常日期")
    test_roc_to_ad_民國100年()
    print("✅ test_roc_to_ad_民國100年")
    test_roc_to_ad_民國114年()
    print("✅ test_roc_to_ad_民國114年")
    test_roc_to_ad_格式錯誤回空字串()
    print("✅ test_roc_to_ad_格式錯誤回空字串")
    test_API無Date欄位_不crash_data_date空字串()
    print("✅ test_API無Date欄位_不crash_data_date空字串")
    test_TPEx股也帶data_date()
    print("✅ test_TPEx股也帶data_date")
    test_run_manual_selection_保留data_date()
    print("✅ test_run_manual_selection_保留data_date")
    print("\n🎉 All data_date tests passed!")