"""【V1.1-etf-cache-completeness】fetch_prices 必須回傳全市場清單（不能少）

2026-06-29 21:03 William 反映：
- 「為什麼變成 ETF 選股結果沒有收盤價及漲跌？」
- 截圖時 cache 內只有 1011 筆股票、2330 不在內
- ETF Tab merge 後 2330 收盤價是 NaN → 顯示 --

【根因】
- fetch_prices 抓的時候 MIS 部分失敗 + twse/tpex API 部分失敗
- full_list 從 twse+tpex concat、任一失敗會少一大截
- MIS 又部分成功 → cache 只剩 1011 筆
- 結果：cache 不全、ETF Tab merge 後大部分股票沒股價 → 顯示 --

【修法】
- fetch_prices 內 twse/tpex API 失敗時不該靜默用空 DataFrame
- 必須 retry 或明確告知使用者「資料不全」
- 否則 cache 內容不完整、ETF Tab 顯示殘缺
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
FETCH_MARKET_PY = os.path.join(
    os.path.dirname(__file__), "..", "source", "stocktool", "fetch_market.py"
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_fetch_prices_warns_on_incomplete_market():
    """fetch_prices 內 twse/tpex 抓取失敗必須 retry、不能靜默用空 DataFrame

    Bug：20:04 cache 只有 1011 筆、twse API 失敗但 fetch_prices 靜默用空 DataFrame
    → 結果 cache 內容嚴重不全、ETF Tab 顯示幾乎全部 --

    修法：twse/tpex 抓取失敗時 retry 2 次、間隔 1.5s / 3.0s
    """
    content = _read(FETCH_MARKET_PY)
    # fetch_prices 內整段必須有 retry 字串（twse + tpex 都包在 fetch_prices 函數內）
    fn_start = content.find("def fetch_prices(")
    fn_end = content.find("\ndef ", fn_start + 1)
    fn_body = content[fn_start:fn_end]
    assert "retry" in fn_body, (
        "❌ fetch_prices 內沒看到 retry 邏輯！\n"
        "  V1.1-etf-cache-completeness 修法：twse/tpex 失敗 retry 2 次\n"
        "  不然 twse 失敗 → full_list 變成只剩 tpex 部分 → cache 不全 → ETF Tab 顯示 --"
    )
    # 至少有 2 個 retry（twse 跟 tpex 各一）
    retry_count = fn_body.count("retry")
    assert retry_count >= 2, (
        f"❌ fetch_prices 內 retry 數 {retry_count} 太少（應該 >= 2、twse+tpex 各一）"
    )


def test_save_cache_preserves_dataframe():
    """save_cache 不會過濾或截斷 DataFrame（單元測試避免未來改壞）"""
    from stocktool.cache import save_cache, load_cache, get_cache_file
    import pandas as pd
    import tempfile
    import shutil

    # 建立測試 cache
    test_path = "/tmp/_test_cache.xlsx"
    df = pd.DataFrame({
        "股票代號": ["2330", "2454", "6223"],
        "股價": [2370.0, 3910.0, 6060.0],
        "漲跌": [30.0, 30.0, -440.0],
        "data_date": ["2026-06-29"] * 3,
    })
    save_cache(test_path, df)
    df2, _, _ = load_cache(test_path)
    assert len(df2) == 3, f"save/load 應該保留 3 筆、實際 {len(df2)}"
    os.remove(test_path)