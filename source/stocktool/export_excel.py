"""
stocktool.export_excel - Excel 樣式與 I/O
==========================================

v1.1 重構：把 Excel 相關函數從 StockTool.py 抽出

包含：
- load_stock_list_from_excel（讀取自選股清單）
- autosize_columns, style_header, write_explanation, highlight_true
- get_history_file, init_stock_history, update_stock_history, get_stock_history
  （技術指標歷史檔 cache）

被依賴：pipeline.py / gui/tab_strategy.py
依賴：config.py
"""

from __future__ import annotations

import os
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

from .config import find_col, StrategyConfig, GuiLogger, HISTORY_DIR
from .cache import save_cache, load_cache
from .fetch_market import month_starts_back, fetch_twse_stock_day_month


def load_stock_list_from_excel(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到 Excel: {file_path}")
    df = pd.read_excel(file_path)
    col = find_col(df.columns, ["股票", "code"])
    if col is None:
        raise ValueError("Excel 必須包含 '股票代號' 或 'code' 欄位")
    return df[col].astype(str).str.strip().tolist()


# ==========================================================
# History Cache System
# ==========================================================

def get_history_file(stock_id, history_months):
    return f"{HISTORY_DIR}/{stock_id}_{history_months}m.xlsx"


def init_stock_history(session, cfg, stock_id, history_months):
    months = month_starts_back(history_months)
    frames = []
    for m in months:
        df = fetch_twse_stock_day_month(session, cfg, stock_id, m)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames)
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def update_stock_history(session, cfg, stock_id, df_old):
    today_month = datetime.today().strftime("%Y%m01")
    df_new = fetch_twse_stock_day_month(session, cfg, stock_id, today_month)
    if df_new is None or df_new.empty:
        return df_old
    df_all = pd.concat([df_old, df_new])
    df_all = df_all.drop_duplicates(subset=["Date"]).sort_values("Date")
    return df_all


def get_stock_history(session, cfg, stock_id, logger, history_months):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    file_path = get_history_file(stock_id, history_months)
    if not os.path.exists(file_path):
        logger.log(f"📥 [{stock_id}] 初始化 {history_months} 個月歷史資料")
        df = init_stock_history(session, cfg, stock_id, history_months)
        save_cache(file_path, df)
        return df
    df_old, _, _ = load_cache(file_path)
    logger.log(f"🔄 [{stock_id}] 更新當月資料")
    df_new = update_stock_history(session, cfg, stock_id, df_old)
    save_cache(file_path, df_new)
    return df_new


# ==========================================================

    tech_all = pd.concat(parts, ignore_index=True)
    last_day = tech_all.groupby("股票代號")["Date"].max().reset_index()
    tech_today = tech_all.merge(last_day, on=["股票代號", "Date"], how="inner")
    buy_today = tech_today[tech_today["買點"] == True].copy()

    return tech_all, tech_today, buy_today


# ==========================================================
# Backtest Functions
# ==========================================================

def autosize_columns(ws, min_w=10, max_w=44):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(min_w, min(max_w, max_len + 2))


def style_header(ws, header_row):
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[header_row]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_explanation(ws, lines, start_row=1, start_col=1):
    title_font = Font(bold=True, size=12)
    normal_font = Font(size=11)
    for i, line in enumerate(lines):
        c = ws.cell(row=start_row + i, column=start_col, value=line)
        c.font = title_font if i == 0 else normal_font
        c.alignment = Alignment(wrap_text=True, vertical="top")


def highlight_true(ws, header_row, col_name):
    header_cells = list(ws[header_row])
    idx = None
    for i, cell in enumerate(header_cells, 1):
        if cell.value == col_name:
            idx = i
            break
    if idx is None:
        return
    col_letter = get_column_letter(idx)
    rng = f"{col_letter}{header_row + 1}:{col_letter}{ws.max_row}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=["TRUE"],
                                                  fill=PatternFill("solid", fgColor="FFF2CC")))


# ==========================================================
# Pipeline (核心執行流程)
# ==========================================================

