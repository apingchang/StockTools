"""
stocktool.scoring - 選股評分系統
==================================

v1.1 重構：把評分函數從 StockTool.py 抽出

包含：
- _run_manual_selection（手動選股條件篩選）
- calculate_multi_factor_score（多因子評分、預設）
- calculate_enhanced_score（Enhanced 評分）
- calculate_simple_score（簡易評分）

被依賴：pipeline.py / gui/tab_strategy.py / gui/tab_manual.py
依賴：config.py
"""

from __future__ import annotations

import os
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd
import numpy as np

from .config import StrategyConfig, GuiLogger
from .fetch_market import (
    fetch_prices,
    fetch_revenue_latest,
    fetch_eps_latest,
    _fetch_market_stock_list,
    _fetch_finmind_prices_batch,
)


def _run_manual_selection(
    price_df: pd.DataFrame,      # 來自 pipeline 的股價資料 [股票代號, 股價, ...]
    revenue_df: pd.DataFrame,     # 來自 pipeline 的營收資料 [股票代號, 累計營收YoY(%), ...]
    eps_df: pd.DataFrame,         # 來自 pipeline 的 EPS 資料 [股票代號, EPS本期, ...]
    filters: dict,
    top_n: int = 500,
) -> pd.DataFrame:
    """
    根據 filters 條件，從已知的市場股票中篩選並回傳結果。

    filters 格式：
        {
            "min_rev_yoy": 10.0,          # 累計營收 YoY >= 此值（None = skip）
            "min_pe": None,                # PE <= 此值（None = skip）
            "min_price": None,             # 現價 >= 此值（None = skip）
            "min_volume": None,            # 成交量(張) >= 此值（None = skip）
            "min_bvps": None,             # 淨值 >= 此值（None = skip，暫不支援）
            "min_cash_div": None,          # 今年現金股利 >= 此值（None = skip）
            "min_stock_div": None,         # 今年股票股利 >= 此值（None = skip）
            "min_last_cash_div": None,     # 去年現金股利 >= 此值（None = skip）
            "min_last_stock_div": None,    # 去年股票股利 >= 此值（None = skip）
            "sort_by": ["rev_yoy", "stock_div", "cash_div", "pe"],
        }
    """
    # 1. 取得全市場股票代號與名稱
    # 優先用 pipeline 的 price_df；若為空才 fallback 抓全市場名單
    price_df = price_df.copy() if price_df is not None else pd.DataFrame()
    if price_df.empty:
        base = _fetch_market_stock_list()
    else:
        if "公司名稱_來源" in price_df.columns:
            name_col = "公司名稱_來源"
        else:
            name_col = [c for c in price_df.columns if "名稱" in c or "name" in c.lower()]
            name_col = name_col[0] if name_col else None

        price_cols = ["股票代號"]
        if name_col:
            price_cols.append(name_col)
        # 如果 cache 也有「股價」或「現價」也一起拉進來
        # 【v1.0-info】data_date 也要帶進來（Treeview 「資料日期」欄位用）
        # 【V1.1-remove-after-hour】拿掉「盤後量_股」（欄位已從 Treeview 拿掉）
        for cc in ["股價", "現價", "成交量", "成交量_張", "漲跌", "data_date"]:
            if cc in price_df.columns and cc not in price_cols:
                price_cols.append(cc)
        base = price_df[price_cols].drop_duplicates("股票代號").copy()
        base["股票代號"] = base["股票代號"].astype(str).str.strip()
        if name_col:
            base = base.rename(columns={name_col: "股票名稱"})
        else:
            base["股票名稱"] = ""
        # 統一欄位名：「股價」→「現價」、「成交量_張」不變
        if "股價" in base.columns and "現價" not in base.columns:
            base = base.rename(columns={"股價": "現價"})

    # 2. 取得現價：若 base 已有「現價」就用 cache，不抓 FinMind
    if "現價" in base.columns:
        # 已有現價（來自 cache），不重抓 FinMind
        # cache 不一定有成交量，若沒有則先移除「成交量」條件
        if "成交量_張" not in base.columns:
            base["成交量_張"] = None  # None 表示 cache 沒資料
        # 【V1.1-remove-after-hour】拿掉「盤後量_股」補 None 邏輯（欄位已拿掉）
        # 「漲跌」欄位只在 cache 才有，移到後面
    else:
        all_codes = base["股票代號"].tolist()
        price_finmind = _fetch_finmind_prices_batch(all_codes)
        if not price_finmind.empty:
            base = base.merge(price_finmind, on="股票代號", how="left")
        else:
            base["現價"] = None
            base["成交量_張"] = 0

    # 3. 合併營收 YoY（容錯：空 df 跳過）
    if not revenue_df.empty and "股票代號" in revenue_df.columns:
        revenue_df = revenue_df.copy()
        revenue_df["股票代號"] = revenue_df["股票代號"].astype(str).str.strip()
        rev_cols = ["股票代號", "營收YoY(%)"]
        rev_cols = [c for c in rev_cols if c in revenue_df.columns]
        if len(rev_cols) == 2:
            base = base.merge(revenue_df[rev_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "營收YoY(%)" not in base.columns:
        base["營收YoY(%)"] = None

    # 4. 合併 EPS（容錯：空 df 跳過）
    if not eps_df.empty and "股票代號" in eps_df.columns:
        eps_df = eps_df.copy()
        eps_df["股票代號"] = eps_df["股票代號"].astype(str).str.strip()
        eps_cols = ["股票代號", "EPS本期"]
        eps_cols = [c for c in eps_cols if c in eps_df.columns]
        if len(eps_cols) == 2:
            base = base.merge(eps_df[eps_cols].drop_duplicates("股票代號"),
                              on="股票代號", how="left")
    if "EPS本期" not in base.columns:
        base["EPS本期"] = None

    # 5. 計算 PE
    # 注：EPS 接近 0 會讓 PE 爆炸（ex: EPS=0.01、股價=24 → PE=2400）
    #     設 PE = None 讓使用者看到 --，比看到「3000 倍 PE」合理
    # 門檻：EPS >= 0.05 元視為有意義的獲利能力（低於 0.05 視為雞蛋水餃股）
    PE_MIN_EPS = 0.05
    base["PE"] = None
    pe_mask = (
        (base["現價"].notna()) & (base["現價"] > 0)
        & (base["EPS本期"].notna()) & (base["EPS本期"] >= PE_MIN_EPS)
    )
    base.loc[pe_mask, "PE"] = (base.loc[pe_mask, "現價"] / base.loc[pe_mask, "EPS本期"]).round(2)

    # 6. 抓 FinMind 股利（會用 DB 快取，只在 DB 沒有的才抓 FinMind）
    all_codes = base["股票代號"].tolist()
    # 【v1.1 重構】用模組存取取代直接名稱、避免 monkeypatch st_fetch_market 後找不到
    from stocktool import fetch_market as _fm_ms
    div_df = _fm_ms._fetch_finmind_dividend(all_codes, skip_remote=True)
    if not div_df.empty:
        base = base.merge(div_df, on="股票代號", how="left")
    else:
        cy = datetime.now().year
        for suf in [f"{cy}現金股利", f"{cy}股票股利",
                    f"{cy - 1}現金股利", f"{cy - 1}股票股利",
                    f"{cy - 2}現金股利", f"{cy - 2}股票股利",
                    f"{cy - 1}除息日", f"{cy - 1}除息日收盤價",
                    # V0.9.5-goodinfo：殖利率欄位
                    f"{cy}現金殖利率_goodinfo", f"{cy}股票殖利率_goodinfo",
                    f"{cy - 1}現金殖利率_goodinfo", f"{cy - 1}股票殖利率_goodinfo",
                    f"{cy - 2}現金殖利率_goodinfo", f"{cy - 2}股票殖利率_goodinfo"]:
            if suf not in base.columns:
                base[suf] = None

    # 7. 今年/去年現金股利欄位（干擾名稱，用固定名）
    # 【V0.9.5-goodinfo 修 Bug】2026-06-16 William 反映：
    #   - 群聯 (8299) 半年配：App 原本「今年」= DB year=cy-1=2025=31.31
    #     但 goodinfo 2026 支付年 = 16.96 (2026 H1 只配了一半、H2 還沒)
    #   - 原設計「cy-1 = 該年除息」是 fiscal year 語意 → 半年配/季配會跟 goodinfo 不一致
    #   - 修法：改用「cy = 該年除息」= payment year 語意，跟 goodinfo「發放年度」一致
    #     讓使用者看到的「今年現金股利」= 今年實際收到的股利金額
    #   - 範例：cy=2026
    #     * 今年 (cy) = DB year=2026 = goodinfo 2026 = 「2026 收到的股利」
    #     * 去年 (cy-1) = DB year=2025 = goodinfo 2025 = 「2025 收到的股利」
    #     * 前年 (cy-2) = DB year=2024 = goodinfo 2024 = 「2024 收到的股利」
    cy = datetime.now().year
    base["今年現金股利"] = base.get(f"{cy}現金股利", None)
    base["今年股票股利"] = base.get(f"{cy}股票股利", None)
    base["去年現金股利"] = base.get(f"{cy - 1}現金股利", None)
    base["去年股票股利"] = base.get(f"{cy - 1}股票股利", None)
    # 前年度（保留給 UI 顯示）
    base["前年現金股利"] = base.get(f"{cy - 2}現金股利", None)
    base["前年股票股利"] = base.get(f"{cy - 2}股票股利", None)
    # V0.9.5+ Phase 10：去年除息日 + 除息日收盤價（供除息價 fallback 用）
    # 【V0.9.5-goodinfo 配合修改】去年 = cy-1 = DB year=cy-1
    base["去年除息日"] = base.get(f"{cy - 1}除息日", None)
    base["去年除息日收盤價"] = base.get(f"{cy - 1}除息日收盤價", None)
    # V0.9.5-goodinfo：殖利率原始值（goodinfo 來源）— 殖利率直接用、不計算
    base["今年現金殖利率_goodinfo"] = base.get(f"{cy}現金殖利率_goodinfo", None)
    base["今年股票殖利率_goodinfo"] = base.get(f"{cy}股票殖利率_goodinfo", None)
    base["去年現金殖利率_goodinfo"] = base.get(f"{cy - 1}現金殖利率_goodinfo", None)
    base["去年股票殖利率_goodinfo"] = base.get(f"{cy - 1}股票殖利率_goodinfo", None)

    # 8. 今年現金殖利率（V0.9.5-goodinfo6+++ 改：cash / 現價 × 100，不用 goodinfo）
    # 【William 2026-06-26 14:18 反映】「2026 漲利率不能從 goodinfo 抓、要用現價去計算！」
    #   - goodinfo 殖利率是用「除息基準日還原價」算的、是歷史值
    #   - 9946 樣本：goodinfo cyld=6.9% 但除息日未公布、現價 29 → cash 1.37 = 4.72%
    #   - 過去歷史殖利率仍用 goodinfo（已除息完成、有歷史價）
    #   - 今年殖利率要反映「現價 × 今年現金股利」、使用者看得到即時意義
    #   - cash=0 也要算 → 結果 0.0%
    base["今年現金殖利率(%)"] = None
    if "現價" not in base.columns:
        base["現價"] = None
    yld_mask = (
        base["現價"].notna() & (base["現價"] > 0)
        & base["今年現金股利"].notna()
    )
    base.loc[yld_mask, "今年現金殖利率(%)"] = (
        (base.loc[yld_mask, "今年現金股利"] / base.loc[yld_mask, "現價"]) * 100
    ).round(2)

    # 9. 去年現金殖利率（V0.9.5-goodinfo3：100% 用 goodinfo、不走 cash/現價 fallback）
    # 【原本】cash=0 → continue 跳過 → 殖利率 None（5386 去年現金殖利率 bug）
    # 【修正】cash=0 也要看 goodinfo 有沒有殖利率值、有就直接用
    for col in ["去年除息日", "去年除息日收盤價"]:
        if col not in base.columns:
            base[col] = None
    base["去年現金殖利率(%)"] = None
    goodinfo_last_mask = base["去年現金殖利率_goodinfo"].notna()
    base.loc[goodinfo_last_mask, "去年現金殖利率(%)"] = (
        base.loc[goodinfo_last_mask, "去年現金殖利率_goodinfo"].round(2)
    )

    # 9.5 V0.9.5-goodinfo：今年/去年股票殖利率（直接用 goodinfo 提供）
    base["今年股票殖利率(%)"] = None
    base["去年股票殖利率(%)"] = None
    sy_mask_this = base["今年股票殖利率_goodinfo"].notna()
    base.loc[sy_mask_this, "今年股票殖利率(%)"] = (
        base.loc[sy_mask_this, "今年股票殖利率_goodinfo"].round(2)
    )
    sy_mask_last = base["去年股票殖利率_goodinfo"].notna()
    base.loc[sy_mask_last, "去年股票殖利率(%)"] = (
        base.loc[sy_mask_last, "去年股票殖利率_goodinfo"].round(2)
    )

    # 10. 應用篩選條件（V0.9.5+ B 邏輯修正版）
    #     【關鍵修正】2026-06-14 William 反映「YoY < 30 還跑出來」
    #
    #     【原本的 BUG（V0.9.5-alpha 5th commit）】
    #     - 拿掉 AND mask、只用 data_score > 0 過濾
    #     - 結果：YoY 沒過、但殖利率/PE/現價/成交量過的股票也被納入
    #     - 截圖實例：1810 和成（YoY -7.42）被納入
    #
    #     【本版的設計】
    #     - 硬條件（YoY、PE、現價、成交量、股利金額）：AND mask
    #       - None 一律算 fail（資料缺漏不能說達標）
    #       - 不過門檻也算 fail
    #     - 軟條件（今年/去年現金殖利率）：不擋 mask
    #       - 殖利率 None：不擋 mask（其他條件過了還是納入）
    #       - 殖利率有值未達標：不擋 mask（其他條件過了還是納入）
    #       - 殖利率達標：拿來算排序分數
    #     - 排序：殖利率有值 > 殖利率高 > 股票股利高 > 營收 YoY 高 > PE 低
    #     - 「至少要有一個篩選 item 過關」= 任何被勾選的硬條件至少要過一個
    #       （全 None、全未達 → 全排除 → 結果為空）
    #     - 沒結果會在 caller 判斷並提示「這次篩選沒有合格股票」
    mask = pd.Series([True] * len(base), index=base.index)
    any_checked = False  # 記錄是否有任何被勾選的條件

    # 累計營收 YoY ≥ X（硬）
    if filters.get("min_rev_yoy") is not None:
        any_checked = True
        rev = base["營收YoY(%)"]
        mask &= rev.notna() & (rev >= filters["min_rev_yoy"])

    # PE ≤ X（硬，filters key 是 min_pe 但語意是「PE 不超過」）
    if filters.get("min_pe") is not None:
        any_checked = True
        pe = base["PE"]
        mask &= pe.notna() & (pe <= filters["min_pe"])

    # 現價 ≥ X（硬）
    if filters.get("min_price") is not None:
        any_checked = True
        price = base["現價"]
        mask &= price.notna() & (price > 0) & (price >= filters["min_price"])

    # 月均成交量 ≥ X（硬）
    if filters.get("min_volume") is not None:
        any_checked = True
        vol = base["成交量_張"]
        mask &= vol.notna() & (vol >= filters["min_volume"])

    # 今年現金股利 ≥ X（元）（硬）
    if filters.get("min_cash_div") is not None:
        any_checked = True
        cd = base["今年現金股利"]
        mask &= cd.notna() & (cd >= filters["min_cash_div"])

    # 今年股票股利 ≥ X（元）（硬）
    if filters.get("min_stock_div") is not None:
        any_checked = True
        sd = base["今年股票股利"]
        mask &= sd.notna() & (sd >= filters["min_stock_div"])

    # 去年現金股利 ≥ X（元）（硬）
    if filters.get("min_last_cash_div") is not None:
        any_checked = True
        cd = base["去年現金股利"]
        mask &= cd.notna() & (cd >= filters["min_last_cash_div"])

    # 去年股票股利 ≥ X（元）（硬）
    if filters.get("min_last_stock_div") is not None:
        any_checked = True
        sd = base["去年股票股利"]
        mask &= sd.notna() & (sd >= filters["min_last_stock_div"])

    # 今年現金殖利率 ≥ X%（軟：不擋 mask、只算排序）
    if filters.get("min_cash_div_yld") is not None:
        any_checked = True
        # 不動 mask、留給排序處理

    # 去年現金殖利率 ≥ X%（軟：不擋 mask、只算排序）
    # 【V0.9.5-alpha Phase 6 修 Bug】2026-06-15
    # 原本以「data_score / pass_score 雙計分」實作（舊 B 邏輯），
    # 但 Phase 4 已改成「硬 AND + 軟不擋 mask」邏輯，data_score/pass_score
    # 從未被初始化，導致勾選「去年現金殖利率 ≥ X%」時 UnboundLocalError，
    # 整個手動選股流程崩潰。
    # 修法：跟「今年現金殖利率」一樣的 no-op（只設 any_checked=True），
    # 排序階段用 _yld_has_data 自然處理殖利率有/無資料的排序。
    if filters.get("min_last_cash_yld") is not None:
        any_checked = True
        # 不動 mask、留給排序處理

    # 過濾：硬條件 AND mask（楊重複保險，殖利率軟條件不擋 mask）
    # 注：如果是「什麼都沒勾」的情況、保留全部（向後相容）
    if any_checked:
        result = base[mask].copy()
    else:
        result = base.copy()

    # 11. 排序：殖利率有值 > 殖利率高 > 股票股利高 > 營收 YoY 高 > PE 低
    # 【重點】殖利率有資料（vs None）排前面、殖利率高的排前面、None 排後面
    # V0.9.5-goodinfo3：拿掉 10Y 平均殖利率 sort key（William 不需要）
    # 【V0.9.5-goodinfo4+5 修 Bug】2026-06-18 18:12 William 反映：
    #   「順便將篩選結果依照營收累計YoY由大到小排序」
    #   → 主要 sort 改為營收累計YoY 降序（高增長排前面）
    #   → 原本是「殖利率 > 股票股利 > 營收YoY > PE」、現在改成「營收YoY > 殖利率 > 股票股利 > PE」
    result["_yld_has_data"] = result["今年現金殖利率(%)"].notna().astype(int)
    # 殖利率直接作 sort key、不加負號→降序時殖利率高排前
    result["_sort_yld"] = result["今年現金殖利率(%)"].fillna(-9999)
    result["_sort_rev"] = result["營收YoY(%)"].fillna(-9999)
    result["_sort_stock"] = result["今年股票股利"].fillna(0)
    result["_sort_pe"] = result["PE"].fillna(9999)

    result = result.sort_values(
        # 主排序：營收累計YoY 降序、其次殖利率、再來股票股利、最後 PE
        ["_sort_rev", "_yld_has_data", "_sort_yld", "_sort_stock", "_sort_pe"],
        ascending=[False, False, False, False, True]
    ).reset_index(drop=True)

    result = result.head(top_n).reset_index(drop=True)

    # 12. 整理輸出欄位
    out_cols = ["股票代號", "股票名稱", "現價", "營收YoY(%)",
                "今年股票股利", "今年現金殖利率(%)", "PE",
                "成交量_張", "今年現金股利",
                "去年現金股利", "去年股票股利", "去年現金殖利率(%)", "EPS本期",
                f"{cy}現金股利", f"{cy - 1}現金股利", f"{cy - 2}現金股利",
                # V0.9.5-goodinfo3：殖利率加強欄位（10Y 平均殖利率已拿掉，William 不需要）
                "今年股票殖利率(%)", "去年股票殖利率(%)",
                "漲跌",
                "data_date"]  # 【v1.0-info】Treeview 「資料日期」欄位用
    out_cols = [c for c in out_cols if c in result.columns]
    # 整理重複的現金股利（保留乾淨的今年/去年/前年）
    result = result[out_cols].rename(columns={
        "成交量_張": "成交量(張)",
        f"{cy}現金股利": "今年現金股利_原始",
        f"{cy - 1}現金股利": "去年現金股利_原始",
        f"{cy - 2}現金股利": "前年現金股利_原始",
    })
    # 還原乾淨名稱
    result = result.rename(columns={
        "今年現金股利_原始": "今年現金股利_原始",
    })
    # 重新整理輸出（最終顯示欄位）
    # 先把「營收YoY(%)」改名為「累計營收YoY(%)」供 Treeview 顯示
    result = result.rename(columns={"營收YoY(%)": "累計營收YoY(%)"})
    final_cols = ["股票代號", "股票名稱", "現價", "漲跌",  # 【V1.1-add-change-col】手動選股加「顀跌價」需要這欄
                  "累計營收YoY(%)",
                  "今年股票股利", "今年現金股利", "今年現金殖利率(%)",
                  "去年股票股利", "去年現金股利", "去年現金殖利率(%)",
                  "今年股票殖利率(%)", "去年股票殖利率(%)",
                  "PE", "成交量(張)", "EPS本期",
                  "data_date"]  # 【v1.0-info】Treeview 「資料日期」欄位用
    final_cols = [c for c in final_cols if c in result.columns]
    return result[final_cols].rename(columns={
        "今年現金股利": "今年現金股利_原始",
        "去年現金股利": "去年現金股利_原始",
    }).rename(columns={
        "今年現金股利_原始": "今年現金股利(元)",
        "去年現金股利_原始": "去年現金股利(元)",
        "今年股票股利": "今年股票股利(元)",
        "去年股票股利": "去年股票股利(元)",
    })


# ==========================================================
# 通用工具
# ==========================================================

def format_for_output(df: pd.DataFrame, sort_by_code: bool = True) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "股票代號" in df.columns:
        df["股票代號"] = df["股票代號"].astype(str).str.strip()
    if "股票代號" in df.columns and "公司名稱_來源" in df.columns:
        cols = ["股票代號", "公司名稱_來源"] + [c for c in df.columns if c not in ["股票代號", "公司名稱_來源"]]
        df = df[cols]
    if sort_by_code and "股票代號" in df.columns:
        df["股票代號_sort"] = df["股票代號"].astype(str).str.extract(r'(\d+)').astype(int)
        df = df.sort_values("股票代號_sort", ascending=True).drop(columns=["股票代號_sort"])
    return df.reset_index(drop=True)


def ensure_str_column(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).str.strip()
    return df
# ==========================================================
# 多因子評分函數
# ==========================================================

def calculate_multi_factor_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    # ✅ 新增：處理異常值
    df["營收YoY(%)"] = df["營收YoY(%)"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_顯示(%)"] = df["EPSYoY_顯示(%)"].replace([float("inf"), -float("inf")], pd.NA)

    if "Close" in df.columns:
        df["mom_1m"] = df.groupby("股票代號")["Close"].pct_change(21) * 100
        df["mom_3m"] = df.groupby("股票代號")["Close"].pct_change(63) * 100
        df["mom_6m"] = df.groupby("股票代號")["Close"].pct_change(126) * 100
    else:
        df["mom_1m"] = 0
        df["mom_3m"] = 0
        df["mom_6m"] = 0

    factors = ['mom_1m', 'mom_3m', 'mom_6m', '營收YoY(%)', 'EPSYoY_顯示(%)']
    for f in factors:
        if f in df.columns:
            mean_val = df[f].mean()
            std_val = df[f].std()
            if std_val > 0:
                df[f"{f}_zscore"] = (df[f] - mean_val) / std_val
            else:
                df[f"{f}_zscore"] = 0

    df["Score"] = (df["mom_1m_zscore"].fillna(0) * cfg.factor_weight_mom1 +
                   df["mom_3m_zscore"].fillna(0) * cfg.factor_weight_mom3 +
                   df["mom_6m_zscore"].fillna(0) * cfg.factor_weight_mom6 +
                   df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev +
                   df["EPSYoY_顯示(%)_zscore"].fillna(0) * cfg.factor_weight_eps)
    df["Score"] = df["Score"].round(2)
    df["評分_動能1M"] = df["mom_1m_zscore"].fillna(0).round(2)
    df["評分_動能3M"] = df["mom_3m_zscore"].fillna(0).round(2)
    df["評分_動能6M"] = df["mom_6m_zscore"].fillna(0).round(2)
    df["評分_成長"] = (df["營收YoY(%)_zscore"].fillna(0) * cfg.factor_weight_rev * 4).round(2)
    return df


def calculate_enhanced_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    return calculate_multi_factor_score(df, cfg)


def calculate_simple_score(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    df = df.copy()

    df["PE"] = df["PE"].replace([float("inf"), -float("inf")], pd.NA)
    df["EPSYoY_raw"] = df["EPSYoY_raw"].replace([float("inf"), -float("inf")], pd.NA)

    # ========== DEBUG: 簡易評分診斷 ==========
    print("\n" + "=" * 60)
    print("🔍 [DEBUG] calculate_simple_score 診斷")
    print("=" * 60)

    print(f"\n📊 原始資料筆數: {len(df)}")
    print(f"📊 有營收YoY資料的筆數: {df['營收YoY(%)'].notna().sum()}")
    print(f"📊 有EPS本期資料的筆數: {df['EPS本期'].notna().sum()}")
    print(f"📊 有EPSYoY_raw資料的筆數: {df['EPSYoY_raw'].notna().sum()}")
    print(f"📊 有PE資料的筆數: {df['PE'].notna().sum()}")

    print(f"\n⚙️ 目前門檻設定:")
    print(f"   simple_min_rev_yoy = {cfg.simple_min_rev_yoy}")
    print(f"   simple_min_eps_yoy = {cfg.simple_min_eps_yoy}")
    print(f"   simple_min_eps = {cfg.simple_min_eps}")
    print(f"   simple_max_pe = {cfg.simple_max_pe}")
    # ========== DEBUG 結束 ==========

    mask = pd.Series([True] * len(df))

    if cfg.simple_min_rev_yoy > -998:
        rev_ok = df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy
        mask = mask & rev_ok

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_ok = (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy
        mask = mask & eps_yoy_ok

    if cfg.simple_min_eps > -998:
        eps_ok = df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps
        mask = mask & eps_ok

    if cfg.simple_max_pe < 998:
        pe_ok = df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe
        mask = mask & pe_ok

    # ========== DEBUG: 門檻通過數量 ==========
    print(f"\n✅ 各門檻通過數量:")
    if cfg.simple_min_rev_yoy > -998:
        rev_pass = (df["營收YoY(%)"].fillna(cfg.simple_min_rev_yoy - 1) >= cfg.simple_min_rev_yoy).sum()
        print(f"   營收門檻 (>= {cfg.simple_min_rev_yoy}%): {rev_pass} 檔")
    else:
        print(f"   營收門檻: 未啟用")

    if cfg.simple_min_eps_yoy > -998:
        eps_yoy_pass = (
                    (df["EPSYoY_raw"].fillna(cfg.simple_min_eps_yoy / 100 - 1) * 100) >= cfg.simple_min_eps_yoy).sum()
        print(f"   EPS YoY 門檻 (>= {cfg.simple_min_eps_yoy}%): {eps_yoy_pass} 檔")
    else:
        print(f"   EPS YoY 門檻: 未啟用")

    if cfg.simple_min_eps > -998:
        eps_pass = (df["EPS本期"].fillna(cfg.simple_min_eps - 1) >= cfg.simple_min_eps).sum()
        print(f"   EPS 門檻 (>= {cfg.simple_min_eps}元): {eps_pass} 檔")
    else:
        print(f"   EPS 門檻: 未啟用")

    if cfg.simple_max_pe < 998:
        pe_pass = (df["PE"].fillna(cfg.simple_max_pe + 1) <= cfg.simple_max_pe).sum()
        print(f"   PE 門檻 (<= {cfg.simple_max_pe}倍): {pe_pass} 檔")
    else:
        print(f"   PE 門檻: 未啟用")

    print(f"\n🎯 最終通過所有門檻的股票數量: {mask.sum()} 檔")

    if mask.sum() == 0 and len(df) > 0:
        print(f"\n⚠️ 前5筆未通過股票的診斷:")
        failed_df = df[~mask].head(5)
        for idx, row in failed_df.iterrows():
            code = row.get("股票代號", "N/A")
            name = str(row.get("公司名稱_來源", "N/A"))[:20]
            rev = row.get("營收YoY(%)", "N/A")
            eps_yoy_raw = row.get("EPSYoY_raw", "N/A")
            eps = row.get("EPS本期", "N/A")
            pe = row.get("PE", "N/A")
            print(f"   {code} {name} | 營收:{rev}% | EPS YoY:{eps_yoy_raw} | EPS:{eps} | PE:{pe}")
    # ========== DEBUG 結束 ==========

    rev_score = df["營收YoY(%)"].fillna(0)
    eps_score = (df["EPSYoY_raw"].fillna(0) * 100)
    div_score = df["殖利率(估)"].fillna(0) * 100
    pe_score = df["PE"].fillna(0)

    w_rev = cfg.simple_score_weight_rev
    w_eps = cfg.simple_score_weight_eps
    w_div = cfg.simple_score_weight_div
    w_pe = cfg.simple_score_weight_pe

    df["Score_raw"] = (rev_score * (w_rev / 100) +
                       eps_score * (w_eps / 100) +
                       div_score * (w_div / 100) +
                       pe_score * (w_pe / 100))

    df["Score"] = df["Score_raw"].where(mask, pd.NA)
    df["通過門檻"] = mask

    print("\n" + "=" * 60 + " DEBUG 結束 " + "=" * 60 + "\n")

    return df


# ==========================================================
# 強化版技術指標
# ==========================================================

