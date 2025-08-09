from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List

from config import load_config, AppConfig
from exchange.alpaca_client import AlpacaClient
from risk.manager import RiskManager, RiskConfig, EquityContext
from execution.executor import Executor, TradePlanItem
from trading_script import set_data_dir
from research.llm_research import LLMResearch, openai_generator_factory
from orchestration.scheduler import run_market_hours_loop


def build_executor(cfg: AppConfig, data_dir: Path) -> Executor:
    risk_cfg = RiskConfig(
        max_notional_per_trade=cfg.max_notional_per_trade,
        max_symbol_exposure_pct=cfg.max_symbol_exposure_pct,
        daily_loss_cap_pct=cfg.daily_loss_cap_pct,
        min_price=cfg.min_price,
        max_spread_pct=cfg.max_spread_pct,
        allow_after_hours=cfg.allow_after_hours,
        max_position_risk_pct=cfg.max_position_risk_pct,
        max_portfolio_heat_pct=cfg.max_portfolio_heat_pct,
        max_positions=cfg.max_positions,
        daily_loss_tier_warn_pct=cfg.daily_loss_tier_warn_pct,
        daily_loss_tier_block_pct=cfg.daily_loss_tier_block_pct,
        require_bracket=cfg.require_bracket,
        default_stop_loss_pct=cfg.default_stop_loss_pct,
    )
    risk = RiskManager(risk_cfg)
    if cfg.exchange == "alpaca":
        client = AlpacaClient(base_url=cfg.alpaca_base_url)
    else:
        raise ValueError(f"Unsupported exchange: {cfg.exchange}")
    audit = data_dir / "execution_log.csv"
    return Executor(client, risk, audit_log_path=audit)


def _load_universe(path: str | None, default_dir: Path) -> List[str]:
    if path is None:
        p = default_dir / "microcap_universe.csv"
    else:
        p = Path(path)
    if not p.exists():
        return ["AAPL", "MSFT", "AMD"]
    syms = [s.strip().upper() for s in p.read_text().splitlines() if s.strip()]
    return syms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default=None, help="dry-run | paper | live")
    parser.add_argument("--plan-file", default=None, help="Path to JSON plan file")
    parser.add_argument("--plan-source", default="file", help="file | llm")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--data-dir", default="Start Your Own", help="Directory for CSV/logs")
    parser.add_argument("--minutes", type=float, default=None, help="Run duration for llm scheduler, minutes")
    parser.add_argument("--cadence", type=int, default=None, help="Override cadence seconds for llm scheduler")
    parser.add_argument("--llm-once", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    if args.mode:
        cfg.mode = args.mode  # type: ignore[assignment]

    data_dir = Path(args.data_dir)
    set_data_dir(data_dir)

    if cfg.mode == "dry-run":
        print("Running in dry-run mode; no orders will be placed.")
    else:
        print(f"Running in {cfg.mode} mode")

    plan_items: list[TradePlanItem] = []

    if args.plan_source == "file":
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
    elif args.plan_source == "llm":
        if not cfg.openai_api_key:
            print("OPENAI_API_KEY not set; cannot run llm plan source.")
            return
        os.environ["OPENAI_API_KEY"] = cfg.openai_api_key
        universe = _load_universe(cfg.llm_universe_file, data_dir)
        gen = openai_generator_factory(cfg.llm_model)
        llm = LLMResearch(cfg.llm_model, gen, log_path=data_dir / "llm_research_log.jsonl")
        ex = None if cfg.mode == "dry-run" else build_executor(cfg, data_dir)
        equity_ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)

        def step_once() -> None:
            nonlocal ex
            items = llm.generate_trade_plans(universe, ex.risk.cfg if ex else RiskManager(RiskConfig()).cfg, cfg.llm_strategy_text)
            if cfg.mode == "dry-run":
                for i in items:
                    print(f"[DRY-RUN][LLM] Would place: {i.symbol} {i.side} {i.qty} {i.type} stop={i.stop_price} limit={i.limit_price}")
                return
            if ex is None:
                ex = build_executor(cfg, data_dir)
            for i in items:
                try:
                    resp = ex.place_and_reconcile(i, equity_ctx)
                    print(f"[LLM] Order: {resp.symbol} {resp.side} status={resp.status} filled={resp.filled_qty} avg={resp.avg_fill_price}")
                except Exception as e:
                    print(f"[LLM] Failed to place order for {i.symbol}: {e}")

        if args.llm_once or args.minutes is None:
            step_once()
            return
        cadence = args.cadence or cfg.llm_cadence_seconds
        ex_client = None if ex is None else ex.client

        def is_open() -> bool:
            if ex_client is None and cfg.exchange == "alpaca":
                tmp = AlpacaClient(base_url=cfg.alpaca_base_url)
                return tmp.is_market_open()
            if ex is not None:
                return ex.client.is_market_open()
            tmp2 = AlpacaClient(base_url=cfg.alpaca_base_url)
            return tmp2.is_market_open()

        run_market_hours_loop(is_open, step_once, cadence_seconds=cadence, max_minutes=args.minutes)
        return
    else:
        print(f"Unknown plan-source: {args.plan_source}")
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

    ex = build_executor(cfg, data_dir)
    equity_ctx = EquityContext(equity=100.0, symbol_exposure=0.0, day_realized_pnl_pct=0.0, open_positions=0, portfolio_heat_pct=0.0)

    for i in plan_items:
        try:
            resp = ex.place_and_reconcile(i, equity_ctx)
            print(f"Order: {resp.symbol} {resp.side} status={resp.status} filled={resp.filled_qty} avg={resp.avg_fill_price}")
        except Exception as e:
            print(f"Failed to place order for {i.symbol}: {e}")

if __name__ == "__main__":
    main()
