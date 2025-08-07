from research.llm_research import LLMResearch
from risk.manager import RiskConfig

def fake_gen_ok(prompt: str) -> str:
    return '{"ideas":[{"symbol":"AAPL","side":"buy","entry_type":"market","entry":null,"stop":170.0,"take_profit":null,"confidence":0.8,"rationale":"Breakout with tight spread"}]}'

def test_llm_parse_and_plan_conversion(tmp_path):
    llm = LLMResearch(model="test", generator=fake_gen_ok, log_path=tmp_path / "log.jsonl")
    cfg = RiskConfig()
    plans = llm.generate_trade_plans(["AAPL","MSFT"], cfg, "test strategy", max_candidates=2)
    assert len(plans) == 1
    p = plans[0]
    assert p.symbol == "AAPL"
    assert p.side == "buy"
    assert p.type == "market"
    assert p.stop_price == 170.0
def test_parse_ideas_handles_code_fences():
    from research.llm_research import LLMResearch
    llm = LLMResearch("gpt-4o-mini", lambda s: s)
    fenced = "```json\n{\n  \"ideas\": [\n    {\"symbol\": \"ABCD\", \"side\": \"buy\", \"entry_type\": \"market\", \"entry\": null, \"stop\": 2.5, \"take_profit\": null, \"confidence\": 0.7, \"rationale\": \"test\"}\n  ]\n}\n```"
    ideas = llm.parse_ideas(fenced)
    assert len(ideas) == 1
    assert ideas[0].symbol == "ABCD"
    assert ideas[0].side == "buy"
