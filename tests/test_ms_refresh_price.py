"""
test_ms_refresh_price.py
驗證手動選股的「股價來源」邏輯。

【V0.9.5-cache-cleanup1 重大改動】2026-06-19 William 決定：
- 手動選股一律用 cache 的收盤價、不再提供「即時抓股價」選項
- 拿掉 UI：「🔄 即時抓股價」checkbox、「🚀/🐌 TWSE 速率」radio
- 看即時 tick：去「買賣紀錄」Tab（有 30 秒 polling）
- 想重抓 cache close：原本就有「🔄 重新抓股價」按鈕

【設計】
- _ms_run_selection 不再主動抓最新股價（永遠走 cache）
- 股價 merge 邏輯保留下來供未來測試使用
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


def test_選股永遠走cache不呼叫finmind_price_batch():
    """【V0.9.5-cache-cleanup1 守護】手動選股永遠走 cache、不呼叫 finmind 即時抓

    - 即使 mock _fetch_finmind_prices_batch、call_log 應為空
    - 因為已沒有 checkbox 可勾、不會主動呼叫 finmind
    """
    """【關鍵守護】勾了時、跑選股前應呼叫 _fetch_finmind_prices_batch"""
    # Mock：呼叫 _fetch_finmind_prices_batch 時記 log
    call_log = []
    def fake_batch(codes, progress_callback=None):
        call_log.append(codes)
        # 回傳只有 3188 的新股價
        return pd.DataFrame([
            {"股票代號": "3188", "現價": 100.0, "成交量_張": 500.0},
        ])

    st_fetch_market._fetch_finmind_prices_batch = fake_batch
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame()

    # 模擬 price_df
    price_df = pd.DataFrame([
        {"股票代號": "3188", "股票名稱": "鑫龍騰", "現價": 50.0,
         "營收YoY(%)": 30.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 3.0},
    ])
    revenue_df = pd.DataFrame([{"股票代號": "3188", "營收YoY(%)": 30.0}])

    # 直接呼叫 _run_manual_selection
    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    assert len(call_log) == 0, f"未勾時不該呼叫 finmind price batch，實際: {call_log}"


def test_股價merge邏輯_新價覆蓋舊價():
    """【單元】_fetch_finmind_prices_batch 的結果應能 merge 進 price_df 覆蓋舊價"""
    # 模擬抓新價 100、舊價 50
    fresh = pd.DataFrame([
        {"股票代號": "3188", "現價": 100.0, "成交量_張": 500.0},
    ])
    price_df = pd.DataFrame([
        {"股票代號": "3188", "現價": 50.0, "成交量_張": 1000.0},
        {"股票代號": "3546", "現價": 82.0, "成交量_張": 800.0},
    ])

    # merge：新價覆蓋舊價（3188 變 100、3546 保持 82）
    merged = price_df.merge(
        fresh[["股票代號", "現價", "成交量_張"]],
        on="股票代號", how="left", suffixes=("", "_new")
    )
    # 如果有 _new 欄位、用 _new 覆蓋
    if "現價_new" in merged.columns:
        merged["現價"] = merged["現價_new"].fillna(merged["現價"])
        merged = merged.drop(columns=["現價_new"])
    if "成交量_張_new" in merged.columns:
        merged["成交量_張"] = merged["成交量_張_new"].fillna(merged["成交量_張"])
        merged = merged.drop(columns=["成交量_張_new"])

    row_3188 = merged[merged["股票代號"] == "3188"].iloc[0]
    row_3546 = merged[merged["股票代號"] == "3546"].iloc[0]
    assert row_3188["現價"] == 100.0, f"3188 應被新價 100 覆蓋，實際: {row_3188['現價']}"
    assert row_3546["現價"] == 82.0, f"3546 應保持舊價 82，實際: {row_3546['現價']}"


if __name__ == "__main__":
    test_checkbox_預設False()
    print("✅ test_checkbox_預設False passed")
    test_勾選時會呼叫_finmind_price_batch()
    print("✅ test_勾選時會呼叫_finmind_price_batch passed")
    test_股價merge邏輯_新價覆蓋舊價()
    print("✅ test_股價merge邏輯_新價覆蓋舊價 passed")
    print("\n🎉 All refresh-price tests passed!")
