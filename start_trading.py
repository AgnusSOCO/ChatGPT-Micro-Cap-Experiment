from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import load_config, AppConfig
from exchange.alpaca_client import AlpacaClient
from risk.manager import RiskManager, RiskConfig, EquityContext
from execution.executor import Executor, TradePlanItem
from trading_script import set_data_dir


def build_executor(cfg: AppConfig) -> Executor:
    risk_cfg = RiskConfig(
        max_notional_per_trade=cfg.max_notional_per_trade,
        max_symbol_exposure_pct=cfg.max_symbol_exposure_pct,
        daily_loss_cap_pct=cfg.daily_loss_cap_pct,
        min_price=cfg.min_price,
        max_spread_pct=cfg.max_spread_pct,
        allow_after_hours=cfg.allow_after_hours,
    )
    risk = RiskManager(risk_cfg)
    if cfg.exchange == "alpaca":
        client = AlpacaClient(base_url=cfg.alpaca_base_url)
    else:
        raise ValueError(f"Unsupported exchange: {cfg.exchange}")
    return Executor(client, risk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default=None, help="dry-run | paper | live")
    parser.add_argument("--plan-file", default=None, help="Path to JSON plan file")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--data-dir", default="Start Your Own", help="Directory for CSV/logs")
    args = parser.parse_args()

    cfg = load_config()
    if args.mode:
        cfg.mode = args.mode  # type: ignore[assignment]

    set_data_dir(Path(args.data_dir))

    if cfg.mode == "dry-run":
        print("Running in dry-run mode; no orders will be placed.")
    else:
        print(f"Running in {cfg.mode} mode")

    plan_items: list[TradePlanItem] = []
    if args.plan_file:
        plan = json.loads(Path(args.plan_file).read_text())
        for leg in plan.get("orders", []):
            plan_items.append(
                TradePlanItem(
                    symbol=leg["symbol"],
                    side=leg["side"],
                    qty=float(leg["qty"]),
                    type=leg.get("type", "market"),
                    limit_price=leg.get("limit_price"),
                    stop_price=leg.get("stop_price"),
                    client_order_id=leg.get("client_order_id"),
                )
            )

    if not plan_items:
        print("No plan provided; exiting.")
        return

    if args.confirm:
        ok = input(f"About to submit {len(plan_items)} orders. Continue? [y/N]: ").strip().lower() == "y"
        if not ok:
            print("Aborted.")
            return

    if cfg.mode == "dry-run":
        for i in plan_items:
            print(f"[DRY-RUN] Would place: {i.symbol} {i.side} {i.qty} {i.type}")
        return

    ex = build_executor(cfg)
    equity_ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0)

    for i in plan_items:
        try:
            resp = ex.place_and_reconcile(i, equity_ctx)
            print(f"Order: {resp.symbol} {resp.side} status={resp.status} filled={resp.filled_qty} avg={resp.avg_fill_price}")
        except Exception as e:
            print(f"Failed to place order for {i.symbol}: {e}")

if __name__ == "__main__":
    main()
