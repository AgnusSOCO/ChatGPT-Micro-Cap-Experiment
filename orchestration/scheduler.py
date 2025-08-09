from __future__ import annotations

import time
from typing import Callable


def run_market_hours_loop(
    is_market_open_fn: Callable[[], bool],
    step_fn: Callable[[], None],
    cadence_seconds: int,
    max_minutes: float | None = None,
) -> None:
    start = time.time()
    while True:
        if not is_market_open_fn():
            time.sleep(min(30, cadence_seconds))
            if max_minutes is not None and (time.time() - start) > max_minutes * 60.0:
                return
            continue
        step_fn()
        if max_minutes is not None and (time.time() - start) > max_minutes * 60.0:
            return
        time.sleep(cadence_seconds)
