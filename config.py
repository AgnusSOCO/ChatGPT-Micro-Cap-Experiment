from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

from dotenv import load_dotenv

load_dotenv()


Mode = Literal["dry-run", "paper", "live"]


@dataclass
class AppConfig:
    mode: Mode = "dry-run"
    exchange: str = "alpaca"
    alpaca_base_url: str | None = os.getenv("ALPACA_BASE_URL")
    max_notional_per_trade: float = float(os.getenv("RISK_MAX_NOTIONAL_PER_TRADE", "25"))
    max_symbol_exposure_pct: float = float(os.getenv("RISK_MAX_SYMBOL_EXPOSURE_PCT", "0.4"))
    daily_loss_cap_pct: float = float(os.getenv("RISK_DAILY_LOSS_CAP_PCT", "0.1"))
    min_price: float = float(os.getenv("RISK_MIN_PRICE", "1"))
    max_spread_pct: float = float(os.getenv("RISK_MAX_SPREAD_PCT", "0.03"))
    allow_after_hours: bool = os.getenv("RISK_ALLOW_AFTER_HOURS", "false").lower() == "true"


def load_config() -> AppConfig:
    mode_str = os.getenv("MODE", "dry-run")
    if mode_str not in ("dry-run", "paper", "live"):
        mode_str = "dry-run"
    exchange = os.getenv("EXCHANGE", "alpaca")
    cfg = AppConfig(mode=cast(Mode, mode_str), exchange=exchange)
    return cfg
