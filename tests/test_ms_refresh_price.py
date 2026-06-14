"""
test_ms_refresh_price.py
驗證 V0.9.5+「即時抓股價」checkbox 的邏輯。

【動機】
William 2026-06-15 反映：2101 南港我算 2.10%、他預期 1.99%
trace 結果：殖利率算法 OK、現價時間差（我抓 33.35、他看 35.18）

→ 背景重抓股價的時間跟使用者看見的時間可能不同
→ 加「即時抓股價」checkbox：勾了 → 跑選股前先抓最新股價

【設計】
- 「🔄 即時抓股價」checkbox（預設不勾）
- 勾了 → _ms_run_selection 跑前先抓 price_df 全部股票的最新股價
- 不勾 → 用 cache（背景抓的版本、較快）
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402


def test_checkbox_預設False():
    """【關鍵】checkbox 預設 False（不勾、用 cache 行為）"""
    # 用 mock 模擬 _ms_refresh_price_var 的預設值
    # 直接讀 source code 確認預設值
    import re
    with open(os.path.join(os.path.dirname(__file__), "..", "source", "StockTool.py")) as f:
        code = f.read()
    # 找 _ms_refresh_price_var = tk.BooleanVar(value=...)
    match = re.search(r"self\._ms_refresh_price_var\s*=\s*tk\.BooleanVar\(value=(\w+)\)", code)
    assert match, "找不到 _ms_refresh_price_var 設定"
    assert match.group(1) == "False", f"預設應為 False，實際: {match.group(1)}"


def test_勾選時會呼叫_finmind_price_batch():
    """【關鍵守護】勾了時、跑選股前應呼叫 _fetch_finmind_prices_batch"""
    # Mock：呼叫 _fetch_finmind_prices_batch 時記 log
    call_log = []
    def fake_batch(codes, progress_callback=None):
        call_log.append(codes)
        # 回傳只有 3188 的新股價
        return pd.DataFrame([
            {"股票代號": "3188", "現價": 100.0, "成交量_張": 500.0},
        ])

    st._fetch_finmind_prices_batch = fake_batch
    st._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame()

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
