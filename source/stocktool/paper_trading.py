"""
stocktool.paper_trading - 模擬買賣模組 (Paper Trading)
======================================================

【V1.2.0-paper-trading】新增功能

設計重點：
- 跟回測 (backtest.py) 完全不同 → 這是「即時紙上交易」
- 從「按下執行」當下開始 → 每天 14:00 自動跑一次 → 用「當時可得最新價」決策
- 不做當沖、可加碼、可換手
- 多組合並存、每組獨立參數
- AI Meta-Strategy 組合：動態加權 + reasoning log

資料表（建在 portfolio.db）：
- sim_portfolios        模擬帳戶（每組一筆）
- sim_holdings          持倉（即時狀態）
- sim_trades            交易紀錄（含 reasoning）
- sim_daily_snapshot    每日資產快照（畫權益曲線用）

被依賴：StockTool.py（UI 觸發）
依賴：fetch_market.py / scoring.py / config.py / database.py
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional, Callable

import pandas as pd


# ==========================================================
# Schema
# ==========================================================

PAPER_TRADING_SCHEMA = """
-- 模擬帳戶（每組投資組合一筆）
CREATE TABLE IF NOT EXISTS sim_portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    excel_file      TEXT,
    stock_pool      TEXT    NOT NULL DEFAULT '[]',
    initial_cash    REAL    NOT NULL DEFAULT 1000000,
    max_holdings    INTEGER NOT NULL DEFAULT 10,
    -- 買入參數
    buy_score_threshold  REAL DEFAULT 70.0,
    buy_use_score        INTEGER DEFAULT 1,
    buy_min_rev_yoy      REAL DEFAULT 0.0,
    buy_min_eps_yoy      REAL DEFAULT 0.0,
    buy_max_pe           REAL DEFAULT 50.0,
    buy_min_yield        REAL DEFAULT 0.0,
    -- 賣出參數
    sell_stop_loss_pct   REAL DEFAULT 8.0,
    sell_take_profit_pct REAL DEFAULT 20.0,
    sell_max_hold_days   INTEGER DEFAULT 30,
    -- AI / 模式
    strategy_mode        TEXT    DEFAULT 'manual',
    ai_threshold         REAL    DEFAULT 70.0,
    -- 狀態
    status               TEXT    DEFAULT 'active',
    last_run_date        TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    started_at           TEXT,
    notes                TEXT
);

-- 持倉（即時狀態）
CREATE TABLE IF NOT EXISTS sim_holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT,
    shares          REAL    NOT NULL,
    avg_cost        REAL    NOT NULL,
    entry_date      TEXT    NOT NULL,
    entry_reason    TEXT,
    entry_score     REAL,
    last_buy_date   TEXT,
    add_count       INTEGER DEFAULT 0,
    FOREIGN KEY (portfolio_id) REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    UNIQUE (portfolio_id, stock_code)
);

-- 交易紀錄（含 AI reasoning）
CREATE TABLE IF NOT EXISTS sim_trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    trade_date      TEXT    NOT NULL,
    action          TEXT    NOT NULL,
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT,
    shares          REAL    NOT NULL,
    price           REAL    NOT NULL,
    fee             REAL    NOT NULL DEFAULT 0,
    tax             REAL    NOT NULL DEFAULT 0,
    amount          REAL    NOT NULL,
    cash_after      REAL    NOT NULL,
    signal_score    REAL,
    reasoning       TEXT,
    confidence      INTEGER,
    is_add          INTEGER DEFAULT 0,
    FOREIGN KEY (portfolio_id) REFERENCES sim_portfolios(id) ON DELETE CASCADE
);

-- 每日資產快照
CREATE TABLE IF NOT EXISTS sim_daily_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id    INTEGER NOT NULL,
    trade_date      TEXT    NOT NULL,
    cash            REAL    NOT NULL,
    holdings_value  REAL    NOT NULL,
    total_value     REAL    NOT NULL,
    holdings_count  INTEGER NOT NULL DEFAULT 0,
    cumulative_return_pct  REAL,
    benchmark_return_pct   REAL,
    twse_close      REAL,
    FOREIGN KEY (portfolio_id) REFERENCES sim_portfolios(id) ON DELETE CASCADE,
    UNIQUE (portfolio_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_sim_trades_portfolio_date ON sim_trades(portfolio_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_sim_holdings_portfolio ON sim_holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_sim_snapshot_portfolio_date ON sim_daily_snapshot(portfolio_id, trade_date);
"""


def init_paper_trading_db(db_path: str = "portfolio.db"):
    """【V1.2.0】初始化模擬買賣的 4 張表（冪等、可重複執行）"""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(PAPER_TRADING_SCHEMA)
        conn.commit()


# ==========================================================
# Data classes
# ==========================================================

@dataclass
class PaperPortfolio:
    """一組模擬投資組合"""
    id: Optional[int] = None
    name: str = ""
    excel_file: Optional[str] = None
    stock_pool: List[str] = field(default_factory=list)
    initial_cash: float = 1_000_000.0
    max_holdings: int = 10
    # 買入參數
    buy_score_threshold: float = 70.0
    buy_use_score: bool = True
    buy_min_rev_yoy: float = 0.0
    buy_min_eps_yoy: float = 0.0
    buy_max_pe: float = 50.0
    buy_min_yield: float = 0.0
    # 賣出參數
    sell_stop_loss_pct: float = 8.0
    sell_take_profit_pct: float = 20.0
    sell_max_hold_days: int = 30
    # 模式
    strategy_mode: str = "manual"  # 'manual' / 'ai_meta'
    ai_threshold: float = 70.0
    # 狀態
    status: str = "active"
    last_run_date: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SimHolding:
    id: Optional[int] = None
    portfolio_id: int = 0
    stock_code: str = ""
    stock_name: Optional[str] = None
    shares: float = 0.0
    avg_cost: float = 0.0
    entry_date: str = ""
    entry_reason: Optional[str] = None
    entry_score: Optional[float] = None
    last_buy_date: Optional[str] = None
    add_count: int = 0


@dataclass
class SimTrade:
    id: Optional[int] = None
    portfolio_id: int = 0
    trade_date: str = ""
    action: str = ""          # 'BUY' / 'SELL'
    stock_code: str = ""
    stock_name: Optional[str] = None
    shares: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    tax: float = 0.0
    amount: float = 0.0
    cash_after: float = 0.0
    signal_score: Optional[float] = None
    reasoning: Optional[str] = None
    confidence: Optional[int] = None
    is_add: int = 0


# ==========================================================
# DB CRUD
# ==========================================================

def list_portfolios(db_path: str = "portfolio.db", status: Optional[str] = None) -> List[PaperPortfolio]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT * FROM sim_portfolios WHERE status = ? ORDER BY id",
                (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM sim_portfolios ORDER BY id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("stock_pool"), str):
                try:
                    d["stock_pool"] = json.loads(d["stock_pool"])
                except Exception:
                    d["stock_pool"] = []
            for k in ["buy_use_score"]:
                if k in d:
                    d[k] = bool(d[k])
            out.append(PaperPortfolio(**d))
        return out


def get_portfolio(db_path: str, portfolio_id: int) -> Optional[PaperPortfolio]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sim_portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("stock_pool"), str):
            try:
                d["stock_pool"] = json.loads(d["stock_pool"])
            except Exception:
                d["stock_pool"] = []
        for k in ["buy_use_score"]:
            if k in d:
                d[k] = bool(d[k])
        return PaperPortfolio(**d)


def create_portfolio(db_path: str, p: PaperPortfolio) -> int:
    p.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO sim_portfolios
               (name, excel_file, stock_pool, initial_cash, max_holdings,
                buy_score_threshold, buy_use_score, buy_min_rev_yoy, buy_min_eps_yoy,
                buy_max_pe, buy_min_yield,
                sell_stop_loss_pct, sell_take_profit_pct, sell_max_hold_days,
                strategy_mode, ai_threshold, status, started_at, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.name, p.excel_file, json.dumps(p.stock_pool, ensure_ascii=False),
             p.initial_cash, p.max_holdings,
             p.buy_score_threshold, int(p.buy_use_score),
             p.buy_min_rev_yoy, p.buy_min_eps_yoy,
             p.buy_max_pe, p.buy_min_yield,
             p.sell_stop_loss_pct, p.sell_take_profit_pct, p.sell_max_hold_days,
             p.strategy_mode, p.ai_threshold, p.status, p.started_at, p.notes)
        )
        conn.commit()
        return cur.lastrowid


def update_portfolio(db_path: str, p: PaperPortfolio):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """UPDATE sim_portfolios SET
               name=?, excel_file=?, stock_pool=?, initial_cash=?, max_holdings=?,
               buy_score_threshold=?, buy_use_score=?, buy_min_rev_yoy=?, buy_min_eps_yoy=?,
               buy_max_pe=?, buy_min_yield=?,
               sell_stop_loss_pct=?, sell_take_profit_pct=?, sell_max_hold_days=?,
               strategy_mode=?, ai_threshold=?, status=?, notes=?
               WHERE id=?""",
            (p.name, p.excel_file, json.dumps(p.stock_pool, ensure_ascii=False),
             p.initial_cash, p.max_holdings,
             p.buy_score_threshold, int(p.buy_use_score),
             p.buy_min_rev_yoy, p.buy_min_eps_yoy,
             p.buy_max_pe, p.buy_min_yield,
             p.sell_stop_loss_pct, p.sell_take_profit_pct, p.sell_max_hold_days,
             p.strategy_mode, p.ai_threshold, p.status, p.notes, p.id)
        )
        conn.commit()


def update_portfolio_status(db_path: str, portfolio_id: int, status: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE sim_portfolios SET status = ? WHERE id = ?", (status, portfolio_id))
        conn.commit()


def update_portfolio_last_run(db_path: str, portfolio_id: int, trade_date: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE sim_portfolios SET last_run_date = ? WHERE id = ?", (trade_date, portfolio_id))
        conn.commit()


def delete_portfolio(db_path: str, portfolio_id: int):
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM sim_portfolios WHERE id = ?", (portfolio_id,))
        conn.commit()


def list_holdings(db_path: str, portfolio_id: int) -> List[SimHolding]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM sim_holdings WHERE portfolio_id = ? ORDER BY entry_date",
            (portfolio_id,)
        ).fetchall()
        return [SimHolding(**dict(r)) for r in rows]


def upsert_holding(db_path: str, h: SimHolding):
    """新增或更新一筆持倉（同 portfolio_id+stock_code 只保留一筆）"""
    with sqlite3.connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM sim_holdings WHERE portfolio_id = ? AND stock_code = ?",
            (h.portfolio_id, h.stock_code)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE sim_holdings SET shares=?, avg_cost=?, last_buy_date=?,
                                          add_count=add_count+1 WHERE id=?""",
                (h.shares, h.avg_cost, h.last_buy_date, existing[0])
            )
        else:
            conn.execute(
                """INSERT INTO sim_holdings
                   (portfolio_id, stock_code, stock_name, shares, avg_cost,
                    entry_date, entry_reason, entry_score, last_buy_date, add_count)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (h.portfolio_id, h.stock_code, h.stock_name, h.shares, h.avg_cost,
                 h.entry_date, h.entry_reason, h.entry_score, h.last_buy_date, h.add_count)
            )
        conn.commit()


def delete_holding(db_path: str, portfolio_id: int, stock_code: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM sim_holdings WHERE portfolio_id = ? AND stock_code = ?",
            (portfolio_id, stock_code)
        )
        conn.commit()


def insert_trade(db_path: str, t: SimTrade) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO sim_trades
               (portfolio_id, trade_date, action, stock_code, stock_name,
                shares, price, fee, tax, amount, cash_after,
                signal_score, reasoning, confidence, is_add)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t.portfolio_id, t.trade_date, t.action, t.stock_code, t.stock_name,
             t.shares, t.price, t.fee, t.tax, t.amount, t.cash_after,
             t.signal_score, t.reasoning, t.confidence, t.is_add)
        )
        conn.commit()
        return cur.lastrowid


def list_trades(db_path: str, portfolio_id: int, limit: int = 500) -> List[SimTrade]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM sim_trades WHERE portfolio_id = ? ORDER BY trade_date DESC, id DESC LIMIT ?",
            (portfolio_id, limit)
        ).fetchall()
        return [SimTrade(**dict(r)) for r in rows]


def upsert_daily_snapshot(db_path: str, portfolio_id: int, trade_date: str,
                          cash: float, holdings_value: float, total_value: float,
                          holdings_count: int, cum_return_pct: Optional[float] = None,
                          bench_return_pct: Optional[float] = None,
                          twse_close: Optional[float] = None):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO sim_daily_snapshot
               (portfolio_id, trade_date, cash, holdings_value, total_value,
                holdings_count, cumulative_return_pct, benchmark_return_pct, twse_close)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(portfolio_id, trade_date) DO UPDATE SET
                cash=excluded.cash,
                holdings_value=excluded.holdings_value,
                total_value=excluded.total_value,
                holdings_count=excluded.holdings_count,
                cumulative_return_pct=excluded.cumulative_return_pct,
                benchmark_return_pct=excluded.benchmark_return_pct,
                twse_close=excluded.twse_close""",
            (portfolio_id, trade_date, cash, holdings_value, total_value,
             holdings_count, cum_return_pct, bench_return_pct, twse_close)
        )
        conn.commit()


def list_snapshots(db_path: str, portfolio_id: int) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT * FROM sim_daily_snapshot WHERE portfolio_id = ? ORDER BY trade_date",
            conn, params=(portfolio_id,)
        )


def get_current_cash(db_path: str, portfolio_id: int, initial_cash: float) -> float:
    """從交易紀錄推算當前現金"""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT action, amount, fee, tax FROM sim_trades
               WHERE portfolio_id = ? ORDER BY id""",
            (portfolio_id,)
        ).fetchall()
    cash = initial_cash
    for action, amount, fee, tax in rows:
        if action == "BUY":
            cash -= (amount + fee + tax)
        else:
            cash += (amount - fee - tax)
    return cash


# ==========================================================
# 費用計算（複用 V0.9.4 公式：max(20, 股數×價×0.001425) + 賣出稅 0.003）
# ==========================================================

BROKER_DISCOUNT = 1.0   # 無折扣，牌告 0.1425%
FEE_RATE = 0.001425
TAX_RATE_SELL = 0.003


def calc_buy_cost(shares: float, price: float) -> Tuple[float, float, float]:
    """回傳 (fee, tax, total_cost)
    買進：fee = max(20, shares*price*0.001425*discount)、tax=0
    """
    fee = max(20.0, shares * price * FEE_RATE * BROKER_DISCOUNT)
    tax = 0.0
    return fee, tax, fee + tax


def calc_sell_cost(shares: float, price: float) -> Tuple[float, float, float]:
    """回傳 (fee, tax, total_cost)
    賣出：fee = max(20, shares*price*0.001425*discount)、tax = shares*price*0.003
    """
    fee = max(20.0, shares * price * FEE_RATE * BROKER_DISCOUNT)
    tax = shares * price * TAX_RATE_SELL
    return fee, tax, fee + tax