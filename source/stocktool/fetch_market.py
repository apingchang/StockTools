"""
stocktool.fetch_market - 行情資料抓取（TWSE/TPEx/FinMind/goodinfo）
=====================================================================

v1.1 重構：把 fetch_* 函數從 StockTool.py 抽出

包含：
- 日期工具：to_num_series, month_starts_back, roc_to_ad
- GoodInfo 12Q EPSRate：_load_goodinfo_12q_epsrate
- 全市場清單：_fetch_market_stock_list
- TWSE 即時股價：_fetch_twse_realtime_batch, _pick_latest_price_row
- FinMind API：_finmind_get, _parse_roc_year, _fetch_finmind_prices_batch,
              _fmt_float, _fetch_finmind_dividend, _background_fetch_all_dividend
- 除息日收盤價：_update_ex_date_close, _fetch_ex_date_close
- 主流程抓取：fetch_csv_requests, fetch_prices, fetch_revenue_latest, fetch_eps_latest
- TWSE 歷史日 K：safe_parse_json, fetch_twse_stock_day_month, fetch_twse_history

被依賴：pipeline.py / gui/tab_strategy.py / gui/tab_portfolio.py / gui/tab_manual.py
依賴：config.py / cache.py / database.py
"""

from __future__ import annotations

import os
import re
import io
import time
import json
import sqlite3
import logging
import requests
from datetime import date, datetime, timedelta
from io import StringIO
from typing import List, Tuple, Optional, Dict, Any

import pandas as pd
import numpy as np

from .config import (
    VERSION,
    StrategyConfig,
    GuiLogger,
    find_col,
)
from .cache import (
    save_cache,
    load_cache,
    get_or_fetch,
    _is_market_hours,
    _is_price_cache_valid,
    get_cache_file,
)
from .database import (
    _upsert_div_history,
    _upsert_eps_history,
    _query_div_history,
    _query_div_history_with_fetched,
    _query_eps_history,
    _div_history_stats,
    _eps_history_stats,
    _init_div_history_db,
    _init_eps_history_db,
)


# ==========================================================
# 模組內常數
# ==========================================================

_TWSE_REALTIME_BATCH_SIZE = 10  # 【V0.9.5-goodinfo4+5】降批：50→10（避免TWSE rate limit）

_MS_PROGRESS: Dict[str, Any] = {}


# ==========================================================
# 日期 / 數字工具
# ==========================================================

def to_num_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.replace("+", "", regex=False)
         .str.strip(),
        errors="coerce"
    )


def month_starts_back(n_months: int) -> List[str]:
    today = date.today()
    y, m = today.year, today.month
    out = []
    for i in range(n_months):
        mm = m - i
        yy = y
        while mm <= 0:
            yy -= 1
            mm += 12
        out.append(f"{yy}{mm:02d}01")
    return out


def roc_to_ad(roc_str: str):
    parts = str(roc_str).strip().split("/")
    if len(parts) != 3:
        return None
    yy = int(parts[0]) + 1911
    mm = int(parts[1])
    dd = int(parts[2])
    return date(yy, mm, dd)


# ==========================================================


# 股利歷史庫（跟 eps_history 同一風格）
def _load_goodinfo_12q_epsrate(goodinfo_dir=None):
    """【V0.9.5-tab-split-phase3-C Fix10】
    載入 GoodInfo 12QEPSRate 3 個檔案，回傳 {stock_id: {quarter_str: yoy_pct}}

    quarter_str 格式: "26Q1"
    yoy_pct 是 GoodInfo 直接算好的同季 YoY 成長率 (百分比)

    【v1.1.1+ William 2026-06-24 22:35 反映】
    pd.read_html 需要 lxml。如果系統沒裝 lxml → 0 檔 → EPSYoY 全 NaN。
    現在加 friendly error message + fallback 提示使用 html5lib。
    """
    import os as _os
    import re as _re
    if goodinfo_dir is None:
        goodinfo_dir = _os.path.expanduser(
            "~/.openclaw/workspace/股神/.tmp/goodinfo_export/eps"
        )
    if not _os.path.isdir(goodinfo_dir):
        return {}

    # 預先檢查 lxml（pd.read_html 需要這個）
    try:
        import lxml  # noqa: F401
    except ImportError:
        print("⚠️ GoodInfo 12QEPSRate 需要 lxml 才能讀取 .xls 檔（pd.read_html 依賴）")
        print("   請執行：pip install lxml")
        print("   或裝：pip install -r requirements.txt")
        print("   （沒有 lxml → GoodInfo 覆蓋會跳過、EPSYoY 全 NaN）")
        return {}

    out = {}
    files = ["55U_12QEPSRate.xls", "20-55_12QEPSRate.xls", "20L_12QEPSRate.xls"]
    for fname in files:
        fpath = _os.path.join(goodinfo_dir, fname)
        if not _os.path.exists(fpath):
            print(f"⚠️ GoodInfo 12QEPSRate 缺檔: {fpath}")
            continue
        try:
            # 這幾個檔案其實是 HTML 格式 (內容偽裝 .xls)
            tables = pd.read_html(fpath)
            if not tables:
                continue
            df = tables[0]
            df["代號"] = df["代號"].astype(str).str.strip()
            # 找出所有季度欄位 (e.g. "26Q1成長(%)")
            qcols = [c for c in df.columns if _re.match(r"^[0-9]{2}Q[1-4]成長\(%\)$", str(c))]
            if not qcols:
                continue
            for _, r in df.iterrows():
                sid = str(r["代號"]).strip()
                for qc in qcols:
                    val = r[qc]
                    if pd.notna(val):
                        qkey = str(qc).replace("成長(%)", "")  # "26Q1"
                        out.setdefault(sid, {})[qkey] = float(val)
        except Exception as e:
            print(f"⚠️ 讀取 {fname} 失敗: {e}")
    print(f"📂 GoodInfo 12QEPSRate: {len(out)} 檔")
    return out


# ==========================================================
# V0.9.5: 手動選股功能 - FinMind 資料拉取輔助
# ==========================================================

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# 手動選股進度（背景 thread 寫、UI thread 讀）
_MS_PROGRESS = {"stage": "", "done": 0, "total": 0, "msg": "", "error": ""}


def _fetch_market_stock_list() -> pd.DataFrame:
    """
    從 TWSE / TPEx 抓全市場股票代號與名稱（當 pipeline 未執行時的 fallback）。
    回傳 DataFrame：[股票代號, 股票名稱]
    """
    import sqlite3
    # 優先用 eps_history.db 湊出名單（已有股票代號，快速）
    db_path = "eps_history.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            codes = pd.read_sql_query(
                "SELECT DISTINCT stock_id FROM eps_history ORDER BY stock_id", conn)
            conn.close()
            if not codes.empty:
                df = codes.copy()
                df["股票名稱"] = ""
                return df.rename(columns={"stock_id": "股票代號"})
        except Exception:
            pass

    # TWSE / TPEx 上市股票清單（從 ISIN 頁面）
    rows = []
    for url in ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
                 "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]:
        try:
            r = requests.get(url, timeout=20, verify=False)
            from io import StringIO
            tables = pd.read_html(StringIO(r.text), header=0)
            for t in tables:
                if "有價證券代號及名稱" in t.columns:
                    # 第一欄是「代號　名稱」混合，需用空白拆開
                    combined = t["有價證券代號及名稱"].dropna().tolist()
                    for item in combined:
                        s = str(item).strip()
                        # 格式：「1101　台泥」或「1101 台泥」
                        parts = s.split(maxsplit=1)
                        if len(parts) == 2 and parts[0].strip().isdigit() and len(parts[0].strip()) == 4:
                            rows.append({"股票代號": parts[0].strip(), "股票名稱": parts[1].strip()})
                    break  # 只處理第一張表
        except Exception:
            continue

    if rows:
        result = pd.DataFrame(rows).drop_duplicates("股票代號")
        result["股票代號"] = result["股票代號"].astype(str).str.strip()
        return result
    return pd.DataFrame(columns=["股票代號", "股票名稱"])

# ────────────────────────────────────────────────────────────────
# V0.9.5-twser：TWSE 即時股價（取代 FinMind）
# URL: https://mis.twse.com.tw/stock/api/getStockInfo.jsp
# 格式：上市 tse_XXXX.tw，上櫃 otc_XXXX.tw
# 主力欄位：z=現價，tv=當筆量，v=累積量，o/h/l/y=開高低昨
# 延遲：實測 15-20 秒（TWSE 官方）
# 限制：一次建議 50 檔，興櫃不支援
# ────────────────────────────────────────────────────────────────
_TWSE_REALTIME_BATCH_SIZE = 50   # 【V0.9.5-info3】batch 10→50（fetch_prices 一次拿全部上市上櫃、需要 balance 速度跟 TWSE rate limit）


def _fetch_twse_realtime_batch(stock_ids: List[str],
                                progress_callback=None) -> pd.DataFrame:
    """
    批次抓取台灣證券交易所即時股價（TWSE / TPEx 即時資訊）。
    完全取代 FinMind TaiwanStockPrice，實現【免費、無額度限制】的即時股價。

    URL 格式
    ----------
    https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw|otc_3188.tw|...

    主力欄位
    ---------
    - z : 現價（盤中即時成交價）；若為 "-" 表示該股票目前無成交（可能處於預約拍賣階段）
    - o : 開盤價（揭示）
    - tv : 當筆成交量
    - v : 累積成交量
    - h / l / y : 今日最高 / 最低 / 昨日收盤

    預開盤行為（9:00–9:30）
    ------------------------
    - z = "-"（尚未成交）→ fallback 到 o（開盤拍賣價，視為現時合理報價）
    - 若 o 也是 "-" → fallback 到 y（昨日收盤價）

    【V0.9.5-goodinfo4+5 (vol+cache) 重要修正】2026-06-18 18:34 William 反映
    - 「現價沒資料、成交不是今日總量」
    - 根因 1：v 欄位是「股」不是「張」、原本 int(v/1000) 會丟失 99% 資料
      例：v=4016（股）= 4.016 張、原本顯示 "4"（=4 張）
      修法：vol = v / 1000 保留小數、顯示用 f"{vol:.3f}" 張
    - 根因 2：上市/上櫃前綴誤判（6 開頭並非都是上櫃）
      例：6669 緯穎是上市、不是上櫃
      修法：先打 tse_ 拿、抓不到的股再用 otc_ 重打
    - 根因 3：抓完後沒回寫 cache、下次還要重抓
      修法：在 caller merge 完後 save_cache()

    Parameters
    ----------
    stock_ids : list[str]
        股票代號清單（如 ["2330", "0050", "3188"]）
        系統會自動判斷上市（tse_）或上櫃（otc_）、抓不到的股會 fallback
    progress_callback : callable, optional
        (n_done, n_total) → 每批完成後呼叫，用於 UI 動態進度顯示

    Returns
    -------
    pd.DataFrame，欄位：[股票代號, 現價, 成交量_張]
    - 現價：float 或 None（完全抓不到時）
    - 成交量_張：float（v / 1000，**股轉張**、保留小數）
      例：v=4016 股 → 4.016 張（不是 4 張）
    """
    rows = []
    codes = [str(c).strip() for c in stock_ids if str(c).strip()]
    total = len(codes)
    n_batches = (total + _TWSE_REALTIME_BATCH_SIZE - 1) // _TWSE_REALTIME_BATCH_SIZE
    _MS_PROGRESS["stage"] = "TWSE即時股價"
    _MS_PROGRESS["total"] = total

    for batch_idx in range(n_batches):
        batch_codes = codes[
            batch_idx * _TWSE_REALTIME_BATCH_SIZE:
            (batch_idx + 1) * _TWSE_REALTIME_BATCH_SIZE
        ]
        # 【V0.9.5-goodinfo4+5 (vol-int) 修 batch sleep】2026-06-18 21:37 William 反映
        # 原本 0.5s × 48 批 = 24s、加上 retry 6 次 × 6s = 36s
        # 改 0.3s × 48 = 14.4s、總耗時可控制在 30s 內
        if batch_idx > 0:
            time.sleep(0.3)
        # 【V0.9.5-goodinfo4+5 (vol+cache) 修正】2026-06-18 18:34 William 反映
        # 原本 6 開頭 = otc_ 是粗略判斷、有些 6 開頭是上市（例：6669 緯穎）
        # 修法：先全部打 tse_、回傳中沒有 c 欄位的股再用 otc_ 重打
        def _query_twse(prefix: str, max_retries: int = 3) -> list:
            """打一次 TWSE MIS API、回傳 msgArray（prefix 是 tse 或 otc）

            V0.9.5-goodinfo4+5 (vol+cache) 加 retry：2026-06-18 19:25 William 反映
            - 原本 0 retry、48 批連打可能導致最後幾批被 rate limit
            - 加 3 次 retry、間隔 1.0s / 2.0s / 4.0s 成長退避
            """
            ex_ch = "|".join(f"{prefix}_{c}.tw" for c in batch_codes)
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"
            for attempt in range(max_retries):
                try:
                    resp = requests.get(
                        url,
                        headers={
                            # 【V0.9.5-goodinfo4+5 (vol-int) 修 UA】2026-06-18 21:37 William 反映
                            # User-Agent 寫死 Windows NT、但 William 在 Ubuntu 上跑
                            # → TWSE 可能辨識為偽 UA、加上 retry 6 次 (tse+otc) 連打
                            # → 被當 bot 擋
                            # 修法：用 StockTool/VERSION 標識 + Linux UA
                            "User-Agent": f"StockTool/{VERSION} (+https://github.com/apingchang/StockTools)",
                            "Referer": "https://mis.twse.com.tw/",
                            "Accept": "application/json,text/plain,*/*",
                            "Accept-Language": "zh-TW,zh;q=0.9",
                            "Accept-Encoding": "gzip, deflate",
                        },
                        timeout=20,
                    )
                    resp.raise_for_status()
                    return resp.json().get("msgArray", [])
                except Exception as e:
                    # 【V0.9.5-goodinfo4+5 (vol-int) 修 retry】2026-06-18 21:37 William 反映
                    # 原本 1.0s / 2.0s / 3.0s 太短、tse 還沒放人就重試
                    # → 改 3.0s / 8.0s / 15.0s 拉長退避
                    wait_sec = [3.0, 8.0, 15.0][attempt] if attempt < 3 else 15.0
                    if attempt < max_retries - 1:
                        print(f"⚠️ TWSE API 失敗（批{batch_idx+1}/{n_batches}、{prefix}，重試 {attempt+1}/{max_retries}）：{type(e).__name__} - 等 {wait_sec}s")
                        time.sleep(wait_sec)
                    else:
                        print(f"⚠️ TWSE API 失敗（批{batch_idx+1}/{n_batches}、{prefix}，放棄）：{type(e).__name__}: {e}")
            return []

        # Step 1: 先打 tse_
        msg_tse = _query_twse("tse")
        # 找出 tse_ 沒回應的股
        tse_codes = {str(rec.get("c", "")).strip() for rec in msg_tse if rec.get("c")}
        missing_codes = [c for c in batch_codes if c not in tse_codes]

        # Step 2: missing 的股用 otc_ 重打（V0.9.5-goodinfo4+5 vol+cache 用同一個 retry helper）
        msg_otc = []
        # 【V0.9.5-goodinfo4+5 (vol-int) 修 otc fallback】2026-06-18 21:37 William 反映
        # 原本 missing_codes 全部 codes（tse 完全失敗時）→ otc 也打 50 個 → 也失敗
        # 改：missing 超過 batch 90%（表示 tse 整批失敗、不是「抓不到個別股」）→ 跳過 otc
        if missing_codes and len(missing_codes) < len(batch_codes) * 0.9:
            time.sleep(0.5)  # 避免連打兩個請求被擋
            ex_ch = "|".join(f"otc_{c}.tw" for c in missing_codes)
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}"
            for attempt in range(2):  # otc fallback 只 retry 2 次（比 tse 少）
                try:
                    resp = requests.get(
                        url,
                        headers={
                            "User-Agent": f"StockTool/{VERSION} (+https://github.com/apingchang/StockTools)",
                            "Referer": "https://mis.twse.com.tw/",
                            "Accept": "application/json,text/plain,*/*",
                            "Accept-Language": "zh-TW,zh;q=0.9",
                        },
                        timeout=15,
                    )
                    resp.raise_for_status()
                    msg_otc = resp.json().get("msgArray", [])
                    break
                except Exception as e:
                    wait_sec = [2.0, 5.0][attempt] if attempt < 2 else 5.0
                    if attempt < 1:
                        print(f"⚠️ TWSE API otc fallback 失敗（重試 {attempt+1}/2）：{type(e).__name__} - 等 {wait_sec}s")
                        time.sleep(wait_sec)
                    else:
                        print(f"⚠️ TWSE API otc fallback 失敗（放棄）：{type(e).__name__}: {e}")
                        msg_otc = []
        elif missing_codes:
            # tse 整批失敗（missing > 90%）→ 不打 otc（otc 也會被擋）
            print(f"⚠️ TWSE tse 整批失敗（{len(missing_codes)}/{len(batch_codes)}）→ 跳過 otc fallback")

        all_msg = msg_tse + msg_otc

        for rec in all_msg:
            raw_code = rec.get("c", "").strip()
            if not raw_code:
                continue
            z = rec.get("z", "-")   # 現價（盤中）
            o = rec.get("o", "-")   # 開盤價
            y = rec.get("y", "-")   # 昨收

            # 現價計算：z 為 "-" → fallback 到 o → fallback 到 y
            if z != "-":
                price = float(z)
            elif o != "-":
                price = float(o)
            elif y != "-":
                price = float(y)
            else:
                price = None

            # 【V0.9.5-info3 新增】MIS API 沒「漲跌」欄位、要自己算 (現價 - 昨收)
            # 【原本】漲跌是從 STOCK_DAY_ALL 的 Change 欄位拿的
            # 但 V0.9.5-info3 改用 MIS 即時為主、MIS 不給 Change → 要用 z - y 算
            change = None
            if price is not None and y != "-":
                try:
                    change = round(price - float(y), 2)
                except (ValueError, TypeError):
                    change = None

            # 【V0.9.5-goodinfo4+5 (vol-int) 修正】2026-06-18 20:05 William 反映
            # 「每日總成交量不會有小數點」、「今天 2548 是 4020 張」
            # 【V0.9.5-goodinfo4+5 (vol-no-divide) 修正】2026-06-18 21:54 William 反映
            # 「成交量不要除以1000應該就對了」
            # → TWSE MIS API 的 v 欄位已經是「張」（不是股）
            # → 2548 v=4016 → 顯示 4,016 張（不是 4 張）
            # → 我之前看 Asoul/tsrtc 文件以為是股、所以寫 // 1000 → 顯示 4 張
            # → 那是錯的：v 已經是張、不需要除
            v_raw = rec.get("v", "0")
            try:
                vol = int(float(v_raw))  # v 已經是「張」（整數）
            except (ValueError, TypeError):
                vol = 0

            rows.append({
                "股票代號": raw_code,
                "現價": price,
                "漲跌": change,
                "成交量_張": vol,
                # 【V0.9.5-info3】個股對應的成交交易日 (西元格式 "20260626")
                # - 收盤後抓: d = 今日 (= 个股今日收盤對應日)
                # - 盤中抓: d = 今日 (= 即時價對應日)
                # - 个股今日沒成交 (z="-"): d = 該股最後成交日 (TWSE API 給的)
                "data_date_raw": rec.get("d", ""),
            })

        # tse_ + otc_ 都沒回的股 → 另設 None（後面 caller 會 fallback 到 cache / FinMind）
        for code in batch_codes:
            if not any(str(r.get("c", "")).strip() == code for r in all_msg):
                rows.append({"股票代號": code, "現價": None, "漲跌": None, "成交量_張": 0.0, "data_date_raw": ""})

        # 進度回呼
        n_done = min((batch_idx + 1) * _TWSE_REALTIME_BATCH_SIZE, total)
        _MS_PROGRESS["done"] = n_done
        if progress_callback:
            progress_callback(n_done, total)

        # 輕微延遲，避免對 TWSE 伺服器造成壓力
        if batch_idx < n_batches - 1:
            time.sleep(0.5)  # 【V0.9.5-info3】原本 0.1s 太短、連打 30 批被 rate limit

    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["股票代號", "現價", "漲跌", "成交量_張", "data_date_raw"])
    df["股票代號"] = df["股票代號"].astype(str).str.strip()
    return df


_FINMIND_PRICE_CACHE = {}   # {stock_id: {date: row}}（多日 cache）


def _pick_latest_price_row(data: list) -> tuple:
    """從 FinMind TaiwanStockPrice 資料中選「今日」或退到「前一個交易日」的一筆

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本：直接 data[-1] → 盤中時 data[-1] 可能是今日（對）或昨日（誤）
    修法：從後往前找第一個 date == today 的、找不到就回傳 data[-1]（最後一個交易日）

    Returns
    -------
    (row, date_str) → 選到的 row 跟它的 date（ROC 格式 '1150617'）
    """
    from datetime import datetime as _dt
    today_roc = (_dt.now().year - 1911) * 10000 + _dt.now().month * 100 + _dt.now().day
    # 從後往前找
    for rec in reversed(data):
        rec_date = rec.get("date", "")
        if str(rec_date) == str(today_roc):
            return rec, rec_date
    # 找不到今日 → 取最後一筆（上一個交易日的收盤）
    if data:
        return data[-1], data[-1].get("date", "")
    return None, None


_FINMIND_DIVIDEND_CACHE = {}  # {stock_id: {year: {cash, stock}}}


def _finmind_get(dataset: str, stock_id: str, start: str, end: str, retry: int = 2) -> list:
    """統一的 FinMind API 呼叫（含 429 回退、402 額度檢查）。

    重要：402 Payment Required 表示 FinMind plan 額度用完
          此時應規舉到上层、不要 silently 回傳空 list
    （空 list 會讓 caller 誤以為「該股沒股利」而不是「API 額度不夠」）
    """
    for attempt in range(retry + 1):
        try:
            r = requests.get(FINMIND_BASE, params={
                "dataset": dataset,
                "data_id": stock_id,
                "start_date": start,
                "end_date": end,
            }, timeout=20)
            if r.status_code == 429:
                time.sleep(61)
                continue
            if r.status_code == 402:
                # FinMind plan 額度用完 → 拋例外（不再 silently 回傳空）
                raise RuntimeError(
                    "FinMind 額度已用完（status 402）｜請升級 plan 或等下月重置"
                    f"｜URL: {r.url}"
                )
            r.raise_for_status()
            d = r.json()
            return d.get("data", []) or []
        except RuntimeError:
            # 402 額度錯誤直接往上拋
            raise
        except Exception:
            if attempt < retry:
                time.sleep(2)
            return []
    return []


def _parse_roc_year(year_str: str) -> int:
    """把 "113年第3季" → 2024（西元年）。民國年 = 西元年 - 1911。"""
    import re
    m = re.match(r"(\d+)年", str(year_str))
    if m:
        return int(m.group(1)) + 1911  # 錯誤：-1911；修正：+1911
    return 0


def _fetch_finmind_prices_batch(stock_ids: List[str],
                                progress_callback=None,
                                force_refresh: bool = False) -> pd.DataFrame:
    """
    批次抓取股票現價（FinMind TaiwanStockPrice，支援 rate limit 回退）。
    每批 10 個，間隔 0.35s，超過 300/h 會被擋 → 等 61s 再試。
    progress_callback(n_done, n_total) 可傳進來做 UI 更新。

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本：data[-1] 直接用 → 盤中時 data[-1] 可能是「上一個交易日的收盤」誤判為今日
    修法：用 _pick_latest_price_row 判斷 date == today
          - 盤後：data[-1].date == today → 拿今日收盤
          - 盤中：data[-1].date == today → 拿今日盤中最後一筆（盤中即時）
          - 週末：data[-1].date 是上週五 → 拿上週五收盤（合理）

    V0.9.5-goodinfo4.3 修 Bug：2026-06-18 William 反映
    原本：每次呼叫都用 _FINMIND_PRICE_CACHE 命中 → 「即時抓股價」checkbox 失效
          因為 App 啟動時背景抓過一次、cache 已被填滿、按 checkbox 也直接拿 cache
    修法：加 force_refresh 參數
          - True → 先清空 _FINMIND_PRICE_CACHE 再抓（用於「即時抓股價」checkbox）
          - False → 用 cache（默認，背景抓取場景）

    Parameters
    ----------
    stock_ids : list[str]
        要抓取的股票代號清單
    progress_callback : callable
        (n_done, n_total) → 進度更新回呼（用於 UI 動態顯示）
    force_refresh : bool
        True：清 cache 重抓（耗時）；False：直接用 cache（快速）
    """
    if force_refresh:
        # 【V0.9.5-goodinfo4.3】「即時抓股價」checkbox 場景
        # App 啟動時背景抓的 cache 不能擋、必須清掉重抓
        n_cleared = len(_FINMIND_PRICE_CACHE)
        _FINMIND_PRICE_CACHE.clear()
        # log 印在 console、不走 logger（背景 thread 也行）
        print(f"🔄 [force_refresh] 已清空 {n_cleared} 檔 price cache，重新打 FinMind")

    rows = []
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    total = len(stock_ids)
    _MS_PROGRESS["stage"] = "股價"
    _MS_PROGRESS["total"] = total

    for i, code in enumerate(stock_ids):
        code = str(code).strip()
        if code in _FINMIND_PRICE_CACHE:
            cached = _FINMIND_PRICE_CACHE[code]
            if cached:
                rows.append({"股票代號": code,
                            "現價": cached.get("close"),
                            "成交量_張": (cached.get("Trading_Volume", 0) or 0) / 1000})
        else:
            data = _finmind_get("TaiwanStockPrice", code, start_date, end_date)
            if data:
                latest, _date = _pick_latest_price_row(data)
                _FINMIND_PRICE_CACHE[code] = latest
                rows.append({"股票代號": code,
                            "現價": latest.get("close") if latest else None,
                            "成交量_張": ((latest.get("Trading_Volume", 0) or 0) / 1000) if latest else 0})
            else:
                _FINMIND_PRICE_CACHE[code] = None

            # Rate limit：每小時最多 300 次 → 每次間隔 12s
            # 實測 0.35s 可用（用 threading 並行），但避免一次打太多
            _MS_PROGRESS["done"] = i + 1
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, total)
            time.sleep(0.35)

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", "現價", "成交量_張"])


def _fmt_float(v, decimals: int = 2) -> str:
    """統一格式化數值為字串：None/NaN → '—'、否則顯示數值

    V0.9.5-goodinfo4 修 Bug：2026-06-17 William 反映
    原本用「if val and ...」是 truthy 判斷
    → 殖利率 0.0 被誤判為 None、顯示 '—'（0.0 是 falsy）
    → 5386 現金殖利率 0.3 會被當 0.0 顯示 '—' 看起來像無資料

    修法：用 pd.isna() 判斷（None/NaN 才視為空）、數值照實顯示
    """
    try:
        if pd.isna(v):
            return "—"
    except (TypeError, ValueError):
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fetch_finmind_dividend(stock_ids: List[str],
                             db_path: str = None,
                             progress_callback=None,
                             skip_remote: bool = False,
                             cache_max_age_days: int = 30) -> pd.DataFrame:
    """
    取得近 3 年股利（先查 DB，沒有的、或過期的才即時抓 FinMind 並寫回 DB）。
    - skip_remote=True: DB 沒有的回 None，不抓 FinMind（避免 rate limit）
    - cache_max_age_days：DB 資料超過 N 天視為過期（預設 30 天）→ 重抓 FinMind
      （避免 DB 過期→使用者誤以為沒額度問題是 DB 缺漏）
    - 第一次跑：會 FinMind 抓一批 + 寫 DB
    - 之後跑：只查 DB，不打網路

    【V0.9.5-goodinfo6++ 修】William 2026-06-26 13:56 反映：
      系統選股結果 9946 殖利率顯示 0.07 (應為 0)、
                  4973 殖利率顯示 0.015 (應為 1.28)
      根因：fetcher 預設 db_path = "dividend_history.db" 是相對路徑
      → App 跑時 cwd 不同會抓到空 DB 或錯的 DB → 殖利率全 None → fallback 估算
      → 9946 估算 (1.5×0.7/29) = 0.036 → 顯示 0.04 (但 William 說是 0.07、表示部分用 goodinfo 6.9%)
      修法：db_path=None 時自動找 fetch_market.py 同目錄的 dividend_history.db
            (絕對路徑、不受 cwd 影響)
    """
    # 【V0.9.5-goodinfo6++ 修】db_path=None 自動找正確路徑
    # fetch_market.py 在 source/stocktool/、DB 在 source/
    if db_path is None:
        _module_dir = os.path.dirname(os.path.abspath(__file__))
        _source_dir = os.path.dirname(_module_dir)  # source/
        db_path = os.path.join(_source_dir, "dividend_history.db")
    rows = []
    current_year = datetime.now().year
    """
    取得近 3 年股利（先查 DB，沒有的、或過期的才即時抓 FinMind 並寫回 DB）。
    - skip_remote=True: DB 沒有的回 None，不抓 FinMind（避免 rate limit）
    - cache_max_age_days：DB 資料超過 N 天視為過期（預設 30 天）→ 重抓 FinMind
      （避免 DB 過期→使用者誤以為沒額度問題是 DB 缺漏）
    - 第一次跑：會 FinMind 抓一批 + 寫 DB
    - 之後跑：只查 DB，不打網路
    """
    rows = []
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"

    # 1. 先查 DB（含 fetched_at 用來判斷過期）
    # 【V0.9.5-twser2 Fix】統一是用 _query_div_history_with_fetched（含 cash_yield_pct/share_yield_pct）
    #   cached[code] = {"_fetched_at": ..., "years": {year: {...}}}
    #   舊版 _query_div_history 無殖利率欄位 → 殖利率全部 None → "-"
    _init_div_history_db(db_path)
    cached_with_fetched = _query_div_history_with_fetched(
        db_path, [str(c).strip() for c in stock_ids]
    )
    cached = _query_div_history_with_fetched(
        db_path, [str(c).strip() for c in stock_ids]
    )

    # 2. 區分「DB 有的」跟「要即時抓的」
    #    - DB 沒有的 → 抓
    #    - DB 有但過期的（> cache_max_age_days）→ 抓
    #    - DB 有且新鮮的 → 跳過
    #    - cache_max_age_days < 0 視為「永不過期」→ 保持原本行為（向後相容）
    from datetime import datetime as _dt, timedelta as _td
    if cache_max_age_days < 0:
        threshold_iso = None  # 永不過期
    else:
        threshold_iso = (_dt.now() - _td(days=cache_max_age_days)).isoformat()
    to_fetch = []
    for c in [str(c).strip() for c in stock_ids]:
        if c not in cached_with_fetched:
            to_fetch.append(c)
        elif threshold_iso is not None:
            fetched_at = cached_with_fetched[c].get("_fetched_at", "")
            if fetched_at and fetched_at < threshold_iso:
                to_fetch.append(c)  # 過期
    if skip_remote:
        # 跳過 FinMind 抓取：DB 沒有的回 None（避免 rate limit）
        to_fetch = []
    fetch_rows: list = []
    _MS_PROGRESS["stage"] = "股利"
    _MS_PROGRESS["total"] = len(to_fetch)
    _MS_PROGRESS["error"] = ""  # 重設錯誤狀態
    import re as _re_div
    try:
        for i, code in enumerate(to_fetch):
            _MS_PROGRESS["done"] = i
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
            by_year: Dict[int, Dict[str, Any]] = {}
            for rec in data:
                year_str = rec.get("year", "")
                cash_raw = float(rec.get("CashEarningsDistribution") or 0)
                stock_raw = float(rec.get("StockEarningsDistribution") or 0)
                # 【V0.9.5+ Phase 10】保留 ex_date（除息日）給後面算殖利率用
                ex_date = rec.get("date", "") or ""
                m_q = _re_div.match(r"(\d+)年第(\d+)季", year_str)
                m_h1 = _re_div.match(r"(\d+)年前半年度", year_str)
                m_h2 = _re_div.match(r"(\d+)年後半年度", year_str)
                m_y = _re_div.match(r"^(\d+)年$", year_str)  # 純年（無季/半年度）
                is_max_logic = False  # 記 year 該年 是用 max 還是 sum 邏輯
                if m_q:
                    finmind_yr = int(m_q.group(1)) + 1911
                    is_max_logic = True
                elif m_h1:
                    finmind_yr = int(m_h1.group(1)) + 1911
                elif m_h2:
                    finmind_yr = int(m_h2.group(1)) + 1911
                elif m_y:
                    finmind_yr = int(m_y.group(1)) + 1911
                    is_max_logic = True
                else:
                    continue
                # 【V0.9.5-goodinfo6+ 修 Bug】FinMind year = 會計年度（ex: 113年）≠ 發放年度
                # ex_date 除息日才是對應 goodinfo 發放年度
                # 證據：6219 finmind 113年第4季 cash=0.7 ex_date=2025-07-03 → goodinfo 2025 發放=0.7
                # 證據：2342 finmind yr=2024 cash=0.299 ex_date=2025-08-08 → goodinfo 2025 cash=0.3
                # 修法：優先用 CashExDividendTradingDate（現金除息日）或 StockExDividendTradingDate（股票除權日）
                #       都不存在才退回 date 欄位（公告日）或 finmind year+1911
                cash_ex_date = rec.get("CashExDividendTradingDate", "") or ""
                stock_ex_date = rec.get("StockExDividendTradingDate", "") or ""
                if cash_ex_date and len(cash_ex_date) >= 4:
                    ex_date = cash_ex_date
                elif stock_ex_date and len(stock_ex_date) >= 4:
                    ex_date = stock_ex_date
                # ex_date 還是空才退回 finmind year+1911
                if ex_date and len(ex_date) >= 4:
                    yr = int(ex_date[:4])
                else:
                    yr = finmind_yr
                yd = by_year.setdefault(yr, {"cash": 0.0, "stock": 0.0, "ex_date": ""})
                if is_max_logic:
                    # max 邏輯：保留 cash 大的、ex_date 跟著更新到該筆
                    if cash_raw >= yd["cash"]:
                        yd["cash"] = cash_raw
                        yd["stock"] = stock_raw
                        yd["ex_date"] = ex_date
                else:
                    # sum 邏輯（半年配/季度配）：累加、ex_date 取最後一筆
                    yd["cash"] += cash_raw
                    yd["stock"] += stock_raw
                    if ex_date > yd["ex_date"]:
                        yd["ex_date"] = ex_date
            # 寫入 DB（V0.9.5+ Phase 10 加 ex_date欄位）
            for yr, d in by_year.items():
                fetch_rows.append((code, yr, d["cash"], d["stock"], "finmind", d["ex_date"], None))
            if (i + 1) % 10 == 0 and progress_callback:
                progress_callback(i + 1, len(to_fetch))
            time.sleep(0.35)
    except RuntimeError as e:
        # FinMind 402 額度已用完 → 記下錯誤、跳出 loop
        # 保留已抓到的 fetch_rows（不丢）
        _MS_PROGRESS["error"] = str(e)
        print(f"❌ FinMind 額度錯誤：{e}（已抓 {len(fetch_rows)} 筆、部分寫入 DB）")
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
        # 重新讀一次 DB 拿新資料（確保拿最新寫入的）
        cached = _query_div_history_with_fetched(db_path, [str(c).strip() for c in stock_ids])

    # 3. 組裝結果
    for code in [str(c).strip() for c in stock_ids]:
        # 【V0.9.5-twser2 Fix】用 _query_div_history_with_fetched 的 nested 結構：
        #   cached[code] = {"_fetched_at": ..., "years": {year: {...}}}
        #   所以要 .get("years", {}) 而不是直接 .get(year)
        code_data = cached.get(code, {})
        years_data = code_data.get("years", {}) if isinstance(code_data, dict) else {}
        this_yr = years_data.get(current_year, {})
        last_yr = years_data.get(current_year - 1, {})
        prev_yr = years_data.get(current_year - 2, {})
        rows.append({
            "股票代號": code,
            f"{current_year}現金股利": this_yr.get("cash", 0.0),
            f"{current_year}股票股利": this_yr.get("stock", 0.0),
            f"{current_year - 1}現金股利": last_yr.get("cash", 0.0),
            f"{current_year - 1}股票股利": last_yr.get("stock", 0.0),
            f"{current_year - 2}現金股利": prev_yr.get("cash", 0.0),
            f"{current_year - 2}股票股利": prev_yr.get("stock", 0.0),
            # V0.9.5+ Phase 10：回傳 ex_date / ex_date_close、供「去年現金殖利率」算法用
            f"{current_year - 1}除息日": this_yr.get("ex_date", "") or "",
            f"{current_year - 1}除息日收盤價": this_yr.get("ex_date_close"),
            # V0.9.5-goodinfo：殖利率（百分比, goodinfo 來源）— 優先用於殖利率算法
            f"{current_year}現金殖利率_goodinfo": this_yr.get("cash_yield_pct"),
            f"{current_year}股票殖利率_goodinfo": this_yr.get("share_yield_pct"),
            f"{current_year - 1}現金殖利率_goodinfo": last_yr.get("cash_yield_pct"),
            f"{current_year - 1}股票殖利率_goodinfo": last_yr.get("share_yield_pct"),
            f"{current_year - 2}現金殖利率_goodinfo": prev_yr.get("cash_yield_pct"),
            f"{current_year - 2}股票殖利率_goodinfo": prev_yr.get("share_yield_pct"),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["股票代號", f"{current_year}現金股利", f"{current_year}股票股利",
                 f"{current_year - 1}現金股利", f"{current_year - 1}股票股利",
                 f"{current_year - 2}現金股利", f"{current_year - 2}股票股利",
                 f"{current_year - 1}除息日", f"{current_year - 1}除息日收盤價",
                 f"{current_year}現金殖利率_goodinfo", f"{current_year}股票殖利率_goodinfo",
                 f"{current_year - 1}現金殖利率_goodinfo", f"{current_year - 1}股票殖利率_goodinfo",
                 f"{current_year - 2}現金殖利率_goodinfo", f"{current_year - 2}股票殖利率_goodinfo"])

def _background_fetch_all_dividend(stock_ids: List[str], db_path: str = None,
                                  progress_callback=None, batch_size: Optional[int] = None) -> int:
    """
    背景抓取全市場股利寫入 DB（手動啟動用）。

    Parameters
    ----------
    stock_ids : List[str]
        股票代號清單
    db_path : str
        DB 路徑
    progress_callback : callable
        進度回呼 (done, total)
    batch_size : int | None
        - None = 一次抓全部缺漏（舊行為）
        - 100  = 只抓缺漏中的前 N 檔（V0.9.5+ 推薦用，Free tier 額度友善）

    Returns
    -------
    int
        這次實際抓的股數（原本沒資料的）
        -1 = FinMind 402 額度錯誤
         0 = 沒缺漏、沒抓
    """
    # 【V0.9.5-goodinfo6++】db_path=None 自動找正確路徑（source/dividend_history.db）
    if db_path is None:
        _module_dir = os.path.dirname(os.path.abspath(__file__))
        _source_dir = os.path.dirname(_module_dir)  # source/
        db_path = os.path.join(_source_dir, "dividend_history.db")
    _init_div_history_db(db_path)
    cached = _query_div_history(db_path, [str(c).strip() for c in stock_ids])
    to_fetch = [c for c in stock_ids if str(c).strip() not in cached]
    if not to_fetch:
        return 0
    # V0.9.5+: 批次切片（Free tier 額度友善、可分散跑）
    if batch_size is not None and batch_size > 0 and len(to_fetch) > batch_size:
        to_fetch = to_fetch[:batch_size]
    current_year = datetime.now().year
    start_date = f"{current_year - 2}-01-01"
    end_date = f"{current_year}-12-31"
    fetch_rows: list = []
    total = len(to_fetch)
    quota_exceeded = False
    for i, code in enumerate(to_fetch):
        try:
            data = _finmind_get("TaiwanStockDividend", code, start_date, end_date)
        except RuntimeError as e:
            # FinMind 402 額度用完 → 停止 loop、保留已抓的
            print(f"❌ {e}")
            quota_exceeded = True
            break
        for rec in data:
            yr = _parse_roc_year(rec.get("year", ""))
            if yr == 0:
                continue
            # 【V0.9.5-goodinfo6+ 修 Bug】FinMind year 是會計年度、不是發放年度
            # 用 CashExDividendTradingDate / StockExDividendTradingDate 年份才是 goodinfo 發放年度
            cash_ex_date = rec.get("CashExDividendTradingDate", "") or ""
            stock_ex_date = rec.get("StockExDividendTradingDate", "") or ""
            ex_date_str = cash_ex_date or stock_ex_date or rec.get("date", "") or ""
            if ex_date_str and len(ex_date_str) >= 4:
                yr = int(ex_date_str[:4])
            cash_raw = float(rec.get("CashEarningsDistribution") or 0)
            stock_raw = float(rec.get("StockEarningsDistribution") or 0)
            fetch_rows.append((code, yr, cash_raw, stock_raw, "finmind"))
        time.sleep(0.35)
        if progress_callback:
            try:
                progress_callback(i + 1, total)
            except Exception:
                pass
    if fetch_rows:
        _upsert_div_history(db_path, fetch_rows)
    # 用「負值」表示 FinMind 額度錯誤（讓 caller 知道不是完成）
    if quota_exceeded:
        return -1
    return len(to_fetch)


def _update_ex_date_close(db_path: str, stock_id: str, year: int,
                          ex_date: str, ex_date_close: float) -> None:
    """V0.9.5+ Phase 10：把「除息日 + 除息日收盤價」寫入 dividend_history 緩存
    下次重跑手動選股時免打 FinMind
    """
    import sqlite3
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """UPDATE dividend_history
                   SET ex_date = ?, ex_date_close = ?
                   WHERE stock_id = ? AND year = ?""",
                (ex_date, ex_date_close, stock_id, year),
            )
            conn.commit()
    except Exception:
        pass


def _fetch_ex_date_close(stock_id: str, ex_date: str) -> Optional[float]:
    """V0.9.5+ Phase 10：抓除息日當天（或附近）的收盤價

    William 11:39 反映：去年現金殖利率應除以「去年除息日收盤價」、不是現價
    本函式供「手動選股」算去年現金殖利率時使用

    Parameters
    ----------
    stock_id : str
        股票代號
    ex_date : str
        除息日 (YYYY-MM-DD)、可能是空字串

    Returns
    -------
    Optional[float]
        除息日附近的收盤價（None = 抓不到）
    """
    if not ex_date or not stock_id:
        return None
    try:
        from datetime import datetime as _dt, timedelta as _td
        ed = _dt.strptime(ex_date, "%Y-%m-%d")
        # 抓除息日 ±3 天的股價（避免假日沒資料）
        start = (ed - _td(days=3)).strftime("%Y-%m-%d")
        end = (ed + _td(days=3)).strftime("%Y-%m-%d")
        data = _finmind_get("TaiwanStockPrice", stock_id, start, end)
        if not data:
            return None
        # 找最接近 ex_date 的那一天
        best = None
        best_diff = None
        for rec in data:
            rec_date = rec.get("date", "")
            try:
                rd = _dt.strptime(rec_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            diff = abs((rd - ed).days)
            if best_diff is None or diff < best_diff:
                best = rec
                best_diff = diff
        if best:
            close = float(best.get("close") or 0)
            return close if close > 0 else None
    except RuntimeError:
        # FinMind 額度用完 → silently 回 None
        return None
    except Exception:
        return None
    return None



def fetch_csv_requests(session: requests.Session, url: str, cfg: StrategyConfig,
                       encodings=("utf-8-sig", "utf-8")) -> pd.DataFrame:
    r = session.get(url, timeout=cfg.timeout, verify=cfg.verify_ssl)
    r.raise_for_status()
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(r.content), encoding=enc, engine="python", on_bad_lines="skip")
        except Exception:
            continue
    raise RuntimeError(f"讀取失敗：{url}")


# ==========================================================
# 【V1.1-remove-after-hour】2026-06-29 13:46 William 反映：
# 「手動選股結果盤後量都沒資料、取消顯示！」
# 拿掉 fetch_after_hour_volumes() 函數、Step 6 整合、return cols 的「盤後量_股」
#
# 原因：
# - TWSE BFT41U API 只有個位數筆個股有盤後定價成交
# - TPEx 上櫃無公開 API
# - 絕大多數個股顯示「—」、欄位沒實質用處
# - 未來若需要可從 git history 還原
# ==========================================================


# ==========================================================
# Data fetchers
# ==========================================================

def fetch_prices(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    """【V0.9.5-info3】2026-06-27 00:17 William 反映：
    「手動選股資料日期要最後收盤日期及收盤價格才對」

    【舊版問題（V0.9.5-info2、已廢棄）】
    - data_date 一律 = today
    - 但股價本身仍是昨日收盤 (TWSE STOCK_DAY_ALL 沒 flush)
    - 結果「日期統一、價格是昨日」的混亂狀態

    【V0.9.5-info3 新版】
    - 以 TWSE MIS 即時 API 為主：拿「當下真實市場狀態」
      - 收盤後: pz = 今日收盤價、d = 今日 (TWSE 會在 ~16:00 開始提供)
      - 盤中: pz = 當下成交價、d = 今日
      - 個股今日沒成交 (z="-"): fallback 到 o (開盤) 或 y (昨收)
    - 興櫃股 / MIS 失敗的股 → fallback 到 STOCK_DAY_ALL + TPEx
    - data_date 完整來源：
      - MIS 有回的股：個股對應成交日（d 欄位）
      - MIS 沒回的股：STOCK_DAY_ALL 的 Date（= 個股最後成交日）
    - 結果：股價與 data_date 是同一個時點的真實狀態
    """
    from datetime import datetime as _dt
    today_ad = _dt.now().strftime("%Y-%m-%d")

    # Step 1: 抓 STOCK_DAY_ALL + TPEx（拿全市場清單、公司名、與 MIS 失敗時的 fallback 資料）
    twse_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    tpex_url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"

    try:
        twse_response = session.get(twse_url, timeout=cfg.timeout)
        twse_response.raise_for_status()
        twse = pd.DataFrame(twse_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上市股價失敗：{e}")
        twse = pd.DataFrame()

    try:
        tpex_response = session.get(tpex_url, timeout=cfg.timeout)
        tpex_response.raise_for_status()
        tpex = pd.DataFrame(tpex_response.json())
    except Exception as e:
        print(f"⚠️ 讀取上櫃股價失敗：{e}")
        tpex = pd.DataFrame()

    if twse.empty and tpex.empty:
        print("❌ 無法讀取任何股價資料")
        return pd.DataFrame()

    _twse_date_col = find_col(twse.columns, ["Date", "資料日期"])
    _tpex_date_col = find_col(tpex.columns, ["Date", "資料日期"])
    _twse_vol_col = find_col(twse.columns, ["TradeVolume"])
    _tpex_vol_col = find_col(tpex.columns, ["TradingShares", "TradeVolume"])

    if twse.empty:
        twse = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "股價", "漲跌"])
    if tpex.empty:
        tpex = pd.DataFrame(columns=["股票代號", "公司名稱_來源", "股價", "漲跌"])

    twse = twse.rename(columns={
        find_col(twse.columns, ["證券代號", "Code"]): "股票代號",
        find_col(twse.columns, ["證券名稱", "Name"]): "公司名稱_來源",
        find_col(twse.columns, ["收盤價", "ClosingPrice"]): "股價",
        find_col(twse.columns, ["漲跌價差", "Change"]): "漲跌",
        **({_twse_date_col: "_raw_date"} if _twse_date_col else {}),
        **({_twse_vol_col: "_raw_volume"} if _twse_vol_col else {}),
    })

    tpex = tpex.rename(columns={
        find_col(tpex.columns, ["SecuritiesCompanyCode", "股票代號", "Code"]): "股票代號",
        find_col(tpex.columns, ["CompanyName", "公司名稱", "Name"]): "公司名稱_來源",
        find_col(tpex.columns, ["Close", "收盤", "ClosingPrice"]): "股價",
        find_col(tpex.columns, ["Change", "漲跌"]): "漲跌",
        **({_tpex_date_col: "_raw_date"} if _tpex_date_col else {}),
        **({_tpex_vol_col: "_raw_volume"} if _tpex_vol_col else {}),
    })

    def _roc_to_ad(s: str) -> str:
        """民國年 YYYMMDD → 西元 YYYY-MM-DD"""
        try:
            s = str(s).strip()
            if len(s) != 7 or not s.isdigit():
                return ""
            roc_y = int(s[:3])
            m = int(s[3:5])
            d = int(s[5:7])
            return f"{roc_y + 1911:04d}-{m:02d}-{d:02d}"
        except Exception:
            return ""

    if "_raw_date" not in twse.columns:
        twse["_raw_date"] = ""
    if "_raw_date" not in tpex.columns:
        tpex["_raw_date"] = ""
    if "_raw_volume" not in twse.columns:
        twse["_raw_volume"] = None
    if "_raw_volume" not in tpex.columns:
        tpex["_raw_volume"] = None

    def _vol_to_kilos(s):
        try:
            v = pd.to_numeric(s, errors="coerce")
            if pd.isna(v):
                return None
            return v / 1000.0
        except Exception:
            return None

    # Step 2: 全市場清單
    full_list = pd.concat([twse[["股票代號", "公司名稱_來源"]],
                           tpex[["股票代號", "公司名稱_來源"]]], ignore_index=True)
    full_list["股票代號"] = full_list["股票代號"].astype(str).str.strip()
    full_list = full_list.drop_duplicates("股票代號").reset_index(drop=True)
    all_codes = full_list["股票代號"].tolist()

    # Step 3: TWSE MIS 即時 API 抓全部（上市上櫃涵蓋、~30 批 × 0.1s ~3s）
    print(f"📡 TWSE MIS 即時股價、{len(all_codes)} 檔...")
    realtime_df = _fetch_twse_realtime_batch(all_codes, progress_callback=None)
    # realtime_df 欄位: 股票代號 / 現價 / 成交量_張 / data_date_raw (西元 "20260626")

    # Step 4: 合併
    merged = full_list.merge(realtime_df, on="股票代號", how="left")
    # MIS 沒回的股（興櫃股）→ 用 STOCK_DAY_ALL / TPEx 補
    missing = merged[merged["現價"].isna()]["股票代號"].tolist()
    if missing:
        print(f"⚠️ MIS 未覆蓋 {len(missing)} 檔 (興櫃股)、fallback 到 STOCK_DAY_ALL / TPEx")
        fallback = pd.concat([
            twse[["股票代號", "股價", "漲跌", "_raw_date", "_raw_volume"]],
            tpex[["股票代號", "股價", "漲跌", "_raw_date", "_raw_volume"]]
        ], ignore_index=True)
        fallback["股票代號"] = fallback["股票代號"].astype(str).str.strip()
        fallback = fallback[fallback["股票代號"].isin(missing)].drop_duplicates("股票代號")
        for _, r in fallback.iterrows():
            code = r["股票代號"]
            if code in merged["股票代號"].values:
                idx = merged[merged["股票代號"] == code].index[0]
                if pd.isna(merged.at[idx, "現價"]):
                    merged.at[idx, "現價"] = pd.to_numeric(r["股價"], errors="coerce")
                    merged.at[idx, "漲跌"] = pd.to_numeric(r["漲跌"], errors="coerce")
                # data_date 用 STOCK_DAY_ALL 的 Date (個股最後成交日、民國格式)
                if pd.isna(merged.at[idx, "data_date_raw"]) or str(merged.at[idx, "data_date_raw"]).strip() == "":
                    merged.at[idx, "data_date_raw"] = r["_raw_date"]
                # 成交量 fallback
                # 【V0.9.5-info3 修】原本只查 isna、但 MIS 設的預設值是 0.0 (不是 NaN)
                # → 0.0 被誤判為「已有值」、fallback 不會覆蓋
                # → 修法: 0 也視為「需要 fallback」
                cur_vol = merged.at[idx, "成交量_張"]
                if pd.isna(cur_vol) or cur_vol == 0:
                    merged.at[idx, "成交量_張"] = _vol_to_kilos(r["_raw_volume"])

    # Step 5: 整理欄位
    merged["現價"] = pd.to_numeric(merged["現價"], errors="coerce")
    merged["漲跌"] = pd.to_numeric(merged["漲跌"], errors="coerce")
    merged["成交量_張"] = pd.to_numeric(merged["成交量_張"], errors="coerce")

    def _mis_date_to_ad(s):
        """MIS d 欄位 "20260626" (西元 8 碼) → "2026-06-26" """
        try:
            s = str(s).strip()
            if len(s) == 8 and s.isdigit():
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            return ""
        except Exception:
            return ""

    # data_date 來源:
    # - MIS d 欄位 (8 碼西元): 個股對應成交日
    # - fallback (7 碼民國): STOCK_DAY_ALL Date
    # - 都沒有: today (避免空字串)
    def _to_ad_safe(x):
        x = str(x).strip()
        if len(x) == 8 and x.isdigit():
            return _mis_date_to_ad(x)
        return _roc_to_ad(x)

    merged["data_date"] = merged["data_date_raw"].apply(_to_ad_safe)
    # 空的、格式不對的 → today
    merged.loc[merged["data_date"].fillna("") == "", "data_date"] = today_ad
    merged = merged.rename(columns={"現價": "股價"})

    # 【V1.1-remove-after-hour】拿掉 Step 6: 盤後定價交易量
    # 原因：TWSE BFT41U 只有個位數筆個股有資料、TPEx 無 API、絕大多數顯示「—」

    return merged[["股票代號", "公司名稱_來源", "股價", "漲跌", "data_date", "成交量_張"]].reset_index(drop=True)


def fetch_revenue_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv"]
    rev = pd.concat([fetch_csv_requests(session, u, cfg) for u in urls], ignore_index=True)

    code_col = find_col(rev.columns, ["公司代號"])
    ym_col = find_col(rev.columns, ["資料年月"])
    rev_col = find_col(rev.columns, ["營業收入-當月營收", "當月營收"])
    yoy_col = find_col(rev.columns, ["累計營業收入-前期比較增減", "前期比較增減"])
    yoy2_col = find_col(rev.columns, ["營業收入-去年同月增減", "去年同月增減"])

    if code_col is None or ym_col is None or rev_col is None:
        raise RuntimeError(f"營收欄位無法識別：{rev.columns}")

    rename_map = {code_col: "股票代號", ym_col: "年月", rev_col: "當月營收"}
    if yoy_col:
        rename_map[yoy_col] = "累計年增(%)"
    if yoy2_col:
        rename_map[yoy2_col] = "當月年增(%)"

    rev = rev.rename(columns=rename_map)
    rev["股票代號"] = rev["股票代號"].astype(str).str.strip()
    rev["年月"] = pd.to_numeric(rev["年月"], errors="coerce")

    latest_month = rev["年月"].max()
    rev = rev[rev["年月"] == latest_month].copy()

    rev["當月營收(億元)"] = to_num_series(rev["當月營收"]) / 1e8
    if "累計年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["累計年增(%)"])
    elif "當月年增(%)" in rev.columns:
        rev["營收YoY(%)"] = to_num_series(rev["當月年增(%)"])
    else:
        rev["營收YoY(%)"] = 0.0

    return rev[["股票代號", "年月", "當月營收(億元)", "營收YoY(%)"]].drop_duplicates("股票代號").reset_index(drop=True)


def fetch_eps_latest(session: requests.Session, cfg: StrategyConfig) -> pd.DataFrame:
    urls = ["https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv",
            "https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv"]

    eps_list = []
    for url in urls:
        try:
            df = fetch_csv_requests(session, url, cfg)
            eps_list.append(df)
        except Exception as e:
            print(f"⚠️ 讀取 {url} 失敗：{e}")

    if not eps_list:
        return pd.DataFrame()

    eps = pd.concat(eps_list, ignore_index=True)

    code_col = find_col(eps.columns, ["公司代號", "證券代號"])
    year_col = find_col(eps.columns, ["年度", "西元年度"])
    q_col = find_col(eps.columns, ["季別", "季度"])
    eps_col = find_col(eps.columns, ["基本每股盈餘(元)", "基本每股盈餘", "每股盈餘"])

    if None in [code_col, year_col, q_col, eps_col]:
        print(f"❌ 找不到必要欄位")
        return pd.DataFrame()

    eps = eps.rename(columns={
        code_col: "股票代號",
        year_col: "年度",
        q_col: "季別",
        eps_col: "EPS"
    })

    eps["股票代號"] = eps["股票代號"].astype(str).str.strip()
    eps["年度"] = pd.to_numeric(eps["年度"], errors="coerce")
    eps["季別"] = pd.to_numeric(eps["季別"], errors="coerce")
    eps["EPS"] = pd.to_numeric(eps["EPS"], errors="coerce")
    eps = eps.dropna(subset=["年度", "季別", "股票代號"])

    if eps.empty:
        return pd.DataFrame()

    # 找「覆蓋率達標」的最新季，避免年初時只取到少數 Q4 公告的公司
    # 邏輯：以最大覆蓋數為基準，要求 >= 80% 才採用
    year_q_counts = eps.groupby(["年度", "季別"]).size().reset_index(name='count')
    max_count = int(year_q_counts['count'].max())
    threshold = max_count * 0.8
    candidates = year_q_counts[year_q_counts['count'] >= threshold]

    if candidates.empty:
        # 全部都不達標（罕見），退而求其次用最大覆蓋那一季
        latest_row = year_q_counts.sort_values('count', ascending=False).iloc[0]
    else:
        latest_row = candidates.sort_values(['年度', '季別'], ascending=False).iloc[0]

    # Fix9: 民國年轉西元年（跟 DB 對齊，GoodInfo 歷史庫用西元年）
    latest_year = int(latest_row['年度']) + 1911
    latest_q = int(latest_row['季別'])
    latest_count = int(latest_row['count'])
    coverage_pct = latest_count / max_count * 100

    print(f"📊 EPS 最新季: {latest_year}Q{latest_q}（{latest_count}/{max_count} 筆，覆蓋率 {coverage_pct:.0f}%）")

    # ========== V0.9.4 phase4: 寫入歷史庫 ==========
    # 每天都存最新一季，累積一年後 fetch_eps_latest 就能算 YoY
    try:
        _init_eps_history_db(cfg.eps_history_db)
        # Fix9: MOPS CSV 的「年度」是民國年（例如 115=2026），
        # 但 GoodInfo 匯入歷史庫用的是西元年（2024、2025），要轉成西元年才對得到
        rows_to_save = [
            (str(r["股票代號"]).strip(), int(r["年度"]) + 1911, int(r["季別"]),
             float(r["EPS"]) if pd.notna(r["EPS"]) else None, "twse_csv")
            for _, r in eps.iterrows()
        ]
        saved = _upsert_eps_history(cfg.eps_history_db, rows_to_save)
        stats = _eps_history_stats(cfg.eps_history_db)
        print(f"💾 歷史庫: 本次存 {saved} 筆，總累計 {stats['total']} 筆 / {stats['periods']} 季")
    except Exception as e:
        print(f"⚠️ 寫入歷史庫失敗（不影響本函式結果）：{e}")

    # Fix9: eps["年度"] 還是民國年（原始 CSV）、latest_year 已經是西元年
    cur = eps[(eps["年度"] == latest_year - 1911) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS本期"})

    # ========== V0.9.4 phase4: 從歷史庫查去年同期 ==========
    # TWSE CSV 只保留最新一季，必須靠歷史庫才能跨年比對
    prev_year = latest_year - 1
    prev_from_csv = eps[(eps["年度"] == prev_year - 1911) & (eps["季別"] == latest_q)][["股票代號", "EPS"]].rename(
        columns={"EPS": "EPS去年"})
    prev_from_db = _query_eps_history(cfg.eps_history_db, prev_year, latest_q)
    if not prev_from_db.empty:
        prev_from_db = prev_from_db.rename(columns={"eps": "EPS去年"})[["stock_id", "EPS去年"]]
        prev_from_db = prev_from_db.rename(columns={"stock_id": "股票代號"})
        # CSV 與 DB 合併，CSV 優先（更新）
        prev = prev_from_csv.merge(prev_from_db, on="股票代號", how="outer", suffixes=("_csv", "_db"))
        prev["EPS去年"] = prev["EPS去年_csv"].combine_first(prev["EPS去年_db"])
        prev = prev[["股票代號", "EPS去年"]]
        print(f"📂 去年同期 {prev_year}Q{latest_q}: CSV {len(prev_from_csv)} 筆 + 歷史庫 {len(prev_from_db)} 筆 → 合併 {len(prev)} 筆")
    else:
        prev = prev_from_csv
        if prev.empty:
            # Fix9: 從 GoodInfo 歷史庫找「去年 Q4 全年 EPS」當 fallback
            # （GoodInfo P20U/P20-50/P20L EPSRate12Y.xls 都有 12 年完整資料）
            #
            # 【v1.1.1+ William 2026-06-24 21:48 反映】
            # 3490 EPSYoY 算成 4040%（實際應為 476%）：因為本期是 Q1、去比去年 Q4 全年 EPS=0.05、
            # (2.07-0.05)/0.05=40.4=4040%。Q1 vs 全年 是有意義的理語義但使用者只关心「同季 YoY」。
            # 修法：Q1/Q2/Q3 不適用 Q4 fallback、只有 Q4（本身就是全年）才適用。
            if latest_q == 4:
                prev_q4 = _query_eps_history(cfg.eps_history_db, prev_year, 4)
                if not prev_q4.empty and (prev_q4["source"] == "goodinfo").any():
                    prev = prev_q4.rename(columns={"eps": "EPS去年", "stock_id": "股票代號"})[
                        ["股票代號", "EPS去年"]
                    ]
                    prev["股票代號"] = prev["股票代號"].astype(str).str.strip()
                    print(f"   GoodInfo Q4 全年 EPS fallback: {len(prev)} 檔有 {prev_year}Q4 EPS")
                else:
                    print(f"⚠️ 去年同期 {prev_year}Q{latest_q} 沒有資料（CSV 無、歷史庫也無）→ YoY 將全 NA")
            else:
                # Q1/Q2/Q3 不適用 Q4 全年 fallback → 不算 YoY、等 GoodInfo 覆蓋
                print(f"⚠️ 去年同期 {prev_year}Q{latest_q} 沒有資料、不适用 Q4 全年 fallback（避免 Q1 vs 全年 误算）→ YoY 留空等 GoodInfo 覆蓋")

    out = cur.merge(prev, on="股票代號", how="left")

    def safe_yoy(row):
        if pd.isna(row["EPS去年"]) or row["EPS去年"] == 0:
            return pd.NA
        return (row["EPS本期"] - row["EPS去年"]) / abs(row["EPS去年"])

    out["EPSYoY_raw"] = out.apply(safe_yoy, axis=1)
    out["EPSYoY_顯示(%)"] = out["EPSYoY_raw"].apply(
        lambda x: round(x * 100, 2) if pd.notna(x) else pd.NA
    )

    # Fix10: GoodInfo 12QEPSRate 直接覆蓋 (更精準的同季 YoY)
    # "26Q1成長(%)" 是 GoodInfo 算好的 %，比 EPS相減÷base 還準
    gi_12q = _load_goodinfo_12q_epsrate()
    quarter_key = f"{str(latest_year)[-2:]}Q{latest_q}"  # 2026Q1 -> "26Q1"
    if gi_12q:
        covered = 0
        for sid, qdict in gi_12q.items():
            if quarter_key not in qdict:
                continue
            val = qdict[quarter_key]
            sid_clean = str(sid).strip()
            mask = out["股票代號"].astype(str).str.strip() == sid_clean
            if mask.any():
                out.loc[mask, "EPSYoY_raw"] = val / 100.0
                out.loc[mask, "EPSYoY_顯示(%)"] = val
                covered += int(mask.sum())
        total = out["EPSYoY_顯示(%)"].notna().sum()
        print(f"📈 GoodInfo 12QEPSRate 覆蓋 {quarter_key}: {covered}/{len(out)} (總有 YoY: {total}/{len(out)})")

    out["EPS季別"] = f"{latest_year}Q{latest_q}"

    print(f"📊 EPS 計算結果: 本期 {len(out)} 筆，有 YoY 資料 {out['EPSYoY_raw'].notna().sum()} 筆")

    return out[["股票代號", "EPS季別", "EPS本期", "EPSYoY_raw", "EPSYoY_顯示(%)"]].drop_duplicates(
        "股票代號").reset_index(drop=True)


# ==========================================================
# TWSE STOCK_DAY fetch
# ==========================================================

def safe_parse_json(r):
    text = (r.text or "").strip()
    if not text or text.startswith("<"):
        return None
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return r.json()
    except Exception:
        return None


def fetch_twse_stock_day_month(session: requests.Session, cfg: StrategyConfig, stock_no: str, yyyymm01: str) -> pd.DataFrame:
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": yyyymm01, "stockNo": stock_no}

    for attempt in range(1, cfg.twse_retries + 1):
        try:
            r = session.get(url, params=params, timeout=cfg.timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")

            js = safe_parse_json(r)
            if js is None or js.get("stat") != "OK" or "data" not in js:
                return pd.DataFrame()

            fields = js.get("fields", [])
            data = js.get("data", [])
            if not fields or not data:
                return pd.DataFrame()

            dfm = pd.DataFrame(data, columns=fields)

            date_col = find_col(dfm.columns, ["日期"])
            vol_col = find_col(dfm.columns, ["成交股數"])
            close_col = find_col(dfm.columns, ["收盤價"])
            if date_col is None or close_col is None:
                return pd.DataFrame()

            rename_map = {date_col: "Date_roc", close_col: "Close"}
            if vol_col:
                rename_map[vol_col] = "Volume"
            dfm = dfm.rename(columns=rename_map)

            dfm["Date"] = pd.to_datetime(dfm["Date_roc"].apply(roc_to_ad))
            dfm["股票代號"] = str(stock_no).strip()
            dfm["Close"] = to_num_series(dfm["Close"])
            if "Volume" in dfm.columns:
                dfm["Volume"] = to_num_series(dfm["Volume"])
            else:
                dfm["Volume"] = pd.NA

            return dfm[["Date", "股票代號", "Close", "Volume"]].dropna(subset=["Date", "Close"])

        except Exception:
            if attempt == cfg.twse_retries:
                return pd.DataFrame()
            time.sleep(cfg.twse_backoff * attempt)
    return pd.DataFrame()


def fetch_twse_history(session: requests.Session, cfg: StrategyConfig, codes: List[str], logger: GuiLogger, history_months: int) -> pd.DataFrame:
    # 【v1.1 重構】避免循環 import fetch_market ↔ export_excel
    # 改用 lazy lookup
    from . import export_excel as _export_excel
    hist_list = []
    for code in codes:
        try:
            df = _export_excel.get_stock_history(session, cfg, code, logger, history_months)
            if df is not None and not df.empty:
                df["股票代號"] = code
                hist_list.append(df)
        except Exception as e:
            logger.log(f"❌ [{code}] 歷史資料錯誤: {e}")
    if not hist_list:
        return pd.DataFrame()
    return pd.concat(hist_list, ignore_index=True)


