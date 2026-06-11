"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                               portfolio.py                                  ║
║                      StockTool V0.9.4 買賣記錄模組                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
V0.9.4
【版本資訊】
Version: v0.9.4-alpha.2
最後更新: 2026-06-10 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: sqlite3 (內建), pandas, openpyxl, requests, datetime

════════════════════════════════════════════════════════════════════════════════
【模組說明】
════════════════════════════════════════════════════════════════════════════════

提供 PortfolioDB 類別，管理股票買賣記錄與持倉計算。

【V0.9.4-alpha.2 新增】
- 手續費 / 證交稅 自動計算（依券商折扣 + 法定 20 元下限 + 賣出 0.3% 稅）
- 股票現價自動從 TWSE / TPEx 抓（單股查詢，不抓全市場）
- 股票名稱自動從 TWSE / TPEx 補上
- 對話框輸入代號即可即時帶出名稱 + 現價 + 預估手續費

【資料模型】
- 平均成本法（同一檔股票可有多筆買入，自動加權計算均價）
- 支援零股（REAL 欄位）
- 手續費與證交稅分開欄位（v0.9.4 起）
- 當前市價由 fetch_current_price() 抓或外部傳入

【手續費公式】
- 買入手續費 = max(20, 股數 × 價格 × 0.001425 × 券商折扣)
- 賣出手續費 = max(20, 股數 × 價格 × 0.001425 × 券商折扣)
- 賣出證交稅 = 股數 × 價格 × 0.003   （買入不收）
- 賣出總成本 = 賣出手續費 + 賣出證交稅

【主要 API】
    db = PortfolioDB("portfolio.db")
    db.add_buy("2330", "2026-06-01", 1000, 580.0)         # 手續費自動算
    db.add_sell("2330", "2026-06-15", 500, 620.0)          # 稅也自動算
    info = db.fetch_stock_info("2330")                      # → {"name": "台積電", "price": 620.0}
    positions = db.get_positions(current_prices={"2330": 620.0})
    db.export_excel("portfolio_20260610.xlsx")

════════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import sqlite3
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any, Union

import pandas as pd

# openpyxl 樣式（與 StockTool.py 一致）
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule

# requests（單股報價用）
import requests

# ==========================================================
# 常數：手續費 / 稅率
# ==========================================================
BROKER_FEE_RATE = 0.001425            # 0.1425% 牌告手續費
SELL_TAX_RATE = 0.003                  # 0.3% 賣出證交稅
MIN_FEE = 20                            # 最低手續費 20 元
DEFAULT_BROKER_DISCOUNT = 1.0          # 券商折扣（1.0 = 沒打折，0.6 = 6 折）

# ==========================================================
# 常數：TWSE / TPEx 抓現價
# ==========================================================
TWSE_SINGLE_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
HTTP_TIMEOUT = 8                        # 單股查詢 timeout
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StockTool/V0.9.4 Portfolio",
    "Accept": "application/json",
}

# ==========================================================
# 常數：DB Schema
# ==========================================================
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id    TEXT    NOT NULL,
    stock_name  TEXT,
    action      TEXT    NOT NULL CHECK(action IN ('BUY','SELL')),
    trade_date  TEXT    NOT NULL,
    shares      REAL    NOT NULL CHECK(shares > 0),
    price       REAL    NOT NULL CHECK(price >= 0),  -- V0.9.4 phase2.3: 允許 price=0（股票股利配發）
    fee         REAL    NOT NULL DEFAULT 0,
    tax         REAL    NOT NULL DEFAULT 0,
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tx_stock   ON transactions(stock_id);
CREATE INDEX IF NOT EXISTS idx_tx_date    ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_tx_action  ON transactions(action);
"""

# 舊版 schema（v0.9.4-alpha.1 沒有 tax 欄位）→ migration 用
MIGRATION_SQL = [
    # 如果 tax 欄位不存在就加
    "ALTER TABLE transactions ADD COLUMN tax REAL NOT NULL DEFAULT 0",
]

DEFAULT_PORTFOLIO_DB = "portfolio.db"

# ==========================================================
# V0.9.4 phase2.3: 費用 default（台股規定值，可經策略參數覆寫）
# ==========================================================
DEFAULT_BROKER_DISCOUNT = 1.0          # 券商折扣（1.0 = 零折扣，0.6 = 6折）
DEFAULT_MIN_FEE = 20                   # 最低手續費 20 元（台股規定）
DEFAULT_BROKER_FEE_RATE = 0.001425     # 0.1425%（台股牌告手續費率）
DEFAULT_SELL_TAX_RATE = 0.003          # 0.3%（台股賣出證交稅率，買入不收）


# ==========================================================
# 費用計算（靜態工具）
# ==========================================================
def calc_fee(shares: float, price: float, broker_discount: float = DEFAULT_BROKER_DISCOUNT) -> float:
    """
    計算券商手續費（買 / 賣都適用）

    公式：max(20, 股數 × 價格 × 0.001425 × 券商折扣)
    注意：股票股利配發（price=0）時不收手續費，直接回傳 0
    """
    if price == 0:
        return 0.0
    raw = shares * price * BROKER_FEE_RATE * broker_discount
    return round(max(MIN_FEE, raw), 2)


def calc_tax(shares: float, price: float) -> float:
    """
    計算賣出證交稅（買入不收）

    公式：股數 × 價格 × 0.003
    """
    return round(shares * price * SELL_TAX_RATE, 2)


def estimate_total_cost(action: str,
                        shares: float,
                        price: float,
                        broker_discount: float = DEFAULT_BROKER_DISCOUNT) -> Dict[str, float]:
    """
    預估整筆交易成本

    Returns:
        {"fee": 手續費, "tax": 證交稅, "total": 總成本}
    """
    fee = calc_fee(shares, price, broker_discount)
    tax = calc_tax(shares, price) if action == "SELL" else 0.0
    return {"fee": fee, "tax": tax, "total": fee + tax}


# ==========================================================
# 抓單股現價 + 名稱（TWSE / TPEx）
# ==========================================================
def fetch_stock_info(stock_id: str,
                     session: Optional[requests.Session] = None,
                     timeout: int = HTTP_TIMEOUT) -> Dict[str, Any]:
    """
    抓單一股票的「現價 + 名稱」

    自動判斷上市 / 上櫃：
    - 先試 TWSE (ex_ch=tse_<id>.tw)
    - 失敗 / 沒資料 → 試 TPEx (ex_ch=otc_<id>.tw)

    Returns:
        {
            "stock_id": "2330",
            "name": "台積電",                # 簡稱
            "full_name": "台灣積體電路製造",    # 全名（可能沒有）
            "price": 620.0,                  # 現價（0 = 沒抓到）
            "open": 615.0, "high": 625.0, "low": 610.0, "prev_close": 618.0,
            "volume": 42395,
            "exchange": "tse" or "otc",
            "trade_time": "13:30:00",
            "ok": True / False,
            "error": ""  (失敗時)
        }
    """
    stock_id = stock_id.strip()
    if not stock_id:
        return {"ok": False, "error": "股票代號為空", "stock_id": "", "price": 0.0, "name": ""}

    if session is None:
        session = requests.Session()
        session.headers.update(HTTP_HEADERS)

    result: Dict[str, Any] = {
        "stock_id": stock_id,
        "name": "",
        "full_name": "",
        "price": 0.0,
        "open": 0.0, "high": 0.0, "low": 0.0, "prev_close": 0.0,
        "volume": 0,
        "exchange": "",
        "trade_time": "",
        "ok": False,
        "error": "",
    }

    # 先試 TWSE，再試 TPEx
    for exchange, ex_ch in [("tse", "tse"), ("otc", "otc")]:
        url = f"{TWSE_SINGLE_URL}?ex_ch={ex_ch}_{stock_id}.tw"
        try:
            r = session.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            arr = data.get("msgArray", [])
            if not arr:
                continue  # 這個交易所沒資料，換下一個
            item = arr[0]

            def _num(key: str) -> float:
                """TWSE 回傳數字字串，轉 float"""
                try:
                    return float(item.get(key, 0) or 0)
                except (ValueError, TypeError):
                    return 0.0

            result.update({
                "name": item.get("n", "") or "",
                "full_name": item.get("nf", "") or "",
                "price": _num("z"),
                "open": _num("o"),
                "high": _num("h"),
                "low": _num("l"),
                "prev_close": _num("y"),
                "volume": int(_num("v")),
                "exchange": exchange,
                "trade_time": item.get("t", "") or "",
                "ok": True,
                "error": "",
            })
            return result

        except requests.RequestException as e:
            result["error"] = f"HTTP 失敗 ({ex_ch}): {e}"
            continue
        except (ValueError, KeyError) as e:
            result["error"] = f"解析失敗 ({ex_ch}): {e}"
            continue

    return result


def fetch_prices_batch(stock_ids: List[str],
                       session: Optional[requests.Session] = None) -> Dict[str, Dict[str, Any]]:
    """
    批次抓多檔股票的現價 + 名稱

    Returns:
        {stock_id: {info dict}}
    """
    if session is None:
        session = requests.Session()
        session.headers.update(HTTP_HEADERS)

    out: Dict[str, Dict[str, Any]] = {}
    for sid in stock_ids:
        info = fetch_stock_info(sid, session=session)
        out[sid] = info
    return out


# ==========================================================
# 資料類別
# ==========================================================
@dataclass
class Transaction:
    """單筆買賣交易紀錄"""
    id: Optional[int] = None
    stock_id: str = ""
    stock_name: str = ""
    action: str = "BUY"          # "BUY" or "SELL"
    trade_date: str = ""          # YYYY-MM-DD
    shares: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    tax: float = 0.0              # V0.9.4 新增：賣出證交稅
    note: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Position:
    """單一股票持倉彙總"""
    stock_id: str
    stock_name: str
    shares: float = 0.0
    avg_cost: float = 0.0
    total_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pl: float = 0.0
    unrealized_pl_pct: float = 0.0
    realized_pl: float = 0.0
    buy_count: int = 0
    sell_count: int = 0

    def calc_market_value(self):
        self.market_value = self.shares * self.current_price
        self.unrealized_pl = self.market_value - (self.shares * self.avg_cost)
        if self.shares > 0 and self.avg_cost > 0:
            self.unrealized_pl_pct = (self.current_price - self.avg_cost) / self.avg_cost * 100
        else:
            self.unrealized_pl_pct = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PortfolioSummary:
    """整體持倉總覽"""
    total_cost: float = 0.0
    total_market_value: float = 0.0
    total_unrealized_pl: float = 0.0
    total_realized_pl: float = 0.0
    total_pl: float = 0.0
    total_return_pct: float = 0.0
    position_count: int = 0
    tx_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ==========================================================
# 核心：PortfolioDB
# ==========================================================
class PortfolioDB:
    def __init__(self,
                 db_path: str = DEFAULT_PORTFOLIO_DB,
                 broker_discount: float = DEFAULT_BROKER_DISCOUNT):
        self.db_path = db_path
        self.broker_discount = broker_discount
        self._init_schema()
        self._migrate()

    # ──────── 連線管理 ────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def _migrate(self):
        """舊版 DB 自動升級（V0.9.4-alpha.1 沒有 tax 欄位 → 加上去）"""
        with self._connect() as conn:
            # 檢查欄位是否存在
            cols = [row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()]
            if "tax" not in cols:
                for sql in MIGRATION_SQL:
                    try:
                        conn.execute(sql)
                    except sqlite3.OperationalError:
                        pass
                conn.commit()

    # ──────── CRUD：新增 ────────
    def add_buy(self,
                stock_id: str,
                trade_date: str,
                shares: float,
                price: float,
                fee: Optional[float] = None,
                tax: float = 0.0,
                stock_name: str = "",
                note: str = "") -> int:
        """
        新增一筆買入

        Args:
            fee: 手續費。None = 自動算（依 broker_discount）
            tax: 證交稅（買入 = 0，預設 0）
        """
        self._validate_tx_params(stock_id, "BUY", trade_date, shares, price, fee if fee is not None else 0, tax)
        if fee is None:
            fee = calc_fee(shares, price, self.broker_discount)
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO transactions
                   (stock_id, stock_name, action, trade_date, shares, price, fee, tax, note)
                   VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?, ?)""",
                (stock_id, stock_name, trade_date, shares, price, fee, tax, note)
            )
            conn.commit()
            return cur.lastrowid

    def add_sell(self,
                 stock_id: str,
                 trade_date: str,
                 shares: float,
                 price: float,
                 fee: Optional[float] = None,
                 tax: Optional[float] = None,
                 note: str = "") -> int:
        """
        新增一筆賣出

        Args:
            fee: 手續費。None = 自動算
            tax: 證交稅。None = 自動算（賣出才收）
        """
        self._validate_tx_params(
            stock_id, "SELL", trade_date, shares, price,
            fee if fee is not None else 0, tax if tax is not None else 0
        )
        if fee is None:
            fee = calc_fee(shares, price, self.broker_discount)
        if tax is None:
            tax = calc_tax(shares, price)
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO transactions
                   (stock_id, stock_name, action, trade_date, shares, price, fee, tax, note)
                   VALUES (?, '', 'SELL', ?, ?, ?, ?, ?, ?)""",
                (stock_id, trade_date, shares, price, fee, tax, note)
            )
            conn.commit()
            return cur.lastrowid

    def add_transaction(self, tx: Transaction) -> int:
        if tx.action == "BUY":
            return self.add_buy(
                stock_id=tx.stock_id, trade_date=tx.trade_date,
                shares=tx.shares, price=tx.price,
                fee=tx.fee if tx.fee > 0 else None,
                tax=tx.tax, stock_name=tx.stock_name, note=tx.note
            )
        elif tx.action == "SELL":
            return self.add_sell(
                stock_id=tx.stock_id, trade_date=tx.trade_date,
                shares=tx.shares, price=tx.price,
                fee=tx.fee if tx.fee > 0 else None,
                tax=tx.tax if tx.tax > 0 else None, note=tx.note
            )
        else:
            raise ValueError(f"action 必須是 BUY 或 SELL，得到 {tx.action!r}")

    # ──────── CRUD：查詢 ────────
    def get_transaction(self, tx_id: int) -> Optional[Transaction]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
            return Transaction(**dict(row)) if row else None

    def list_transactions(self,
                          stock_id: Optional[str] = None,
                          action: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Transaction]:
        sql = "SELECT * FROM transactions WHERE 1=1"
        params: List[Any] = []
        if stock_id:
            sql += " AND stock_id = ?"
            params.append(stock_id)
        if action:
            sql += " AND action = ?"
            params.append(action)
        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)
        sql += " ORDER BY trade_date ASC, id ASC"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [Transaction(**dict(r)) for r in rows]

    def update_transaction(self, tx: Transaction) -> bool:
        if tx.id is None:
            raise ValueError("update_transaction 需要 tx.id")
        self._validate_tx_params(
            tx.stock_id, tx.action, tx.trade_date, tx.shares, tx.price, tx.fee, tx.tax
        )
        with self._connect() as conn:
            cur = conn.execute(
                """UPDATE transactions SET
                   stock_id=?, stock_name=?, action=?, trade_date=?,
                   shares=?, price=?, fee=?, tax=?, note=?
                   WHERE id=?""",
                (tx.stock_id, tx.stock_name, tx.action, tx.trade_date,
                 tx.shares, tx.price, tx.fee, tx.tax, tx.note, tx.id)
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_transaction(self, tx_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM transactions")
            conn.commit()
            return cur.rowcount

    # ──────── 持倉計算 ────────
    def get_positions(self,
                      current_prices: Optional[Dict[str, float]] = None) -> List[Position]:
        if current_prices is None:
            current_prices = {}
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT stock_id,
                          COALESCE(MAX(stock_name), '') AS stock_name,
                          SUM(CASE WHEN action='BUY'  THEN shares ELSE 0 END) AS buy_shares,
                          SUM(CASE WHEN action='SELL' THEN shares ELSE 0 END) AS sell_shares,
                          SUM(CASE WHEN action='BUY'  THEN shares * price + fee ELSE 0 END) AS total_buy_cost,
                          SUM(CASE WHEN action='SELL' THEN shares * price - fee - tax ELSE 0 END) AS total_sell_revenue,
                          SUM(CASE WHEN action='BUY'  THEN 1 ELSE 0 END) AS buy_count,
                          SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) AS sell_count
                   FROM transactions
                   GROUP BY stock_id
                   ORDER BY stock_id ASC"""
            ).fetchall()

        positions: List[Position] = []
        for r in rows:
            d = dict(r)
            buy_shares = d["buy_shares"] or 0.0
            sell_shares = d["sell_shares"] or 0.0
            total_buy_cost = d["total_buy_cost"] or 0.0
            total_sell_revenue = d["total_sell_revenue"] or 0.0
            current_shares = buy_shares - sell_shares

            avg_cost = (total_buy_cost / buy_shares) if buy_shares > 0 else 0.0
            # 已實現損益 = 賣出淨收入 - 對應均價成本
            # 賣出淨收入已扣 fee + tax，這樣實現損益是「真正拿到 / 付出」的錢
            realized_pl = total_sell_revenue - (sell_shares * avg_cost)

            pos = Position(
                stock_id=d["stock_id"],
                stock_name=d["stock_name"],
                shares=current_shares,
                avg_cost=avg_cost,
                total_cost=current_shares * avg_cost,
                current_price=current_prices.get(d["stock_id"], 0.0),
                realized_pl=realized_pl,
                buy_count=d["buy_count"] or 0,
                sell_count=d["sell_count"] or 0,
            )
            pos.calc_market_value()
            positions.append(pos)
        return positions

    def get_position(self, stock_id: str, current_price: float = 0.0) -> Optional[Position]:
        for p in self.get_positions({stock_id: current_price}):
            if p.stock_id == stock_id:
                return p
        return None

    def get_summary(self,
                    current_prices: Optional[Dict[str, float]] = None) -> PortfolioSummary:
        if current_prices is None:
            current_prices = {}
        positions = self.get_positions(current_prices)
        txs = self.list_transactions()

        total_cost = sum(p.total_cost for p in positions)
        total_mv = sum(p.market_value for p in positions)
        total_unrealized = sum(p.unrealized_pl for p in positions)
        total_realized = sum(p.realized_pl for p in positions)
        total_pl = total_unrealized + total_realized
        total_return = (total_pl / total_cost * 100) if total_cost > 0 else 0.0

        return PortfolioSummary(
            total_cost=total_cost,
            total_market_value=total_mv,
            total_unrealized_pl=total_unrealized,
            total_realized_pl=total_realized,
            total_pl=total_pl,
            total_return_pct=total_return,
            position_count=sum(1 for p in positions if p.shares > 0),
            tx_count=len(txs),
        )

    # ──────── 現價更新（記憶體） ────────
    def update_current_prices(self, current_prices: Dict[str, float]):
        """未來擴充用，目前現價不在 DB"""
        pass

    # ──────── 匯出 Excel ────────
    def export_excel(self,
                     output_path: str,
                     current_prices: Optional[Dict[str, float]] = None) -> str:
        if current_prices is None:
            current_prices = {}
        positions = self.get_positions(current_prices)
        summary = self.get_summary(current_prices)
        txs = self.list_transactions()

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            self._write_summary_sheet(writer, summary)
            self._write_positions_sheet(writer, positions)
            self._write_transactions_sheet(writer, txs)
            self._write_meta_sheet(writer, summary)

        return output_path

    def _write_summary_sheet(self, writer: pd.ExcelWriter, summary: PortfolioSummary):
        df = pd.DataFrame([{
            "總成本": summary.total_cost,
            "總市值": summary.total_market_value,
            "未實現損益": summary.total_unrealized_pl,
            "已實現損益": summary.total_realized_pl,
            "總損益": summary.total_pl,
            "總報酬率 %": round(summary.total_return_pct, 2),
            "持倉檔數": summary.position_count,
            "交易筆數": summary.tx_count,
        }])
        df.to_excel(writer, index=False, sheet_name="持倉總覽")
        ws = writer.sheets["持倉總覽"]
        self._style_header(ws, 1)
        self._autosize_columns(ws, max_w=20)
        for col in ["總成本", "總市值", "未實現損益", "已實現損益", "總損益"]:
            idx = list(df.columns).index(col) + 1
            ws.cell(row=2, column=idx).number_format = "#,##0"

    def _write_positions_sheet(self, writer: pd.ExcelWriter, positions: List[Position]):
        if not positions:
            df = pd.DataFrame(columns=[
                "代號", "名稱", "持有股數", "平均成本", "目前市價",
                "市值", "未實現損益", "報酬率 %", "已實現損益", "買入筆數", "賣出筆數"
            ])
        else:
            df = pd.DataFrame([{
                "代號": p.stock_id,
                "名稱": p.stock_name,
                "持有股數": p.shares,
                "平均成本": round(p.avg_cost, 2),
                "目前市價": p.current_price,
                "市值": round(p.market_value, 0),
                "未實現損益": round(p.unrealized_pl, 0),
                "報酬率 %": round(p.unrealized_pl_pct, 2),
                "已實現損益": round(p.realized_pl, 0),
                "買入筆數": p.buy_count,
                "賣出筆數": p.sell_count,
            } for p in positions])
        df.to_excel(writer, index=False, sheet_name="持倉明細")
        ws = writer.sheets["持倉明細"]
        self._style_header(ws, 1)
        self._autosize_columns(ws, max_w=20)
        if "未實現損益" in df.columns:
            idx = list(df.columns).index("未實現損益") + 1
            col_letter = get_column_letter(idx)
            rng = f"{col_letter}2:{col_letter}{ws.max_row}"
            ws.conditional_formatting.add(rng, CellIsRule(
                operator="lessThan", formula=["0"],
                font=Font(color="C00000")
            ))

    def _write_transactions_sheet(self, writer: pd.ExcelWriter, txs: List[Transaction]):
        if not txs:
            df = pd.DataFrame(columns=[
                "日期", "代號", "名稱", "買/賣", "股數", "價格",
                "手續費", "證交稅", "總成本", "備註"
            ])
        else:
            df = pd.DataFrame([{
                "日期": t.trade_date,
                "代號": t.stock_id,
                "名稱": t.stock_name,
                "買/賣": "買" if t.action == "BUY" else "賣",
                "股數": t.shares,
                "價格": t.price,
                "手續費": round(t.fee, 2),
                "證交稅": round(t.tax, 2),
                "總成本": round(t.fee + t.tax, 2),
                "備註": t.note,
            } for t in txs])
        df.to_excel(writer, index=False, sheet_name="交易明細")
        ws = writer.sheets["交易明細"]
        self._style_header(ws, 1)
        self._autosize_columns(ws, max_w=20)

    def _write_meta_sheet(self, writer: pd.ExcelWriter, summary: PortfolioSummary):
        df = pd.DataFrame([{
            "匯出時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "StockTool 版本": "V0.9.4-alpha.2",
            "資料庫路徑": self.db_path,
            "券商折扣": f"{self.broker_discount:.2%}",
            "總交易筆數": summary.tx_count,
            "持倉檔數": summary.position_count,
            "資料起始日": self._get_first_tx_date() or "（無）",
            "資料結束日": self._get_last_tx_date() or "（無）",
        }])
        df.to_excel(writer, index=False, sheet_name="匯出資訊")
        ws = writer.sheets["匯出資訊"]
        self._style_header(ws, 1)
        self._autosize_columns(ws, max_w=24)

    # ──────── 工具方法 ────────
    def _validate_tx_params(self, stock_id, action, trade_date, shares, price, fee, tax):
        if not stock_id or not stock_id.strip():
            raise ValueError("stock_id 不可為空")
        if action not in ("BUY", "SELL"):
            raise ValueError(f"action 必須是 BUY 或 SELL，得到 {action!r}")
        if not trade_date or not trade_date.strip():
            raise ValueError("trade_date 不可為空")
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"trade_date 格式錯誤：{trade_date!r}（應為 YYYY-MM-DD）")
        if shares <= 0:
            raise ValueError(f"shares 必須 > 0，得到 {shares}")
        # V0.9.4 phase2.3: 股利配發（price=0）僅限 BUY；SELL 必須有價格
        if action == "BUY":
            if price < 0:
                raise ValueError(f"price 不可為負（股利配發可設為 0），得到 {price}")
        elif action == "SELL":
            if price <= 0:
                raise ValueError(f"SELL 時 price 必須 > 0，得到 {price}")
        if fee < 0:
            raise ValueError(f"fee 不可為負，得到 {fee}")
        if tax < 0:
            raise ValueError(f"tax 不可為負，得到 {tax}")

    def _get_first_tx_date(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT MIN(trade_date) AS d FROM transactions").fetchone()
            return row["d"] if row else None

    def _get_last_tx_date(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(trade_date) AS d FROM transactions").fetchone()
            return row["d"] if row else None

    def _style_header(self, ws, header_row: int):
        for cell in ws[header_row]:
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor="2E5A88")

    def _autosize_columns(self, ws, min_w: int = 10, max_w: int = 44):
        for col_idx, col_cells in enumerate(ws.columns, start=1):
            try:
                max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
            except Exception:
                max_len = min_w
            width = max(min_w, min(max_w, max_len + 2))
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    def stock_ids(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT stock_id FROM transactions ORDER BY stock_id ASC"
            ).fetchall()
            return [r["stock_id"] for r in rows]

    def tx_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()
            return row["c"] if row else 0

    def total_realized_pl(self) -> float:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT
                       SUM(CASE WHEN action='SELL' THEN shares*price - fee - tax ELSE 0 END) AS rev,
                       SUM(CASE WHEN action='BUY'  THEN shares*price + fee ELSE 0 END) AS cost,
                       SUM(CASE WHEN action='SELL' THEN shares ELSE 0 END) AS sell_shares,
                       SUM(CASE WHEN action='BUY'  THEN shares ELSE 0 END) AS buy_shares
                   FROM transactions"""
            ).fetchone()
            if not row or not row["buy_shares"]:
                return 0.0
            d = dict(row)
            avg_cost = d["cost"] / d["buy_shares"] if d["buy_shares"] > 0 else 0
            return d["rev"] - (d["sell_shares"] * avg_cost)

    def __repr__(self):
        return f"<PortfolioDB db_path={self.db_path!r} tx_count={self.tx_count()}>"


# ==========================================================
# 便利函式
# ==========================================================
def make_portfolio(db_path: str = DEFAULT_PORTFOLIO_DB,
                   broker_discount: float = DEFAULT_BROKER_DISCOUNT) -> PortfolioDB:
    return PortfolioDB(db_path=db_path, broker_discount=broker_discount)


def quick_demo():
    """快速 demo：完整流程 + 驗算手續費 + 抓現價"""
    import tempfile
    logging.basicConfig(level=logging.WARNING)

    print("=" * 60)
    print("V0.9.4-alpha.2 quick_demo")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "demo.db")
        db = PortfolioDB(db_path, broker_discount=1.0)

        # ── 驗算 1：手續費公式 ──
        print("\n[1] 手續費公式驗算（broker_discount=1.0）")
        for shares, price, label in [
            (1000, 580, "1000 股 @ 580"),
            (100, 50, "100 股 @ 50"),
            (1, 1000, "1 股 @ 1000"),
            (10000, 10, "10000 股 @ 10"),
        ]:
            fee_buy = calc_fee(shares, price, 1.0)
            tax_sell = calc_tax(shares, price)
            fee_sell = calc_fee(shares, price, 1.0)
            print(f"  {label}: 買費 {fee_buy:>8.2f} | "
                  f"賣費 {fee_sell:>8.2f} + 稅 {tax_sell:>8.2f} = {fee_sell + tax_sell:>8.2f}")

        # ── 驗算 2：DB CRUD ──
        print("\n[2] DB CRUD 測試")
        id1 = db.add_buy("2330", "2026-06-01", 1000, 580.0, stock_name="台積電", note="首次建倉")
        print(f"  買入 1 筆 id={id1}, fee 自動算")
        id2 = db.add_buy("2330", "2026-06-15", 500, 600.0, stock_name="台積電", note="加碼")
        print(f"  買入 1 筆 id={id2}, fee 自動算")
        id3 = db.add_buy("2454", "2026-06-10", 2000, 100.0, stock_name="聯發科")
        print(f"  買入 1 筆 id={id3}, fee 自動算")
        id4 = db.add_sell("2330", "2026-06-20", 300, 620.0, note="部分停利")
        print(f"  賣出 1 筆 id={id4}, fee + tax 自動算")

        # ── 驗算 3：計算損益 ──
        print("\n[3] 持倉 + 損益")
        # 嘗試抓真實現價（可能失敗就 fallback 用假資料）
        prices = {}
        for sid in ["2330", "2454"]:
            try:
                info = fetch_stock_info(sid)
                if info["ok"] and info["price"] > 0:
                    prices[sid] = info["price"]
                    print(f"  [TWSE] {sid} {info['name']}: 現價 {info['price']}")
                else:
                    prices[sid] = 620.0 if sid == "2330" else 105.0
                    print(f"  [fallback] {sid}: 用假價 {prices[sid]}")
            except Exception as e:
                prices[sid] = 620.0 if sid == "2330" else 105.0
                print(f"  [fallback] {sid}: {e}, 用假價 {prices[sid]}")

        positions = db.get_positions(current_prices=prices)
        for p in positions:
            print(f"  {p.stock_id} {p.stock_name}: 持 {p.shares:,.0f} @ {p.avg_cost:.2f}, "
                  f"未實現 {p.unrealized_pl:+,.0f} ({p.unrealized_pl_pct:+.2f}%), "
                  f"已實現 {p.realized_pl:+,.0f}")

        summary = db.get_summary(current_prices=prices)
        print(f"\n  總成本: {summary.total_cost:,.0f}")
        print(f"  總市值: {summary.total_market_value:,.0f}")
        print(f"  未實現: {summary.total_unrealized_pl:+,.0f}")
        print(f"  已實現: {summary.total_realized_pl:+,.0f}")
        print(f"  總損益: {summary.total_pl:+,.0f} ({summary.total_return_pct:+.2f}%)")

        # ── 驗算 4：Excel 匯出 ──
        print("\n[4] 匯出 Excel")
        out = os.path.join(tmp, "demo.xlsx")
        db.export_excel(out, current_prices=prices)
        print(f"  寫入：{out} ({os.path.getsize(out)} bytes)")

        # ── 驗算 5：Migration ──
        print("\n[5] DB migration 測試（模擬 v0.9.4-alpha.1 舊 DB）")
        old_path = os.path.join(tmp, "old.db")
        # 模擬舊 schema（沒 tax 欄位）
        conn = sqlite3.connect(old_path)
        conn.executescript("""
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id TEXT NOT NULL,
                stock_name TEXT,
                action TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)
        conn.execute(
            "INSERT INTO transactions (stock_id, action, trade_date, shares, price, fee) VALUES (?,?,?,?,?,?)",
            ("9999", "BUY", "2026-01-01", 100, 50, 20)
        )
        conn.commit()
        conn.close()
        # 用 PortfolioDB 開啟，應該自動 migration
        db2 = PortfolioDB(old_path)
        rows = db2.list_transactions()
        assert len(rows) == 1
        assert rows[0].tax == 0.0
        print(f"  ✅ 舊 DB 自動升級，新增 tax 欄位，資料保留")

    print("\n=" * 60)
    print("✅ quick_demo 全部完成")
    print("=" * 60)


if __name__ == "__main__":
    quick_demo()
