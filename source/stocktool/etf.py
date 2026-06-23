"""
stocktool.etf - ETF 持股統計
==============================

v1.1 重構：把 ETF 持股相關函數從 StockTool.py 抽出

被依賴：gui/tab_etf.py / pipeline.py
依賴：config.py / database.py
"""

from __future__ import annotations

import os
import re
import time
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import requests

from .config import StrategyConfig, GuiLogger
from .database import (
    _init_etf_history_db,
    _save_etf_holding_snapshot,
    _query_etf_holdings_by_date,
    _query_latest_two_dates,
    _compute_etf_changes,
)


def fetch_active_etf_list(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    """【V0.9.5-etf】抓 TWSE 主動式 ETF 列表、只保留 domestic（台股）
    回傳 DataFrame: code, name, category
    """
    r = session.get(
        ETF_ACTIVELIST_URL,
        timeout=cfg.timeout,
        verify=cfg.verify_ssl,
        headers={
            "User-Agent": "StockTool/AdvisorStyle-v1.0",
            "Referer": "https://www.twse.com.tw/zh/products/securities/etf/products/active-list.html",
        },
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"TWSE ETF activeList 回傳非 ok：{data}")
    df = pd.DataFrame(data["data"], columns=data["fields"])
    # 只留 domestic（台股）、拿掉 foreign (海外) 和 bfIncome (債券)
    df = df[df["ETF分類"] == "domestic"].copy()
    df = df.rename(columns={
        "證券代號": "etf_code",
        "證券簡稱": "etf_name",
    })
    df["etf_code"] = df["etf_code"].astype(str).str.strip()
    df = df[["etf_code", "etf_name"]].reset_index(drop=True)
    return df


def fetch_etf_top10_holdings(session: requests.Session, cfg: StrategyConfig,
                              etf_code: str) -> list:
    """【V0.9.5-etf】抓 etfinfo.tw 總覽頁的「前 10 大成分股」

    從 SSR 解析（__NUXT_DATA__ 內含 shares + industry）：
    範例：`{"code":149,"name":150,"weight":151,"shares":152,"unit":153,"industry":17},"2330","台積電",57.01,519237994,"股","半導體"`

    回傳 list of dict，每個含 {stock_code, stock_name, weight, shares, industry}
    例：
    [
        {"stock_code": "2330", "stock_name": "台積電", "weight": 57.01, "shares": 519237994, "industry": "半導體"},
        {"stock_code": "2454", "stock_name": "聯發科", "weight": 6.28, "shares": 31410621, "industry": "半導體"},
    ]

    【V0.9.5-etf-history】shares 是持股股數（如 519237994 股 = 519,237.994 張）
    """
    import re as _re
    url = ETFINFO_ETF_URL.format(code=etf_code)
    r = session.get(
        url,
        timeout=cfg.timeout,
        verify=cfg.verify_ssl,
        headers={
            "User-Agent": "StockTool/AdvisorStyle-v1.0",
            "Referer": "https://www.etfinfo.tw/",
        },
    )
    r.raise_for_status()
    html = r.text

    # 抓「前 10 大成分股」section
    section_start = html.find("前 10 大成分股")
    if section_start < 0:
        raise RuntimeError(f"{etf_code} 找不到「前 10 大成分股」section")

    # 只看 section 後 5000 字元
    section = html[section_start:section_start + 5000]

    # Parse HTML 表格（SSR 渲染、可靠）
    rows = _re.findall(
        r'<a href="/stock/(\d+)"[^>]*>(\d+)</a></td>\s*'
        r'<td[^>]*><span[^>]*>([^<]+)</span></td>\s*'
        r'<td[^>]*><strong[^>]*>([0-9.]+)%',
        section,
        _re.DOTALL,
    )
    if not rows:
        raise RuntimeError(f"{etf_code} 解析前 10 大失敗")

    # 【V0.9.5-etf-history】從 SSR __NUXT_DATA__ parse shares
    # 結構（Nuxt 3 flat array）：
    #   schema: {"code":X,"name":X,"weight":X,"shares":X,"unit":X,"industry":17}
    #   values: "2330","台積電",57.01,519237994,"股"
    # 注意：industry=17 指向 None（schema ref、沒有填值）→ 暫時拿不到 industry
    # → 重點在 shares（計算張數異動）、industry 可後續再補
    import json as _json
    nuxt_match = _re.search(r"__NUXT_DATA__[^>]*>([^<]+)</script>", html)
    nuxt_list = []
    if nuxt_match:
        try:
            nuxt_list = _json.loads(nuxt_match.group(1))
        except Exception:
            nuxt_list = []

    # 建立 stock_code → shares 對照
    # Nuxt 3 flat array 結構：每個 holding 是
    #   [schema_dict, code_val, name_val, weight_val, shares_val, unit_val]
    # schema_dict.shares 是指向 shares_val 的 index reference
    # 注意：unit 通常 reuse 已存在的 "股" ref → 不佔位置
    # 計算 holding 長度：從 schema dict 後到下一個 schema 之間 = 5 個值（reuse unit）或 6 個值（首次 unit）

    def _resolve_val(arr, idx):
        """解 Nuxt ref：追蹤整數 ref 直到拿到實際值"""
        depth = 0
        while depth < 5:
            try:
                v = arr[idx]
            except IndexError:
                return None
            if isinstance(v, int) and 0 <= v < len(arr):
                idx = v
                depth += 1
                continue
            return v
        return None

    code_to_shares = {}
    n = len(nuxt_list)
    i = 0
    while i < n:
        item = nuxt_list[i]
        # schema dict：{"code":X, "name":X, "weight":X, "shares":X, "unit":X, "industry":X}
        if not (isinstance(item, dict)
                and "code" in item and "shares" in item
                and isinstance(item.get("code"), int)
                and isinstance(item.get("shares"), int)):
            i += 1
            continue
        # schema dict 後面跟著 5 個值（code, name, weight, shares, unit）
        # unit 可能 reuse（指向已存在的 "股" ref）→ 計算 layout 長度
        schema = item
        # 從 schema 算 holding 結尾：找出 max ref index + 1
        max_ref = i  # schema 自己
        for field in ("code", "name", "weight", "shares", "unit"):
            ref = schema.get(field)
            if isinstance(ref, int) and ref > max_ref:
                max_ref = ref
        # 但 unit 可能指向已存在 ref（< i + 5）、就不會佔新位置
        # 簡化：假設 holding layout 是 schema + 5 個新值 = 6 位置
        #       除非 unit ref < i + 5（reuse）、那就只有 5 位置
        unit_ref = schema.get("unit")
        expected_end = i + 6  # schema + 5 values
        if isinstance(unit_ref, int) and unit_ref < i + 5:
            # unit reuse、不佔新位置
            expected_end = i + 5

        try:
            # 用 schema ref 拿真實值（避免 layout 偏移）
            code_val = _resolve_val(nuxt_list, schema["code"])
            name_val = _resolve_val(nuxt_list, schema["name"])
            weight_val = _resolve_val(nuxt_list, schema["weight"])
            shares_val = _resolve_val(nuxt_list, schema["shares"])
            if (isinstance(code_val, str) and code_val.isdigit()
                    and isinstance(shares_val, (int, float))
                    and shares_val > 0):
                code_to_shares[code_val] = int(shares_val)
        except (IndexError, ValueError, TypeError):
            pass

        # 推進：跳到下一個 schema（使用 expected_end）
        # 但要驗證下個位置真的是 schema、否則前進 1 格
        next_i = expected_end
        if next_i < n:
            next_item = nuxt_list[next_i]
            if isinstance(next_item, dict) and "code" in next_item and "shares" in next_item:
                i = next_i
            else:
                i += 1
        else:
            i = expected_end

    holdings = []
    for stock_code, _, stock_name, weight in rows:
        stock_code = stock_code.strip()
        stock_name = stock_name.strip()
        weight_val = float(weight)
        shares = code_to_shares.get(stock_code, 0)
        holdings.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "weight": weight_val,
            "shares": shares,
            "industry": "",  # etfinfo.tw holdings 結構內 industry 是 ref→None、暫拿不到
        })

    # 若 shares 全為 0、可能 SSR parse 失敗、警告
    if holdings and not any(h["shares"] > 0 for h in holdings):
        print(f"[V0.9.5-etf-history] ⚠️ {etf_code} SSR parse 失敗、shares 全為 0")

    return holdings


def build_etf_holdings_table(session: requests.Session, cfg: StrategyConfig,
                              logger) -> pd.DataFrame:
    """【V0.9.5-etf】完整 ETF 持股 table
    1. 抓 18 檔 domestic ETF 列表
    2. 對每檔 ETF 抓前 10 大
    3. 合併為長表 (stock_code, stock_name, etf_code, etf_name, weight)
    """
    etfs = fetch_active_etf_list(session, cfg)
    logger.log(f"📋 [ETF] 抓到 {len(etfs)} 檔台股主動式 ETF（domestic）")

    all_rows = []
    for _, row in etfs.iterrows():
        etf_code = row["etf_code"]
        etf_name = row["etf_name"]
        try:
            holdings = fetch_etf_top10_holdings(session, cfg, etf_code)
            for h in holdings:
                # 【V0.9.5-tab-split-phase3-H FixA】2026-06-23 William 09:55 反映
                # ETF 持股篩選結果「今日異動」全是 -- → 根因是 build_etf_holdings_table
                # 沒把 shares 放進 long_df → _save_etf_holdings_to_db 寫入 DB 全是 0
                # → _compute_etf_changes 算出 change_lots 全 0 → 顯示 --。
                # 修法：shares 也要放進 long_df → DB 才會有 shares → 異動才會算得出來。
                all_rows.append({
                    "stock_code": h["stock_code"],
                    "stock_name": h["stock_name"],
                    "etf_code": etf_code,
                    "etf_name": etf_name,
                    "weight": h["weight"],
                    "shares": h.get("shares", 0),
                    "industry": h.get("industry", ""),
                })
            logger.log(f"  ✅ [{etf_code}] {etf_name} 抓到 {len(holdings)} 檔前 10 大")
        except Exception as e:
            logger.log(f"  ⚠️ [{etf_code}] {etf_name} 抓取失敗：{e}")

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    # 整理型別
    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["stock_name"] = df["stock_name"].astype(str).str.strip()
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    return df


def aggregate_etf_holdings(holdings_long: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """【V0.9.5-etf】合併去重、計算「被幾檔 ETF 持有」、merge 收盤價

    holdings_long: long-format (stock_code, stock_name, etf_code, etf_name, weight)
    price_df: stockTool price cache (股票代號, 公司名稱_來源, 股價, data_date, 成交量_張)

    回傳 wide-format:
    - 股票代號、股票名稱、收盤價
    - etf_count：被幾檔 ETF 持有
    - etf_list：字串 "00981A 主動統一台股增長(9.68%)\n00403A 主動統一升級50(18.29%)..."
    - 排序：依 etf_count 由大到小
    """
    if holdings_long.empty:
        return pd.DataFrame()

    # 1. 計算每檔個股的 etf_count + 整合 etf_list 字串
    grouped = holdings_long.groupby("stock_code")
    rows = []
    for stock_code, g in grouped:
        # 該檔個股被多檔 ETF 持有、每檔一個 (etf_code, etf_name, weight)
        etf_entries = []
        for _, r in g.iterrows():
            etf_entries.append(
                f"{r['etf_code']} {r['etf_name']}({r['weight']:.2f}%)"
            )
        rows.append({
            "股票代號": stock_code,
            "股票名稱": g["stock_name"].iloc[0],  # 取第一個當主名
            "etf_count": len(g),
            "etf_list": "\n".join(etf_entries),  # 【V0.9.5-etf-popup-fix】每個 ETF 一行、改用 Text widget 顯示
        })

    result = pd.DataFrame(rows)

    # 2. merge 收盤價
    if price_df is not None and not price_df.empty:
        price_map = price_df[["股票代號", "股價"]].copy()
        price_map["股票代號"] = price_map["股票代號"].astype(str).str.strip()
        price_map["股價"] = pd.to_numeric(price_map["股價"], errors="coerce")
        result = result.merge(
            price_map,
            on="股票代號",
            how="left",
        )
        result = result.rename(columns={"股價": "收盤價"})
    else:
        result["收盤價"] = None

    # 3. 排序：依 etf_count 由大到小
    result = result.sort_values(
        by=["etf_count", "股票代號"],
        ascending=[False, True],
    ).reset_index(drop=True)

    return result


# 【V0.9.5-etf 新增】2026-06-19 William 要求：
#   主動式 ETF 成份股 Tab
#   - 來源 1：TWSE 官方 API `/rwd/zh/ETF/activeList` 拿 18 檔 domestic 主動式 ETF
#   - 來源 2：etfinfo.tw `/etf/{code}` 總覽頁、parse「前 10 大成分股」HTML 表格
# ==========================================================

ETF_ACTIVELIST_URL = "https://www.twse.com.tw/rwd/zh/ETF/activeList"
ETFINFO_ETF_URL = "https://www.etfinfo.tw/etf/{code}"

def _display_width(s: str) -> int:
    """【V0.9.5-etf-popup-width】估算字串在 Text widget 中的顯示寬度
    - 中文字（CJK）算 2 字元寬
    - ASCII 算 1 字元寬
    - 因為 Tkinter Text widget 的 width 參數以「平均字元寬度」為單位
      → 純算字元數會讓中文超出 width 計算、後面字被截斷
    """
    w = 0
    for c in s:
        cp = ord(c)
        # CJK 統一表意文字：0x4E00-0x9FFF
        # CJK 符號和標點：0x3000-0x303F
        # 全形 ASCII：0xFF00-0xFFEF
        # 平假名/片假名：0x3040-0x30FF
        if 0x3000 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF:
            w += 2
        else:
            w += 1
    return w

