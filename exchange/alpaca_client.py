from __future__ import annotations

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .base import ExchangeClient, OrderRequest, OrderResponse, Quote

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest, StopOrderRequest, StopLimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce as AlpacaTif, OrderType as AlpacaOrderType
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
except Exception:
    TradingClient = None  # type: ignore[assignment]
    StockHistoricalDataClient = None  # type: ignore[assignment]
    GetOrdersRequest = None  # type: ignore[assignment]
    LimitOrderRequest = None  # type: ignore[assignment]
    MarketOrderRequest = None  # type: ignore[assignment]
    StopOrderRequest = None  # type: ignore[assignment]
    StopLimitOrderRequest = None  # type: ignore[assignment]
    OrderSide = None  # type: ignore[assignment]
    AlpacaTif = None  # type: ignore[assignment]
    AlpacaOrderType = None  # type: ignore[assignment]
    StockLatestQuoteRequest = None  # type: ignore[assignment]


@dataclass
class _Clients:
    trading: Any
    data: Any


class AlpacaClient(ExchangeClient):
    def __init__(self, api_key: str | None = None, api_secret: str | None = None, base_url: str | None = None) -> None:
        key = api_key or os.getenv("ALPACA_API_KEY_ID", "")
        secret = api_secret or os.getenv("ALPACA_API_SECRET_KEY", "")
        use_paper = True
        if base_url:
            use_paper = "paper" in base_url.lower()
        if TradingClient is None:
            raise RuntimeError("alpaca-py is not installed. Please add it to requirements and install.")
        self._clients = _Clients(
            trading=TradingClient(key, secret, paper=use_paper),
            data=StockHistoricalDataClient(key, secret),
        )

    def get_account(self) -> Dict[str, Any]:
        acct = self._clients.trading.get_account()
        return dict(acct)

    def get_positions(self) -> List[Dict[str, Any]]:
        positions = self._clients.trading.get_all_positions()
        return [dict(p) for p in positions]

    def get_quote(self, symbol: str) -> Quote:
        if StockLatestQuoteRequest is None:
            return Quote(symbol=symbol, bid=None, ask=None, last=None, timestamp=None)
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        resp = self._clients.data.get_stock_latest_quote(req)
        q = resp[symbol]
        bid = float(q.bid_price) if q and q.bid_price is not None else None
        ask = float(q.ask_price) if q and q.ask_price is not None else None
        last = None
        ts = str(q.timestamp) if q and q.timestamp is not None else None
        return Quote(symbol=symbol, bid=bid, ask=ask, last=last, timestamp=ts)

    def place_order(self, req: OrderRequest) -> OrderResponse:
        alp_side = OrderSide.BUY if req.side == "buy" else OrderSide.SELL
        tif_map = {
            "day": AlpacaTif.DAY,
            "gtc": AlpacaTif.GTC,
            "opg": AlpacaTif.OPG,
            "cls": AlpacaTif.CLS,
            "ioc": AlpacaTif.IOC,
            "fok": AlpacaTif.FOK,
        }
        tif = tif_map.get(req.time_in_force, AlpacaTif.DAY)
        qty = req.qty

        if req.type == "market":
            order_req = MarketOrderRequest(symbol=req.symbol, qty=qty, side=alp_side, time_in_force=tif, client_order_id=req.client_order_id)
        elif req.type == "limit":
            if req.limit_price is None:
                raise ValueError("limit_price required for limit orders")
            order_req = LimitOrderRequest(symbol=req.symbol, qty=qty, side=alp_side, time_in_force=tif, limit_price=req.limit_price, client_order_id=req.client_order_id)
        elif req.type == "stop":
            if req.stop_price is None:
                raise ValueError("stop_price required for stop orders")
            order_req = StopOrderRequest(symbol=req.symbol, qty=qty, side=alp_side, time_in_force=tif, stop_price=req.stop_price, client_order_id=req.client_order_id)
        elif req.type == "stop_limit":
            if req.stop_price is None or req.limit_price is None:
                raise ValueError("stop_price and limit_price required for stop_limit orders")
            order_req = StopLimitOrderRequest(symbol=req.symbol, qty=qty, side=alp_side, time_in_force=tif, limit_price=req.limit_price, stop_price=req.stop_price, client_order_id=req.client_order_id)
        else:
            raise ValueError(f"Unsupported order type: {req.type}")

        order = self._clients.trading.submit_order(order_req)
        return OrderResponse(
            id=str(order.id),
            symbol=str(order.symbol),
            side=req.side,
            qty=float(order.qty),
            filled_qty=float(order.filled_qty or 0),
            status=str(order.status),
            avg_fill_price=float(order.filled_avg_price) if order.filled_avg_price is not None else None,
            submitted_at=str(order.submitted_at) if order.submitted_at else None,
            updated_at=str(order.updated_at) if order.updated_at else None,
            raw=dict(order),
        )

    def get_order(self, order_id: str) -> OrderResponse:
        order = self._clients.trading.get_order_by_id(order_id)
        return OrderResponse(
            id=str(order.id),
            symbol=str(order.symbol),
            side="buy" if str(order.side).lower() == "buy" else "sell",
            qty=float(order.qty),
            filled_qty=float(order.filled_qty or 0),
            status=str(order.status),
            avg_fill_price=float(order.filled_avg_price) if order.filled_avg_price is not None else None,
            submitted_at=str(order.submitted_at) if order.submitted_at else None,
            updated_at=str(order.updated_at) if order.updated_at else None,
            raw=dict(order),
        )

    def list_open_orders(self) -> list[OrderResponse]:
        orders = self._clients.trading.get_orders(GetOrdersRequest(status="open"))
        out: list[OrderResponse] = []
        for o in orders:
            out.append(OrderResponse(
                id=str(o.id),
                symbol=str(o.symbol),
                side="buy" if str(o.side).lower() == "buy" else "sell",
                qty=float(o.qty),
                filled_qty=float(o.filled_qty or 0),
                status=str(o.status),
                avg_fill_price=float(o.filled_avg_price) if o.filled_avg_price is not None else None,
                submitted_at=str(o.submitted_at) if o.submitted_at else None,
                updated_at=str(o.updated_at) if o.updated_at else None,
                raw=dict(o),
            ))
        return out

    def cancel_order(self, order_id: str) -> None:
        self._clients.trading.cancel_order_by_id(order_id)

    def is_market_open(self) -> bool:
        clock = self._clients.trading.get_clock()
        return bool(clock.is_open)
