"""
tests/test_paper_rollback.py - 測試模擬買賣時間回推 (Rollback) 與狀態還原
"""

import os
import sys
import tempfile
import sqlite3
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "source")))

from stocktool import paper_trading as pt


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    pt.init_paper_trading_db(path)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def test_get_portfolio_simulated_dates(temp_db):
    p = pt.PaperPortfolio(name="TestDates", initial_cash=1000000)
    pid = pt.create_portfolio(temp_db, p)

    # 初始無任何模擬日
    dates = pt.get_portfolio_simulated_dates(temp_db, pid)
    assert dates == []

    # 插入不同日期的快照與交易
    pt.upsert_daily_snapshot(temp_db, pid, "2026-09-10", cash=900000, holdings_value=100000, total_value=1000000, holdings_count=1)
    pt.upsert_daily_snapshot(temp_db, pid, "2026-09-12", cash=800000, holdings_value=200000, total_value=1000000, holdings_count=2)

    t1 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-11", action="BUY",
        stock_code="2330", stock_name="台積電", shares=1000, price=500,
        fee=712, tax=0, amount=500000, cash_after=500000
    )
    pt.insert_trade(temp_db, t1)

    dates = pt.get_portfolio_simulated_dates(temp_db, pid)
    assert dates == ["2026-09-10", "2026-09-11", "2026-09-12"]


def test_rollback_portfolio_single_day(temp_db):
    p = pt.PaperPortfolio(name="TestRollback1", initial_cash=1000000)
    pid = pt.create_portfolio(temp_db, p)

    # Day 1: 2026-09-10 買入 2330
    t1 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-10", action="BUY",
        stock_code="2330", stock_name="台積電", shares=1000, price=600,
        fee=855, tax=0, amount=600000, cash_after=399145,
        signal_score=85.0, reasoning="首日買入"
    )
    pt.insert_trade(temp_db, t1)
    pt.upsert_holding(temp_db, pt.SimHolding(
        portfolio_id=pid, stock_code="2330", stock_name="台積電",
        shares=1000, avg_cost=600.855, entry_date="2026-09-10",
        entry_reason="首日買入", entry_score=85.0, last_buy_date="2026-09-10"
    ))
    pt.upsert_daily_snapshot(temp_db, pid, "2026-09-10", cash=399145, holdings_value=600000, total_value=999145, holdings_count=1)
    pt.update_portfolio_last_run(temp_db, pid, "2026-09-10")

    # Day 2: 2026-09-11 買入 2317
    t2 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-11", action="BUY",
        stock_code="2317", stock_name="鴻海", shares=1000, price=100,
        fee=142, tax=0, amount=100000, cash_after=299003,
        signal_score=75.0, reasoning="次日買入"
    )
    pt.insert_trade(temp_db, t2)
    pt.upsert_holding(temp_db, pt.SimHolding(
        portfolio_id=pid, stock_code="2317", stock_name="鴻海",
        shares=1000, avg_cost=100.142, entry_date="2026-09-11",
        entry_reason="次日買入", entry_score=75.0, last_buy_date="2026-09-11"
    ))
    pt.upsert_daily_snapshot(temp_db, pid, "2026-09-11", cash=299003, holdings_value=700000, total_value=999003, holdings_count=2)
    pt.update_portfolio_last_run(temp_db, pid, "2026-09-11")

    # Day 3: 2026-09-12 賣出 2330
    t3 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-12", action="SELL",
        stock_code="2330", stock_name="台積電", shares=1000, price=650,
        fee=926, tax=1950, amount=650000, cash_after=946127,
        signal_score=60.0, reasoning="停利賣出"
    )
    pt.insert_trade(temp_db, t3)
    pt.delete_holding(temp_db, pid, "2330")
    pt.upsert_daily_snapshot(temp_db, pid, "2026-09-12", cash=946127, holdings_value=100000, total_value=1046127, holdings_count=1)
    pt.update_portfolio_last_run(temp_db, pid, "2026-09-12")

    # 驗證回推前狀態：持倉僅 2317，交易共 3 筆，最新日期 2026-09-12
    assert len(pt.list_holdings(temp_db, pid)) == 1
    assert pt.list_holdings(temp_db, pid)[0].stock_code == "2317"
    assert len(pt.list_trades(temp_db, pid)) == 3
    assert pt.get_portfolio(temp_db, pid).last_run_date == "2026-09-12"

    # 執行回推 1 日至 2026-09-11
    del_trades, del_snaps = pt.rollback_portfolio(temp_db, pid, target_date="2026-09-11")
    assert del_trades == 1  # 刪除 t3
    assert del_snaps == 1   # 刪除 09-12 快照

    # 驗證回推後狀態：
    # 1. 交易紀錄剩 2 筆 (t1, t2)
    trades = pt.list_trades(temp_db, pid)
    assert len(trades) == 2
    assert all(t.trade_date <= "2026-09-11" for t in trades)

    # 2. 持倉重建：2330 尚未被賣出！應同時持有 2330 與 2317
    holdings = pt.list_holdings(temp_db, pid)
    assert len(holdings) == 2
    holdings_dict = {h.stock_code: h for h in holdings}
    assert "2330" in holdings_dict
    assert "2317" in holdings_dict
    assert holdings_dict["2330"].shares == 1000
    assert abs(holdings_dict["2330"].avg_cost - 600.855) < 0.01
    assert holdings_dict["2317"].shares == 1000

    # 3. 現金還原至 2026-09-11 狀態
    cash = pt.get_current_cash(temp_db, pid, initial_cash=1000000)
    assert round(cash) == 299003

    # 4. last_run_date 回到 2026-09-11
    assert pt.get_portfolio(temp_db, pid).last_run_date == "2026-09-11"


def test_rollback_portfolio_by_days_helper(temp_db):
    p = pt.PaperPortfolio(name="TestHelper", initial_cash=1000000)
    pid = pt.create_portfolio(temp_db, p)

    # 寫入 4 天的快照
    dates = ["2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]
    for d in dates:
        pt.upsert_daily_snapshot(temp_db, pid, d, cash=1000000, holdings_value=0, total_value=1000000, holdings_count=0)

    # 回推 1 日 -> target_date 應為 2026-09-10
    target, del_t, del_s = pt.rollback_portfolio_by_days(temp_db, pid, days=1)
    assert target == "2026-09-10"
    assert del_s == 1

    # 再回推 2 日 -> target_date 應為 2026-09-08
    target, del_t, del_s = pt.rollback_portfolio_by_days(temp_db, pid, days=2)
    assert target == "2026-09-08"

    # 回推超過剩餘天數 -> 完全重置 (None)
    target, del_t, del_s = pt.rollback_portfolio_by_days(temp_db, pid, days=5)
    assert target is None
    assert pt.get_portfolio(temp_db, pid).last_run_date is None
    assert pt.get_portfolio_simulated_dates(temp_db, pid) == []


def test_holdings_replay_with_accumulation_and_partial_sell(temp_db):
    """測試加碼 (加權平均成本) 與部分賣出時的還原正確性"""
    p = pt.PaperPortfolio(name="TestAccum", initial_cash=1000000)
    pid = pt.create_portfolio(temp_db, p)

    # Day 1: 買入 1000 股 @ 100, 費用 142.5 -> 總花費 100142.5
    t1 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-01", action="BUY",
        stock_code="2330", stock_name="台積電", shares=1000, price=100,
        fee=142.5, tax=0, amount=100000, cash_after=899857.5,
        signal_score=80.0, reasoning="初次建倉"
    )
    pt.insert_trade(temp_db, t1)

    # Day 2: 加碼 1000 股 @ 120, 費用 171 -> 總花費 120171
    # 兩次總股數 2000, 總花費 220313.5 -> 均成本 110.15675
    t2 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-02", action="BUY",
        stock_code="2330", stock_name="台積電", shares=1000, price=120,
        fee=171.0, tax=0, amount=120000, cash_after=779686.5,
        signal_score=85.0, reasoning="加碼", is_add=1
    )
    pt.insert_trade(temp_db, t2)

    # Day 3: 部分賣出 1000 股
    t3 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-03", action="SELL",
        stock_code="2330", stock_name="台積電", shares=1000, price=130,
        fee=185.0, tax=390.0, amount=130000, cash_after=909111.5,
        reasoning="減碼"
    )
    pt.insert_trade(temp_db, t3)

    # 回推至 Day 2 (2026-09-02)
    pt.rollback_portfolio(temp_db, pid, target_date="2026-09-02")
    holdings = pt.list_holdings(temp_db, pid)
    assert len(holdings) == 1
    h = holdings[0]
    assert h.stock_code == "2330"
    assert h.shares == 2000
    expected_avg = (100142.5 + 120171.0) / 2000
    assert abs(h.avg_cost - expected_avg) < 0.01
    assert h.add_count == 1
    assert h.last_buy_date == "2026-09-02"

    # 再回推至 Day 1 (2026-09-01)
    pt.rollback_portfolio(temp_db, pid, target_date="2026-09-01")
    holdings = pt.list_holdings(temp_db, pid)
    assert len(holdings) == 1
    h = holdings[0]
    assert h.shares == 1000
    assert abs(h.avg_cost - 100.1425) < 0.01
    assert h.add_count == 0
    assert h.last_buy_date == "2026-09-01"
