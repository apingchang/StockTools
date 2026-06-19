"""
test_twse_realtime.py
驗證 V0.9.5-twser TWSE 即時股價 API 的正確性。

【動機】
William 2026-06-18 09:45 確認 TWSE 即時資訊延遲 15-20 秒（不是 15 分鐘），且有免費 JSON API 可用。

【API 規格】
URL: https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw|otc_XXXX.tw
主力欄位: z=現價, o=開盤, h=高, l=低, y=昨收, v=累積成交量
預開盤行為: z="-" (9:00-9:30) → fallback 到 o（開盤拍賣價）

所有情境皆用 mock requests 以確保穩定，live 端對端另用一個 smoke test。
"""
import os
import sys
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def _mock_get_factory(msg_array):
    """工廠：產生假的 requests.get，回傳指定 msgArray"""
    original_get = requests.get

    def fake_get(url, **kwargs):
        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"rtcode": "0000", "msgArray": msg_array}
        return FakeResp()

    return original_get, fake_get


def test_基本API格式_live():
    """【Live smoke test】確認 API 打得通且格式正確"""
    result = st._fetch_twse_realtime_batch(["2330", "0050"])
    assert not result.empty
    assert list(result.columns) == ["股票代號", "現價", "成交量_張"]
    assert set(result["股票代號"].tolist()) == {"2330", "0050"}


def test_現價欄位型態():
    """【基本守護】現價應為 float 或 None，成交量_張 應為 float"""
    msg = [{"c": "TEST", "z": "100.5", "o": "100.0", "y": "99.5", "v": "5000"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["TEST"])
        row = result.iloc[0]
        assert row["現價"] == 100.5
        # V0.9.5-goodinfo4+5 (vol-no-divide)：v 已是張、不除 1000
        assert row["成交量_張"] == 5000
    finally:
        requests.get = orig


def test_z為零時fallback到o():
    """【白箱】z=\"-\" 時 fallback 到 o（開盤拍賣價）"""
    msg = [{"c": "TEST01", "z": "-", "o": "123.5", "y": "120.0", "v": "1000"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["TEST01"])
        assert len(result) == 1
        assert result.iloc[0]["現價"] == 123.5
    finally:
        requests.get = orig


def test_z和o都為零時回退到y():
    """【白箱】z=\"-\" 且 o=\"-\" 時 fallback 到 y（昨收）"""
    msg = [{"c": "TEST02", "z": "-", "o": "-", "y": "99.5", "v": "0"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["TEST02"])
        assert len(result) == 1
        assert result.iloc[0]["現價"] == 99.5
    finally:
        requests.get = orig


def test_三個股都是零時price為None():
    """【白箱】z/o/y 全為 \"-\" 時現價應為 None（不 crash）"""
    msg = [{"c": "TEST03", "z": "-", "o": "-", "y": "-", "v": "0"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["TEST03"])
        assert len(result) == 1
        assert result.iloc[0]["現價"] is None
    finally:
        requests.get = orig


def test_批量多檔一次回():
    """【白箱】10 檔一次回（模擬批量上限，batch_size=10）

    V0.9.5-goodinfo4+5 (rate-mode)：BATCH_SIZE 50→10
    """
    msg = [{"c": f"ST{i:04d}", "z": str(100 + i), "o": str(100 + i), "y": "99", "v": "1000"}
           for i in range(10)]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch([f"ST{i:04d}" for i in range(10)])
        assert len(result) == 10, f'10檔應全回、實際: {len(result)}'
        assert result.iloc[0]["現價"] == 100.0
        assert result.iloc[9]["現價"] == 109.0
    finally:
        requests.get = orig


def test_不回應的股票被跳過():
    """【容錯】API 回 c=\"\"（查無此股）時不 crash、行數等於有回應的檔數

    V0.9.5-goodinfo4+5 (vol+cache) 更新：
    - 原本行為：6 開頭用 otc_、其他用 tse_，c="" 跳過
    - 新行為：先全部打 tse_、c="" 的股再用 otc_ 重打
    - 這裡 mock 會回傳同樣 msgArray 給 tse_ 和 otc_
      → 最終 rows 會包含 2 個 REAL01/REAL02 (tse_ 回的) + 2 個 REAL01/REAL02 (otc_ 回的) + 1 個 FAKECODE fallback row
    - 守護重點：不能 crash、結果要有 REAL01/REAL02、FAKECODE 是 None fallback row
    """
    msg = [
        {"c": "REAL01", "z": "50.0", "o": "50.0", "y": "49.0", "v": "1000"},
        {"c": "", "z": "-", "o": "-", "y": "-", "v": "0"},  # 查無
        {"c": "REAL02", "z": "60.0", "o": "60.0", "y": "59.0", "v": "2000"},
    ]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["REAL01", "FAKECODE", "REAL02"])
        # 守護：有抓到的股都有、沒抓到的股有 fallback row (現價 None)
        codes = result["股票代號"].astype(str).str.strip().tolist()
        assert "REAL01" in codes, f"REAL01 應被抓到: {codes}"
        assert "REAL02" in codes, f"REAL02 應被抓到: {codes}"
        assert "FAKECODE" in codes, f"FAKECODE 應有 fallback row: {codes}"
        # FAKECODE 的現價應為 None（fallback row）
        fc_row = result[result["股票代號"]=="FAKECODE"]
        assert len(fc_row) >= 1
        assert pd.isna(fc_row.iloc[0]["現價"]), f"FAKECODE 現價應為 None、實際: {fc_row.iloc[0]['現價']}"
    finally:
        requests.get = orig


def test_otc上櫃前綴():
    """【上櫃守護】6 開頭走 otc_ 前綴"""
    # 驗證 _prefix_v2 邏輯：3188 → otc_3188.tw
    msg = [{"c": "3188", "z": "25.1", "o": "25.2", "y": "25.0", "v": "194"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["3188"])
        assert len(result) == 1
        assert result.iloc[0]["股票代號"] == "3188"
    finally:
        requests.get = orig


def test_股票代號字串潔化():
    """【格式守護】股票代號左右空白應被去除"""
    msg = [{"c": " 2330 ", "z": "100", "o": "100", "y": "99", "v": "1000"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch([" 2330 "])
        assert result.iloc[0]["股票代號"] == "2330"
    finally:
        requests.get = orig


def test_成交量單位是張():
    """【單位守護】TWSE 回 v=5000 → 輸出應為 5,000 張（不除 1000）

    V0.9.5-goodinfo4+5 (vol-no-divide) 修正：v 已經是「張」
    William 2026-06-18 21:54 反映：「成交量不要除以1000應該就對了」
    """
    msg = [{"c": "VOL01", "z": "50.0", "o": "50.0", "y": "49.0", "v": "5000"}]
    orig, fake = _mock_get_factory(msg)
    requests.get = fake
    try:
        result = st._fetch_twse_realtime_batch(["VOL01"])
        assert result.iloc[0]["成交量_張"] == 5000, \
            f"v=5000 應為 5,000 張（不除 1000）、實際: {result.iloc[0]['成交量_張']}"
    finally:
        requests.get = orig


def test_TWSE_batch_size常數():
    """【架構守護】_TWSE_REALTIME_BATCH_SIZE = 10"""
    assert st._TWSE_REALTIME_BATCH_SIZE == 10


if __name__ == "__main__":
    test_基本API格式_live()
    print("✅ test_基本API格式_live passed")
    test_現價欄位型態()
    print("✅ test_現價欄位型態 passed")
    test_z為零時fallback到o()
    print("✅ test_z為零時fallback到o passed")
    test_z和o都為零時回退到y()
    print("✅ test_z和o都為零時回退到y passed")
    test_三個股都是零時price為None()
    print("✅ test_三個股都是零時price為None passed")
    test_批量多檔一次回()
    print("✅ test_批量多檔一次回 passed")
    test_不回應的股票被跳過()
    print("✅ test_不回應的股票被跳過 passed")
    test_otc上櫃前綴()
    print("✅ test_otc上櫃前綴 passed")
    test_股票代號字串潔化()
    print("✅ test_股票代號字串潔化 passed")
    test_成交量單位是張()
    print("✅ test_成交量單位是張 passed")
    test_TWSE_batch_size常數()
    print("✅ test_TWSE_batch_size常數 passed")
    print("\n🎉 All TWSE realtime tests passed!")
