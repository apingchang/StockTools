"""
【V1.2.0-paper-trading】模擬買賣核心邏輯測試
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import pytest

from stocktool.paper_trading import (
    init_paper_trading_db, PaperPortfolio, SimHolding, SimTrade,
    create_portfolio, list_portfolios, get_portfolio, delete_portfolio,
    upsert_holding, list_holdings, delete_holding,
    insert_trade, list_trades, upsert_daily_snapshot, list_snapshots,
    get_current_cash, calc_buy_cost, calc_sell_cost,
    update_portfolio_status, update_portfolio_last_run,
)
from stocktool.paper_engine import (
    calc_simple_signal, evaluate_portfolio_one_day,
    evaluate_ai_portfolio_one_day, detect_market_regime, MarketRegime,
)
from stocktool.paper_excel import parse_excel_to_stock_pool


@pytest.fixture
def tmp_db(tmp_path):
    db = str(tmp_path / "test_portfolio.db")
    init_paper_trading_db(db)
    yield db


# ==========================================================
# CRUD tests
# ==========================================================

def test_init_db_creates_tables(tmp_db):
    """init 應該建 4 張表"""
    import sqlite3
    conn = sqlite3.connect(tmp_db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "sim_portfolios" in tables
    assert "sim_holdings" in tables
    assert "sim_trades" in tables
    assert "sim_daily_snapshot" in tables
    conn.close()


def test_create_and_list_portfolio(tmp_db):
    p = PaperPortfolio(name="測試A", stock_pool=["2330", "2454"], initial_cash=1_000_000)
    pid = create_portfolio(tmp_db, p)
    assert pid > 0

    plist = list_portfolios(tmp_db)
    assert len(plist) == 1
    assert plist[0].name == "測試A"
    assert plist[0].stock_pool == ["2330", "2454"]


def test_portfolio_status_pause_resume(tmp_db):
    p = PaperPortfolio(name="可暫停", stock_pool=["2330"])
    pid = create_portfolio(tmp_db, p)

    update_portfolio_status(tmp_db, pid, "paused")
    assert get_portfolio(tmp_db, pid).status == "paused"

    active = list_portfolios(tmp_db, status="active")
    paused = list_portfolios(tmp_db, status="paused")
    assert len(active) == 0
    assert len(paused) == 1

    update_portfolio_status(tmp_db, pid, "active")
    assert get_portfolio(tmp_db, pid).status == "active"


# ==========================================================
# Holding & trade tests
# ==========================================================

def test_upsert_holding_insert_then_update(tmp_db):
    p = PaperPortfolio(name="H", stock_pool=["2330"])
    pid = create_portfolio(tmp_db, p)

    h = SimHolding(portfolio_id=pid, stock_code="2330", shares=1000, avg_cost=950,
                   entry_date="2026-07-01", entry_reason="測試")
    upsert_holding(tmp_db, h)
    assert len(list_holdings(tmp_db, pid)) == 1

    # 第二次 upsert（加碼）
    h2 = SimHolding(portfolio_id=pid, stock_code="2330", shares=2000, avg_cost=960,
                    entry_date="2026-07-02", last_buy_date="2026-07-02")
    upsert_holding(tmp_db, h2)
    holdings = list_holdings(tmp_db, pid)
    assert len(holdings) == 1
    assert holdings[0].shares == 2000
    assert holdings[0].avg_cost == 960


def test_insert_trade_and_current_cash(tmp_db):
    p = PaperPortfolio(name="T", stock_pool=["2330"], initial_cash=1_000_000)
    pid = create_portfolio(tmp_db, p)

    # 買 1000 股 @ 950、手續費 1354 → cash = 1,000,000 - 950,000 - 1354 = 48,646
    insert_trade(tmp_db, SimTrade(
        portfolio_id=pid, trade_date="2026-07-01", action="BUY",
        stock_code="2330", shares=1000, price=950, fee=1353.75, tax=0,
        amount=950_000, cash_after=48_646.25,
    ))
    cash = get_current_cash(tmp_db, pid, 1_000_000)
    assert abs(cash - 48_646.25) < 0.01

    # 賣 1000 股 @ 1050、稅 3150 + 手續費 1496 → cash = 48,646 + 1,050,000 - 1496 - 3150
    insert_trade(tmp_db, SimTrade(
        portfolio_id=pid, trade_date="2026-07-15", action="SELL",
        stock_code="2330", shares=1000, price=1050, fee=1496.25, tax=3150,
        amount=1_050_000, cash_after=1_094_000,
    ))
    cash = get_current_cash(tmp_db, pid, 1_000_000)
    assert abs(cash - 1_094_000) < 0.01


# ==========================================================
# Fee calculation tests
# ==========================================================

def test_calc_buy_cost():
    """買進：fee = max(20, shares*price*0.001425)"""
    fee, tax, total = calc_buy_cost(1000, 950)
    assert fee == max(20, 1000 * 950 * 0.001425)
    assert tax == 0
    assert total == fee + tax


def test_calc_sell_cost():
    """賣出：fee + 證交稅"""
    fee, tax, total = calc_sell_cost(1000, 1000)
    assert fee == max(20, 1000 * 1000 * 0.001425)
    assert tax == 1000 * 1000 * 0.003
    assert total == fee + tax


def test_calc_fee_floor_at_20():
    """小金額時手續費下限 20"""
    fee, _, _ = calc_buy_cost(100, 50)  # 100*50*0.001425 = 7.125 → 應 max(20)
    assert fee == 20


# ==========================================================
# Engine: 規則版
# ==========================================================

def test_evaluate_portfolio_buy_basic(tmp_db):
    """規則版：分數過門檻 → 買入"""
    p = PaperPortfolio(name="BUY", stock_pool=["2330"], initial_cash=1_000_000,
                       max_holdings=5, buy_score_threshold=70)
    pid = create_portfolio(tmp_db, p)

    stock_data = {"2330": {"code": "2330", "name": "台積電", "price": 950,
                            "pe": 22, "eps": 43, "rev_yoy": 30, "yield_pct": 1.8}}
    result = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-03", stock_data)

    assert len(result.buy_actions) == 1
    assert result.buy_actions[0].stock_code == "2330"
    assert result.buy_actions[0].signal_score >= 70

    # 持倉應該有 1 筆
    holdings = list_holdings(tmp_db, pid)
    assert len(holdings) == 1
    assert holdings[0].stock_code == "2330"


def test_evaluate_portfolio_no_buy_below_threshold(tmp_db):
    """訊號分數太低不買"""
    p = PaperPortfolio(name="LOW", stock_pool=["2330"], buy_score_threshold=90)
    pid = create_portfolio(tmp_db, p)

    stock_data = {"2330": {"code": "2330", "name": "X", "price": 100,
                            "pe": 100, "eps": -1, "rev_yoy": -50, "yield_pct": 0}}
    result = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-03", stock_data)
    assert len(result.buy_actions) == 0


def test_evaluate_portfolio_sell_take_profit(tmp_db):
    """第二天漲 25% → 觸發停利"""
    p = PaperPortfolio(name="TP", stock_pool=["2330"], initial_cash=1_000_000,
                       max_holdings=5, buy_score_threshold=70,
                       sell_take_profit_pct=20.0, sell_stop_loss_pct=8.0)
    pid = create_portfolio(tmp_db, p)

    # Day 1: 買（1M / 100 = 10,000 股 = 10 張）
    stock_data1 = {"2330": {"code": "2330", "name": "X", "price": 100,
                             "pe": 15, "eps": 7, "rev_yoy": 30, "yield_pct": 3.0}}
    result_day1 = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-01", stock_data1)
    assert len(result_day1.buy_actions) == 1
    holdings_day1 = list_holdings(tmp_db, pid)
    assert len(holdings_day1) == 1
    day1_shares = holdings_day1[0].shares

    # Day 2: 漲到 125 → 觸發停利 20%
    stock_data2 = {"2330": {"code": "2330", "name": "X", "price": 125,
                             "pe": 15, "eps": 7, "rev_yoy": 30, "yield_pct": 3.0}}
    result = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-02", stock_data2)
    assert len(result.sell_actions) == 1
    assert "停利" in result.sell_actions[0].reasoning
    assert result.sell_actions[0].shares == day1_shares
    # 賣出後 cash 又有 ~247K、會再買 1 張 1000 股
    # 這是設計行為（每天重新評估、不是靜默等待）
    holdings_after = list_holdings(tmp_db, pid)
    if holdings_after:
        # 有再買 → entry_date 應為 Day2
        assert holdings_after[0].entry_date == "2026-07-02"
        assert len(result.buy_actions) == 1


def test_evaluate_portfolio_no_buy_when_full(tmp_db):
    """持倉已滿 → 不再買"""
    p = PaperPortfolio(name="FULL", stock_pool=["2330", "2454"], max_holdings=2,
                       initial_cash=1_000_000)
    pid = create_portfolio(tmp_db, p)

    stock_data = {
        "2330": {"code": "2330", "name": "A", "price": 100, "pe": 15, "eps": 7, "rev_yoy": 30, "yield_pct": 3},
        "2454": {"code": "2454", "name": "B", "price": 100, "pe": 15, "eps": 7, "rev_yoy": 30, "yield_pct": 3},
    }
    evaluate_portfolio_one_day(tmp_db, pid, "2026-07-01", stock_data)
    holdings = list_holdings(tmp_db, pid)
    assert len(holdings) == 2
    # 現金已被兩檔均分、各約 5000 股 = 5 張

    # Day 2：池裡多加一檔，但 max_holdings 已滿
    stock_data2 = dict(stock_data)
    stock_data2["2882"] = {"code": "2882", "name": "C", "price": 100, "pe": 15, "eps": 7, "rev_yoy": 30, "yield_pct": 3}
    p.stock_pool = ["2330", "2454", "2882"]
    from stocktool.paper_trading import update_portfolio
    update_portfolio(tmp_db, p)
    result = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-02", stock_data2)
    assert len(result.buy_actions) == 0
    assert len(list_holdings(tmp_db, pid)) == 2  # 仍 2 筆、沒加 2882


def test_evaluate_portfolio_paused_skipped(tmp_db):
    """暫停的組合跳過"""
    p = PaperPortfolio(name="PAUSE", stock_pool=["2330"])
    pid = create_portfolio(tmp_db, p)
    update_portfolio_status(tmp_db, pid, "paused")

    stock_data = {"2330": {"code": "2330", "name": "X", "price": 100}}
    result = evaluate_portfolio_one_day(tmp_db, pid, "2026-07-01", stock_data)
    assert len(result.buy_actions) == 0


# ==========================================================
# Engine: AI 版
# ==========================================================

def test_detect_market_regime_bull():
    """MA20 > MA60 + 上漲 → 多頭"""
    import pandas as pd
    closes = list(range(100, 160))  # 上漲趨勢
    df = pd.DataFrame({"close": closes})
    regime = detect_market_regime(df)
    assert regime.label == "bull"


def test_detect_market_regime_bear():
    """MA20 < MA60 + 下跌 → 空頭"""
    import pandas as pd
    closes = list(range(200, 140, -1))  # 下跌趨勢
    df = pd.DataFrame({"close": closes})
    regime = detect_market_regime(df)
    assert regime.label == "bear"


def test_detect_market_regime_sideways():
    """盤整"""
    import pandas as pd
    closes = [100 + (i % 5) for i in range(70)]  # 震盪
    df = pd.DataFrame({"close": closes})
    regime = detect_market_regime(df)
    assert regime.label == "sideways"


def test_evaluate_ai_portfolio_basic(tmp_db):
    """AI 版能跑且有 reasoning"""
    p = PaperPortfolio(name="AI", stock_pool=["2330"], initial_cash=1_000_000,
                       max_holdings=5, strategy_mode="ai_meta", ai_threshold=60)
    pid = create_portfolio(tmp_db, p)

    regime = MarketRegime("bull", 22800, 21500, 5.5, "多頭")
    stock_data = {"2330": {"code": "2330", "name": "台積電", "price": 950,
                            "pe": 22, "eps": 43, "rev_yoy": 30, "yield_pct": 1.8}}
    result = evaluate_ai_portfolio_one_day(tmp_db, pid, "2026-07-03", stock_data, regime)
    if result.buy_actions:
        assert "[AI meta:" in result.buy_actions[0].reasoning


# ==========================================================
# Signal calculation
# ==========================================================

def test_calc_simple_signal_high_score():
    """強勢股應得高分"""
    p = PaperPortfolio(name="X")
    info = {"code": "2330", "name": "X", "price": 100, "pe": 10, "eps": 10,
            "rev_yoy": 50, "yield_pct": 5}
    sig = calc_simple_signal(info, p)
    assert sig.score >= 75
    assert len(sig.reasoning_parts) > 0


def test_calc_simple_signal_low_score():
    """虧損股應得低分"""
    p = PaperPortfolio(name="X")
    info = {"code": "1111", "name": "Y", "price": 50, "pe": 200, "eps": -2,
            "rev_yoy": -30, "yield_pct": 0}
    sig = calc_simple_signal(info, p)
    assert sig.score < 50


# ==========================================================
# Excel parser
# ==========================================================

def test_parse_excel_basic(tmp_path):
    import openpyxl
    xlsx = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["股票代號", "其他欄"])
    ws.append(["2330", "x"])
    ws.append(["2454", "y"])
    ws.append(["9906", "z"])
    wb.save(xlsx)

    pool, warns = parse_excel_to_stock_pool(str(xlsx))
    assert pool == ["2330", "2454", "9906"]


def test_parse_excel_fuzzy_match(tmp_path):
    """支援不同欄位名"""
    import openpyxl
    xlsx = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["代號", "X"])  # 簡寫
    ws.append(["2330", "x"])
    wb.save(xlsx)

    pool, _ = parse_excel_to_stock_pool(str(xlsx))
    assert pool == ["2330"]


def test_parse_excel_skip_invalid(tmp_path):
    """非數字代號跳過"""
    import openpyxl
    xlsx = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["股票代號", "X"])
    ws.append(["2330", "x"])
    ws.append(["abc", "y"])  # 無效
    ws.append(["99", "z"])   # 太短
    wb.save(xlsx)

    pool, warns = parse_excel_to_stock_pool(str(xlsx))
    assert pool == ["2330"]
    assert any("跳過" in w for w in warns)


def test_parse_excel_no_code_col(tmp_path):
    import openpyxl
    xlsx = tmp_path / "test.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["XXX", "YYY"])  # 找不到股票代號欄
    wb.save(xlsx)

    pool, warns = parse_excel_to_stock_pool(str(xlsx))
    assert pool == []
    assert any("找不到" in w for w in warns)