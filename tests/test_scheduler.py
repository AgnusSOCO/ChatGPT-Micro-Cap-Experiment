from orchestration.scheduler import run_market_hours_loop

def test_scheduler_runs_steps_until_time(monkeypatch):
    calls = {"n": 0}
    def is_open():
        return True
    def step():
        calls["n"] += 1
    run_market_hours_loop(is_open, step, cadence_seconds=1, max_minutes=0.01)
    assert calls["n"] >= 1
