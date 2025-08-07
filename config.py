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
    daily_loss_cap_pct: float = float(os.getenv("RISK_DAILY_LOSS_CAP_PCT", "0.06"))
    min_price: float = float(os.getenv("RISK_MIN_PRICE", "1"))
    max_spread_pct: float = float(os.getenv("RISK_MAX_SPREAD_PCT", "0.03"))
    allow_after_hours: bool = os.getenv("RISK_ALLOW_AFTER_HOURS", "false").lower() == "true"
    max_position_risk_pct: float = float(os.getenv("RISK_MAX_POSITION_RISK_PCT", "0.02"))
    max_portfolio_heat_pct: float = float(os.getenv("RISK_MAX_PORTFOLIO_HEAT_PCT", "0.10"))
    max_positions: int = int(os.getenv("RISK_MAX_POSITIONS", "5"))
    daily_loss_tier_warn_pct: float = float(os.getenv("RISK_DAILY_LOSS_TIER_WARN_PCT", "0.045"))
    daily_loss_tier_block_pct: float = float(os.getenv("RISK_DAILY_LOSS_TIER_BLOCK_PCT", "0.054"))
    require_bracket: bool = os.getenv("RISK_REQUIRE_BRACKET", "true").lower() == "true"
    default_stop_loss_pct: float = float(os.getenv("RISK_DEFAULT_STOP_LOSS_PCT", "0.10"))


def load_config() -> AppConfig:
    mode_str = os.getenv("MODE", "dry-run")
    if mode_str not in ("dry-run", "paper", "live"):
        mode_str = "dry-run"
    exchange = os.getenv("EXCHANGE", "alpaca")
    cfg = AppConfig(mode=cast(Mode, mode_str), exchange=exchange)
    return cfg
