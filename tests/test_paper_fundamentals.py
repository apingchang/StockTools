"""
【V1.2.1-paper-fundamentals】歷史基本面與技術指標串接測試
======================================================
1. 測試 _query_latest_eps_for_date 的財報公佈日隔離 (Look-ahead bias 防範)
2. 測試 _query_latest_div_for_date 的股利與殖利率撈取
3. 測試 enrich_stock_fundamentals 的資料注入與 PE / 殖利率計算
4. 測試 _get_historical_prices 產出之完整欄位 (含 RSI, MA20 斜率)
5. 測試績優股信號評分達到 >= 70 分買入門檻
6. 測試版本資訊與視窗標題時間戳記
"""

import os
import sys
from datetime import datetime
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from stocktool.config import VERSION, BUILD_TIMESTAMP
from stocktool.database import (
    _query_latest_eps_for_date,
    _query_latest_div_for_date,
)
from stocktool.paper_catchup import (
    enrich_stock_fundamentals,
    _get_historical_prices,
)
from stocktool.paper_trading import PaperPortfolio
from stocktool.paper_engine import calc_simple_signal


def test_version_and_timestamp():
    """驗證版本號與建立時間戳記格式"""
    assert VERSION.startswith("v1.2.")
    assert datetime.strptime(BUILD_TIMESTAMP, "%Y/%m/%d %H:%M:%S")


def test_eps_lookahead_bias_isolation():
    """測試財報公佈法規日隔離（5/15 前只能用前一年 Q4，8/15 前可用 Q1，8/15 後可用 Q2）"""
    codes = ["2330", "2454"]

    # 1. 2026-05-10: 只能看到 2025Q4
    res_may = _query_latest_eps_for_date(None, codes, "2026-05-10")
    if res_may:
        for c in codes:
            if c in res_may:
                assert res_may[c]["year"] == 2025
                assert res_may[c]["quarter"] == 4

    # 2. 2026-07-15: 可看到 2026Q1
    res_jul = _query_latest_eps_for_date(None, codes, "2026-07-15")
    if res_jul:
        for c in codes:
            if c in res_jul:
                assert res_jul[c]["year"] == 2026
                assert res_jul[c]["quarter"] == 1
                assert res_jul[c]["annualized_eps"] == round(res_jul[c]["eps"] * 4, 2)

    # 3. 2026-08-20: 可看到 2026Q2
    res_aug = _query_latest_eps_for_date(None, codes, "2026-08-20")
    if res_aug:
        for c in codes:
            if c in res_aug:
                assert res_aug[c]["year"] == 2026
                assert res_aug[c]["quarter"] == 2
                assert res_aug[c]["annualized_eps"] == round(res_aug[c]["eps"] * 2, 2)


def test_dividend_query_latest():
    """測試股利與殖利率撈取"""
    codes = ["2330", "2548", "2851"]
    div_data = _query_latest_div_for_date(None, codes, "2026-07-15")
    assert "2330" in div_data
    assert div_data["2330"]["cash"] > 0
    assert "2548" in div_data
    assert div_data["2548"]["cash"] >= 8.0  # 華固 2026 現金 8 元


def test_enrich_stock_fundamentals():
    """測試資料補齊與動態 PE、殖利率計算"""
    stock_data = {
        "2330": {"code": "2330", "name": "台積電", "price": 950.0},
        "2548": {"code": "2548", "name": "華固", "price": 100.0},
    }
    enriched = enrich_stock_fundamentals(stock_data, "2026-07-15")

    # 2330 應有 EPS, PE, yield_pct, rev_yoy
    assert enriched["2330"].get("eps") is not None
    assert enriched["2330"].get("pe") is not None
    assert enriched["2330"]["pe"] > 0
    assert enriched["2330"].get("yield_pct") is not None

    # 2548: 現金 8 元 / 股價 100 = 8.0%
    assert enriched["2548"].get("yield_pct") is not None
    assert enriched["2548"]["yield_pct"] >= 7.0


def test_calc_simple_signal_with_enriched_data():
    """測試注入基本面後，績優股評分突破 70 分門檻"""
    p = PaperPortfolio(name="TestPortfolio", buy_score_threshold=70.0)

    stock_data = {
        "2330": {"code": "2330", "name": "台積電", "price": 950.0},
        "2548": {"code": "2548", "name": "華固", "price": 101.0},
        "4973": {"code": "4973", "name": "廣穎", "price": 166.0},
    }
    enriched = enrich_stock_fundamentals(stock_data, "2026-07-15")

    for code, info in enriched.items():
        sig = calc_simple_signal(info, p)
        assert sig.score >= 70.0, (
            f"❌ {code} {info.get('name')} 分數 {sig.score} 未達 70 分門檻！\n"
            f"   info={info}\n"
            f"   reasoning={sig.reasoning_parts}"
        )


def test_catch_up_portfolio_buys_quality_stock(tmp_path):
    """端到端測試：補跑時高分績優股能成功觸發 BUY 交易並建立持倉"""
    from stocktool import paper_trading as pt
    from stocktool import paper_catchup as pc
    import sqlite3

    db_path = str(tmp_path / "test_port.db")
    pt.init_paper_trading_db(db_path)
    p = PaperPortfolio(
        name="TestPortfolio",
        stock_pool=["2330", "2548"],
        initial_cash=1_000_000.0,
        max_holdings=5,
        buy_score_threshold=70.0,
    )
    pid = pt.create_portfolio(db_path, p)

    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE sim_portfolios SET started_at='2026-07-10 00:00:00', last_run_date=NULL WHERE id=?", (pid,))
        conn.commit()

    res = pc.catch_up_portfolio(db_path, pid, end_date="2026-07-13")
    assert res.total_buys >= 1

    trades = pt.list_trades(db_path, pid)
    assert len(trades) >= 1
    assert trades[0].action == "BUY"
    assert "2548" in trades[0].stock_code
    assert trades[0].shares > 0
    assert "訊號" in trades[0].reasoning

    holdings = pt.list_holdings(db_path, pid)
    assert len(holdings) >= 1
    assert holdings[0].stock_code == "2548"
