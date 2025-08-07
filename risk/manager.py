from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from exchange.base import OrderRequest, Quote


@dataclass
class RiskConfig:
    max_notional_per_trade: float = 25.0
    max_symbol_exposure_pct: float = 0.4
    daily_loss_cap_pct: float = 0.1
    min_price: float = 1.0
    min_avg_volume: int = 0  # placeholder, not enforced without data source
    max_spread_pct: float = 0.03
    allow_after_hours: bool = False


@dataclass
class EquityContext:
    equity: float
    symbol_exposure: float  # current pct exposure for symbol 0..1
    day_realized_pnl_pct: float  # -0.05 for -5%


@dataclass
class RiskDecision:
    approved: bool
    reason: str = ""
    adjusted_qty: Optional[float] = None


class RiskManager:
    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg

    def evaluate(self, req: OrderRequest, quote: Quote, ctx: EquityContext, market_open: bool) -> RiskDecision:
        if not market_open and not self.cfg.allow_after_hours:
            return RiskDecision(False, "Market is closed")

        if ctx.day_realized_pnl_pct <= -abs(self.cfg.daily_loss_cap_pct):
            return RiskDecision(False, f"Daily loss cap reached ({ctx.day_realized_pnl_pct:.2%})")

        ref_price = quote.last or (None if quote.bid is None or quote.ask is None else (quote.bid + quote.ask) / 2.0)
        if ref_price is None:
            return RiskDecision(False, "No reference price available")

        if ref_price < self.cfg.min_price:
            return RiskDecision(False, f"Price {ref_price:.2f} below min {self.cfg.min_price:.2f}")

        if quote.bid is not None and quote.ask is not None and quote.ask > 0:
            spread_pct = (quote.ask - quote.bid) / quote.ask
            if spread_pct > self.cfg.max_spread_pct:
                return RiskDecision(False, f"Spread {spread_pct:.2%} exceeds max {self.cfg.max_spread_pct:.2%}")

        notional = ref_price * req.qty
        if notional > self.cfg.max_notional_per_trade:
            scaled_qty = max(0.0, self.cfg.max_notional_per_trade / ref_price)
            return RiskDecision(False, f"Notional {notional:.2f} exceeds per-trade cap {self.cfg.max_notional_per_trade:.2f}", adjusted_qty=scaled_qty)

        if req.side == "buy":
            next_exposure = ctx.symbol_exposure + (notional / max(ctx.equity, 1e-9))
            if next_exposure > self.cfg.max_symbol_exposure_pct:
                return RiskDecision(False, f"Symbol exposure {next_exposure:.2%} exceeds cap {self.cfg.max_symbol_exposure_pct:.2%}")

        return RiskDecision(True)
