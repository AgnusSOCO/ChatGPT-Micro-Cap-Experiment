from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional, Any
from pathlib import Path
import csv
import math

from exchange.base import ExchangeClient, OrderRequest, OrderResponse
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
    def __init__(self, client: ExchangeClient, risk: RiskManager, logger: Optional[Any] = None, audit_log_path: Optional[Path] = None) -> None:
        self.client = client
        self.risk = risk
        self.logger = logger
        self.audit_log_path = audit_log_path

    def _log(self, msg: str) -> None:
        if self.logger:
            self.logger.info(msg)
        else:
            print(msg)

    def _audit(self, req: OrderRequest, resp: OrderResponse) -> None:
        if not self.audit_log_path:
            return
        header = [
            "timestamp",
            "symbol",
            "side",
            "qty",
            "type",
            "time_in_force",
            "client_order_id",
            "status",
            "filled_qty",
            "avg_fill_price",
            "order_id",
            "order_class",
            "stop_price",
            "take_profit_price",
        ]
        row = [
            str(int(time.time())),
            req.symbol,
            req.side,
            req.qty,
            req.type,
            req.time_in_force,
            req.client_order_id or "",
            resp.status,
            resp.filled_qty,
            "" if resp.avg_fill_price is None else resp.avg_fill_price,
            resp.id,
            req.order_class or "",
            "" if req.stop_price is None else req.stop_price,
            "" if req.take_profit_price is None else req.take_profit_price,
        ]
        path = self.audit_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(header)
            w.writerow(row)

    def place_and_reconcile(self, item: TradePlanItem, equity_ctx: EquityContext) -> OrderResponse:
        quote = self.client.get_quote(item.symbol)
        market_open = self.client.is_market_open()

        ref_price = quote.last
        if ref_price is None and quote.bid is not None and quote.ask is not None:
            ref_price = (quote.bid + quote.ask) / 2.0

        stop_price = item.stop_price
        if stop_price is None and self.risk.cfg.require_bracket and item.side.lower().startswith("b") and ref_price is not None:
            stop_price = ref_price * (1.0 - abs(self.risk.cfg.default_stop_loss_pct))

        qty = item.qty
        if stop_price is not None and ref_price is not None and qty > 0:
            per_share_risk = abs(ref_price - stop_price)
            if per_share_risk > 0:
                max_risk_amount = self.risk.cfg.max_position_risk_pct * max(equity_ctx.equity, 1e-9)
                max_qty = max_risk_amount / per_share_risk
                if qty > max_qty:
                    self._log(f"Resizing qty from {qty} to {max_qty} due to risk cap")
                    qty = max_qty

        req = OrderRequest(
            symbol=item.symbol,
            side="buy" if item.side.lower().startswith("b") else "sell",
            qty=qty,
            type=item.type,
            limit_price=item.limit_price,
            stop_price=stop_price,
            time_in_force="day",
            client_order_id=item.client_order_id or f"devin-{int(time.time())}-{uuid.uuid4().hex[:8]}",
            order_class="bracket" if (stop_price is not None and item.side.lower().startswith("b")) else None,
        )

        decision: RiskDecision = self.risk.evaluate(req, quote, equity_ctx, market_open)
        if not decision.approved:
            if decision.adjusted_qty and decision.adjusted_qty > 0:
                self._log(f"Risk adjusted qty from {req.qty} to {decision.adjusted_qty}: {decision.reason}")
                req.qty = decision.adjusted_qty
            else:
                raise RuntimeError(f"Risk rejected order: {decision.reason}")

        self._log(f"Submitting order {req.symbol} {req.side} {req.qty} {req.type}")
        attempt = 0
        backoff = 0.5
        while True:
            try:
                resp = self.client.place_order(req)
                break
            except Exception as e:
                attempt += 1
                if attempt >= 5:
                    raise
                time.sleep(backoff)
                backoff = min(5.0, backoff * 2.0)

        tries = 0
        last = resp
        while tries < 20:
            time.sleep(1.0)
            try:
                o = self.client.get_order(resp.id)
            except Exception:
                tries += 1
                continue
            last = o
            if o.status.lower() in ("filled", "partially_filled", "canceled", "replaced", "rejected"):
                self._log(f"Order status: {o.status} filled_qty={o.filled_qty} avg={o.avg_fill_price}")
                self._audit(req, o)
                return o
            tries += 1
        self._log("Timed out waiting for fill; returning last known order state")
        self._audit(req, last)
        return last
