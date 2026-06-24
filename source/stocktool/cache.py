"""
stocktool.cache - 快取 I/O + 時間邏輯
========================================

v1.1 重構：把 save_cache / load_cache / get_cache_file / get_or_fetch /
_is_price_cache_valid 從 StockTool.py 抽出

被依賴：fetch_market.py, gui/main_window.py
依賴：config.py
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd

from .config import _is_market_hours, GuiLogger


def get_cache_file(name: str) -> str:
    """取得 cache 檔案路徑"""
    return f"cache/{name}.xlsx"


def save_cache(file_path: str, df: "pd.DataFrame") -> None:
    """寫入 cache（data + meta sheet）

    【v1.0-time 新增】2026-06-23 William 09:55 反映：
    - cache 只記日期、不記時間 → 跨日才重抓、不夠精準
    - 新規則：cache 要記時間，判斷 cache 是否在「最後一次收盤時間」之後
    - meta sheet 多寫 last_update_time (HH:MM:SS)
    - 舊 cache 只有 last_update 欄位、也讀得到、不會爆
    """
    os.makedirs("cache", exist_ok=True)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=False)
        meta = pd.DataFrame({"last_update": [today], "last_update_time": [time_str]})
        meta.to_excel(writer, sheet_name="meta", index=False)


def load_cache(file_path: str) -> Tuple["pd.DataFrame", Optional[str], Optional[str]]:
    """讀取快取檔案（data + meta sheet）

    【V0.9.5-goodinfo4+5 (vol-no-divide) 修容錯】2026-06-18 22:07 William 反映
    - 之前舊 cache 只有 data sheet、沒有 meta → load_cache 直接 crash
    - 「Worksheet named 'meta' not found → fallback 讀舊 cache」錯訊
    - 修法：meta 不存在時 fallback 回傳今天日期（視為剛抓的、不觸發 refresh）

    【v1.0-time 新增】2026-06-23 William 09:55：
    - 多回傳 last_update_time (HH:MM:SS)、None 表示沒紀錄
    - 舊 cache 沒 last_update_time 時、time=None → _is_price_cache_valid 視為過期、觸發重抓
    - 回傳值從 (df, date) 改為 (df, date, time)
    """
    df = pd.read_excel(file_path, sheet_name="data", engine="openpyxl")
    last_update = None
    last_update_time = None
    try:
        meta = pd.read_excel(file_path, sheet_name="meta", engine="openpyxl")
        last_update = str(meta.loc[0, "last_update"])
        # 向後相容：last_update_time 可能不存在（舊 cache 只有 date）
        if "last_update_time" in meta.columns:
            _t = meta.loc[0, "last_update_time"]
            if pd.notna(_t) and str(_t).strip() != "":
                last_update_time = str(_t)
    except Exception:
        # 舊 cache 沒 meta sheet → fallback 視為剛抓（但 time=None 會觸發時間-based 重抓）
        last_update = datetime.today().strftime("%Y-%m-%d")
        last_update_time = None
    return df, last_update, last_update_time


def _is_price_cache_valid(last_update_date, last_update_time, now: Optional[datetime] = None) -> bool:
    """【v1.0-time 新增】2026-06-23 William 09:55 設定

    判斷 price cache 是否還是「最新收盤價」（可繼續用、免重抓）

    新規則（取代舊的「跨日才重抓」）：
    - 收盤後（>= 收盤時間 13:30 或半日盤 13:00）：cache time >= 今天的收盤時間 → 仍有效
    - 收盤前（< 09:00）：cache time >= 昨天的收盤時間 → 仍有效
    - 其他情況（last_update_date/time 不對、沒時間紀錄）→ False、要重抓

    盤中已由 _is_market_hours() 在 get_or_fetch 先處理、本函式只在「非盤中」被呼。
    """
    from .config import _HALF_DAY_DATES

    if last_update_date is None or last_update_time is None:
        return False

    now = now or datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 判斷現在是收盤後還是收盤前
    is_half_today = today_str in _HALF_DAY_DATES
    close_hour = 13
    close_minute = 0 if is_half_today else 30
    today_close = now.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)

    if now >= today_close:
        # 收盤後 → 看今天的收盤時間
        target_date = today_str
        target_close = today_close
    else:
        # 收盤前 → 看昨天的收盤時間
        yesterday = now - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")
        is_half_y = target_date in _HALF_DAY_DATES
        yh = 13
        ym = 0 if is_half_y else 30
        target_close = yesterday.replace(hour=yh, minute=ym, second=0, microsecond=0)

    # cache 日期必須對得上目標日期
    if str(last_update_date).strip() != target_date:
        return False

    # cache 時間必須 >= 目標收盤時間
    try:
        cache_dt = datetime.strptime(
            f"{target_date} {last_update_time}",
            "%Y-%m-%d %H:%M:%S",
        )
    except Exception:
        return False
    return cache_dt >= target_close


def get_or_fetch(name: str, fetch_func, logger: GuiLogger):
    """統一抓取入口：cache 命中用 cache、未命中或過期重抓

    邏輯（v1.0 重構後順序）：
    1. cache 檔案不存在 → fetch + save + return
    2. price cache 缺欄位（結構檢查優先）→ fetch + save + return
    3. price + 盤中 → 強制 refresh（Phase 7 規則）
    4. price + 收盤後/盤前 + cache 時間有效 → 用 cache
    5. revenue/eps 或 cache 日期 == 今天 → 用 cache
    6. 其他 → fetch + save + return
    """
    file_path = get_cache_file(name)
    today = datetime.today().strftime("%Y-%m-%d")
    if not os.path.exists(file_path):
        logger.log(f"📥 [{name}] 無快取 → 下載資料")
        df = fetch_func()
        save_cache(file_path, df)
        return df
    df, last_update, last_update_time = load_cache(file_path)

    # ============================================================
    # 【結構檢查】優先於時間判斷 — cache 缺欄位就該重抓
    # ============================================================
    if name == "price":
        required_cols = {"成交量_張", "data_date"}
        missing = required_cols - set(df.columns)
        if missing:
            logger.log(
                f"♻️ [{name}] cache 缺欄位 {sorted(missing)}、強制重抓一次 → 寫入新結構"
            )
            df = fetch_func()
            save_cache(file_path, df)
            return df

    # ============================================================
    # 【盤中】強制 refresh（revenue/eps 不適用）
    # ============================================================
    if name == "price" and _is_market_hours():
        logger.log(f"🔄 [{name}] 盤中時段 → 強制 refresh 股價")
        df = fetch_func()
        save_cache(file_path, df)
        return df

    # ============================================================
    # 【收盤後/盤前】時間基準 cache 有效性判斷
    # ============================================================
    if name == "price" and _is_price_cache_valid(last_update, last_update_time):
        logger.log(
            f"✅ [{name}] cache 仍是最新收盤價（{last_update} {last_update_time}）、免重抓"
        )
        return df

    # ============================================================
    # 【一般】日期基準 cache 有效性判斷（revenue/eps / 舊 price cache）
    # ============================================================
    if last_update == today:
        if name == "eps":
            yoy_col = "EPSYoY_顯示(%)"
            # 【v1.1.1+ William 2026-06-24 21:48 反映】
            # 3490 EPSYoY 快取為 4040%、實際 GoodInfo 是 476%。
            # 根因：fetch_eps_latest 找不到去年同期 Q1 時 fallback 到去年 Q4 全年 EPS = 0.05
            #      (2.07 - 0.05) / 0.05 = 40.4 = 4040%，這是計算錯。
            # 修法：快取若檢測到「可疑 YoY」（>500% 或 <-99%）或「大部分都是 NaN」、強制重抓一次讓 GoodInfo 覆蓋。
            needs_refresh = False
            reason = ""
            if yoy_col not in df.columns or df[yoy_col].isna().all() or (df[yoy_col] == 0).all():
                needs_refresh = True
                reason = "缺 EPSYoY 資料或全為 0"
            else:
                # 過濾合法數值、檢查是否超過合理範圍
                valid_yoy = df[yoy_col].dropna()
                valid_yoy = valid_yoy[valid_yoy != 0]
                if not valid_yoy.empty:
                    too_high = (valid_yoy > 500).sum()
                    too_low = (valid_yoy < -99).sum()
                    nan_pct = df[yoy_col].isna().mean() * 100
                    if too_high > 0 or too_low > 0:
                        needs_refresh = True
                        reason = f"有 {too_high} 檔 YoY>500%、{too_low} 檔 YoY<-99%（可能是去年 EPS 太小造成的除零陷阱、強制讓 GoodInfo 覆蓋）"
                    elif nan_pct > 50:
                        # 越過一半股票沒 YoY 資料 → 判斷上次抓取失敗、強制重抓
                        needs_refresh = True
                        reason = f"有 {nan_pct:.0f}% 股票 YoY 是 NaN（>50%、可能是 GoodInfo 覆蓋沒跑到、強制重抓）"
            if needs_refresh:
                logger.log(f"♻️ [{name}] cache {reason}、強制重抓一次")
                df = fetch_func()
                save_cache(file_path, df)
                return df
        logger.log(f"✅ [{name}] 使用快取資料")
        return df
    logger.log(f"♻️ [{name}] 資料過期 → 重新下載")
    df = fetch_func()
    save_cache(file_path, df)
    return df
