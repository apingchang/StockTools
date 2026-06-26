"""
test_data_date_column.py
驗證 V0.9.5-info3：「資料日期 = 對應收盤日的真實收盤價」

【V0.9.5-info3 重設計】2026-06-27 00:17 William 反映：
「手動選股資料日期要最後收盤日期及收盤價格才對」

【舊版設計】（V0.9.5-info2、已廢棄）
- data_date 一律 = today（抓取時點對應的市場日）
- 股價仍用 STOCK_DAY_ALL（TWSE 還沒 flush → 拿昨日收盤）
- 結果「日期統一、價格是昨日」的混亂狀態

【V0.9.5-info3 新版】
- 優先用 TWSE MIS 即時 API 拿「當下真實市場狀態」
- MIS 沒回的股（興櫃、MIS 失敗）→ fallback 到 STOCK_DAY_ALL + TPEx
- data_date 來源：
  - MIS: 個股對應成交日 (MIS API 的 d 欄位、西元格式 "20260626")
  - fallback: STOCK_DAY_ALL 的 Date (個股最後成交日、民國格式)
  - 都沒有: today (邀底)

【為什麼要獨立 test 守護】
- 「股價與 data_date 是同一個時點的真實狀態」是核心設計
- MIS d 欄位是西元格式 (20260626)、STOCK_DAY_ALL Date 是民國格式 (1150626) → 兩種都要處理
"""
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import requests

import StockTool as st  # noqa: E402
from stocktool import fetch_market as _fm  # noqa: E402


def _mock_session_factory(twse_data=None, tpex_data=None):
    """產生 mock session：TWSE STOCK_DAY_ALL / TPEx 回傳指定資料"""
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


def _mock_mis_returning(mis_data: list):
    """mock _fetch_twse_realtime_batch 回傳指定 MIS 資料"""
    import pandas as pd
    if not mis_data:
        # 空也要有正確的 columns 才能 merge
        df = pd.DataFrame(columns=["股票代號", "現價", "漲跌", "成交量_張", "data_date_raw"])
    else:
        df = pd.DataFrame([
            {
                "股票代號": rec["c"],
                "現價": rec.get("pz"),
                "漲跌": None,
                "成交量_張": rec.get("v", "0"),
                "data_date_raw": rec.get("d", ""),
            }
            for rec in mis_data
        ])
    return lambda codes, progress_callback=None: df


# ==========================================================
# 【核心】MIS 即時 → 個股對應成交日 = MIS d 欄位（西元格式）
# ==========================================================

def test_data_date_從MIS_d欄位_西元格式():
    """【V0.9.5-info3 核心】MIS d="20260626" → data_date="2026-06-26"

    即使 STOCK_DAY_ALL 還停在昨日、MIS 給今日 → 用 MIS 的 d
    """
    twse = [{"Date": "1150625", "Code": "2330", "Name": "台積電",
             "ClosingPrice": "2390.0", "Change": "0.0", "TradeVolume": "41099957"}]
    s = _mock_session_factory(twse_data=twse)

    # mock 整個 requests.get：TWSE STOCK_DAY_ALL 用 mock、TWSE MIS 即時用另一個 mock
    mis_data = [{"c": "2330", "pz": "2340.0", "d": "20260626", "y": "2390.0", "v": "39059",
                 "o": "2360.0", "h": "2370.0", "l": "2325.0"}]

    def _smart_get(url, **kw):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "STOCK_DAY_ALL" in url:
            m.json = lambda: twse
        elif "mis.twse.com.tw" in url:
            m.json = lambda: {"msgArray": mis_data}
        else:
            m.json = lambda: []
        return m

    s.get = _smart_get
    df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == "2026-06-26", (
        f"MIS d='20260626' 應轉 2026-06-26、實際: {df.iloc[0]['data_date']}"
    )
    # 股價也是 MIS 的 2340
    assert df.iloc[0]["股價"] == 2340.0
    # 漲跌 = pz - y = 2340 - 2390 = -50
    assert df.iloc[0]["漲跌"] == -50.0


# ==========================================================
# 【fallback】MIS 沒回 → STOCK_DAY_ALL Date（民國格式）
# ==========================================================

def test_data_date_MIS沒回_fallback用STOCK_DAY_ALL_Date():
    """【V0.9.5-info3 fallback】MIS 沒回的股 → 用 STOCK_DAY_ALL Date 轉西元

    興櫃股常見情境
    """
    twse = [{"Date": "1150626", "Code": "5275", "Name": "高端",
             "ClosingPrice": "15.0", "Change": "0.0", "TradeVolume": "5000000"}]
    s = _mock_session_factory(twse_data=twse)
    # MIS 沒回 (興櫃)
    with patch.object(_fm, "_fetch_twse_realtime_batch", _mock_mis_returning([])):
        df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == "2026-06-26", (
        f"STOCK_DAY_ALL Date='1150626' 應轉 2026-06-26、實際: {df.iloc[0]['data_date']}"
    )


def test_data_date_TPEx也_fallback用Date():
    """【V0.9.5-info3】TPEx 股也用 Date 欄位（興櫃股 fallback）"""
    twse = []
    tpex = [{"Date": "1150626", "SecuritiesCompanyCode": "6547",
             "CompanyName": "高端", "Close": "15.0", "Change": "0.0", "TradingShares": "5000000"}]
    s = _mock_session_factory(twse_data=twse, tpex_data=tpex)
    with patch.object(_fm, "_fetch_twse_realtime_batch", _mock_mis_returning([])):
        df = st.fetch_prices(s, st.StrategyConfig())
    row = df[df["股票代號"] == "6547"].iloc[0]
    assert row["data_date"] == "2026-06-26"


# ==========================================================
# 【邊界】STOCK_DAY_ALL Date 格式錯誤
# ==========================================================

def test_data_date_STOCK_DAY_ALL_Date格式錯誤_fallback_today():
    """【邊界】STOCK_DAY_ALL Date 格式不對 → fallback = today"""
    twse = [{"Date": "bad", "Code": "2330", "Name": "台積電",
             "ClosingPrice": "950.0", "Change": "0"}]
    s = _mock_session_factory(twse_data=twse)
    today = datetime.now().strftime("%Y-%m-%d")
    with patch.object(_fm, "_fetch_twse_realtime_batch", _mock_mis_returning([])):
        df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["data_date"] == today


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
    eps_df = st.pd.DataFrame()
    result = st._run_manual_selection(
        price_df, revenue_df, eps_df,
        filters={"rev_yoy": None},
        top_n=500,
    )
    assert "data_date" in result.columns
    row_2330 = result[result["股票代號"] == "2330"].iloc[0]
    row_3188 = result[result["股票代號"] == "3188"].iloc[0]
    assert row_2330["data_date"] == "2026-06-26"
    assert row_3188["data_date"] == "2026-06-26"


# ==========================================================
# 【成交量】TWSE TradeVolume / TPEx TradingShares 轉張
# ==========================================================

def test_fetch_prices_TWSE有成交量_轉成張():
    """【成交量】TWSE TradeVolume 25000000 股 → 25000 張"""
    twse = [{"Date": "1150618", "Code": "2330", "Name": "台積電",
             "ClosingPrice": "950.0", "Change": "0", "TradeVolume": "25000000"}]
    s = _mock_session_factory(twse_data=twse)
    with patch.object(_fm, "_fetch_twse_realtime_batch", _mock_mis_returning([])):
        df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["成交量_張"] == 25000.0


def test_fetch_prices_TPEx有成交量_轉成張():
    """【成交量】TPEx TradingShares 5000000 股 → 5000 張"""
    tpex = [{"Date": "1150618", "SecuritiesCompanyCode": "6547",
             "CompanyName": "高端", "Close": "15.0", "Change": "0", "TradingShares": "5000000"}]
    s = _mock_session_factory(tpex_data=tpex)
    with patch.object(_fm, "_fetch_twse_realtime_batch", _mock_mis_returning([])):
        df = st.fetch_prices(s, st.StrategyConfig())
    assert df.iloc[0]["成交量_張"] == 5000.0


if __name__ == "__main__":
    test_data_date_從MIS_d欄位_西元格式()
    print("✅ test_data_date_從MIS_d欄位_西元格式")
    test_data_date_MIS沒回_fallback用STOCK_DAY_ALL_Date()
    print("✅ test_data_date_MIS沒回_fallback用STOCK_DAY_ALL_Date")
    test_data_date_TPEx也_fallback用Date()
    print("✅ test_data_date_TPEx也_fallback用Date")
    test_data_date_STOCK_DAY_ALL_Date格式錯誤_fallback_today()
    print("✅ test_data_date_STOCK_DAY_ALL_Date格式錯誤_fallback_today")
    test_run_manual_selection_保留data_date()
    print("✅ test_run_manual_selection_保留data_date")
    test_fetch_prices_TWSE有成交量_轉成張()
    print("✅ test_fetch_prices_TWSE有成交量_轉成張")
    test_fetch_prices_TPEx有成交量_轉成張()
    print("✅ test_fetch_prices_TPEx有成交量_轉成張")
    print("\n🎉 All data_date tests passed!")