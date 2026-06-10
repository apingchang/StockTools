"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                               portfolio.py                                  ║
║                      StockTool V0.9.4 買賣記錄模組                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
V0.9.4
【版本資訊】
Version: v0.9.4-alpha.1
最後更新: 2026-06-10 (Asia/Taipei)
Python 版本: 3.8+
依賴套件: sqlite3 (內建), pandas, openpyxl, datetime

════════════════════════════════════════════════════════════════════════════════
【模組說明】
════════════════════════════════════════════════════════════════════════════════

提供 PortfolioDB 類別，管理股票買賣記錄與持倉計算。

【資料模型】
- 採用平均成本法（同一檔股票可有多筆買入，自動加權計算均價）
- 支援零股（股數為 REAL，可小數）
- 支援手續費（每筆交易可選填）
- 當前市價由使用者手動維護（不抓即時報價）

【主要 API】
    db = PortfolioDB("portfolio.db")
    db.add_buy("2330", "台積電", "2026-06-01", 1000, 580.0, 145.0)
    db.add_sell("2330", "2026-06-15", 500, 620.0, 155.0)
    positions = db.get_positions(current_prices={"2330": 620.0})
    summary = db.get_summary(current_prices={"2330": 620.0})
    db.export_excel("portfolio_20260610.xlsx", current_prices={"2330": 620.0})

════════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

# openpyxl 樣式（與 StockTool.py 一致）
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.formatting.rule import CellIsRule


# ==========================================================
# 常數
# ==========================================================
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id    TEXT    NOT NULL,
    stock_name  TEXT,
    action      TEXT    NOT NULL CHECK(action IN ('BUY','SELL')),
    trade_date  TEXT    NOT NULL,
    shares      REAL    NOT NULL CHECK(shares > 0),
    price       REAL    NOT NULL CHECK(price > 0),
    fee         REAL    NOT NULL DEFAULT 0,
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_tx_stock   ON transactions(stock_id);
CREATE INDEX IF NOT EXISTS idx_tx_date    ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_tx_action  ON transactions(action);
"""

# 匯出資訊（current_prices 預設值）
DEFAULT_PORTFOLIO_DB = "portfolio.db"


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
    note: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Position:
    """單一股票持倉彙總"""
    stock_id: str
    stock_name: str
    shares: float = 0.0            # 持有股數（支援負數代表 short，但本版不用）
    avg_cost: float = 0.0           # 平均成本（每股，含分攤手續費）
    total_cost: float = 0.0         # 總成本（買入淨額）
    current_price: float = 0.0      # 目前市價（手動輸入，預設 0）
    market_value: float = 0.0      # 市值 = shares * current_price
    unrealized_pl: float = 0.0      # 未實現損益
    unrealized_pl_pct: float = 0.0  # 未實現報酬率 %
    realized_pl: float = 0.0        # 已實現損益（賣出後）
    buy_count: int = 0
    sell_count: int = 0

    def calc_market_value(self):
        """重新計算市值與未實現損益（用 current_price）"""
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
    total_cost: float = 0.0          # 總成本
    total_market_value: float = 0.0  # 總市值
    total_unrealized_pl: float = 0.0 # 總未實現損益
    total_realized_pl: float = 0.0   # 總已實現損益
    total_pl: float = 0.0            # 總損益（已實現 + 未實現）
    total_return_pct: float = 0.0    # 總報酬率 %
    position_count: int = 0          # 持倉檔數
    tx_count: int = 0                # 交易筆數

    def to_dict(self) -> dict:
        return asdict(self)


# ==========================================================
# 核心：PortfolioDB
# ==========================================================
class PortfolioDB:
    """
    買賣記錄資料庫管理

    設計重點：
    - SQLite 單檔，git 忽略
    - 平均成本法（不實作 FIFO/LIFO）
    - 支援零股（REAL 欄位）
    - 手續費分攤到每股成本
    - 當前市價由外部傳入（GUI 讓使用者手動輸入）
    """

    def __init__(self, db_path: str = DEFAULT_PORTFOLIO_DB):
        self.db_path = db_path
        self._init_schema()

    # ──────── 連線管理 ────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 開啟 FK 限制（本版暫無跨表 FK，留著備用）
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    # ──────── CRUD：新增 ────────
    def add_buy(self,
                stock_id: str,
                trade_date: str,
                shares: float,
                price: float,
                fee: float = 0.0,
                stock_name: str = "",
                note: str = "") -> int:
        """
        新增一筆買入紀錄

        Returns:
            新紀錄的 id
        """
        self._validate_tx_params(stock_id, "BUY", trade_date, shares, price, fee)
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO transactions
                   (stock_id, stock_name, action, trade_date, shares, price, fee, note)
                   VALUES (?, ?, 'BUY', ?, ?, ?, ?, ?)""",
                (stock_id, stock_name, trade_date, shares, price, fee, note)
            )
            conn.commit()
            return cur.lastrowid

    def add_sell(self,
                 stock_id: str,
                 trade_date: str,
                 shares: float,
                 price: float,
                 fee: float = 0.0,
                 note: str = "") -> int:
        """
        新增一筆賣出紀錄

        賣出前不檢查庫存是否足夠（容許短線交易，後續持倉計算會顯示負數）。
        """
        self._validate_tx_params(stock_id, "SELL", trade_date, shares, price, fee)
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO transactions
                   (stock_id, stock_name, action, trade_date, shares, price, fee, note)
                   VALUES (?, '', 'SELL', ?, ?, ?, ?, ?)""",
                (stock_id, trade_date, shares, price, fee, note)
            )
            conn.commit()
            return cur.lastrowid

    def add_transaction(self, tx: Transaction) -> int:
        """通用新增（依 tx.action 判斷買/賣）"""
        if tx.action == "BUY":
            return self.add_buy(
                stock_id=tx.stock_id,
                trade_date=tx.trade_date,
                shares=tx.shares,
                price=tx.price,
                fee=tx.fee,
                stock_name=tx.stock_name,
                note=tx.note
            )
        elif tx.action == "SELL":
            return self.add_sell(
                stock_id=tx.stock_id,
                trade_date=tx.trade_date,
                shares=tx.shares,
                price=tx.price,
                fee=tx.fee,
                note=tx.note
            )
        else:
            raise ValueError(f"action 必須是 BUY 或 SELL，得到 {tx.action!r}")

    # ──────── CRUD：查詢 ────────
    def get_transaction(self, tx_id: int) -> Optional[Transaction]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE id = ?", (tx_id,)
            ).fetchone()
            return Transaction(**dict(row)) if row else None

    def list_transactions(self,
                          stock_id: Optional[str] = None,
                          action: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Transaction]:
        """
        查詢交易明細（可依股票/動作/日期區間篩選）
        """
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

    # ──────── CRUD：更新 / 刪除 ────────
    def update_transaction(self, tx: Transaction) -> bool:
        if tx.id is None:
            raise ValueError("update_transaction 需要 tx.id")
        self._validate_tx_params(
            tx.stock_id, tx.action, tx.trade_date, tx.shares, tx.price, tx.fee
        )
        with self._connect() as conn:
            cur = conn.execute(
                """UPDATE transactions SET
                   stock_id=?, stock_name=?, action=?, trade_date=?,
                   shares=?, price=?, fee=?, note=?
                   WHERE id=?""",
                (tx.stock_id, tx.stock_name, tx.action, tx.trade_date,
                 tx.shares, tx.price, tx.fee, tx.note, tx.id)
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_transaction(self, tx_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> int:
        """清空所有交易（危險操作！測試用）"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM transactions")
            conn.commit()
            return cur.rowcount

    # ──────── 持倉計算（核心） ────────
    def get_positions(self,
                      current_prices: Optional[Dict[str, float]] = None) -> List[Position]:
        """
        取得所有持倉（依股票彙總）

        Args:
            current_prices: {stock_id: 現價}，沒給就是 0

        Returns:
            List[Position]，每個股票一筆
        """
        if current_prices is None:
            current_prices = {}

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT stock_id,
                          COALESCE(MAX(stock_name), '') AS stock_name,
                          SUM(CASE WHEN action='BUY'  THEN shares ELSE 0 END) AS buy_shares,
                          SUM(CASE WHEN action='SELL' THEN shares ELSE 0 END) AS sell_shares,
                          SUM(CASE WHEN action='BUY'  THEN shares * price + fee ELSE 0 END) AS total_buy_cost,
                          SUM(CASE WHEN action='SELL' THEN shares * price - fee ELSE 0 END) AS total_sell_revenue,
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

            # 平均成本 = 總買入成本 / 總買入股數（含分攤手續費）
            avg_cost = (total_buy_cost / buy_shares) if buy_shares > 0 else 0.0

            # 已實現損益 = 賣出收入 - 對應的均價成本
            realized_pl = total_sell_revenue - (sell_shares * avg_cost)

            pos = Position(
                stock_id=d["stock_id"],
                stock_name=d["stock_name"],
                shares=current_shares,
                avg_cost=avg_cost,
                total_cost=current_shares * avg_cost,  # 剩餘庫存的帳面成本
                current_price=current_prices.get(d["stock_id"], 0.0),
                realized_pl=realized_pl,
                buy_count=d["buy_count"] or 0,
                sell_count=d["sell_count"] or 0,
            )
            pos.calc_market_value()
            positions.append(pos)
        return positions

    def get_position(self,
                     stock_id: str,
                     current_price: float = 0.0) -> Optional[Position]:
        """單檔股票的持倉"""
        for p in self.get_positions({stock_id: current_price}):
            if p.stock_id == stock_id:
                return p
        return None

    def get_summary(self,
                    current_prices: Optional[Dict[str, float]] = None) -> PortfolioSummary:
        """整體持倉總覽"""
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
        """
        更新現價（不寫入 DB，只在記憶體用）

        注意：本版的現價是「由外部傳入」，DB 不存 current_price 欄位。
        之後若要持久化，加一張 prices 表格。
        """
        # 本版不存 DB，所以這只是 placeholder，未來擴充用
        pass

    # ──────── 匯出 Excel ────────
    def export_excel(self,
                     output_path: str,
                     current_prices: Optional[Dict[str, float]] = None) -> str:
        """
        匯出持倉 + 交易明細到 Excel（4 sheet）

        Returns:
            output_path
        """
        if current_prices is None:
            current_prices = {}
        positions = self.get_positions(current_prices)
        summary = self.get_summary(current_prices)
        txs = self.list_transactions()

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Sheet 1: 持倉總覽
            self._write_summary_sheet(writer, summary)

            # Sheet 2: 持倉明細
            self._write_positions_sheet(writer, positions)

            # Sheet 3: 交易明細
            self._write_transactions_sheet(writer, txs)

            # Sheet 4: 匯出資訊
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
        # 數字格式
        for col in ["總成本", "總市值", "未實現損益", "已實現損益", "總損益"]:
            cell = ws[f"{chr(ord('A') + list(df.columns).index(col))}2"]
            cell.number_format = "#,##0"

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
        # 數字格式
        for col in ["持有股數", "平均成本", "目前市價", "市值", "未實現損益", "已實現損益"]:
            if col in df.columns:
                idx = list(df.columns).index(col) + 1
                for r in range(2, ws.max_row + 1):
                    ws.cell(row=r, column=idx).number_format = "#,##0.00" if "成本" in col or "市價" in col else "#,##0"
        # 負數紅字（未實現損益欄）
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
                "日期", "代號", "名稱", "買/賣", "股數", "價格", "手續費", "備註"
            ])
        else:
            df = pd.DataFrame([{
                "日期": t.trade_date,
                "代號": t.stock_id,
                "名稱": t.stock_name,
                "買/賣": "買" if t.action == "BUY" else "賣",
                "股數": t.shares,
                "價格": t.price,
                "手續費": t.fee,
                "備註": t.note,
            } for t in txs])
        df.to_excel(writer, index=False, sheet_name="交易明細")
        ws = writer.sheets["交易明細"]
        self._style_header(ws, 1)
        self._autosize_columns(ws, max_w=20)

    def _write_meta_sheet(self, writer: pd.ExcelWriter, summary: PortfolioSummary):
        df = pd.DataFrame([{
            "匯出時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "StockTool 版本": "V0.9.4-alpha.1",
            "資料庫路徑": self.db_path,
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
    def _validate_tx_params(self, stock_id, action, trade_date, shares, price, fee):
        if not stock_id or not stock_id.strip():
            raise ValueError("stock_id 不可為空")
        if action not in ("BUY", "SELL"):
            raise ValueError(f"action 必須是 BUY 或 SELL，得到 {action!r}")
        if not trade_date or not trade_date.strip():
            raise ValueError("trade_date 不可為空")
        # 簡單日期格式檢查
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"trade_date 格式錯誤：{trade_date!r}（應為 YYYY-MM-DD）")
        if shares <= 0:
            raise ValueError(f"shares 必須 > 0，得到 {shares}")
        if price <= 0:
            raise ValueError(f"price 必須 > 0，得到 {price}")
        if fee < 0:
            raise ValueError(f"fee 不可為負，得到 {fee}")

    def _get_first_tx_date(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(trade_date) AS d FROM transactions"
            ).fetchone()
            return row["d"] if row else None

    def _get_last_tx_date(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) AS d FROM transactions"
            ).fetchone()
            return row["d"] if row else None

    def _style_header(self, ws, header_row: int):
        """表頭藍底白字"""
        for cell in ws[header_row]:
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor="2E5A88")

    def _autosize_columns(self, ws, min_w: int = 10, max_w: int = 44):
        """自動調整欄寬"""
        for col_idx, col_cells in enumerate(ws.columns, start=1):
            try:
                max_len = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
            except Exception:
                max_len = min_w
            width = max(min_w, min(max_w, max_len + 2))
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    # ──────── 統計 / 維護 ────────
    def stock_ids(self) -> List[str]:
        """回傳所有出現過的股票代號（依字母序）"""
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
        """整體已實現損益（不依 current_prices）"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT
                       SUM(CASE WHEN action='SELL' THEN shares*price - fee ELSE 0 END) AS rev,
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
# 便利函式（給 GUI 呼叫）
# ==========================================================
def make_portfolio(db_path: str = DEFAULT_PORTFOLIO_DB) -> PortfolioDB:
    """建立 PortfolioDB 實例的便利函式"""
    return PortfolioDB(db_path=db_path)


def quick_demo():
    """快速 demo：跑一次完整流程"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "demo.db")
        db = PortfolioDB(db_path)

        print("=== 新增買入 ===")
        db.add_buy("2330", "2026-06-01", 1000, 580.0, 145.0, "台積電", "首次建倉")
        db.add_buy("2330", "2026-06-15", 500, 600.0, 150.0, "台積電", "加碼")
        db.add_buy("2454", "2026-06-10", 2000, 100.0, 100.0, "聯發科")

        print("=== 賣出部分台積電 ===")
        db.add_sell("2330", "2026-06-20", 300, 620.0, 93.0, "部分停利")

        print("=== 持倉 ===")
        positions = db.get_positions(current_prices={"2330": 620.0, "2454": 105.0})
        for p in positions:
            print(f"  {p.stock_id} {p.stock_name}: "
                  f"持有 {p.shares} 股 @ 均價 {p.avg_cost:.2f}, "
                  f"未實現 {p.unrealized_pl:+.0f} ({p.unrealized_pl_pct:+.2f}%), "
                  f"已實現 {p.realized_pl:+.0f}")

        print("=== 總覽 ===")
        summary = db.get_summary(current_prices={"2330": 620.0, "2454": 105.0})
        print(f"  總成本: {summary.total_cost:,.0f}")
        print(f"  總市值: {summary.total_market_value:,.0f}")
        print(f"  未實現: {summary.total_unrealized_pl:+,.0f}")
        print(f"  已實現: {summary.total_realized_pl:+,.0f}")
        print(f"  總損益: {summary.total_pl:+,.0f} ({summary.total_return_pct:+.2f}%)")
        print(f"  持 {summary.position_count} 檔，{summary.tx_count} 筆交易")

        print("=== 匯出 Excel ===")
        out = os.path.join(tmp, "demo.xlsx")
        db.export_excel(out, current_prices={"2330": 620.0, "2454": 105.0})
        print(f"  寫入：{out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    quick_demo()
