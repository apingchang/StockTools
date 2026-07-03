"""
【V1.2.0-paper-trading】回測參數轉換測試
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

import pytest

from stocktool.config import StrategyConfig
from stocktool.paper_config import BacktestParamsMapping, apply_backtest_params_to_portfolio
from stocktool.paper_trading import PaperPortfolio


def test_mapping_basic():
    cfg = StrategyConfig()
    cfg.stop_loss = -0.05
    cfg.take_profit = 0.15
    cfg.hold_days = 20
    cfg.capital = 2_000_000
    cfg.topk = 8
    cfg.min_rev_yoy = 10.0
    cfg.min_eps_yoy = 5.0
    cfg.simple_max_pe = 25.0

    p = BacktestParamsMapping(cfg=cfg).to_paper_portfolio(name="A", stock_pool=["2330"])

    assert p.initial_cash == 2_000_000
    assert p.max_holdings == 8
    assert p.sell_stop_loss_pct == 5.0  # abs(-0.05) * 100
    assert p.sell_take_profit_pct == 15.0
    assert p.sell_max_hold_days == 20
    assert p.buy_min_rev_yoy == 10.0
    assert p.buy_min_eps_yoy == 5.0
    assert p.buy_max_pe == 25.0


def test_mapping_negative_stop_loss_to_positive_pct():
    """回測 stop_loss 是負數(-0.03)、轉成 paper 的正值 3.0%"""
    cfg = StrategyConfig()
    cfg.stop_loss = -0.03
    p = BacktestParamsMapping(cfg=cfg).to_paper_portfolio()
    assert p.sell_stop_loss_pct == 3.0


def test_mapping_default_values():
    """未設定時用預設"""
    cfg = StrategyConfig()
    p = BacktestParamsMapping(cfg=cfg).to_paper_portfolio()
    assert p.initial_cash == 1_000_000
    assert p.max_holdings == 7
    assert p.sell_stop_loss_pct == 3.0
    assert p.sell_take_profit_pct == 8.0
    assert p.sell_max_hold_days == 10


def test_apply_to_existing_portfolio():
    """套用回測參數到現有 portfolio"""
    cfg = StrategyConfig()
    cfg.capital = 5_000_000
    cfg.topk = 3
    cfg.stop_loss = -0.10
    cfg.take_profit = 0.30

    p = PaperPortfolio(name="X", stock_pool=["2330"])
    apply_backtest_params_to_portfolio(p, cfg)

    assert p.initial_cash == 5_000_000
    assert p.max_holdings == 3
    assert p.sell_stop_loss_pct == 10.0
    assert p.sell_take_profit_pct == 30.0
    # name / stock_pool 不被覆寫
    assert p.name == "X"
    assert p.stock_pool == ["2330"]