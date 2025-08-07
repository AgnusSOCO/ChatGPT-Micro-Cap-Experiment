from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional, Dict, Any

from exchange.base import ExchangeClient, OrderRequest, OrderResponse, Quote
from risk.manager import RiskManager, EquityContext, RiskDecision


@dataclass
class TradePlanItem:
    symbol: str
    side: str
    qty: float
    type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None


class Executor:
    def __init__(self, client: ExchangeClient, risk: RiskManager, logger: Optional[Any] = None) -> None:
        self.client = client
        self.risk = risk
        self.logger = logger

    def _log(self, msg: str) -> None:
        if self.logger:
            self.logger.info(msg)
        else:
            print(msg)

    def place_and_reconcile(self, item: TradePlanItem, equity_ctx: EquityContext) -> OrderResponse:
        quote = self.client.get_quote(item.symbol)
        market_open = self.client.is_market_open()
        req = OrderRequest(
            symbol=item.symbol,
            side="buy" if item.side.lower().startswith("b") else "sell",
            qty=item.qty,
            type=item.type,  # type: ignore[arg-type]
            limit_price=item.limit_price,
            stop_price=item.stop_price,
            time_in_force="day",
            client_order_id=item.client_order_id or f"devin-{int(time.time())}-{uuid.uuid4().hex[:8]}",
        )
        decision: RiskDecision = self.risk.evaluate(req, quote, equity_ctx, market_open)
        if not decision.approved:
            if decision.adjusted_qty and decision.adjusted_qty > 0:
                self._log(f"Risk adjusted qty from {req.qty} to {decision.adjusted_qty}: {decision.reason}")
                req.qty = decision.adjusted_qty
            else:
                raise RuntimeError(f"Risk rejected order: {decision.reason}")

        self._log(f"Submitting order {req.symbol} {req.side} {req.qty} {req.type}")
        resp = self.client.place_order(req)
        tries = 0
        while tries < 20:
            time.sleep(1.0)
            o = self.client.get_order(resp.id)
            if o.status.lower() in ("filled", "partially_filled", "canceled", "replaced", "rejected"):
                self._log(f"Order status: {o.status} filled_qty={o.filled_qty} avg={o.avg_fill_price}")
                return o
            tries += 1
        self._log("Timed out waiting for fill; returning last known order state")
        return resp
