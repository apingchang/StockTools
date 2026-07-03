"""
stocktool.paper_config - 回測參數 → 模擬買賣參數的轉換
=====================================================

【V1.2.0-paper-trading】
讓使用者點「採用回測參數」一鍵把 backtest 模組的設定帶進來。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .paper_trading import PaperPortfolio


# 回測參數 → 模擬買賣參數的對應表
# 回測參數的單位說明（從 stocktool.config DEFAULT_CONFIG 抄過來）：
# - stop_loss: -0.03 = -3% → sell_stop_loss_pct: 3.0
# - take_profit: 0.08 = +8% → sell_take_profit_pct: 8.0
# - capital: 1000000.0 → initial_cash: 1000000
# - topk: 7 → max_holdings: 7
# - hold_days: 10 → sell_max_hold_days: 10
# - min_rev_yoy: 0.0 (%) → buy_min_rev_yoy: 0.0
# - min_eps_yoy: 0.0 (%) → buy_min_eps_yoy: 0.0
# - simple_max_pe: 50 → buy_max_pe: 50
# - simple_min_eps: 1.0 (元) → 不直接對應 paper（paper 用訊號分數）

# 注意：回測的 stop_loss 是負數 (-0.03)、paper 用正值 (3.0) 表「跌多少 % 就賣」


@dataclass
class BacktestParamsMapping:
    """回測 → 模擬買賣 參數對應"""
    cfg: object  # StrategyConfig（用 duck typing）

    def to_paper_portfolio(self, name: str = "", excel_file: Optional[str] = None,
                           stock_pool: Optional[list] = None) -> PaperPortfolio:
        """從 cfg 產生一個 PaperPortfolio、套用回測參數"""
        cfg = self.cfg
        p = PaperPortfolio(
            name=name,
            excel_file=excel_file,
            stock_pool=stock_pool or [],
            initial_cash=float(getattr(cfg, "capital", 1_000_000.0)),
            max_holdings=int(getattr(cfg, "topk", 7)),
            # 買入參數（複用既有評分參數）
            buy_score_threshold=70.0,   # 訊號門檻 paper 自己定、回測沒對應
            buy_min_rev_yoy=float(getattr(cfg, "min_rev_yoy", 0.0)),
            buy_min_eps_yoy=float(getattr(cfg, "min_eps_yoy", 0.0)),
            buy_max_pe=float(getattr(cfg, "simple_max_pe", 50.0)),
            buy_min_yield=0.0,  # 回測目前沒有殖利率下限參數
            # 賣出參數（停損是負數 → 取絕對值轉成正數 %）
            sell_stop_loss_pct=abs(float(getattr(cfg, "stop_loss", -0.03))) * 100,
            sell_take_profit_pct=float(getattr(cfg, "take_profit", 0.08)) * 100,
            sell_max_hold_days=int(getattr(cfg, "hold_days", 10)),
            # 預設 manual
            strategy_mode="manual",
        )
        return p


def apply_backtest_params_to_portfolio(p: PaperPortfolio, cfg) -> PaperPortfolio:
    """把回測參數套到現有 PaperPortfolio（in-place 修改）"""
    mapping = BacktestParamsMapping(cfg=cfg)
    template = mapping.to_paper_portfolio(name=p.name, excel_file=p.excel_file, stock_pool=p.stock_pool)
    p.initial_cash = template.initial_cash
    p.max_holdings = template.max_holdings
    p.buy_min_rev_yoy = template.buy_min_rev_yoy
    p.buy_min_eps_yoy = template.buy_min_eps_yoy
    p.buy_max_pe = template.buy_max_pe
    p.buy_min_yield = template.buy_min_yield
    p.sell_stop_loss_pct = template.sell_stop_loss_pct
    p.sell_take_profit_pct = template.sell_take_profit_pct
    p.sell_max_hold_days = template.sell_max_hold_days
    return p