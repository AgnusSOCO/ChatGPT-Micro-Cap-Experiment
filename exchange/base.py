from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, Literal, Dict, Any


Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
TimeInForce = Literal["day", "gtc", "opg", "cls", "ioc", "fok"]


@dataclass
class Quote:
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    timestamp: Optional[str]


@dataclass
class OrderRequest:
    symbol: str
    side: Side
    qty: float
    type: OrderType = "market"
    time_in_force: TimeInForce = "day"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    take_profit_price: Optional[float] = None
    order_class: Optional[str] = None


@dataclass
class OrderResponse:
    id: str
    symbol: str
    side: Side
    qty: float
    filled_qty: float
    status: str
    avg_fill_price: Optional[float]
    submitted_at: Optional[str] = None
    updated_at: Optional[str] = None
    raw: Dict[str, Any] | None = None


class ExchangeClient(Protocol):
    def get_account(self) -> Dict[str, Any]: ...
    def get_positions(self) -> list[Dict[str, Any]]: ...
    def get_quote(self, symbol: str) -> Quote: ...
    def place_order(self, req: OrderRequest) -> OrderResponse: ...
    def get_order(self, order_id: str) -> OrderResponse: ...
    def list_open_orders(self) -> list[OrderResponse]: ...
    def cancel_order(self, order_id: str) -> None: ...
    def is_market_open(self) -> bool: ...
