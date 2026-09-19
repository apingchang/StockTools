"""
tests/test_paper_stock_names.py - 驗證模擬買賣股票名稱對照與修復機制
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "source")))

from stocktool import paper_trading as pt
from stocktool import paper_engine as pe


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


def test_get_stock_name_known_stocks():
    """驗證常用台股代號可精確解析出中文名稱而非代號數字"""
    assert pt.get_stock_name("2330") == "台積電"
    assert pt.get_stock_name("2344") == "華邦電"
    assert pt.get_stock_name("2408") in ("南亞科", "南亞科技")
    assert pt.get_stock_name("2454") == "聯發科"
    assert pt.get_stock_name("2317") == "鴻海"


def test_repair_paper_stock_names(temp_db):
    """驗證 repair_paper_stock_names 可修復資料庫中名稱被寫成代號數字之歷史紀錄"""
    p = pt.PaperPortfolio(name="TestRepair", initial_cash=1000000)
    pid = pt.create_portfolio(temp_db, p)

    # 模擬過去產生的錯誤紀錄 (名稱填成代號)
    pt.upsert_holding(temp_db, pt.SimHolding(
        portfolio_id=pid, stock_code="2344", stock_name="2344",
        shares=613, avg_cost=160.23, entry_date="2026-09-10"
    ))
    pt.upsert_holding(temp_db, pt.SimHolding(
        portfolio_id=pid, stock_code="2408", stock_name="2408",
        shares=207, avg_cost=473.67, entry_date="2026-09-10"
    ))
    t1 = pt.SimTrade(
        portfolio_id=pid, trade_date="2026-09-10", action="BUY",
        stock_code="2344", stock_name="2344", shares=613, price=160.0,
        amount=98080, cash_after=900000
    )
    pt.insert_trade(temp_db, t1)

    # 執行修復
    fixed = pt.repair_paper_stock_names(temp_db)
    assert fixed >= 3

    # 驗證持倉名稱已被更新為中文
    holdings = pt.list_holdings(temp_db, pid)
    holdings_dict = {h.stock_code: h.stock_name for h in holdings}
    assert holdings_dict["2344"] == "華邦電"
    assert holdings_dict["2408"] in ("南亞科", "南亞科技")

    # 驗證交易紀錄已被更新
    trades = pt.list_trades(temp_db, pid)
    assert trades[0].stock_name == "華邦電"


def test_calc_simple_signal_name_resolution():
    """驗證 calc_simple_signal 在 stock_info 名稱缺失時自動補齊中文名稱"""
    p = pt.PaperPortfolio(name="TestSig")
    info_no_name = {
        "code": "2344",
        "name": "",
        "price": 160.0,
    }
    sig = pe.calc_simple_signal(info_no_name, p)
    assert sig.code == "2344"
    assert sig.name == "華邦電"
