from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List
from exchange.base import ExchangeClient, OrderRequest, OrderResponse, Quote
from risk.manager import RiskManager, RiskConfig, EquityContext
from execution.executor import Executor, TradePlanItem

@dataclass
class FakeOrder:
    id: str
    status: str
    filled_qty: float
    avg_fill_price: float | None

class FakeClient(ExchangeClient):
    def __init__(self) -> None:
        self.orders: Dict[str, FakeOrder] = {}
        self.last_id = 0
    def get_account(self) -> Dict[str, Any]:
        return {}
    def get_positions(self) -> List[Dict[str, Any]]:
        return []
    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, bid=10.0, ask=10.2, last=10.1, timestamp=None)
    def place_order(self, req: OrderRequest) -> OrderResponse:
        self.last_id += 1
        oid = str(self.last_id)
        self.orders[oid] = FakeOrder(id=oid, status="new", filled_qty=0.0, avg_fill_price=None)
        return OrderResponse(id=oid, symbol=req.symbol, side=req.side, qty=req.qty, filled_qty=0.0, status="new", avg_fill_price=None)
    def get_order(self, order_id: str) -> OrderResponse:
        o = self.orders[order_id]
        if o.status == "new":
            o.status = "filled"
            o.filled_qty = 1.0
            o.avg_fill_price = 10.1
        return OrderResponse(id=order_id, symbol="AAPL", side="buy", qty=1.0, filled_qty=o.filled_qty, status=o.status, avg_fill_price=o.avg_fill_price)
    def list_open_orders(self) -> list[OrderResponse]:
        return []
    def cancel_order(self, order_id: str) -> None:
        pass
    def is_market_open(self) -> bool:
        return True

def test_executor_audits(tmp_path: Path):
    client = FakeClient()
    risk = RiskManager(RiskConfig(max_notional_per_trade=1000.0, min_price=1.0))
    audit = tmp_path / "execution_log.csv"
    ex = Executor(client, risk, audit_log_path=audit)
    ctx = EquityContext(equity=1000.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0)
    item = TradePlanItem(symbol="AAPL", side="buy", qty=1.0, type="market")
    resp = ex.place_and_reconcile(item, ctx)
    assert resp.status.lower() == "filled"
    assert audit.exists()
    text = audit.read_text()
    assert "AAPL" in text and "filled" in text
