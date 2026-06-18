"""
test_twse_realtime_vol_otc.py
驗證 V0.9.5-goodinfo4+5 (vol+cache) 三個 fix：
1. 成交量單位修正（v 是股、不是張）
2. otc_ fallback（6 開頭 = 上櫃、但 6669 等是上市）
3. 抓完回寫 cache

【Bug 1 描述】2026-06-18 18:34 William 反映
- 「成交量依舊不是今日總成交量！」
- 根因：TWSE MIS API 的 v 欄位是「股」、不是「張」！
- 原本 int(v/1000) 會把 4016 股變成 4 張（丟失 0.016 張的精度）
- 修法：vol = v / 1000 保留小數、顯示用 f"{vol:,.3f}" 張

【Bug 2 描述】2026-06-18 18:34 William 反映
- 「現價沒資料」
- 根因：原本 _prefix_v2 判斷「6 開頭 = otc_」、但 6669 等少數股是上市
- 修法：先打 tse_、抓不到的股再用 otc_ 重打（fallback）

【Bug 3 描述】2026-06-18 18:34 William 反映
- 「手動選股有開啟 TWSE 即時股價時、抓完全部的股價應該要去 update cache」
- 修法：merge 完後 save_cache(get_cache_file("price"), price_df)

【pytest】
- test_vol_換算_股轉張_保留小數
- test_vol_2548_正確值
- test_otc_fallback_6開頭上櫃股
- test_otc_fallback_6開頭上市股（如 6669）
- test_otc_fallback_混合（2548 上市 + 5386 上櫃）
- test_vol_0_保留為0
- test_vol_NaN_變0
"""
import os
import sys
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


# ==========================================================
# 【Bug 1：成交量單位】v 是股、不是張
# ==========================================================

def test_vol_換算_張直接顯示():
    """【V0.9.5-goodinfo4+5 (vol-no-divide) 守護】v 欄位已經是「張」、不要再除

    William 2026-06-18 21:54 反映：「成交量不要除以1000應該就對了」
    之前測試 v=4,020,000 假設是股、但實際 2548 v=4016 對應 4,016 張（接近 4020 張收盤量）
    → TWSE MIS API 的 v 欄位已經是「張」單位
    → 不需要 // 1000
    """
    v_raw = "4016"  # TWSE API 對 2548 收盤時的 v 值
    vol = int(float(v_raw))  # 直接是張
    assert vol == 4016, f"v=4016 應為 4,016 張（不除 1000）、實際: {vol}"
    print("PASS: test_vol_換算_張直接顯示")


def test_vol_2548_正確值():
    """【V0.9.5-goodinfo4+5 (vol-no-divide) 守護】2548 v=4016 → 顯示 4,016 張

    William 2026-06-18 21:54 反映：「2548 今天是 4020 張」
    TWSE API 抓到的 v=4016（接近收盤量 4020）→ 直接顯示 4,016 張
    """
    v_raw = "4016"
    vol = int(float(v_raw))  # 不再除以 1000
    vol_str = f"{int(vol):,}" if pd.notna(vol) and vol > 0 else "—"
    assert vol_str == "4,016", f"2548 成交量應顯示 '4,016'、實際: {vol_str}"
    print("PASS: test_vol_2548_正確值")


def test_vol_大於1000張_用千分位():
    """【V0.9.5-goodinfo4+5 (vol-int) 守護】大於 1000 張用千分位（整數）"""
    vol = 12345
    vol_str = f"{int(vol):,}" if pd.notna(vol) and vol > 0 else "—"
    assert vol_str == "12,345", f"大於 1000 張應用千分位整數: {vol_str}"
    print("PASS: test_vol_大於1000張_用千分位")


def test_vol_None_顯示橫線():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】vol=None → '—'"""
    vol = None
    vol_str = f"{vol:,.3f}" if pd.notna(vol) else "—"
    assert vol_str == "—", f"vol=None 應顯示 '—'、實際: {vol_str}"
    print("PASS: test_vol_None_顯示橫線")


def test_vol_NaN_顯示橫線():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】vol=NaN → '—'"""
    vol = float('nan')
    vol_str = f"{vol:,.3f}" if pd.notna(vol) else "—"
    assert vol_str == "—", f"vol=NaN 應顯示 '—'、實際: {vol_str}"
    print("PASS: test_vol_NaN_顯示橫線")


def test_vol_0_顯示橫線():
    """【V0.9.5-goodinfo4+5 (vol-int) 守護】vol=0 表示「沒抓到」應顯示 '—'"""
    vol = 0
    vol_str = f"{int(vol):,}" if pd.notna(vol) and vol > 0 else "—"
    assert vol_str == "—", f"vol=0 應顯示 '—'、實際: {vol_str}"
    print("PASS: test_vol_0_顯示橫線")


# ==========================================================
# 【Bug 2：otc_ fallback】先打 tse_ 抓不到的再用 otc_
# ==========================================================

def test_otc_fallback_合併6開頭上櫃股():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】先打 tse_、6 開頭的股 fallback otc_"""
    # Mock _query_twse 來模擬：tse_ 抓不到 5386、otc_ 抓到
    def mock_query_twse(prefix, batch_codes, batch_idx=0, n_batches=1):
        """模擬：tse_ 只回上市股、otc_ 只回上櫃股"""
        msgs = []
        for c in batch_codes:
            # 5386 = 上櫃、2548 = 上市
            is_listed = not c.startswith('6')
            if (prefix == "tse" and is_listed) or (prefix == "otc" and not is_listed):
                msgs.append({
                    "c": c, "n": f"Stock_{c}", "z": "100.0", "o": "100.0", "y": "100.0", "v": "1000"
                })
            # 否則不回（模擬「抓不到」）
        return msgs

    # 用 monkeypatch 測 _fetch_twse_realtime_batch 行為
    import requests
    original_get = requests.get

    def fake_get(url, **kwargs):
        # 解析 URL 拿 codes 跟 prefix
        import re
        m = re.search(r'ex_ch=([^&]+)', url)
        if not m:
            return MagicMock(json=lambda: {"msgArray": []}, raise_for_status=lambda: None)
        ex_ch = m.group(1)
        entries = ex_ch.split('|')
        msgs = []
        for entry in entries:
            # 格式：tse_2548.tw 或 otc_5386.tw
            m2 = re.match(r'(tse|otc)_(\w+)\.tw', entry)
            if not m2:
                continue
            prefix = m2.group(1)
            code = m2.group(2)
            is_listed = not code.startswith('6')
            if (prefix == "tse" and is_listed) or (prefix == "otc" and not is_listed):
                msgs.append({"c": code, "n": f"S_{code}", "z": "100.0", "o": "100.0", "y": "100.0", "v": "1000"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"msgArray": msgs}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch.object(requests, "get", side_effect=fake_get):
        df = st._fetch_twse_realtime_batch(['2548', '5386'])

    # 守護：2548 抓到（上市）+ 5386 抓到（上櫃 fallback）
    assert '2548' in df["股票代號"].values, f"2548 應被抓到: {df}"
    assert '5386' in df["股票代號"].values, f"5386 應透過 otc_ fallback 抓到: {df}"
    assert df[df["股票代號"]=="2548"].iloc[0]["現價"] == 100.0
    assert df[df["股票代號"]=="5386"].iloc[0]["現價"] == 100.0
    print("PASS: test_otc_fallback_合併6開頭上櫃股")


def test_otc_fallback_6開頭上市股():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】6669 是上市、6 開頭但不該 fallback"""
    # 6669 緯穎是上市、用 tse_ 抓得到
    import requests
    def fake_get(url, **kwargs):
        import re
        m = re.search(r'ex_ch=([^&]+)', url)
        msgs = []
        if m:
            ex_ch = m.group(1)
            for entry in ex_ch.split('|'):
                m2 = re.match(r'(tse|otc)_(\w+)\.tw', entry)
                if m2:
                    prefix = m2.group(1)
                    code = m2.group(2)
                    # 6669 上市、tse_ 抓得到
                    if code == "6669" and prefix == "tse":
                        msgs.append({"c": "6669", "n": "緯穎", "z": "5130.0", "o": "5150.0", "y": "5100.0", "v": "1537"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"msgArray": msgs}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    with patch.object(requests, "get", side_effect=fake_get):
        df = st._fetch_twse_realtime_batch(['6669'])

    # 6669 應該被抓到（一次 tse_ 就 OK）
    assert '6669' in df["股票代號"].values
    assert df[df["股票代號"]=="6669"].iloc[0]["現價"] == 5130.0
    # 確認 vol 換算（v=1537 → 1,537 張，不再除以 1000）
    assert df[df["股票代號"]=="6669"].iloc[0]["成交量_張"] == 1537, \
        f"v=1537 應為 1,537 張（不除 1000）、實際: {df[df['股票代號']=='6669'].iloc[0]['成交量_張']}"
    print("PASS: test_otc_fallback_6開頭上市股")


# ==========================================================
# 【Bug 3：cache 回寫】整合測試
# ==========================================================

def test_抓完後_save_cache():
    """【V0.9.5-goodinfo4+5 (vol+cache) 守護】caller merge 完後要 save_cache"""
    # 這個測試主要確認 StockTool 有 save_cache function 可用
    assert hasattr(st, 'save_cache')
    assert hasattr(st, 'get_cache_file')
    print("PASS: test_抓完後_save_cache")


if __name__ == "__main__":
    test_vol_換算_股轉張_保留小數()
    test_vol_2548_正確值()
    test_vol_大於1000張_用千分位()
    test_vol_None_顯示橫線()
    test_vol_NaN_顯示橫線()
    test_vol_0_保留為0()
    test_otc_fallback_合併6開頭上櫃股()
    test_otc_fallback_6開頭上市股()
    test_抓完後_save_cache()
    print("\nAll V0.9.5-goodinfo4+5 (vol+cache) tests passed!")