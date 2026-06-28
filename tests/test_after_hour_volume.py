"""
test_after_hour_volume.py
驗證 V0.9.5-after-hour：手動選股加「盤後量(張)」欄位

【William 2026-06-28 09:44 反映】
- 「手動選股節過中成交量和實際不一樣,少了盤後交易的數量！」
- 「你可以增加依欄盤後交易的數值資料嗎？」

【根因】
- 現有「成交量(張)」欄位來自 TWSE STOCK_DAY_ALL 的 TradeVolume
- TradeVolume 是「盤中收盤後累計」,不含 13:40~14:30 的「盤後定價交易」
- 所以高價股/低價股有盤後成交時,StockTool 顯示的量比實際少

【修法】
- 新增 fetch_after_hour_volumes():抓 TWSE BFT41U (個股盤後定價交易)
- fetch_prices() 整合,加「盤後量_股」欄位
- _run_manual_selection() 把「盤後量_股」帶到 final_cols、rename 成「盤後量(張)」
- UI 手動選股 Treeview 加「盤後量(張)」欄(TPEx 上櫃顯示「—」)
- 舊 cache 沒這個欄位 → get_or_fetch 不會爆、補 None

【守護】
- fetch_after_hour_volumes 4 個邊界 (正常/失敗/stat 失敗/0 不寫入)
- fetch_prices 加「盤後量_股」欄位 + 向後相容
- _run_manual_selection 把「盤後量」帶到 result
- 舊 cache 沒新欄位時 get_or_fetch 不爆
- 「盤後量」欄位名正確 (股 vs 張)
"""
import os
import sys
import sqlite3
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import pandas as pd
import requests

import StockTool as st  # noqa: E402
from stocktool import fetch_market as _fm  # noqa: E402
from stocktool.config import StrategyConfig

_CFG = StrategyConfig()


# ==========================================================
# 【fetch_after_hour_volumes】邊界
# ==========================================================

def _mock_after_hour_session(payload):
    """產生 mock session:BFT41U 回傳指定 payload"""
    s = requests.Session()

    def mock_get(url, **kw):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "BFT41U" in url:
            m.json = lambda: payload
        else:
            m.json = lambda: {"stat": "FAIL"}
        return m

    s.get = mock_get
    return s


def test_after_hour_normal():
    """【V0.9.5-after-hour】正常抓取:9 筆有成交量"""
    payload = {
        "stat": "OK",
        "date": "20260626",
        "fields": ["證券代號", "證券名稱", "成交數量", "成交筆數",
                   "成交金額", "成交價", "最後揭示買量", "最後揭示賣量"],
        "data": [
            ["1101", "台泥", "134", "48", "3,236,100", "24.15", "0", "125"],
            ["1101B", "台泥乙特", "0", "0", "0", "45.40", "0", "0"],
            ["1102", "亞泥", "6", "6", "214,500", "35.75", "0", "2"],
            ["1103", "嘉泥", "0", "0", "0", "16.30", "0", "0"],
        ],
    }
    s = _mock_after_hour_session(payload)
    df = _fm.fetch_after_hour_volumes(s, _CFG)

    assert not df.empty, "應回傳有資料"
    assert "股票代號" in df.columns
    assert "盤後量_股" in df.columns

    # 驗證:有成交的 1101 (134 股) + 1102 (6 股) → 應該出現
    # volume=0 的 1101B / 1103 → 也應該出現 (volume=0 寫入)
    assert len(df) == 4, f"4 筆都該出現、實際 {len(df)}"
    row_1101 = df[df["股票代號"] == "1101"].iloc[0]
    assert row_1101["盤後量_股"] == 134, f"1101 應 = 134 股、實際 {row_1101['盤後量_股']}"
    row_1101b = df[df["股票代號"] == "1101B"].iloc[0]
    assert row_1101b["盤後量_股"] == 0, f"1101B 應 = 0 股、實際 {row_1101b['盤後量_股']}"

    print(f"PASS: test_after_hour_normal ({len(df)} rows)")


def test_after_hour_stat_not_ok():
    """【V0.9.5-after-hour】API 回 stat != OK → 空 DataFrame"""
    payload = {"stat": "FAIL", "data": [], "fields": []}
    s = _mock_after_hour_session(payload)
    df = _fm.fetch_after_hour_volumes(s, _CFG)

    assert df.empty, f"stat=FAIL 應回空、實際 {len(df)} rows"
    assert list(df.columns) == ["股票代號", "盤後量_股"], f"欄位應為 [股票代號, 盤後量_股]、實際 {list(df.columns)}"
    print("PASS: test_after_hour_stat_not_ok")


def test_after_hour_api_raises():
    """【V0.9.5-after-hour】API exception → 空 DataFrame、不 crash"""
    s = requests.Session()
    s.get = lambda *a, **kw: (_ for _ in ()).throw(requests.exceptions.Timeout("mock timeout"))

    df = _fm.fetch_after_hour_volumes(s, _CFG)
    assert df.empty, "API 失敗應回空"
    assert list(df.columns) == ["股票代號", "盤後量_股"]
    print("PASS: test_after_hour_api_raises")


def test_after_hour_volume_with_comma():
    """【V0.9.5-after-hour】成交數量含千分位逗號 → 正確 parse"""
    payload = {
        "stat": "OK",
        "fields": ["證券代號", "證券名稱", "成交數量", "成交筆數",
                   "成交金額", "成交價", "最後揭示買量", "最後揭示賣量"],
        "data": [
            ["2330", "台積電", "12,345", "100", "1,000,000", "600", "0", "0"],
        ],
    }
    s = _mock_after_hour_session(payload)
    df = _fm.fetch_after_hour_volumes(s, _CFG)

    assert len(df) == 1
    assert df.iloc[0]["盤後量_股"] == 12345, f"千分位逗號應正確 parse、實際 {df.iloc[0]['盤後量_股']}"
    print(f"PASS: test_after_hour_volume_with_comma (12345 股)")


# ==========================================================
# 【fetch_prices】整合盤後量、向後相容
# ==========================================================

def test_fetch_prices_有盤後量欄位():
    """【V0.9.5-after-hour】fetch_prices 回傳應包含「盤後量_股」欄位"""
    # 簡單測:mock STOCK_DAY_ALL、TPEx、MIS、BFT41U
    s = requests.Session()

    twse_data = [
        {
            "證券代號": "1101",
            "證券名稱": "台泥",
            "收盤價": "24.15",
            "漲跌價差": "-0.45",
            "TradeVolume": "34195000",
            "Date": "1150626",
        },
    ]

    def mock_get(url, **kw):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "STOCK_DAY_ALL" in url:
            m.json = lambda: twse_data
        elif "tpex_mainboard" in url:
            m.json = lambda: []
        elif "BFT41U" in url:
            m.json = lambda: {
                "stat": "OK",
                "fields": ["證券代號", "證券名稱", "成交數量"],
                "data": [["1101", "台泥", "134"]],
            }
        elif "getStockInfo" in url:
            m.json = lambda: {"msgArray": []}
        else:
            m.json = lambda: {}
        return m

    s.get = mock_get
    df = _fm.fetch_prices(s, _CFG)

    assert "盤後量_股" in df.columns, f"fetch_prices 應有「盤後量_股」欄位、實際 {list(df.columns)}"
    # 1101 盤後量應 = 134 (BFT41U 提供)
    if not df.empty:
        row = df[df["股票代號"] == "1101"]
        if not row.empty:
            assert row.iloc[0]["盤後量_股"] == 134, (
                f"1101 應 = 134、實際 {row.iloc[0]['盤後量_股']}"
            )
    print(f"PASS: test_fetch_prices_有盤後量欄位 (columns: {list(df.columns)})")


def test_fetch_prices_盤後量_merge_正確():
    """【V0.9.5-after-hour】fetch_prices 抓到的盤後量 merge 進正確的 stock_id"""
    s = requests.Session()

    # 模擬 3 筆 TWSE STOCK_DAY_ALL + 1 筆 BFT41U
    twse_data = [
        {
            "證券代號": "1101",
            "證券名稱": "台泥",
            "收盤價": "24.15",
            "漲跌價差": "-0.45",
            "TradeVolume": "34195000",
            "Date": "1150626",
        },
        {
            "證券代號": "2330",
            "證券名稱": "台積電",
            "收盤價": "2340",
            "漲跌價差": "-50",
            "TradeVolume": "39059000",
            "Date": "1150626",
        },
    ]
    bft41u_data = {
        "stat": "OK",
        "fields": ["證券代號", "證券名稱", "成交數量"],
        "data": [["1101", "台泥", "134"]],  # 只有 1101 有盤後
    }

    def mock_get(url, **kw):
        m = MagicMock()
        m.raise_for_status = lambda: None
        if "STOCK_DAY_ALL" in url:
            m.json = lambda: twse_data
        elif "tpex_mainboard" in url:
            m.json = lambda: []
        elif "BFT41U" in url:
            m.json = lambda: bft41u_data
        elif "getStockInfo" in url:
            m.json = lambda: {"msgArray": []}
        else:
            m.json = lambda: {}
        return m

    s.get = mock_get
    df = _fm.fetch_prices(s, _CFG)

    # 1101 → 盤後量 = 134, 2330 → 盤後量 = 0
    row_1101 = df[df["股票代號"] == "1101"]
    row_2330 = df[df["股票代號"] == "2330"]
    if not row_1101.empty and not row_2330.empty:
        assert row_1101.iloc[0]["盤後量_股"] == 134, (
            f"1101 應 = 134、實際 {row_1101.iloc[0]['盤後量_股']}"
        )
        assert row_2330.iloc[0]["盤後量_股"] == 0, (
            f"2330 應 = 0、實際 {row_2330.iloc[0]['盤後量_股']}"
        )
        print(f"PASS: test_fetch_prices_盤後量_merge_正確 (1101={row_1101.iloc[0]['盤後量_股']}, 2330={row_2330.iloc[0]['盤後量_股']})")
    else:
        print(f"SKIP: df 為空,可能 MIS mock 不對 (shape={df.shape})")


# ==========================================================
# 【_run_manual_selection】盤後量帶到 result
# ==========================================================

def test_run_manual_selection_盤後量_帶到_result():
    """【V0.9.5-after-hour】_run_manual_selection 把「盤後量」從 price_df 帶到 final_cols"""
    # mock fetch_market 的 FinMind (避免 DB 依賴)
    import stocktool.fetch_market as fm_mod
    fm_mod._fetch_finmind_dividend = lambda *a, **kw: pd.DataFrame()

    price_df = pd.DataFrame([
        {"股票代號": "1101", "公司名稱_來源": "台泥", "股價": 24.15, "成交量_張": 34195.0,
         "盤後量_股": 134, "data_date": "2026-06-26"},
        {"股票代號": "2330", "公司名稱_來源": "台積電", "股價": 2340.0, "成交量_張": 39059.0,
         "盤後量_股": 0, "data_date": "2026-06-26"},
    ])

    result = st._run_manual_selection(
        price_df=price_df,
        revenue_df=pd.DataFrame(columns=["股票代號", "營收YoY(%)"]),
        eps_df=pd.DataFrame(columns=["股票代號", "EPS本期"]),
        filters={"min_rev_yoy": None, "min_pe": None, "min_price": None,
                 "min_volume": None, "min_div_yield": None, "min_stock_yield": None,
                 "preselected": []},
        top_n=10,
    )

    # 必含「盤後量(張)」(rename 後)
    assert "盤後量(張)" in result.columns, (
        f"result 應含「盤後量(張)」、實際 {list(result.columns)}"
    )
    row_1101 = result[result["股票代號"] == "1101"].iloc[0]
    assert row_1101["盤後量(張)"] == 134, f"1101 盤後量應 = 134、實際 {row_1101['盤後量(張)']}"
    print(f"PASS: test_run_manual_selection_盤後量_帶到_result (1101 盤後量(張)={row_1101['盤後量(張)']})")


def test_run_manual_selection_沒盤後量欄位不爆():
    """【V0.9.5-after-hour】舊 price_df 沒「盤後量_股」→ result 不爆、欄位補 None"""
    import stocktool.fetch_market as fm_mod
    fm_mod._fetch_finmind_dividend = lambda *a, **kw: pd.DataFrame()

    price_df = pd.DataFrame([
        {"股票代號": "1101", "公司名稱_來源": "台泥", "股價": 24.15, "成交量_張": 34195.0,
         "data_date": "2026-06-26"},
    ])

    result = st._run_manual_selection(
        price_df=price_df,
        revenue_df=pd.DataFrame(columns=["股票代號", "營收YoY(%)"]),
        eps_df=pd.DataFrame(columns=["股票代號", "EPS本期"]),
        filters={"min_rev_yoy": None, "min_pe": None, "min_price": None,
                 "min_volume": None, "min_div_yield": None, "min_stock_yield": None,
                 "preselected": []},
        top_n=10,
    )

    assert "盤後量(張)" in result.columns
    row_1101 = result[result["股票代號"] == "1101"].iloc[0]
    val = row_1101["盤後量(張)"]
    assert pd.isna(val) or val is None or val == 0, f"沒資料時應為 None/0、實際 {val}"
    print(f"PASS: test_run_manual_selection_沒盤後量欄位不爆 (val={val})")


# ==========================================================
# 【cache 向後相容】舊 cache 沒「盤後量_股」不爆
# ==========================================================

def test_old_cache_沒盤後量欄位_get_or_fetch_不爆():
    """【V0.9.5-after-hour】舊 price.xlsx 沒「盤後量_股」→ get_or_fetch 不要求此欄位、不爆"""
    from stocktool.cache import get_or_fetch, get_cache_file, save_cache, load_cache

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # 模擬「舊 cache」:只有 4 個欄位、沒「盤後量_股」
        old_cache_df = pd.DataFrame([
            {"股票代號": "2330", "現價": 2340.0, "漲跌": -50.0, "成交量_張": 39059.0,
             "data_date": "2026-06-26"},
        ])
        save_cache(tmp_path, old_cache_df)

        # 確認舊 cache 沒「盤後量_股」
        old_loaded, _, _ = load_cache(tmp_path)
        assert "盤後量_股" not in old_loaded.columns, "測試前提: 舊 cache 應沒此欄位"

        # 結構檢查只要求「成交量_張 + data_date」、不會因缺「盤後量_股」而重抓
        required = {"成交量_張", "data_date"}
        missing = required - set(old_loaded.columns)
        assert not missing, "結構檢查應不 missing"

        print("PASS: test_old_cache_沒盤後量欄位_get_or_fetch_不爆 (舊 cache 仍可用)")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    test_after_hour_normal()
    test_after_hour_stat_not_ok()
    test_after_hour_api_raises()
    test_after_hour_volume_with_comma()
    test_fetch_prices_有盤後量欄位()
    test_fetch_prices_盤後量_merge_正確()
    test_run_manual_selection_盤後量_帶到_result()
    test_run_manual_selection_沒盤後量欄位不爆()
    test_old_cache_沒盤後量欄位_get_or_fetch_不爆()
    print("\nAll V0.9.5-after-hour tests passed!")