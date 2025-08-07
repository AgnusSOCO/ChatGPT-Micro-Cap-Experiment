import math
from exchange.base import OrderRequest, Quote
from risk.manager import RiskManager, RiskConfig, EquityContext

def test_notional_cap_adjusts_qty():
    cfg = RiskConfig(max_notional_per_trade=50.0, min_price=1.0)
    rm = RiskManager(cfg)
    req = OrderRequest(symbol="AAPL", side="buy", qty=100.0)
    quote = Quote(symbol="AAPL", bid=10.0, ask=10.2, last=10.1, timestamp=None)
    ctx = EquityContext(equity=1000.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)
    dec = rm.evaluate(req, quote, ctx, market_open=True)
    assert not dec.approved
    assert dec.adjusted_qty is not None
    assert math.isclose(dec.adjusted_qty, 50.0 / 10.1, rel_tol=1e-6)

def test_exposure_cap_blocks():
    cfg = RiskConfig(max_symbol_exposure_pct=0.1, min_price=1.0, max_notional_per_trade=1e9)
    rm = RiskManager(cfg)
    req = OrderRequest(symbol="AAPL", side="buy", qty=100.0)
    quote = Quote(symbol="AAPL", bid=10.0, ask=10.2, last=10.1, timestamp=None)
    ctx = EquityContext(equity=1000.0, symbol_exposure=0.11, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)
    dec = rm.evaluate(req, quote, ctx, market_open=True)
    assert not dec.approved
    assert dec.adjusted_qty is None
