"""
stocktool.config - 設定 / Logger / Session / 盤中判斷
=======================================================

v1.1 重構：把原本散落在 StockTool.py 開頭的全域常數、StrategyConfig、GuiLogger、
build_session、_is_market_hours 等基礎建設集中到這裡。

被依賴：所有其他 stocktool 模組
依賴：無（純基礎）
"""

from __future__ import annotations

import os
import json
import queue
import threading
import warnings
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

import requests

warnings.filterwarnings("ignore")


# ==========================================================
# 版本常數（v1.0 中央管理）
# ==========================================================
VERSION = "v1.1-portfolio-taiwan-color"


# ==========================================================
# 損益色彩（v1.1 依台股慣例 + 紅 - 綠）
# ==========================================================
# 2026-06-29 10:16 William 反映：「買賣紀錄中顯示profit + 改用紅字, - 改用綠字」
# 台股慣例：漲 = 紅色、跌 = 綠色（與西方相反）
# 用於：買賣記錄 tab 的 summary labels、_positions_tree、_show_position_detail dialog
COLOR_PROFIT_POS = "#c00000"   # 正數（賺錢 / 漲）= 紅色
COLOR_PROFIT_NEG = "#0a7d2c"   # 負數（虧錢 / 跌）= 綠色
COLOR_PROFIT_ZERO = "#222222"  # 零 = 深灰（不特別高/低）


# ==========================================================
# Config 檔案路徑與預設設定
# ==========================================================

CONFIG_FILE = "stocktool_config.json"

DEFAULT_CONFIG = {
    "top_n_for_tech": 60,
    "tech_months": 24,
    "history_months": 60,
    "timeout": 30,
    "verify_ssl": False,
    "use_excel_stock_list": False,
    "excel_stock_file": "stock_list.xlsx",
    "use_enhanced_score": True,
    "use_top10_backtest": False,
    "excel_force_buy": False,
    "factor_weight_mom1": 0.15,
    "factor_weight_mom3": 0.15,
    "factor_weight_mom6": 0.20,
    "factor_weight_rev": 0.25,
    "factor_weight_eps": 0.25,
    "simple_score_weight_rev": 35.0,
    "simple_score_weight_eps": 35.0,
    "simple_score_weight_div": 20.0,
    "simple_score_weight_pe": -5.0,
    "simple_min_rev_yoy": -999.0,
    "simple_min_eps_yoy": -999.0,
    "simple_min_eps": -999.0,
    "simple_max_pe": 999.0,
    "eps_history_db": "eps_history.db",
    "use_mtf_confirmation": True,
    "use_divergence_detection": True,
    "volume_surge_multiplier": 2.0,
    "wf_enabled": False,
    "wf_train_years": 2,
    "wf_test_years": 1,
    "wf_step_years": 1,
    "twse_retries": 3,
    "twse_backoff": 0.8,
    "twse_sleep": 0.12,
    "topk": 7,
    "capital": 1000000.0,  # 總投入資金（元）
    "hold_days": 10,
    "roundtrip_cost_pct": 0.004,
    "stop_loss": -0.03,
    "take_profit": 0.08,
    "exit_rsi": 70,
    "use_gate": False,
    "min_rev_yoy": 0.0,
    "min_eps_yoy": 0.0,
    "allow_eps_yoy_nan": True,
    "risk_free_annual": 0.0,
    "mar_annual": 0.0,
    "trading_days": 252,
    "rsi_oversold": 40,
    "oversold_lookback": 10,
    "rsi_recover": 40,
    "rsi_aggressive": 45,
    "use_aggressive_signal": True,
    "require_trend_filter": True,
    "ma_slope_days": 3,
    "ma20_tolerance": 0.01,
    "require_volume_filter": True,
    "strong_revenue_yoy": 10.0,
    "strong_pe_max": 30.0,
    "strong_price_min": 10.0,
    "out_file_prefix": "選股報表",
    # V0.9.4 phase2.3: 交易成本設定（台股預設值）
    "broker_discount": 1.0,          # 券商折扣（1.0 = 無折扣，0.6 = 6折）
    # V0.9.5: 手動選股 Preset
    "manual_select_presets": {},
    "manual_select_last_preset": None,
    # V0.9.5-tab-split-phase3-D: 通用 Tab Preset (每個 tab 各自的命名儲存)
    "tab_presets": {},
    "tab_last_preset": {},
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved_config)
            return config
        except Exception as e:
            print(f"載入設定檔失敗: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"儲存設定檔失敗: {e}")
        return False


# ==========================================================
# StrategyConfig
# ==========================================================

HISTORY_DIR = "cache/history"


@dataclass
class StrategyConfig:
    top_n_for_tech: int = 60
    tech_months: int = 24
    history_months: int = 60
    timeout: int = 30
    verify_ssl: bool = False
    use_excel_stock_list: bool = False
    excel_stock_file: str = "stock_list.xlsx"
    use_enhanced_score: bool = True
    use_top10_backtest: bool = False
    excel_force_buy: bool = False      # Excel 清單強制買點模式
    factor_weight_mom1: float = 0.15
    factor_weight_mom3: float = 0.15
    factor_weight_mom6: float = 0.20
    factor_weight_rev: float = 0.25
    factor_weight_eps: float = 0.25
    simple_score_weight_rev: float = 35.0
    simple_score_weight_eps: float = 35.0
    simple_score_weight_div: float = 20.0
    simple_score_weight_pe: float = -5.0
    simple_min_rev_yoy: float = -999.0
    simple_min_eps_yoy: float = -999.0
    simple_min_eps: float = -999.0
    simple_max_pe: float = 999.0
    eps_history_db: str = "eps_history.db"
    # V0.9.4 phase2.3: 券商折扣（1.0 = 無折扣，0.6 = 6折）
    broker_discount: float = 1.0
    use_mtf_confirmation: bool = True
    use_divergence_detection: bool = True
    volume_surge_multiplier: float = 2.0
    wf_enabled: bool = False
    wf_train_years: int = 2
    wf_test_years: int = 1
    wf_step_years: int = 1
    twse_retries: int = 3
    twse_backoff: float = 0.8
    twse_sleep: float = 0.12
    topk: int = 7
    capital: float = 1000000.0  # 總投入資金（元）
    hold_days: int = 10
    roundtrip_cost_pct: float = 0.004
    stop_loss: float = -0.03
    take_profit: float = 0.08
    exit_rsi: int = 70
    use_gate: bool = False
    min_rev_yoy: float = 0.0
    min_eps_yoy: float = 0.0
    allow_eps_yoy_nan: bool = True
    risk_free_annual: float = 0.0
    mar_annual: float = 0.0
    trading_days: int = 252
    rsi_oversold: int = 45
    oversold_lookback: int = 10
    rsi_recover: int = 40
    rsi_aggressive: int = 45
    use_aggressive_signal: bool = True
    require_trend_filter: bool = True
    ma_slope_days: int = 3
    ma20_tolerance: float = 0.01
    require_volume_filter: bool = True
    strong_revenue_yoy: float = 10.0
    strong_pe_max: float = 30.0
    strong_price_min: float = 10.0
    out_file_prefix: str = "選股報表"
    # V0.9.5: 手動選股 Preset
    manual_select_presets: dict = field(default_factory=dict)
    manual_select_last_preset: str = None
    # V0.9.5-tab-split-phase3-D
    tab_presets: dict = field(default_factory=dict)
    tab_last_preset: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def update_from_dict(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# ==========================================================
# Logger
# ==========================================================

class GuiLogger:
    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg):
        self.q.put(("log", msg))

    def status(self, msg):
        self.q.put(("status", msg))

    def progress(self, current, total):
        self.q.put(("progress", current, total))

    def error(self, msg):
        self.q.put(("error", msg))


class PrintLogger:
    """【V0.9.5-twser】無 GUI 模式用 print 印 log"""
    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def log(self, msg):
        if self.verbose:
            print(msg)

    def status(self, msg):
        if self.verbose:
            print(f"[STATUS] {msg}")

    def progress(self, current, total):
        if self.verbose:
            print(f"[PROGRESS] {current}/{total}")

    def error(self, msg):
        print(f"[ERROR] {msg}")


# ==========================================================
# Session 工廠
# ==========================================================

def build_session() -> requests.Session:
    """建立共用的 requests Session、加上 User-Agent 標頭"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return s


# ==========================================================
# 欄位名稱輔助
# ==========================================================

def find_col(cols, keywords):
    """在欄位清單中找第一個匹配任一關鍵字的欄位名

    用法：
        date_col = find_col(df.columns, ["Date", "資料日期"])
        code_col = find_col(df.columns, ["股票代號", "代號", "code"])
    """
    for kw in keywords:
        for c in cols:
            if kw.lower() in str(c).lower():
                return c
    return None


# ==========================================================
# 半日盤清單（v1.0-info）
# ==========================================================

# 【v1.0-info 新增】2026-06-19 William 要求：
#   「_is_market_hours() 要處理台股半日盤（過年前封關日 13:00 收盤）」
#   每年封關日不同、需手動維護此表
#   來源：台灣證券交易所公告的「市場開休市日程」
_HALF_DAY_DATES = {
    "2026-02-13",  # 2026 過年封關日（除夕 2/16 前最後交易日、週五），13:00 收盤
    # "2027-02-05",  # 2027 過年封關日（待驗證）
    # 每年加新日期之前先查證：https://www.twse.com.tw/zh/holidaySchedule/holiday
}


def _is_market_hours(now: Optional[datetime] = None) -> bool:
    """判斷是否在台股盤中時段

    V0.9.5+ Phase 7 新規則（William 2026-06-15 09:56）：
    - 平日 09:00 開盤後到收盤前：股價會一直變 → 任何需要現價的功能都要 refresh
    - 收盤後到隔天 09:00 開盤前：股價已固定 → 一天只要 refresh 一次
    - 週末（週六、週日）：不開盤 → 用上週五收盤價、一天只要 refresh 一次

    v1.0-info 新規則（William 2026-06-19 14:17）：
    - 半日盤（過年封關日等）：13:00 收盤、不是 13:30
    - 依據 _HALF_DAY_DATES 清單判斷

    Returns
    -------
    bool
        True = 盤中（強制 refresh 股價）
        False = 盤前/盤後/週末（一天只 refresh 一次、靠 cache 判斷）

    用途：get_or_fetch 內判斷「price 類 cache」是否要走強制 refresh 路徑
    """
    now = now or datetime.now()
    # 週末（週六=5、週日=6）不開盤
    if now.weekday() >= 5:
        return False
    # 半日盤 → 13:00 收盤；一般交易日 → 13:30 收盤
    is_half_day = now.strftime("%Y-%m-%d") in _HALF_DAY_DATES
    if is_half_day:
        market_close = now.replace(hour=13, minute=0, second=0, microsecond=0)
    else:
        market_close = now.replace(hour=13, minute=30, second=0, microsecond=0)
    market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
