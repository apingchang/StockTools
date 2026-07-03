"""
stocktool.paper_engine - 模擬買賣引擎
====================================

【V1.2.0-paper-trading】

設計：
- 每天盤後（或手動推進）觸發一次
- 對一組 PaperPortfolio 跑一輪：
  1. 抓股票池 + 持股的當日收盤價
  2. 計算賣出訊號 → 觸發就賣
  3. 計算買入訊號 → 排序 → 取前 N 個 → 觸發就買
  4. 寫 daily snapshot

規則：
- 不做當沖（今天買的不能今天賣）
- 可加碼（訊號仍觸發 + 距上次加碼 ≥ 5 日）
- 可換手（賣出後隔日才可進場新標的）

依賴：paper_trading.py / fetch_market.py / scoring.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd

from .paper_trading import (
    PaperPortfolio, SimHolding, SimTrade,
    get_portfolio, list_holdings, upsert_holding, delete_holding,
    insert_trade, list_trades, upsert_daily_snapshot, get_current_cash,
    calc_buy_cost, calc_sell_cost
)


# ==========================================================
# 訊號計算（簡化版：複用既有 calculate_simple_score 的邏輯）
# ==========================================================

@dataclass
class StockSignal:
    code: str
    name: str = ""
    score: float = 0.0          # 0~100 綜合分數
    price: float = 0.0
    pe: Optional[float] = None
    eps: Optional[float] = None
    rev_yoy: Optional[float] = None
    yield_pct: Optional[float] = None
    rsi: Optional[float] = None
    ma20_slope: Optional[float] = None
    reasoning_parts: List[str] = None

    def __post_init__(self):
        if self.reasoning_parts is None:
            self.reasoning_parts = []


def calc_simple_signal(stock_info: Dict[str, Any], p: PaperPortfolio) -> StockSignal:
    """
    簡易訊號計算（不依賴 StrategyConfig）

    stock_info 應包含：
      - code, name, price
      - pe, eps, rev_yoy, yield_pct
      - rsi (optional), ma20_slope (optional)

    回傳 StockSignal（score 0~100）
    """
    sig = StockSignal(code=stock_info.get("code", ""), name=stock_info.get("name", ""))
    sig.price = float(stock_info.get("price") or 0)
    sig.pe = stock_info.get("pe")
    sig.eps = stock_info.get("eps")
    sig.rev_yoy = stock_info.get("rev_yoy")
    sig.yield_pct = stock_info.get("yield_pct")
    sig.rsi = stock_info.get("rsi")
    sig.ma20_slope = stock_info.get("ma20_slope")

    score = 50.0  # 中性起始
    parts: List[str] = []

    # 基本面：4 個因子
    if sig.rev_yoy is not None:
        if sig.rev_yoy >= 30:
            score += 15
            parts.append(f"營收YoY {sig.rev_yoy:.1f}% 強")
        elif sig.rev_yoy >= 10:
            score += 8
            parts.append(f"營收YoY {sig.rev_yoy:.1f}% 中")
        elif sig.rev_yoy >= 0:
            score += 2
        else:
            score -= 10
            parts.append(f"營收YoY {sig.rev_yoy:.1f}% 衰退")

    if sig.eps is not None and sig.eps > 0:
        score += 8
        parts.append(f"EPS {sig.eps:.2f} 為正")
    elif sig.eps is not None and sig.eps <= 0:
        score -= 15
        parts.append(f"EPS {sig.eps:.2f} 虧損")

    if sig.yield_pct is not None and sig.yield_pct > 0:
        score += min(sig.yield_pct * 5, 10)
        parts.append(f"殖利率 {sig.yield_pct:.2f}%")

    if sig.pe is not None and sig.pe > 0:
        if sig.pe <= 15:
            score += 8
            parts.append(f"PE {sig.pe:.1f} 便宜")
        elif sig.pe <= 25:
            score += 3
        elif sig.pe >= 50:
            score -= 10
            parts.append(f"PE {sig.pe:.1f} 偏高")

    # 技術面（如果提供）
    if sig.rsi is not None:
        if sig.rsi < 30:
            score += 10
            parts.append(f"RSI {sig.rsi:.0f} 超賣")
        elif sig.rsi > 70:
            score -= 5
            parts.append(f"RSI {sig.rsi:.0f} 超買")

    if sig.ma20_slope is not None and sig.ma20_slope > 0:
        score += 5
        parts.append(f"MA20 上升")

    # 訊號門檻
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    sig.score = score
    sig.reasoning_parts = parts
    return sig


# ==========================================================
# 買賣決策（單一組合一天）
# ==========================================================

@dataclass
class DailyRunResult:
    trade_date: str
    portfolio_id: int
    sell_actions: List[SimTrade]
    buy_actions: List[SimTrade]
    skipped: List[Dict[str, Any]]
    signals: List[StockSignal]
    twse_close: Optional[float] = None


def evaluate_portfolio_one_day(
    db_path: str,
    portfolio_id: int,
    trade_date: str,
    stock_data: Dict[str, Dict[str, Any]],   # code → {price, pe, eps, rev_yoy, yield_pct, rsi, name}
    twse_close: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> DailyRunResult:
    """
    對一組 PaperPortfolio 跑一天的決策

    stock_data: 股票池 + 持股的所有股票當日資料 dict
    """
    def log(msg: str):
        if logger:
            logger.info(msg)

    p = get_portfolio(db_path, portfolio_id)
    if p is None:
        raise ValueError(f"portfolio {portfolio_id} 不存在")
    if p.status != "active":
        log(f"[P{portfolio_id}] {p.name} 狀態為 {p.status}、跳過")
        return DailyRunResult(trade_date, portfolio_id, [], [], [], [])

    # 載入現況
    holdings = list_holdings(db_path, portfolio_id)
    cash = get_current_cash(db_path, portfolio_id, p.initial_cash)
    holdings_by_code = {h.stock_code: h for h in holdings}

    # 今天有沒有買過（不能當沖）
    today_buy_codes = set()
    for t in list_trades(db_path, portfolio_id, limit=100):
        if t.trade_date == trade_date and t.action == "BUY":
            today_buy_codes.add(t.stock_code)

    sell_actions: List[SimTrade] = []
    buy_actions: List[SimTrade] = []
    skipped: List[Dict[str, Any]] = []

    # ========== Step 1: 賣出決策 ==========
    for h in list(holdings):  # list() 因為可能會改
        if h.stock_code in today_buy_codes:
            skipped.append({"code": h.stock_code, "reason": "當沖禁止（今日已買）"})
            continue
        if h.stock_code not in stock_data:
            skipped.append({"code": h.stock_code, "reason": "無當日資料"})
            continue

        info = stock_data[h.stock_code]
        price = float(info.get("price") or 0)
        if price <= 0:
            skipped.append({"code": h.stock_code, "reason": "價格=0"})
            continue

        # 賣出條件
        holding_days = (datetime.strptime(trade_date, "%Y-%m-%d") -
                        datetime.strptime(h.entry_date, "%Y-%m-%d")).days
        profit_pct = (price - h.avg_cost) / h.avg_cost * 100

        reasons: List[str] = []
        sell_signal = False
        if profit_pct <= -p.sell_stop_loss_pct:
            sell_signal = True
            reasons.append(f"停損 {profit_pct:.1f}%")
        elif profit_pct >= p.sell_take_profit_pct:
            sell_signal = True
            reasons.append(f"停利 {profit_pct:.1f}%")
        elif holding_days >= p.sell_max_hold_days:
            sell_signal = True
            reasons.append(f"持有 {holding_days} 天 >= 上限 {p.sell_max_hold_days}")
        # AI 模式：訊號轉弱
        elif p.strategy_mode == "ai_meta":
            sig = calc_simple_signal(info, p)
            if sig.score < (p.ai_threshold - 20):
                sell_signal = True
                reasons.append(f"AI 訊號轉弱 {sig.score:.0f}")

        if not sell_signal:
            continue

        # 執行賣出
        fee, tax, total_cost = calc_sell_cost(h.shares, price)
        amount = h.shares * price
        cash_after = cash + amount - total_cost

        # 更新均成本價為 0（清倉）
        delete_holding(db_path, portfolio_id, h.stock_code)

        # 記錄交易
        reasoning = "; ".join(reasons)
        trade = SimTrade(
            portfolio_id=portfolio_id,
            trade_date=trade_date,
            action="SELL",
            stock_code=h.stock_code,
            stock_name=h.stock_name,
            shares=h.shares,
            price=price,
            fee=fee, tax=tax,
            amount=amount,
            cash_after=cash_after,
            reasoning=reasoning,
            confidence=3,
        )
        insert_trade(db_path, trade)
        cash = cash_after
        sell_actions.append(trade)
        log(f"  [SELL] {h.stock_code} {h.shares:,.0f} 股 @ {price:.2f} ({reasoning})")

    # ========== Step 2: 買入決策 ==========
    # 重新載入持倉（賣出後）
    holdings = list_holdings(db_path, portfolio_id)
    holdings_by_code = {h.stock_code: h for h in holdings}

    # 計算股票池的訊號
    pool_codes = list(p.stock_pool or [])
    signals: List[StockSignal] = []
    for code in pool_codes:
        if code in holdings_by_code:
            continue  # 已持有不重複進場
        if code in today_buy_codes:
            continue
        if code not in stock_data:
            skipped.append({"code": code, "reason": "無當日資料"})
            continue
        info = stock_data[code]
        if (info.get("price") or 0) <= 0:
            skipped.append({"code": code, "reason": "價格=0"})
            continue
        sig = calc_simple_signal(info, p)
        signals.append(sig)

    # 訊號排序（高分優先）
    signals.sort(key=lambda s: s.score, reverse=True)

    # 最多買入數量 = max_holdings - 現持倉
    slots = max(0, p.max_holdings - len(holdings))
    if slots <= 0:
        log(f"  [BUY] 持倉已滿 {len(holdings)}/{p.max_holdings}、無空間")
    elif cash <= 0:
        log(f"  [BUY] 現金不足 {cash:.0f}")
    else:
        # 每檔可用現金 = cash / slots
        per_slot_cash = cash / slots if slots > 0 else 0

        for sig in signals:
            if slots <= 0:
                break
            if sig.score < p.buy_score_threshold:
                break  # 後面分數更低、不用看

            info = stock_data[sig.code]
            price = float(info.get("price") or 0)
            # 計算可買股數（1 張 = 1000 股，零股支援）
            if per_slot_cash < price * 100:
                # 錢不夠買 1 張 → 跳過
                skipped.append({"code": sig.code, "reason": f"現金 {per_slot_cash:.0f} < 1 張 {price*100:.0f}"})
                continue
            shares = int(per_slot_cash // price)
            shares = (shares // 1000) * 1000  # 整張
            if shares <= 0:
                shares = int(per_slot_cash // price)  # 接受零股
            if shares <= 0:
                continue

            fee, tax, total_cost = calc_buy_cost(shares, price)
            amount = shares * price
            if amount + total_cost > cash:
                skipped.append({"code": sig.code, "reason": "現金不足"})
                continue

            cash_after = cash - amount - total_cost
            reasoning_parts = sig.reasoning_parts or []
            reasoning = f"訊號 {sig.score:.0f} >= {p.buy_score_threshold}; " + "; ".join(reasoning_parts)
            trade = SimTrade(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                action="BUY",
                stock_code=sig.code,
                stock_name=sig.name or info.get("name", ""),
                shares=shares,
                price=price,
                fee=fee, tax=tax,
                amount=amount,
                cash_after=cash_after,
                signal_score=sig.score,
                reasoning=reasoning,
                confidence=4 if sig.score >= 80 else 3,
            )
            insert_trade(db_path, trade)

            # 更新持倉
            upsert_holding(db_path, SimHolding(
                portfolio_id=portfolio_id,
                stock_code=sig.code,
                stock_name=trade.stock_name,
                shares=shares,
                avg_cost=(amount + total_cost) / shares,  # 含手續費/稅的均成本
                entry_date=trade_date,
                entry_reason=reasoning,
                entry_score=sig.score,
                last_buy_date=trade_date,
                add_count=0,
            ))

            buy_actions.append(trade)
            cash = cash_after
            slots -= 1
            log(f"  [BUY] {sig.code} {shares:,} 股 @ {price:.2f} (訊號 {sig.score:.0f})")

    # ========== Step 3: 寫每日 snapshot ==========
    holdings_after = list_holdings(db_path, portfolio_id)
    holdings_value = 0.0
    for h in holdings_after:
        if h.stock_code in stock_data:
            price = float(stock_data[h.stock_code].get("price") or 0)
            holdings_value += h.shares * price
        else:
            holdings_value += h.shares * h.avg_cost  # fallback

    total_value = cash + holdings_value
    cum_return = (total_value - p.initial_cash) / p.initial_cash * 100 if p.initial_cash else 0

    upsert_daily_snapshot(
        db_path, portfolio_id, trade_date,
        cash=cash, holdings_value=holdings_value, total_value=total_value,
        holdings_count=len(holdings_after),
        cum_return_pct=cum_return,
        bench_return_pct=None,  # 留給之後計算
        twse_close=twse_close,
    )

    return DailyRunResult(
        trade_date=trade_date,
        portfolio_id=portfolio_id,
        sell_actions=sell_actions,
        buy_actions=buy_actions,
        skipped=skipped,
        signals=signals,
        twse_close=twse_close,
    )


# ==========================================================
# AI Meta-Strategy：regime-aware 動態加權
# ==========================================================

@dataclass
class MarketRegime:
    label: str            # 'bull' / 'bear' / 'sideways'
    twse_ma20: Optional[float] = None
    twse_ma60: Optional[float] = None
    change_20d_pct: Optional[float] = None
    description: str = ""


def detect_market_regime(twse_history: pd.DataFrame) -> MarketRegime:
    """
    用加權指數近 60 日判定盤勢
    twse_history: 必須有 'close' 欄、index 為 date
    """
    if twse_history is None or len(twse_history) < 60:
        return MarketRegime(label="sideways", description="資料不足，採中性")

    closes = twse_history["close"].astype(float)
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma60 = closes.rolling(60).mean().iloc[-1]
    change_20d = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100 if len(closes) >= 20 else 0

    if ma20 > ma60 * 1.02 and change_20d > 0:
        return MarketRegime("bull", ma20, ma60, change_20d,
                           f"多頭：MA20={ma20:.0f} > MA60={ma60:.0f}, 20日漲 {change_20d:.1f}%")
    elif ma20 < ma60 * 0.98 and change_20d < -3:
        return MarketRegime("bear", ma20, ma60, change_20d,
                           f"空頭：MA20={ma20:.0f} < MA60={ma60:.0f}, 20日跌 {change_20d:.1f}%")
    else:
        return MarketRegime("sideways", ma20, ma60, change_20d,
                           f"盤整：MA20={ma20:.0f} ≈ MA60={ma60:.0f}")


def ai_meta_decision(
    stock_info: Dict[str, Any],
    p: PaperPortfolio,
    regime: MarketRegime,
) -> Tuple[float, str, int]:
    """
    AI Meta-Strategy 決策
    回傳 (signal_score 0~100, reasoning, confidence 1-5)
    """
    sig = calc_simple_signal(stock_info, p)

    # 依盤勢動態加權（這裡只用 score + regime 描述，但設計可擴充）
    base = sig.score
    multiplier = 1.0
    reasoning = []

    if regime.label == "bull":
        # 多頭：偏積極，技術訊號加重
        if stock_info.get("rsi") is not None and 50 <= stock_info["rsi"] <= 70:
            multiplier += 0.1
            reasoning.append("多頭+RSI 健康區")
        if (stock_info.get("ma20_slope") or 0) > 0:
            multiplier += 0.05
            reasoning.append("多頭+MA20 上揚")
    elif regime.label == "bear":
        # 空頭：偏保守，基本面加重
        if (stock_info.get("yield_pct") or 0) >= 4.0:
            multiplier += 0.15
            reasoning.append("空頭+高殖利率防禦")
        if (stock_info.get("rev_yoy") or 0) >= 20:
            multiplier += 0.1
            reasoning.append("空頭+營收強")
    else:
        # 盤整：均權
        reasoning.append("盤整均權")

    # 高分強化（≥ 80 再加乘）
    if base >= 80:
        multiplier += 0.05
        reasoning.append("高分強化")

    score = min(base * multiplier, 100)

    # 信心度（看分數高低 + regime 一致性）
    confidence = 3
    if score >= 80:
        confidence = 4
    if score >= 90:
        confidence = 5
    if score < 40:
        confidence = 2

    full_reasoning = f"[AI meta: {regime.label}] " + "; ".join(reasoning) + f" → score {score:.0f}"
    return score, full_reasoning, confidence


def evaluate_ai_portfolio_one_day(
    db_path: str,
    portfolio_id: int,
    trade_date: str,
    stock_data: Dict[str, Dict[str, Any]],
    regime: MarketRegime,
    twse_close: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> DailyRunResult:
    """
    AI Meta-Strategy 版的單日決策（包裝 evaluate_portfolio_one_day + 替換訊號計算）
    """
    def log(msg: str):
        if logger:
            logger.info(msg)

    p = get_portfolio(db_path, portfolio_id)
    if p is None or p.status != "active":
        return DailyRunResult(trade_date, portfolio_id, [], [], [], [])

    log(f"[AI][P{portfolio_id}] {regime.description}")

    holdings = list_holdings(db_path, portfolio_id)
    cash = get_current_cash(db_path, portfolio_id, p.initial_cash)
    holdings_by_code = {h.stock_code: h for h in holdings}

    today_buy_codes = set()
    for t in list_trades(db_path, portfolio_id, limit=100):
        if t.trade_date == trade_date and t.action == "BUY":
            today_buy_codes.add(t.stock_code)

    sell_actions: List[SimTrade] = []
    buy_actions: List[SimTrade] = []
    skipped: List[Dict[str, Any]] = []

    # Step 1: 賣出（AI 訊號轉弱）
    for h in list(holdings):
        if h.stock_code in today_buy_codes:
            skipped.append({"code": h.stock_code, "reason": "當沖禁止"})
            continue
        if h.stock_code not in stock_data:
            continue
        info = stock_data[h.stock_code]
        price = float(info.get("price") or 0)
        if price <= 0:
            continue

        holding_days = (datetime.strptime(trade_date, "%Y-%m-%d") -
                        datetime.strptime(h.entry_date, "%Y-%m-%d")).days
        profit_pct = (price - h.avg_cost) / h.avg_cost * 100

        # AI 訊號
        ai_score, ai_reason, ai_conf = ai_meta_decision(info, p, regime)

        sell_signal = False
        reasons: List[str] = []

        # 停損 / 停利 / 持有天數（與規則版共用）
        if profit_pct <= -p.sell_stop_loss_pct:
            sell_signal = True
            reasons.append(f"停損 {profit_pct:.1f}%")
        elif profit_pct >= p.sell_take_profit_pct:
            sell_signal = True
            reasons.append(f"停利 {profit_pct:.1f}%")
        elif holding_days >= p.sell_max_hold_days:
            sell_signal = True
            reasons.append(f"持有 {holding_days} 天達上限")
        elif ai_score < (p.ai_threshold - 25):
            # AI 訊號明顯轉弱才賣（避免假訊號）
            sell_signal = True
            reasons.append(f"AI 訊號 {ai_score:.0f} 過低（門檻 {p.ai_threshold - 25}）")

        if not sell_signal:
            continue

        fee, tax, total_cost = calc_sell_cost(h.shares, price)
        amount = h.shares * price
        cash_after = cash + amount - total_cost
        delete_holding(db_path, portfolio_id, h.stock_code)
        reasoning = "; ".join(reasons) + f" | {ai_reason}"
        trade = SimTrade(
            portfolio_id=portfolio_id,
            trade_date=trade_date,
            action="SELL",
            stock_code=h.stock_code,
            stock_name=h.stock_name,
            shares=h.shares,
            price=price,
            fee=fee, tax=tax,
            amount=amount,
            cash_after=cash_after,
            signal_score=ai_score,
            reasoning=reasoning,
            confidence=ai_conf,
        )
        insert_trade(db_path, trade)
        cash = cash_after
        sell_actions.append(trade)
        log(f"  [AI SELL] {h.stock_code} @ {price:.2f} ({reasoning})")

    # Step 2: 買入
    holdings = list_holdings(db_path, portfolio_id)
    holdings_by_code = {h.stock_code: h for h in holdings}

    pool_codes = list(p.stock_pool or [])
    scored: List[Tuple[float, str, str, int, Dict[str, Any]]] = []
    for code in pool_codes:
        if code in holdings_by_code:
            continue
        if code in today_buy_codes:
            continue
        if code not in stock_data:
            continue
        info = stock_data[code]
        if (info.get("price") or 0) <= 0:
            continue
        ai_score, ai_reason, ai_conf = ai_meta_decision(info, p, regime)
        scored.append((ai_score, code, ai_reason, ai_conf, info))

    scored.sort(key=lambda x: x[0], reverse=True)

    slots = max(0, p.max_holdings - len(holdings))
    if slots > 0 and cash > 0:
        per_slot_cash = cash / slots
        for ai_score, code, ai_reason, ai_conf, info in scored:
            if slots <= 0:
                break
            if ai_score < p.ai_threshold:
                break

            price = float(info.get("price") or 0)
            if per_slot_cash < price * 100:
                continue
            shares = int(per_slot_cash // price)
            shares = (shares // 1000) * 1000
            if shares <= 0:
                shares = int(per_slot_cash // price)
            if shares <= 0:
                continue

            fee, tax, total_cost = calc_buy_cost(shares, price)
            amount = shares * price
            if amount + total_cost > cash:
                continue
            cash_after = cash - amount - total_cost

            trade = SimTrade(
                portfolio_id=portfolio_id,
                trade_date=trade_date,
                action="BUY",
                stock_code=code,
                stock_name=info.get("name", ""),
                shares=shares,
                price=price,
                fee=fee, tax=tax,
                amount=amount,
                cash_after=cash_after,
                signal_score=ai_score,
                reasoning=ai_reason,
                confidence=ai_conf,
            )
            insert_trade(db_path, trade)
            upsert_holding(db_path, SimHolding(
                portfolio_id=portfolio_id,
                stock_code=code,
                stock_name=trade.stock_name,
                shares=shares,
                avg_cost=(amount + total_cost) / shares,
                entry_date=trade_date,
                entry_reason=ai_reason,
                entry_score=ai_score,
                last_buy_date=trade_date,
                add_count=0,
            ))
            buy_actions.append(trade)
            cash = cash_after
            slots -= 1
            log(f"  [AI BUY] {code} {shares:,}股 @ {price:.2f} (AI {ai_score:.0f}, {ai_reason})")

    # Snapshot
    holdings_after = list_holdings(db_path, portfolio_id)
    holdings_value = 0.0
    for h in holdings_after:
        if h.stock_code in stock_data:
            price = float(stock_data[h.stock_code].get("price") or 0)
            holdings_value += h.shares * price
        else:
            holdings_value += h.shares * h.avg_cost

    total_value = cash + holdings_value
    cum_return = (total_value - p.initial_cash) / p.initial_cash * 100

    upsert_daily_snapshot(
        db_path, portfolio_id, trade_date,
        cash=cash, holdings_value=holdings_value, total_value=total_value,
        holdings_count=len(holdings_after),
        cum_return_pct=cum_return,
        twse_close=twse_close,
    )

    return DailyRunResult(
        trade_date=trade_date,
        portfolio_id=portfolio_id,
        sell_actions=sell_actions,
        buy_actions=buy_actions,
        skipped=skipped,
        signals=[],
        twse_close=twse_close,
    )