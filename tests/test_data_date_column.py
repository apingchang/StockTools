"""
test_data_date_column.py
驗證 V0.9.5-info2：「資料日期」欄位邏輯

【V0.9.5-info2 重設計】2026-06-26 20:43 William 反映：
「資料時間為當下時間、若在收盤時間這裡是最後收盤價、若盤中這裡是盤中即時價」

【舊版設計】（V0.9.5-cache-info、已廢棄）
- data_date = 個股最後交易日（從 TWSE STOCK_DAY_ALL / TPEx Date 欄位抓）
- 問題：TWSE 收盤後 API 不立刻 flush、今日個股的 data_date 會停在昨日
- 結果：data_date 混雜 6/25 / 6/26、使用者困惑

【新設計】
- data_date = 抓取時點對應的市場日（= today、抓的當下）
- 不論個股是否真有成交、data_date 統一顯示 today
- 已廢棄的「個股最後交易日」概念：可從「收盤價是不是昨日」判斷、若 STOCK_DAY_ALL 還沒 flush
  → 股價是昨日收盤、但 data_date 顯示 today → 在 status bar 提示「TWSE API 尚未更新今日」

【為什麼要獨立 test 守護】
- 「資料日期一律 = today」是設計決策、未來不能改回「個股最後交易日」（會被這個 test 擋下）
- 邊界：fetch_prices 必須有 data_date 欄位、且 = today
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
# 【核心】V0.9.5-info2 新邏輯：data_date 一律 = today
# ==========================================================

def test_data_date_一律是today_不管API給什麼Date():
    """【V0.9.5-info2 核心】data_date 一律 = today、不讀 STOCK_DAY_ALL Date 欄位

    即使 API 給的 Date 是昨日（例：1150625）、data_date 仍是 today
    """
    from datetime import datetime as _dt
    today_ad = _dt.now().strftime("%Y-%m-%d")
    twse = [
        {"Date": "1150625", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "2390.0", "Change": "+0.0"},   # ← API 給昨日
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "data_date" in df.columns
    assert df.iloc[0]["data_date"] == today_ad, (
        f"data_date 應一律 = today ({today_ad})、實際: {df.iloc[0]['data_date']}"
    )


def test_data_date_無Date欄位也_是today():
    """【邊界】API 沒 Date 欄位 → data_date 仍是 today（不是空字串）"""
    from datetime import datetime as _dt
    today_ad = _dt.now().strftime("%Y-%m-%d")
    twse = [
        # 故意不放 Date 欄位
        {"Code": "2330", "Name": "台積電", "ClosingPrice": "950.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "data_date" in df.columns
    assert df.iloc[0]["data_date"] == today_ad


def test_data_date_TPEx也_是today():
    """【整合】TPEx 股也要 data_date = today"""
    from datetime import datetime as _dt
    today_ad = _dt.now().strftime("%Y-%m-%d")
    twse = [
        {"Date": "1150625", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "2390.0", "Change": "0"},
    ]
    tpex = [
        {"Date": "1150625", "SecuritiesCompanyCode": "6547",
         "CompanyName": "高端", "Close": "15.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse, tpex_data=tpex)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert len(df) == 2
    assert df[df["股票代號"] == "2330"].iloc[0]["data_date"] == today_ad
    assert df[df["股票代號"] == "6547"].iloc[0]["data_date"] == today_ad


# ==========================================================
# 【整合】_run_manual_selection 保留 data_date
# ==========================================================

def test_run_manual_selection_保留data_date():
    """【整合】_run_manual_selection merge 後 data_date 仍在 result"""
    price_df = st.pd.DataFrame([
        {"股票代號": "2330", "公司名稱_來源": "台積電", "股價": 950.0,
         "漲跌": 5.0, "data_date": "2026-06-26"},
        {"股票代號": "3188", "公司名稱_來源": "鑫龍騰", "股價": 32.0,
         "漲跌": 0.5, "data_date": "2026-06-26"},
    ])
    revenue_df = st.pd.DataFrame([
        {"股票代號": "2330", "年月": 202605, "當月營收(億元)": 2000.0, "營收YoY(%)": 30.0},
        {"股票代號": "3188", "年月": 202605, "當月營收(億元)": 5.0, "營收YoY(%)": 20.0},
    ])
    eps_df = st.pd.DataFrame()  # 沒 EPS、不影響 data_date
    result = st._run_manual_selection(
        price_df, revenue_df, eps_df,
        filters={"rev_yoy": None},
        top_n=500,
    )
    assert "data_date" in result.columns, (
        f"_run_manual_selection 結果應保留 data_date 欄位、實際: {result.columns.tolist()}"
    )
    row_2330 = result[result["股票代號"] == "2330"].iloc[0]
    row_3188 = result[result["股票代號"] == "3188"].iloc[0]
    assert row_2330["data_date"] == "2026-06-26"
    assert row_3188["data_date"] == "2026-06-26"


# ==========================================================
# 【V0.9.5-cache-vol】fetch_prices 抓成交量（V0.9.5-info2 仍保留）
# ==========================================================

def test_fetch_prices_TWSE有成交量_轉成張():
    """【V0.9.5-cache-vol】TWSE TradeVolume 25000000 股 → 25000 張"""
    twse = [
        {"Date": "1150618", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "950.0", "Change": "+5.0", "TradeVolume": "25000000"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "成交量_張" in df.columns
    assert df.iloc[0]["成交量_張"] == 25000.0, (
        f"TradeVolume=25000000 應為 25000 張、實際: {df.iloc[0]['成交量_張']}"
    )


def test_fetch_prices_TPEx有成交量_轉成張():
    """【V0.9.5-cache-vol】TPEx TradingShares 5000000 股 → 5000 張"""
    tpex = [
        {"Date": "1150618", "SecuritiesCompanyCode": "6547",
         "CompanyName": "高端", "Close": "15.0", "Change": "0", "TradingShares": "5000000"},
    ]
    s = _mock_session_factory(tpex_data=tpex)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["成交量_張"] == 5000.0, (
        f"TradingShares=5000000 應為 5000 張、實際: {df.iloc[0]['成交量_張']}"
    )


def test_fetch_prices_沒成交量欄位_不crash_回None():
    """【V0.9.5-cache-vol 邊界】API 沒 TradeVolume / TradingShares 欄位 → 成交量_張 = None"""
    twse = [
        # 故意不放 TradeVolume
        {"Date": "1150618", "Code": "2330", "Name": "台積電",
         "ClosingPrice": "950.0", "Change": "0"},
    ]
    s = _mock_session_factory(twse_data=twse)
    df = st.fetch_prices(s, st.StrategyConfig())
    assert "成交量_張" in df.columns
    assert df.iloc[0]["成交量_張"] is None, "沒成交量欄位應回 None、不 crash"


if __name__ == "__main__":
    test_data_date_一律是today_不管API給什麼Date()
    print("✅ test_data_date_一律是today_不管API給什麼Date")
    test_data_date_無Date欄位也_是today()
    print("✅ test_data_date_無Date欄位也_是today")
    test_data_date_TPEx也_是today()
    print("✅ test_data_date_TPEx也_是today")
    test_run_manual_selection_保留data_date()
    print("✅ test_run_manual_selection_保留data_date")
    test_fetch_prices_TWSE有成交量_轉成張()
    print("✅ test_fetch_prices_TWSE有成交量_轉成張")
    test_fetch_prices_TPEx有成交量_轉成張()
    print("✅ test_fetch_prices_TPEx有成交量_轉成張")
    test_fetch_prices_沒成交量欄位_不crash_回None()
    print("✅ test_fetch_prices_沒成交量欄位_不crash_回None")
    print("\n🎉 All data_date tests passed!")