import math

from risk.manager import RiskManager, RiskConfig, EquityContext
from exchange.base import OrderRequest, Quote

def make_quote(price: float) -> Quote:
    return Quote(symbol="AAPL", bid=price - 0.01, ask=price + 0.01, last=price, timestamp=None)

def test_daily_loss_cap_blocks_entries():
    cfg = RiskConfig(daily_loss_cap_pct=0.06)
    rm = RiskManager(cfg)
    ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=-0.061, open_positions=0, portfolio_heat_pct=0.0)
    req = OrderRequest(symbol="AAPL", side="buy", qty=1.0, stop_price=9.0)
    dec = rm.evaluate(req, make_quote(10.0), ctx, market_open=True)
    assert not dec.approved
    assert "Daily loss cap" in dec.reason

def test_daily_loss_tier_block_buy_only():
    cfg = RiskConfig(daily_loss_tier_block_pct=0.054)
    rm = RiskManager(cfg)
    ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=-0.055, open_positions=0, portfolio_heat_pct=0.0)
    buy = OrderRequest(symbol="AAPL", side="buy", qty=1.0, stop_price=9.0)
    sell = OrderRequest(symbol="AAPL", side="sell", qty=1.0)
    dec_buy = rm.evaluate(buy, make_quote(10.0), ctx, market_open=True)
    dec_sell = rm.evaluate(sell, make_quote(10.0), ctx, market_open=True)
    assert not dec_buy.approved
    assert dec_sell.approved

def test_percent_of_equity_sizing_adjusts_qty():
    cfg = RiskConfig(max_position_risk_pct=0.02)
    rm = RiskManager(cfg)
    ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)
    req = OrderRequest(symbol="AAPL", side="buy", qty=5.0, stop_price=9.0)
    dec = rm.evaluate(req, make_quote(10.0), ctx, market_open=True)
    assert not dec.approved and dec.adjusted_qty is not None
    assert math.isclose(dec.adjusted_qty, 2.0, rel_tol=1e-6)

def test_max_positions_block():
    cfg = RiskConfig(max_positions=5)
    rm = RiskManager(cfg)
    ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=5, portfolio_heat_pct=0.0)
    req = OrderRequest(symbol="AAPL", side="buy", qty=1.0, stop_price=9.0)
    dec = rm.evaluate(req, make_quote(10.0), ctx, market_open=True)
    assert not dec.approved
