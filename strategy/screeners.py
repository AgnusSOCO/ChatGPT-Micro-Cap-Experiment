from __future__ import annotations

from typing import List
import yfinance as yf

from risk.manager import RiskConfig


def screen_universe(universe: List[str], cfg: RiskConfig, max_candidates: int = 15) -> List[str]:
    out: list[tuple[str, float, float]] = []
    for sym in universe:
        try:
            data = yf.Ticker(sym).history(period="1d", interval="1m")
            if data.empty:
                continue
            last_row = data.iloc[-1]
            close = float(last_row["Close"])
            high = float(last_row["High"])
            low = float(last_row["Low"])
            if close < cfg.min_price:
                continue
            spread_proxy = (high - low) / high if high > 0 else 1.0
            if spread_proxy > max(0.10, cfg.max_spread_pct * 2.0):
                continue
            out.append((sym, close, spread_proxy))
        except Exception:
            continue
    out.sort(key=lambda x: (x[2], -x[1]))
    return [s for s, _, _ in out[:max_candidates]]
