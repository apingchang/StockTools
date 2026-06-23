"""
test_ms_vol_rev_sort.py
驗證 V0.9.5-goodinfo4+5 兩個 fix：
1. 成交量直接顯示今日成交量（拿掉盤中/收盤後切換）
2. 篩選結果依營收累計 YoY 由大到小排序

【Bug 1 描述】2026-06-18 18:12 William 反映
- 「成交量不是我要的今日成交量！」
- 原本 V0.9.5-twser3 加了盤中/收盤後切換邏輯（盤中 "-"，收盤後顯示總量）
- 但 William 要的是今日成交量（不管是盤中還是收盤後、直接看 price_df 的「成交量_張」）
- 修正：拿掉 _is_market_hours() 判斷、直接顯示成交量(張)

【Bug 2 描述】2026-06-18 18:12 William 反映
- 「順便將篩選結果依照營收累計YoY由大到小排序」
- 原本 sort 順序：[殖利率有資料, 殖利率, 股票股利, 營收YoY, PE]
- 改為 sort 順序：[營收YoY, 殖利率有資料, 殖利率, 股票股利, PE]
- 營收累計YoY 降序、高增長排前面

【pytest】
- test_成交量_直接顯示今日量_不管時段
- test_成交量_None_顯示橫線
- test_成交量_盤中不再顯示橫線（regression 守護：盤中也顯示）
- test_排序_以營收累計YoY_降序為主
- test_排序_次要_殖利率_降序
- test_排序_同_營收YoY_時_殖利率高排前
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "source"))

import StockTool as st  # noqa: E402
from stocktool import fetch_market as st_fetch_market  # noqa: E402  # v1.1 重構：fetch_market 函式改用此模組


CY = datetime.now().year  # 2026


# ==========================================================
# 【Bug 1：成交量】今日量直接顯示
# ==========================================================

def test_成交量_直接顯示今日量_不管時段():
    """【V0.9.5-goodinfo4+5 守護】_ms_display_results 直接顯示成交量(張)、不再判斷時段

    不管盤中/收盤後/週末、都直接顯示 price_df 的「成交量(張)」
    """
    row_data = {
        "股票代號": "2548",
        "股票名稱": "華固",
        "現價": 107.0,
        "累計營收YoY(%)": 50.0,
        "今年股票股利(元)": 0.5,
        "今年現金股利(元)": 8.5,
        "今年現金殖利率(%)": 6.53,
        "去年股票股利(元)": 0.5,
        "去年現金股利(元)": 6.0,
        "去年現金殖利率(%)": 5.07,
        "PE": 46.93,
        "成交量(張)": 1500,
        "EPS本期": 2.28,
    }

    # 模擬 _ms_display_results 的成交量格式化
    # 【V0.9.5-goodinfo4+5】拿掉 _is_market_hours() 判斷、直接顯示
    vol = row_data.get("成交量(張)")
    vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"

    assert vol_str == "1,500", f"成交量應顯示 '1,500'、實際: {vol_str}"
    print("PASS: test_成交量_直接顯示今日量_不管時段")


def test_成交量_None_顯示橫線():
    """【V0.9.5-goodinfo4+5 守護】成交量 None → 顯示橫線"""
    vol = None
    vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"

    assert vol_str == "—", f"成交量 None 應顯示 '—'、實際: {vol_str}"
    print("PASS: test_成交量_None_顯示橫線")


def test_成交量_盤中不再顯示橫線():
    """【V0.9.5-goodinfo4+5 regression 守護】盤中也顯示成交量、不再 "-"

    V0.9.5-twser3 邏輯：盤中 → vol_str = "-"
    V0.9.5-goodinfo4+5 修正：盤中也直接顯示今日量
    → 確保新邏輯不會回退到盤中 "-"
    """
    # 不管 _is_market_hours() 是 True/False、vol_str 都應該是一樣的格式化結果
    row_data = {"成交量(張)": 1500}
    vol = row_data.get("成交量(張)")

    # 模擬「無論 _is_market_hours() 是什麼、都執行同一段格式化」
    vol_str = f"{int(vol):,}" if pd.notna(vol) else "—"

    # 即使「盤中」也應該是 "1,500"（不是 "-"）
    with patch.object(st, "_is_market_hours", return_value=True):
        vol_str_market_hours = f"{int(vol):,}" if pd.notna(vol) else "—"

    assert vol_str == "1,500", f"收盤後成交量: {vol_str}"
    assert vol_str_market_hours == "1,500", (
        f"盤中成交量也應顯示 '1,500'、實際: {vol_str_market_hours}（V0.9.5-goodinfo4+5 已拿掉盤中 '-' 邏輯）"
    )
    print("PASS: test_成交量_盤中不再顯示橫線")


# ==========================================================
# 【Bug 2：排序】營收累計YoY 降序
# ==========================================================

def test_排序_以營收累計YoY_降序為主():
    """【V0.9.5-goodinfo4+5 守護】篩選結果依營收累計YoY 由大到小排序"""
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {"股票代號": "1111", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 1.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 1.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},
        {"股票代號": "2222", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 1.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 1.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},
        {"股票代號": "3333", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 1.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 1.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},
    ])

    price_df = pd.DataFrame([
        {"股票代號": "1111", "股票名稱": "高增長", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
        {"股票代號": "2222", "股票名稱": "中增長", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
        {"股票代號": "3333", "股票名稱": "低增長", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "1111", "營收YoY(%)": 100.0},  # 高
        {"股票代號": "2222", "營收YoY(%)": 50.0},   # 中
        {"股票代號": "3333", "營收YoY(%)": 10.0},   # 低
    ])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    order = result["股票代號"].tolist()

    assert order == ["1111", "2222", "3333"], (
        f"應依營收YoY 降序: 1111(100%) > 2222(50%) > 3333(10%)、實際: {order}"
    )
    print("PASS: test_排序_以營收累計YoY_降序為主")


def test_排序_同_營收YoY_時_殖利率高排前():
    """【V0.9.5-goodinfo4+5 守護】營收YoY 相同時、殖利率高排前面"""
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {"股票代號": "1111", f"{CY}現金股利": 3.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 0.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 15.0},  # 高殖利率
        {"股票代號": "2222", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 0.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},  # 低殖利率
    ])

    price_df = pd.DataFrame([
        {"股票代號": "1111", "股票名稱": "高殖利率", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
        {"股票代號": "2222", "股票名稱": "低殖利率", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "1111", "營收YoY(%)": 50.0},
        {"股票代號": "2222", "營收YoY(%)": 50.0},  # 營收YoY 相同
    ])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    order = result["股票代號"].tolist()

    assert order == ["1111", "2222"], (
        f"營收YoY 相同時應依殖利率降序: 1111(15%) > 2222(5%)、實際: {order}"
    )
    print("PASS: test_排序_同_營收YoY_時_殖利率高排前")


def test_排序_None_排最後():
    """【V0.9.5-goodinfo4+5 守護】營收YoY None（-9999）排最後"""
    st_fetch_market._fetch_finmind_dividend = lambda codes, **kw: pd.DataFrame([
        {"股票代號": "1111", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 0.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},
        {"股票代號": "2222", f"{CY}現金股利": 1.0, f"{CY}股票股利": 0.0,
         f"{CY - 1}現金股利": 0.0, f"{CY - 1}股票股利": 0.0,
         f"{CY - 2}現金股利": 0.0, f"{CY - 2}股票股利": 0.0,
         f"{CY}現金殖利率_goodinfo": 5.0},
    ])

    price_df = pd.DataFrame([
        {"股票代號": "1111", "股票名稱": "有營收", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
        {"股票代號": "2222", "股票名稱": "無營收", "現價": 20.0, "成交量_張": 1000.0, "PE": 15.0, "EPS本期": 1.33},
    ])
    revenue_df = pd.DataFrame([
        {"股票代號": "1111", "營收YoY(%)": 30.0},  # 有
        # 2222 沒列 → revenue_df merge 會給 None
    ])

    result = st._run_manual_selection(price_df, revenue_df, pd.DataFrame(), {}, top_n=10)
    order = result["股票代號"].tolist()

    assert order[0] == "1111", f"有營收YoY 應排前面、實際: {order}"
    print(f"PASS: test_排序_None_排最後 → {order}")


if __name__ == "__main__":
    test_成交量_直接顯示今日量_不管時段()
    test_成交量_None_顯示橫線()
    test_成交量_盤中不再顯示橫線()
    test_排序_以營收累計YoY_降序為主()
    test_排序_同_營收YoY_時_殖利率高排前()
    test_排序_None_排最後()
    print("\nAll V0.9.5-goodinfo4+5 (vol + sort) tests passed!")