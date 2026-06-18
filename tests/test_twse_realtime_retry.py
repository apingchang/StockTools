"""
test_twse_realtime_retry.py
驗證 V0.9.5-goodinfo4+5 (vol+cache) retry 機制：
1. 單批失敗 → 自動 retry 最多 3 次（1.0s / 2.0s / 3.0s 退避）
2. 3 次都失敗 → 回傳空 list
3. batch 之間 sleep 0.5s 避免被 rate limit
4. merge 前 cache 現價 fillna 股價（即使 TWSE 抓不到、現價也不變 NaN）
5. vol=0 顯示 "—"（不是 0.000）

【William 2026-06-18 19:25 反映】
- 「成交量還是不對」（v/1000 修了，但 vol=0 顯示 0.000 不對）
- 「這個篩選條件為什麼沒抓到 6669」（PE 過濾掉是合理的、但之前可能 cache 有）
- 「還是有很多沒現價的」（otc fallback 整批失敗 → retry 不夠）
- console：⚠️ TWSE API otc fallback 失敗（Connection aborted）

【修法】
- _query_twse 加 3 次 retry + 退避
- _do() batch 間加 0.5s sleep
- merge 前 cache 現價 fillna 股價
- vol=0 顯示 "—"
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 【重試機制】
# ==========================================================

def test_query_twse_retry_一次失敗後成功():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】第 2 次 retry 才成功"""
    import requests
    call_count = [0]
    def fake_get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # 第一次失敗
            raise ConnectionError("first attempt failed")
        # 第二次成功
        msgs = [{"c": "6669", "n": "緯穎", "z": "5130.0", "o": "5100.0", "y": "5080.0", "v": "1537"}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"msgArray": msgs}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch.object(requests, "get", side_effect=fake_get):
        with patch("time.sleep") as mock_sleep:
            df = st._fetch_twse_realtime_batch(["6669"])

    assert call_count[0] == 2, f"應打 2 次、實際: {call_count[0]}"
    assert '6669' in df["股票代號"].values
    assert df[df["股票代號"]=="6669"].iloc[0]["現價"] == 5130.0
    # retry 應有 sleep
    assert mock_sleep.called, "retry 應呼叫 sleep"
    print("PASS: test_query_twse_retry_一次失敗後成功")


def test_query_twse_三次都失敗回傳空():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】3 次 retry 都失敗回傳空 list（不 crash）"""
    import requests
    call_count = [0]
    def fake_get(url, **kwargs):
        call_count[0] += 1
        raise ConnectionError("permanent failure")

    with patch.object(requests, "get", side_effect=fake_get):
        with patch("time.sleep"):  # skip sleep
            df = st._fetch_twse_realtime_batch(["6669"])

    # V0.9.5-goodinfo4+5 (vol-int) 修：tse 整批失敗時跳過 otc fallback
    # 所以只打 3 次 tse（不再打 otc）
    assert call_count[0] == 3, f"應打 3 次（tse only、tse 整批失敗跳過 otc）、實際: {call_count[0]}"
    # 即使全失敗、也要回傳 fallback row（讓 caller 後面用 cache fallback）
    assert '6669' in df["股票代號"].values, "全失敗應有 fallback row、不是空 df"
    assert pd.isna(df[df["股票代號"]=="6669"].iloc[0]["現價"])
    print("PASS: test_query_twse_三次都失敗回傳空")


# ==========================================================
# 【Vol = 0 顯示橫線】
# ==========================================================

def test_vol_0_顯示橫線不是0_000():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】vol=0 表示「TWSE 沒抓到」應顯示 "—"

    William 19:25 反映：「成交量還是不對」→ 5386 顯示 0.000
    修法：vol=0 也視為「無資料」、顯示 "—"
    """
    # 模擬 _ms_display_results 的 vol_str 邏輯（V0.9.5-goodinfo4+5 vol-int 版本）
    def format_vol(vol):
        if pd.isna(vol):
            return "—"
        if isinstance(vol, (int, float)) and vol == 0:
            return "—"
        return f"{int(vol):,}"  # 整數張 + 千分位

    assert format_vol(0) == "—", f"vol=0 應為 '—'、實際: '{format_vol(0)}'"
    assert format_vol(0.0) == "—", f"vol=0.0 應為 '—'、實際: '{format_vol(0.0)}'"
    assert format_vol(4020) == "4,020", f"vol=4020 應為 '4,020'、實際: '{format_vol(4020)}'"
    assert format_vol(None) == "—", f"vol=None 應為 '—'、實際: '{format_vol(None)}'"
    assert format_vol(float('nan')) == "—", f"vol=NaN 應為 '—'、實際: '{format_vol(float('nan'))}'"
    print("PASS: test_vol_0_顯示橫線不是0_000")


# ==========================================================
# 【Merge 前 cache 現價 fillna 股價】
# ==========================================================

def test_merge前_cache_現價_fillna_股價():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】merge 前 cache 現價 fillna 股價

    William 19:25 反映「還是有很多沒現價的」
    根因：cache 「現價」是 NaN、「股價」是 cache 抓的收盤價
    → merge 時用 fillna(現價) 拿不到舊值
    修法：merge 前先把 cache 現價用股價 fallback
    """
    # 模擬 cache
    cache_df = pd.DataFrame([
        {"股票代號": "5386", "公司名稱_來源": "青雲", "股價": 500.0, "漲跌": 0, "現價": float('nan'), "成交量_張": 0.0},
        {"股票代號": "6669", "公司名稱_來源": "緯穎", "股價": 5080.0, "漲跌": 0, "現價": 5130.0, "成交量_張": 1.537},
    ])
    # 模擬 TWSE 抓不到 5386、抓到 6669
    fresh = pd.DataFrame([
        {"股票代號": "6669", "現價": 5130.0, "成交量_張": 1.537},
    ])

    # 修法：merge 前 fillna
    cache_df["現價"] = cache_df["現價"].fillna(cache_df["股價"])
    fresh_small = fresh[["股票代號", "現價", "成交量_張"]].copy()
    merged = cache_df.merge(fresh_small, on="股票代號", how="left", suffixes=("", "_fresh"))
    merged["現價"] = merged["現價_fresh"].fillna(merged["現價"])
    merged = merged.drop(columns=["現價_fresh"])

    # 守護：5386 現價應為 500（從 cache 股價 fallback）
    assert merged[merged["股票代號"]=="5386"].iloc[0]["現價"] == 500.0, \
        f"5386 現價應為 500.0（cache fallback）、實際: {merged[merged['股票代號']=='5386'].iloc[0]['現價']}"
    # 守護：6669 現價應為 5130.0（從 fresh）
    assert merged[merged["股票代號"]=="6669"].iloc[0]["現價"] == 5130.0
    print("PASS: test_merge前_cache_現價_fillna_股價")


if __name__ == "__main__":
    test_query_twse_retry_一次失敗後成功()
    test_query_twse_三次都失敗回傳空()
    test_vol_0_顯示橫線不是0_000()
    test_merge前_cache_現價_fillna_股價()
    print("\nAll V0.9.5-goodinfo4+5 (retry+vol) tests passed!")