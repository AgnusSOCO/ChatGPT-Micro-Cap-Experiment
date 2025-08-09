from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from execution.executor import TradePlanItem
from risk.manager import RiskConfig
from strategy.screeners import screen_universe


@dataclass
class TradeIdea:
    symbol: str
    side: str
    entry_type: str
    entry: Optional[float]
    stop: Optional[float]
    take_profit: Optional[float]
    confidence: float
    rationale: str


class LLMResearch:
    def __init__(self, model: str, generator: Callable[[str], str], log_path: Optional[Path] = None) -> None:
        self.model = model
        self.generator = generator
        self.log_path = log_path

    def _log_jsonl(self, obj: dict[str, Any]) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(obj) + "\n")

    def build_prompt(self, symbols: list[str], strategy_text: str, cfg: RiskConfig) -> str:
        return (
            "You are an equity trading assistant focused on US micro-cap momentum with strict risk controls.\n"
            "Given a small candidate universe, output up to 2 high-conviction trade ideas in strict JSON only.\n"
            "Respect constraints: avoid illiquid names, prefer tight spreads, use hard stops at entry.\n"
            f"Universe: {', '.join(symbols)}\n"
            "Strategy summary: "
            + strategy_text
            + "\n"
            "Output strict JSON with this schema:\n"
            '{\n'
            '  "ideas": [\n'
            '    {\n'
            '      "symbol": "TICKER",\n'
            '      "side": "buy" | "sell",\n'
            '      "entry_type": "market" | "limit",\n'
            '      "entry": number | null,\n'
            '      "stop": number | null,\n'
            '      "take_profit": number | null,\n'
            '      "confidence": number,\n'
            '      "rationale": "brief reason"\n'
            '    }\n'
            '  ]\n'
            '}\n'
            "Rules:\n"
            "- If side is buy, include a stop <= entry; if entry_type is market, entry can be null.\n"
            "- Do not include any text outside of valid JSON. No markdown, no code fences.\n"
        )

    def parse_ideas(self, content: str) -> list[TradeIdea]:
        s = content.strip()
        if s.startswith("```"):
            s = s.strip("`")
        if not s.startswith("{"):
            l = s.find("{")
            r = s.rfind("}")
            if l != -1 and r != -1 and r > l:
                s = s[l : r + 1]
        data = json.loads(s)
        out: list[TradeIdea] = []
        for it in data.get("ideas", []):
            out.append(
                TradeIdea(
                    symbol=str(it["symbol"]).upper(),
                    side=str(it["side"]).lower(),
                    entry_type=str(it.get("entry_type", "market")).lower(),
                    entry=(None if it.get("entry") is None else float(it.get("entry"))),
                    stop=(None if it.get("stop") is None else float(it.get("stop"))),
                    take_profit=(None if it.get("take_profit") is None else float(it.get("take_profit"))),
                    confidence=float(it.get("confidence", 0.0)),
                    rationale=str(it.get("rationale", "")),
                )
            )
        return out

    def ideas_to_trade_plans(self, ideas: Iterable[TradeIdea]) -> list[TradePlanItem]:
        plans: list[TradePlanItem] = []
        for idea in ideas:
            typ = "limit" if idea.entry_type == "limit" else "market"
            plans.append(
                TradePlanItem(
                    symbol=idea.symbol,
                    side=idea.side,
                    qty=1.0,
                    type=typ,
                    limit_price=idea.entry if typ == "limit" else None,
                    stop_price=idea.stop,
                    client_order_id=None,
                )
            )
        return plans

    def generate_trade_plans(
        self,
        universe: list[str],
        cfg: RiskConfig,
        strategy_text: str,
        max_candidates: int = 15,
    ) -> list[TradePlanItem]:
        filtered = screen_universe(universe, cfg, max_candidates=max_candidates)
        prompt = self.build_prompt(filtered, strategy_text, cfg)
        started = int(time.time())
        try:
            raw = self.generator(prompt)
            ideas = self.parse_ideas(raw)
            self._log_jsonl(
                {
                    "ts": started,
                    "prompt_universe": filtered,
                    "raw": raw,
                    "ideas": [idea.__dict__ for idea in ideas],
                }
            )
            return self.ideas_to_trade_plans(ideas)
        except Exception as e:
            self._log_jsonl(
                {
                    "ts": started,
                    "prompt_universe": filtered,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
            return []


def openai_generator_factory(model: str) -> Callable[[str], str]:
    try:
        from openai import OpenAI
        from openai import APIError, RateLimitError
    except Exception as e:
        raise RuntimeError("openai library is not installed") from e
    client = OpenAI()

    def _gen(prompt: str) -> str:
        delay = 1.0
        last_err = None
        for _ in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a disciplined equities trading assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=800,
                )
                content = resp.choices[0].message.content or ""
                c = content.strip()
                if c.startswith("```"):
                    c = c.strip("`")
                    if "\n" in c:
                        parts = c.split("\n", 1)
                        c = parts[1] if len(parts) > 1 else parts[0]
                return c
            except (RateLimitError, APIError) as e:
                last_err = e
                time.sleep(delay)
                delay *= 2.0
            except Exception as e:
                last_err = e
                break
        raise last_err if last_err else RuntimeError("OpenAI request failed")

    return _gen
