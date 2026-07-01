"""
stocktool.pipeline - 選股流程組合
====================================

v1.1 重構：把選股 / 回測 / 報表的主流程函數從 StockTool.py 抽出

包含：
- _apply_strong_filter（強過濾：營收/PE/現價）
- _run_selection_only（只跑選股）
- run_pipeline（完整流程：選股 + 技術 + 回測 + 報表）

被依賴：gui/tab_strategy.py（按按鈕觸發）
依賴：config.py / fetch_market.py / scoring.py / technical.py / backtest.py / export_excel.py
"""

from __future__ import annotations

import os
import json
import math
import time
import queue
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

import pandas as pd
import numpy as np
import requests

from openpyxl.utils import get_column_letter

from .config import StrategyConfig, GuiLogger, build_session, VERSION
from .fetch_market import (
    fetch_prices,
    fetch_revenue_latest,
    fetch_eps_latest,
    _fetch_finmind_dividend,
)
from .scoring import (
    calculate_multi_factor_score,
    calculate_enhanced_score,
    calculate_simple_score,
    format_for_output,
    ensure_str_column,
)
from .technical import run_tech
from .backtest import (
    portfolio_backtest_topk_event,
    build_gate_map,
    signal_level_backtest_event,
    performance_by_year,
    run_walk_forward,
)
from .cache import get_or_fetch
from .export_excel import (
    autosize_columns,
    style_header,
    write_explanation,
    highlight_true,
    load_stock_list_from_excel,
)


def _apply_strong_filter(df, cfg, logger):
    """【V0.9.5-tab-split-phase3 B-2】套用強勢股過濾

    條件（全部都要符合）：
    - 營收YoY > strong_revenue_yoy
    - EPS 本期 > 0（獲利）
    - PE < strong_pe_max
    - 股價 > strong_price_min

    Args:
        df: 已 sort by Score desc 的 DataFrame
        cfg: StrategyConfig
        logger: GuiLogger

    Returns:
        過濾後的 DataFrame（如果過濾後為空、log warning 並 return 原 df）
    """
    before = len(df)
    mask = (
        (df["營收YoY(%)"] > cfg.strong_revenue_yoy) &
        (df["EPS本期"] > 0) &
        (df["PE"] < cfg.strong_pe_max) &
        (df["股價"] > cfg.strong_price_min)
    )
    filtered = df[mask].copy()
    after = len(filtered)

    if after == 0:
        logger.log(f"⚠️ 強勢股過濾後無股票保留（從 {before} → 0）、使用全部股票")
        return df

    logger.log(
        f"💪 強勢股過濾：{before} → {after} 檔 "
        f"(營收YoY>{cfg.strong_revenue_yoy}% + EPS>0 + PE<{cfg.strong_pe_max} + 股價>{cfg.strong_price_min})"
    )
    return filtered



def _run_selection_only(cfg: StrategyConfig, logger: GuiLogger):
    """【V0.9.5-tab-split-phase3-C Fix2】只做基本面選股、不跑回測

    等同 run_pipeline 的前半段（fetch + merge + 評分 + 強勢股過濾），
    讓「▶ 執行系統選股」快速回應，不回測。
    """
    s = build_session()

    logger.log("=" * 60)
    logger.log(f"🚀 StockTool {VERSION} 篩選模式（不回測）")
    logger.log(f"   評分系統: {'多因子評分' if cfg.use_enhanced_score else '簡易評分'}")
    logger.log("=" * 60)

    logger.log("1) 取得股價資料...")
    price = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
    price = ensure_str_column(price, "股票代號")

    logger.log("2) 取得月營收...")
    revenue = get_or_fetch("revenue", lambda: fetch_revenue_latest(s, cfg), logger)
    revenue = ensure_str_column(revenue, "股票代號")

    logger.log("3) 取得 EPS...")
    eps_data = get_or_fetch("eps", lambda: fetch_eps_latest(s, cfg), logger)
    eps_data = ensure_str_column(eps_data, "股票代號")

    logger.log("4) 合併基本面資料...")
    df_sel = price.merge(revenue, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_data, on="股票代號", how="left")
    df_sel = ensure_str_column(df_sel, "股票代號")

    if "EPSYoY_顯示(%)" in eps_data.columns:
        df_sel["EPSYoY_顯示(%)"] = df_sel["EPSYoY_顯示(%)"]
    else:
        if "EPSYoY_raw" in df_sel.columns:
            df_sel["EPSYoY_顯示(%)"] = (df_sel["EPSYoY_raw"] * 100).fillna(0).round(2)
        else:
            df_sel["EPSYoY_顯示(%)"] = 0

    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # 【v1.1.1+ William 2026-06-24 21:48 反映】
    # 系統選股原本只給「殖利率(估)」(EPS×0.7/股價)、不是實際現金殖利率。
    # 以 3490 為例：估算值 0.04%、實際現金殖利率 1.54%（from GoodInfo）。
    # 修法：跟 manual selection 一樣 fetch FinMind 股利、合併進 df_sel、
    #      並把「殖利率(估)」換成「優先 GoodInfo 殖利率、沒有才估算」。
    logger.log("4.5) 取得股利資料（FinMind DB 快取）...")
    try:
        div_df = _fetch_finmind_dividend(
            df_sel["股票代號"].astype(str).str.strip().tolist(),
            skip_remote=True,  # 只讀 DB、不打 FinMind（避免 rate limit）
        )
        if div_df is not None and not div_df.empty:
            df_sel = df_sel.merge(div_df, on="股票代號", how="left")
            logger.log(f"   股利合併完成：{len(div_df)} 筆")
        else:
            logger.log("   ⚠️ 股利 DB 無資料、殖利率只能走估算")
    except Exception as e:
        logger.log(f"   ⚠️ 讀取股利 DB 失敗：{e}（殖利率只能走估算）")

    # 【V0.9.5-goodinfo6+++】殖利率(估) 優先序改為 cash / 現價，不用 goodinfo
    # 【William 2026-06-26 14:18 反映】「2026 漲利率不能從 goodinfo 抓、要用現價去計算！」
    #   - goodinfo 殖利率是用「除息基準日還原價」算的、是歷史值
    #   - 今年殖利率要反映「現價 × 今年現金股利」
    #   - cash=0 也要算 → 結果 0.0%
    # 過去歷史殖利率仍用 goodinfo（手動選股 scoring.py 那邊仍是）
    cy = datetime.now().year
    cash_col = f"{cy}現金股利"
    price_col = "股價"
    if cash_col in df_sel.columns and price_col in df_sel.columns:
        yld_mask = (
            df_sel[cash_col].notna()
            & df_sel[price_col].notna() & (df_sel[price_col] > 0)
        )
        # 殖利率是小數 (0.069 = 6.9%)
        df_sel.loc[yld_mask, "殖利率(估)"] = (
            df_sel.loc[yld_mask, cash_col] / df_sel.loc[yld_mask, price_col]
        ).round(4)
        logger.log(f"   殖利率：今年現金股利 / 現價（不用 GoodInfo）{yld_mask.sum()} 筆")
    else:
        logger.log("   殖利率：無現金股利或股價、走 EPS×0.7/股價 估算")

    logger.log(f"5) 評分（{'多因子' if cfg.use_enhanced_score else '簡易'}）...")
    if cfg.use_enhanced_score:
        df_sel = calculate_multi_factor_score(df_sel, cfg)
    else:
        df_sel = calculate_simple_score(df_sel, cfg)

    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)
    df_sel = _apply_strong_filter(df_sel, cfg, logger)
    logger.log(f"✅ 篩選完成，共 {len(df_sel)} 檔候選")
    return df_sel


def run_pipeline(cfg: StrategyConfig, logger: GuiLogger):
    s = build_session()

    logger.log("=" * 60)
    logger.log(f"🚀 StockTool {VERSION} 開始執行")
    logger.log(f"   評分系統: {'多因子評分' if cfg.use_enhanced_score else '簡易評分'}")
    logger.log(f"   技術指標: 強化版 (MTF={cfg.use_mtf_confirmation}, 背離={cfg.use_divergence_detection})")
    logger.log("=" * 60)

    logger.log("1) 取得股價資料...")
    price = get_or_fetch("price", lambda: fetch_prices(s, cfg), logger)
    price = ensure_str_column(price, "股票代號")

    logger.log("2) 取得月營收...")
    revenue = get_or_fetch("revenue", lambda: fetch_revenue_latest(s, cfg), logger)
    revenue = ensure_str_column(revenue, "股票代號")

    logger.log("3) 取得 EPS...")
    eps_data = get_or_fetch("eps", lambda: fetch_eps_latest(s, cfg), logger)
    eps_data = ensure_str_column(eps_data, "股票代號")

    logger.log("4) 合併基本面資料...")
    df_sel = price.merge(revenue, on="股票代號", how="left")
    df_sel = df_sel.merge(eps_data, on="股票代號", how="left")
    df_sel = ensure_str_column(df_sel, "股票代號")

    if "EPSYoY_顯示(%)" in eps_data.columns:
        df_sel["EPSYoY_顯示(%)"] = df_sel["EPSYoY_顯示(%)"]
    else:
        if "EPSYoY_raw" in df_sel.columns:
            df_sel["EPSYoY_顯示(%)"] = (df_sel["EPSYoY_raw"] * 100).fillna(0).round(2)
        else:
            df_sel["EPSYoY_顯示(%)"] = 0

    df_sel["PE"] = df_sel["股價"] / df_sel["EPS本期"]
    df_sel["殖利率(估)"] = (df_sel["EPS本期"] * 0.7) / df_sel["股價"]

    # 【v1.1.1+ William 2026-06-24 21:48 反映】run_pipeline 也合併 FinMind 股利資料
    logger.log("4.5) 取得股利資料（FinMind DB 快取）...")
    try:
        div_df = _fetch_finmind_dividend(
            df_sel["股票代號"].astype(str).str.strip().tolist(),
            skip_remote=True,
        )
        if div_df is not None and not div_df.empty:
            df_sel = df_sel.merge(div_df, on="股票代號", how="left")
            logger.log(f"   股利合併完成：{len(div_df)} 筆")
        else:
            logger.log("   ⚠️ 股利 DB 無資料、殖利率只能走估算")
    except Exception as e:
        logger.log(f"   ⚠️ 讀取股利 DB 失敗：{e}（殖利率只能走估算）")

    cy = datetime.now().year
    cash_col = f"{cy}現金股利"
    price_col = "股價"
    if cash_col in df_sel.columns and price_col in df_sel.columns:
        yld_mask = (
            df_sel[cash_col].notna()
            & df_sel[price_col].notna() & (df_sel[price_col] > 0)
        )
        df_sel.loc[yld_mask, "殖利率(估)"] = (
            df_sel.loc[yld_mask, cash_col] / df_sel.loc[yld_mask, price_col]
        ).round(4)
        logger.log(f"   殖利率：今年現金股利 / 現價（不用 GoodInfo）{yld_mask.sum()} 筆")
    else:
        logger.log("   殖利率：無現金股利或股價、走 EPS×0.7/股價 估算")

    # ==========================================================
    # v0.9.2：Top10 基本面回測模式
    # ==========================================================

    if cfg.use_top10_backtest:
        logger.log("=" * 60)
        logger.log("📊 啟動 Top10 基本面回測模式")
        logger.log("   ※ 直接使用 Score 最高的 10 檔股票建倉")
        logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
        logger.log("=" * 60)

        # ========== DEBUG: 基本面資料診斷 ==========
        print("\n" + "=" * 60)
        print("🔍 [DEBUG] 基本面資料合併後診斷")
        print("=" * 60)

        print(f"\n📊 df_sel 總筆數: {len(df_sel)}")
        print(f"📊 有營收YoY的筆數: {df_sel['營收YoY(%)'].notna().sum()}")
        print(f"📊 有EPS本期(非ETF)的筆數: {df_sel['EPS本期'].notna().sum()}")
        print(f"📊 有EPSYoY_raw的筆數: {df_sel['EPSYoY_raw'].notna().sum()}")

        # 顯示前5筆有EPS資料的股票
        eps_notna = df_sel[df_sel['EPS本期'].notna()].head(5)
        if len(eps_notna) > 0:
            print(f"\n📋 有EPS資料的前5檔股票:")
            for idx, row in eps_notna.iterrows():
                print(
                    f"   {row['股票代號']} {row.get('公司名稱_來源', '')} | EPS: {row.get('EPS本期', 'N/A')} | EPS YoY: {row.get('EPSYoY_顯示(%)', 'N/A')}%")
        else:
            print(f"\n⚠️ 沒有任何股票有 EPS 資料！")
            print(f"   請檢查 fetch_eps_latest 函數是否正常運作。")

        print("\n" + "=" * 60 + "\n")
        # ========== DEBUG 結束 ==========



        if cfg.use_enhanced_score:
            df_sel = calculate_multi_factor_score(df_sel, cfg)
            logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
        else:
            df_sel = calculate_simple_score(df_sel, cfg)

        df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)
        # V0.9.5-tab-split-phase3 B-2：套用強勢股過濾
        df_sel = _apply_strong_filter(df_sel, cfg, logger)

        top10_codes = df_sel.head(10)["股票代號"].dropna().astype(str).str.strip().tolist()
        logger.log(f"   Top10 股票: {top10_codes}")

        tech_all_top10, tech_today_top10, buy_today_top10 = run_tech(cfg, s, top10_codes, logger, cfg.history_months)

        if tech_all_top10.empty:
            logger.log("❌ 無法獲取 Top10 股票的歷史資料")
            return

        tech_all_top10["買點"] = True
        tech_all_top10["買點_基礎"] = True
        tech_all_top10["確認層級"] = 3

        score_map = df_sel.set_index("股票代號")["Score"].to_dict()
        gate_map = build_gate_map(cfg, df_sel)
        eq_top10, trades_top10, pf_kpi_top10, reason_stats_top10 = portfolio_backtest_topk_event(
            cfg, tech_all_top10, score_map, gate_map
        )
        sig_summary_top10 = signal_level_backtest_event(cfg, tech_all_top10)

        logger.log("\n" + "=" * 60)
        logger.log("📊 Top10 基本面回測結果")
        logger.log("=" * 60)
        logger.log("✅ Signal-level KPI:")
        logger.log(sig_summary_top10.to_string(index=False) if not sig_summary_top10.empty else "(無訊號)")
        logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
        logger.log(pf_kpi_top10.to_string(index=False) if not pf_kpi_top10.empty else "(無投組資料)")

        out_file = f"{cfg.out_file_prefix}_Top10Backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        startrow = 6
        name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")

        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            format_for_output(df_sel.head(10), sort_by_code=True).to_excel(writer, index=False, sheet_name="Top10_股票列表")
            if not eq_top10.empty:
                eq_top10.to_excel(writer, index=False, sheet_name="投組回測", startrow=startrow)
            if not trades_top10.empty:
                trades_out = trades_top10.merge(name_map, on="股票代號", how="left")
                trades_out = format_for_output(trades_out, sort_by_code=True)
                # ✅ 按進場日排序
                if "進場日" in trades_out.columns:
                    trades_out = trades_out.sort_values("進場日")
                trades_out.to_excel(writer, index=False, sheet_name="交易明細", startrow=0)
            if not pf_kpi_top10.empty:
                pf_kpi_top10.to_excel(writer, index=False, sheet_name="績效摘要", startrow=startrow)
            if not reason_stats_top10.empty:
                reason_stats_top10.to_excel(writer, index=False, sheet_name="出場原因統計")

        logger.log(f"✅ Top10 回測完成 → {out_file}")
        return

    # ==========================================================
    # 正常回測模式
    # ==========================================================

    if cfg.use_enhanced_score:
        df_sel = calculate_multi_factor_score(df_sel, cfg)
        logger.log(f"   因子權重: 動能1M={cfg.factor_weight_mom1:.0%} 動能3M={cfg.factor_weight_mom3:.0%} 動能6M={cfg.factor_weight_mom6:.0%} 營收={cfg.factor_weight_rev:.0%} EPS={cfg.factor_weight_eps:.0%}")
    else:
        df_sel = calculate_simple_score(df_sel, cfg)
        w_rev = cfg.simple_score_weight_rev
        w_eps = cfg.simple_score_weight_eps
        w_div = cfg.simple_score_weight_div
        w_pe = cfg.simple_score_weight_pe
        logger.log(f"   權重: 營收{w_rev:.0f}% / EPS{w_eps:.0f}% / 殖利率{w_div:.0f}% / PE{w_pe:.0f}%")

    # 【V1.1-no-double-score】2026-07-01 修 P0：只算一次評分
    # 原本：line 367 df_sel_temp 算一次、line 415 df_sel 又算一次（同一份原始 df_sel 算兩次）
    # 改成：df_sel 算一次、df_sel_temp 只是 strong_filter 副本（拿來跑技術分析 top N）
    df_sel = df_sel.sort_values("Score", ascending=False).reset_index(drop=True)
    # V0.9.5-tab-split-phase3 B-2：套用強勢股過濾（給技術分析 top N 用、給評分輸出用 df_sel 不過濾）
    df_sel_temp = _apply_strong_filter(df_sel, cfg, logger)

    logger.log(f"5) 抓取前 {cfg.top_n_for_tech} 檔股票的歷史日K...")

    if cfg.use_excel_stock_list:
        logger.log("📂 使用 Excel 指定股票清單")
        try:
            tech_codes = load_stock_list_from_excel(cfg.excel_stock_file)
        except Exception as e:
            logger.log(f"❌ Excel 選股失敗：{e}")
            return

        # ✅ v0.9.4 Excel 清單強制買點模式
        if cfg.excel_force_buy:
            logger.log("   📊 啟用 Excel 清單強制買點模式")
            logger.log("   ※ 不經過技術買點過濾（買點強制設為 True）")
    else:
        tech_codes = df_sel_temp.head(cfg.top_n_for_tech)["股票代號"].dropna().astype(str).str.strip().tolist()
    logger.log(f"   選股檔數: {len(tech_codes)}，每檔 {cfg.history_months} 個月歷史資料")

    #tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)
    tech_all, tech_today, buy_today = run_tech(cfg, s, tech_codes, logger, cfg.history_months)

    # ✅ v0.9.4 Excel 清單強制買點模式：將買點強制設為 True
    if cfg.use_excel_stock_list and cfg.excel_force_buy:
        if not tech_all.empty:
            tech_all["買點"] = True
            tech_all["買點_基礎"] = True
            tech_all["確認層級"] = 3
            logger.log("   🔧 已強制將所有日期設為買點")

    if tech_all.empty:
        logger.log("❌ 無歷史資料，請檢查網路連線")
        return

    # 【V1.1-no-double-score】2026-07-01 修 P0：刪掉重複的評分計算（line 367 已算過）
    # df_sel 已在 line 367 算完評分 + sort，這裡直接用、不要再算一次
    strong_sel = df_sel[
        (df_sel["營收YoY(%)"] > cfg.strong_revenue_yoy) &
        (df_sel["EPS本期"] > 0) &
        (df_sel["PE"] < cfg.strong_pe_max) &
        (df_sel["股價"] > cfg.strong_price_min)
    ].copy()
    top10_sel = df_sel.head(10).copy()

    logger.log("6) 執行回測...")
    gate_map = build_gate_map(cfg, df_sel)
    score_map = df_sel.set_index("股票代號")["Score"].to_dict()
    eq, trades, pf_kpi, reason_stats = portfolio_backtest_topk_event(cfg, tech_all, score_map, gate_map)
    sig_summary = signal_level_backtest_event(cfg, tech_all)

    try:
        yearly_perf = performance_by_year(trades)
        logger.log("✅ 年度績效分析：")
        if not yearly_perf.empty:
            logger.log(yearly_perf.to_string(index=False))
    except Exception as e:
        logger.log(f"⚠️ 年度績效分析失敗：{e}")
        yearly_perf = pd.DataFrame()

    wf_results = pd.DataFrame()
    if cfg.wf_enabled:
        logger.log("7) 執行 Walk-forward 分析...")
        wf_results = run_walk_forward(cfg, logger, s)

    name_map = price[["股票代號", "公司名稱_來源"]].drop_duplicates("股票代號")
    name_map = ensure_str_column(name_map, "股票代號")
    eps_disp_map = df_sel.set_index("股票代號")["EPSYoY_顯示(%)"].to_dict()

    df_out_all = format_for_output(df_sel, sort_by_code=True)
    strong_out = format_for_output(strong_sel, sort_by_code=True)
    top10_out = format_for_output(top10_sel, sort_by_code=True)

    if tech_today is None or tech_today.empty:
        tech_today_out = pd.DataFrame()
    else:
        tech_today = ensure_str_column(tech_today, "股票代號")
        tech_today_out = tech_today.merge(name_map, on="股票代號", how="left")
        tech_today_out["EPSYoY_顯示(%)"] = tech_today_out["股票代號"].map(eps_disp_map)
        tech_today_out = format_for_output(tech_today_out, sort_by_code=True)

    if buy_today is None or buy_today.empty:
        buy_today_out = pd.DataFrame([{
            "說明": "今日無符合買點條件的股票",
            "可能原因": "1. 市場震盪或下跌 2. 買點條件設定較嚴格 3. 選股檔數不足",
            "建議調整參數": "放寬 RSI_OVERSOLD / 關閉成交量過濾 / 關閉趨勢過濾 / 增加選股檔數",
            "當前 RSI_OVERSOLD": cfg.rsi_oversold,
            "當前 Volume Filter": cfg.require_volume_filter,
            "當前 Trend Filter": cfg.require_trend_filter,
            "當前 MTF Filter": cfg.use_mtf_confirmation,
            "選股檔數 (TopN)": cfg.top_n_for_tech,
            "歷史月數": cfg.history_months
        }])
        logger.log("   📭 今日無買點訊號（已建立診斷說明 Sheet）")
    else:
        buy_today = ensure_str_column(buy_today, "股票代號")
        buy_today_out = buy_today.merge(name_map, on="股票代號", how="left")
        buy_today_out["EPSYoY_顯示(%)"] = buy_today_out["股票代號"].map(eps_disp_map)
        buy_today_out = format_for_output(buy_today_out, sort_by_code=True)
        logger.log(f"   📈 今日買點數量: {len(buy_today_out)} 檔")
    # ==========================================================
    # ✅ v0.9.3 今日出場清單（計算當日需要賣出的股票）
    # ==========================================================

    exit_today_list = []

    if trades is not None and not trades.empty:
        # 獲取最新交易日
        latest_date = tech_today["Date"].max() if not tech_today.empty else datetime.now()

        # 獲取所有有進場但尚未出場的股票
        for code in tech_codes:
            code_trades = trades[trades["股票代號"] == code]
            if code_trades.empty:
                continue

            # 找出最新的出場日
            if "出場日" in code_trades.columns:
                last_exit = code_trades["出場日"].max()
                # 如果最後出場日 < 最新交易日，且還有進場記錄，表示仍在持有中
                if pd.to_datetime(last_exit) < pd.to_datetime(latest_date):
                    # 找出該股票最新的進場記錄（在最後出場日之後）
                    code_entries = code_trades[code_trades["出場日"] <= last_exit] if last_exit else code_trades
                    if not code_entries.empty:
                        latest_entry = code_entries.sort_values("進場日", ascending=False).iloc[0]
                        entry_price = latest_entry["進場價"]
                        entry_date = latest_entry["進場日"]

                        # 獲取當前價格
                        code_tech = tech_today[tech_today["股票代號"] == code]
                        if not code_tech.empty:
                            current_price = code_tech.iloc[0]["Close"]
                            ret = (current_price - entry_price) / entry_price
                            rsi = code_tech.iloc[0]["RSI"] if "RSI" in code_tech.columns else None
                            hold_days = (pd.to_datetime(latest_date) - pd.to_datetime(entry_date)).days

                            # 檢查出場條件
                            exit_reason = None
                            if ret <= cfg.stop_loss:
                                exit_reason = "STOP_LOSS"
                            elif ret >= cfg.take_profit:
                                exit_reason = "TAKE_PROFIT"
                            elif rsi is not None and rsi >= cfg.exit_rsi:
                                exit_reason = "RSI_EXIT"
                            elif hold_days >= cfg.hold_days:
                                exit_reason = "TIME_EXIT"

                            if exit_reason is not None:
                                # ✅ 獲取公司名稱
                                company_name = name_map[name_map["股票代號"] == code]["公司名稱_來源"].values
                                company_name_str = company_name[0] if len(company_name) > 0 else ""

                                exit_today_list.append({
                                    "股票代號": code,
                                    "公司名稱": company_name_str,
                                    "進場日": entry_date,
                                    "進場價": round(entry_price, 2),
                                    "今日收盤價": round(current_price, 2),
                                    "累計報酬(%)": round(ret * 100, 2),
                                    "持有天數": hold_days,
                                    "出場原因": exit_reason,
                                    "當前 RSI": round(rsi, 1) if rsi else None
                                })

    exit_today_df = pd.DataFrame(exit_today_list)

    if exit_today_df.empty:
        exit_today_df = pd.DataFrame([{
            "說明": "今日無需要出場的股票",
            "可能原因": "1. 無持股 2. 所有持倉均未觸發出場條件",
            "當前停損門檻": f"{cfg.stop_loss * 100:.1f}%",
            "當前停利門檻": f"{cfg.take_profit * 100:.1f}%",
            "當前 RSI 出場門檻": cfg.exit_rsi,
            "最大持有天數": cfg.hold_days
        }])
        logger.log("   📭 今日無出場訊號（已建立診斷說明 Sheet）")
    else:
        logger.log(f"   📤 今日出場數量: {len(exit_today_df)} 檔")

    if trades is None or trades.empty:
        trades_out = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "進場日", "進場價", "出場日", "出場價", "出場原因", "報酬(%)", "報酬_扣成本(%)"])
    else:
        trades = ensure_str_column(trades, "股票代號")
        trades_out = trades.merge(name_map, on="股票代號", how="left")
        trades_out = format_for_output(trades_out, sort_by_code=True)
        if "進場日" in trades_out.columns:
            trades_out = trades_out.sort_values("進場日")

    out_file = f"{cfg.out_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    startrow = 6


    logger.log(f"8) 輸出 Excel: {out_file}")

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_out_all.to_excel(writer, index=False, sheet_name="全市場_基本面")
        strong_out.to_excel(writer, index=False, sheet_name="強勢股_基本面")
        top10_out.to_excel(writer, index=False, sheet_name="Top10_基本面")

        if not tech_today_out.empty:
            tech_today_out.to_excel(writer, index=False, sheet_name="技術分析_今日", startrow=startrow)

        buy_today_out.to_excel(writer, index=False, sheet_name="技術買點_今日", startrow=startrow)
        # ✅ v0.9.3 今日出場清單
        exit_today_df.to_excel(writer, index=False, sheet_name="今日出場清單", startrow=startrow)

        if not reason_stats.empty:
            reason_stats.to_excel(writer, index=False, sheet_name="出場原因統計")

        summary_sheet = pd.concat([pd.DataFrame([{"區塊": "Signal-level"}]),
                                   sig_summary,
                                   pd.DataFrame([{"區塊": f"Portfolio-level (Top{cfg.topk})"}]),
                                   pf_kpi], ignore_index=True)
        summary_sheet.to_excel(writer, index=False, sheet_name="回測摘要", startrow=startrow)

        if not eq.empty:
            eq.to_excel(writer, index=False, sheet_name="投組回測_TopK等權", startrow=startrow)
        if not trades_out.empty:
            trades_out.to_excel(writer, index=False, sheet_name="投組交易明細", startrow=0)
        if not yearly_perf.empty:
            yearly_perf.to_excel(writer, sheet_name="年度績效", index=False)
        if not wf_results.empty:
            wf_results.to_excel(writer, sheet_name="WalkForward分析", index=False)
        # ==========================================================
        # Excel 美化（技術買點_今日、今日出場清單等）
        # ==========================================================

        # 技術買點_今日美化
        if "技術買點_今日" in writer.sheets:
            ws_buy = writer.sheets["技術買點_今日"]

            # 檢查是否有實際買點
            first_cell = ws_buy.cell(row=startrow + 1, column=1).value if ws_buy.max_row > startrow else None

            if first_cell == "說明":
                buy_explain = [
                    "【技術買點_今日】診斷說明",
                    "今日無符合買點條件的股票。",
                    "",
                    "可能的調整方式：",
                    f"  - 降低 RSI_OVERSOLD（目前為 {cfg.rsi_oversold}）",
                    f"  - 關閉「成交量過濾」require_volume_filter",
                    f"  - 關閉「趨勢過濾」require_trend_filter",
                    f"  - 關閉「多時間框架確認」use_mtf_confirmation",
                    f"  - 增加選股檔數 TopN_for_Tech（目前為 {cfg.top_n_for_tech}）",
                    "",
                    "※ 買點條件較嚴格時，可能數日無訊號，屬正常現象。"
                ]
                write_explanation(ws_buy, buy_explain, start_row=startrow + len(buy_today_out) + 2)
            else:
                buy_explain = [
                    "【技術買點_今日】說明",
                    "買點 = 超跌(過去10天RSI低於門檻) + 轉強(RSI回升或MACD翻正) + 趨勢(站穩MA20) + 成交量過濾",
                    "多時間框架確認：週線/月線趨勢確認可提高買點品質"
                ]
                write_explanation(ws_buy, buy_explain)

            header_row = startrow + 1
            style_header(ws_buy, header_row)
            ws_buy.freeze_panes = ws_buy[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_buy.max_column)
            ws_buy.auto_filter.ref = f"A{header_row}:{last_col}{ws_buy.max_row}"
            autosize_columns(ws_buy)

            # 只有在有實際買點時才高亮「買點」欄位
            if first_cell != "說明" and "買點" in [cell.value for cell in ws_buy[header_row]]:
                highlight_true(ws_buy, header_row, "買點")

        # 今日出場清單美化
        if "今日出場清單" in writer.sheets:
            ws_exit = writer.sheets["今日出場清單"]

            # 檢查是否有實際出場
            first_cell = ws_exit.cell(row=startrow + 1, column=1).value if ws_exit.max_row > startrow else None

            if first_cell == "說明":
                exit_explain = [
                    "【今日出場清單】診斷說明",
                    "今日無需要出場的股票。",
                    "",
                    "出場條件：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天",
                    "",
                    "如果持有股票但未觸發條件，表示仍在正常持有中。"
                ]
                write_explanation(ws_exit, exit_explain, start_row=startrow + len(exit_today_df) + 2)
            else:
                exit_explain = [
                    "【今日出場清單】說明",
                    "以下股票今日觸發賣出條件，建議賣出：",
                    f"  - 停損：報酬 ≤ {cfg.stop_loss * 100:.1f}%",
                    f"  - 停利：報酬 ≥ {cfg.take_profit * 100:.1f}%",
                    f"  - RSI 出場：RSI ≥ {cfg.exit_rsi}",
                    f"  - 時間出場：持有 ≥ {cfg.hold_days} 天"
                ]
                write_explanation(ws_exit, exit_explain)

            header_row = startrow + 1
            style_header(ws_exit, header_row)
            ws_exit.freeze_panes = ws_exit[f"A{header_row + 1}"]
            last_col = get_column_letter(ws_exit.max_column)
            ws_exit.auto_filter.ref = f"A{header_row}:{last_col}{ws_exit.max_row}"
            autosize_columns(ws_exit)
    logger.log("\n" + "=" * 60)
    logger.log("📊 回測結果摘要")
    logger.log("=" * 60)
    logger.log("✅ Signal-level KPI:")
    logger.log(sig_summary.to_string(index=False) if not sig_summary.empty else "(無訊號)")
    logger.log(f"\n✅ Portfolio-level KPI (Top{cfg.topk} 等權):")
    logger.log(pf_kpi.to_string(index=False) if not pf_kpi.empty else "(無投組資料)")
    if not eq.empty:
        final_equity = eq["Equity"].iloc[-1]
        total_ret = (final_equity / cfg.capital - 1) * 100
        logger.log(f"   💰 初始本金：{cfg.capital:,.0f} 元 → 最終權益：{final_equity:,.0f} 元（總報酬：{total_ret:+.1f}%）")
        logger.log(f"   📊 標準化起始：1.0000 → 最終：{final_equity / cfg.capital:.4f}")
    logger.log("\n✅ 出場原因統計:")
    logger.log(reason_stats.to_string(index=False) if not reason_stats.empty else "(無交易資料)")
    logger.log(f"\n✅ 完成 → {out_file}")


    # V0.9.5-tab-split-phase3 B-1 fix：top10_codes 只在 use_top10_backtest=True 時賦值
    # 用 try/except 處理未定義情況
    try:
        _top10_codes = top10_codes
    except NameError:
        _top10_codes = []

    return {
        "df_sel": df_sel,
        "top10_codes": _top10_codes,
        "out_file": out_file,
        "pf_kpi": pf_kpi,
        "sig_summary": sig_summary,
        "reason_stats": reason_stats,
        "yearly_perf": yearly_perf,
        "capital": cfg.capital,
        "final_equity": eq["Equity"].iloc[-1] if not eq.empty else 0,
    }



# ==========================================================
# V0.9.4 phase2.3: 萬年曆挑選日期（純 Tkinter 原生，無額外 dependency）
# ==========================================================
