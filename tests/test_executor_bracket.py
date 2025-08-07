from pathlib import Path

from execution.executor import Executor, TradePlanItem
from risk.manager import RiskManager, RiskConfig, EquityContext
from exchange.base import OrderRequest, OrderResponse, Quote

class DummyClient:
    def __init__(self):
        self.orders = []
    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, bid=9.99, ask=10.01, last=10.0, timestamp=None)
    def is_market_open(self) -> bool:
        return True
    def place_order(self, req: OrderRequest) -> OrderResponse:
        self.orders.append(req)
        return OrderResponse(id="1", symbol=req.symbol, side=req.side, qty=req.qty, filled_qty=0.0, status="accepted", avg_fill_price=None)
    def get_order(self, oid: str) -> OrderResponse:
        return OrderResponse(id=oid, symbol="AAPL", side="buy", qty=1.0, filled_qty=1.0, status="filled", avg_fill_price=10.0)
    def list_open_orders(self):
        return []
    def cancel_order(self, order_id: str):
        return None

def test_executor_builds_bracket_and_resizes(tmp_path: Path):
    cfg = RiskConfig(max_position_risk_pct=0.02, require_bracket=True, default_stop_loss_pct=0.10)
    rm = RiskManager(cfg)
    client = DummyClient()
    audit = tmp_path / "audit.csv"
    ex = Executor(client=client, risk=rm, audit_log_path=audit)
    ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)
    item = TradePlanItem(symbol="AAPL", side="buy", qty=10.0, type="market", stop_price=None)
    resp = ex.place_and_reconcile(item, ctx)
    assert resp.status.lower() == "filled"
    assert len(client.orders) >= 1
    req0 = client.orders[0]
    assert req0.order_class == "bracket"
    assert req0.stop_price is not None
    assert req0.qty <= 2.0
