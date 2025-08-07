from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from exchange.base import OrderRequest, Quote


@dataclass
class RiskConfig:
    max_notional_per_trade: float = 25.0
    max_symbol_exposure_pct: float = 0.4
    daily_loss_cap_pct: float = 0.06
    min_price: float = 1.0
    min_avg_volume: int = 0
    max_spread_pct: float = 0.03
    allow_after_hours: bool = False
    max_position_risk_pct: float = 0.02
    max_portfolio_heat_pct: float = 0.10
    max_positions: int = 5
    daily_loss_tier_warn_pct: float = 0.045
    daily_loss_tier_block_pct: float = 0.054
    require_bracket: bool = True
    default_stop_loss_pct: float = 0.10


@dataclass
class EquityContext:
    equity: float
    symbol_exposure: float
    day_realized_pnl_pct: float
    open_positions: int = 0
    portfolio_heat_pct: float = 0.0


@dataclass
class RiskDecision:
    approved: bool
    reason: str = ""
    adjusted_qty: Optional[float] = None
    warn: bool = False
    block_new_entries: bool = False


class RiskManager:
    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg

    def evaluate(self, req: OrderRequest, quote: Quote, ctx: EquityContext, market_open: bool) -> RiskDecision:
        if not market_open and not self.cfg.allow_after_hours:
            return RiskDecision(False, "Market is closed")

        if ctx.day_realized_pnl_pct <= -abs(self.cfg.daily_loss_cap_pct):
            return RiskDecision(False, f"Daily loss cap reached ({ctx.day_realized_pnl_pct:.2%})")

        if ctx.day_realized_pnl_pct <= -abs(self.cfg.daily_loss_tier_block_pct) and req.side == "buy":
            return RiskDecision(False, f"Daily loss tier 90% reached ({ctx.day_realized_pnl_pct:.2%})", block_new_entries=True)

        ref_price = quote.last or (None if quote.bid is None or quote.ask is None else (quote.bid + quote.ask) / 2.0)
        if ref_price is None:
            return RiskDecision(False, "No reference price available")

        if ref_price < self.cfg.min_price:
            return RiskDecision(False, f"Price {ref_price:.2f} below min {self.cfg.min_price:.2f}")

        if quote.bid is not None and quote.ask is not None and quote.ask > 0:
            spread_pct = (quote.ask - quote.bid) / quote.ask
            if spread_pct > self.cfg.max_spread_pct:
                return RiskDecision(False, f"Spread {spread_pct:.2%} exceeds max {self.cfg.max_spread_pct:.2%}")

        if req.side == "buy":
            if ctx.open_positions >= self.cfg.max_positions:
                return RiskDecision(False, f"Max positions {self.cfg.max_positions} reached")
        warn = ctx.day_realized_pnl_pct <= -abs(self.cfg.daily_loss_tier_warn_pct)
 
        per_share_risk = None
        if req.stop_price is not None and ref_price is not None:
            per_share_risk = abs(ref_price - req.stop_price)
        if per_share_risk and per_share_risk > 0:
            max_risk_amount = self.cfg.max_position_risk_pct * max(ctx.equity, 1e-9)
            max_qty_by_risk = max_risk_amount / per_share_risk
            if req.qty > max_qty_by_risk:
                return RiskDecision(False, f"Qty exceeds risk cap; max {max_qty_by_risk:.6f}", adjusted_qty=max_qty_by_risk, warn=warn)
 
            est_added_heat = max_risk_amount / max(ctx.equity, 1e-9)
            if req.side == "buy" and (ctx.portfolio_heat_pct + est_added_heat) > self.cfg.max_portfolio_heat_pct:
                return RiskDecision(False, f"Portfolio heat would exceed {self.cfg.max_portfolio_heat_pct:.2%}", warn=warn)
 
        notional = ref_price * max(req.qty, 0.0)
        if notional > self.cfg.max_notional_per_trade:
            scaled_qty = max(0.0, self.cfg.max_notional_per_trade / ref_price)
            return RiskDecision(False, f"Notional {notional:.2f} exceeds per-trade cap {self.cfg.max_notional_per_trade:.2f}", adjusted_qty=scaled_qty, warn=warn)
 
        if req.side == "buy":
            next_exposure = ctx.symbol_exposure + (notional / max(ctx.equity, 1e-9))
            if next_exposure > self.cfg.max_symbol_exposure_pct:
                return RiskDecision(False, f"Symbol exposure {next_exposure:.2%} exceeds cap {self.cfg.max_symbol_exposure_pct:.2%}", warn=warn)
 
        return RiskDecision(True, warn=warn)
