"""
stocktool - StockTool 模組化 package
====================================

v1.1 重構：把原本的 10,341 行超級檔案拆成 11 個聚焦模組

模組清單：
- stocktool.config        設定 / Logger / Session / 盤中判斷
- stocktool.cache         快取 I/O
- stocktool.database      3 個歷史 DB CRUD
- stocktool.fetch_market  行情資料抓取
- stocktool.etf           ETF 持股統計
- stocktool.scoring       評分系統
- stocktool.technical     技術指標
- stocktool.backtest      回測引擎
- stocktool.export_excel  Excel 樣式
- stocktool.pipeline      選股流程組合
- stocktool.gui.*         GUI 主視窗 + 4 個 Tab

向後相容：本 __init__.py re-export 所有常用符號，
原本 `from StockTool import StrategyConfig` 的程式碼可以無痛改成 `from stocktool import StrategyConfig`。
"""

__version__ = "1.1.0"

# 向後相容：重新 export 常用符號
from .config import (
    DEFAULT_CONFIG,
    CONFIG_FILE,
    HISTORY_DIR,
    VERSION,
    _HALF_DAY_DATES,
    load_config,
    save_config,
    StrategyConfig,
    GuiLogger,
    PrintLogger,
    build_session,
    find_col,
    _is_market_hours,
)
from .cache import (
    get_cache_file,
    save_cache,
    load_cache,
    get_or_fetch,
    _is_price_cache_valid,
)
from .fetch_market import (
    to_num_series,
    month_starts_back,
    roc_to_ad,
    _load_goodinfo_12q_epsrate,
    _fetch_market_stock_list,
    _fetch_twse_realtime_batch,
    _pick_latest_price_row,
    _finmind_get,
    _parse_roc_year,
    _fetch_finmind_prices_batch,
    _fmt_float,
    _fetch_finmind_dividend,
    _background_fetch_all_dividend,
    _update_ex_date_close,
    _fetch_ex_date_close,
    fetch_csv_requests,
    fetch_prices,
    fetch_revenue_latest,
    fetch_eps_latest,
    safe_parse_json,
    fetch_twse_stock_day_month,
    fetch_twse_history,
)
from .etf import (
    fetch_active_etf_list,
    fetch_etf_top10_holdings,
    build_etf_holdings_table,
    aggregate_etf_holdings,
    ETF_ACTIVELIST_URL,
    ETFINFO_ETF_URL,
    _display_width,
)
from .database import (
    DIV_HISTORY_SCHEMA,
    DIV_HISTORY_MIGRATIONS,
    EPS_HISTORY_SCHEMA,
    ETF_HISTORY_SCHEMA,
    _init_div_history_db,
    _init_eps_history_db,
    _init_etf_history_db,
    _save_etf_holding_snapshot,
    _query_etf_holdings_by_date,
    _query_latest_two_dates,
    _compute_etf_changes,
    _upsert_div_history,
    _query_div_history,
    _query_div_history_with_fetched,
    _div_history_stats,
    _upsert_eps_history,
    _query_eps_history,
    _eps_history_stats,
)
