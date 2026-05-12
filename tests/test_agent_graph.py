from orchestration.agent_graph import activate_specialists
from orchestration.router_policy import decide_route


def ids_for(query: str, mode: str = "normal") -> list[str]:
    decision = decide_route(query, forced_mode=mode)
    return activate_specialists(query, decision).to_dict()["agent_ids"]


def test_agent_graph_routes_options_trade_cluster():
    ids = ids_for("Analyze NVDA calls expiring next month with options flow and risk")
    assert "D2" in ids
    assert "D3" in ids
    assert "IQ8" in ids


def test_agent_graph_routes_real_estate_cluster():
    ids = ids_for("Should I rent or buy a house in Miami with today's mortgage rates?")
    assert "R1" in ids
    assert "R2" in ids
    assert "R7" in ids
    assert "W7" in ids


def test_agent_graph_routes_crypto_wallet_tax_cluster():
    ids = ids_for("How do I move crypto from Coinbase to my bank and handle taxes?")
    assert "D1" in ids
    assert "L1" in ids


def test_agent_graph_quick_chat_activates_no_agents():
    decision = decide_route("hi")
    activation = activate_specialists("hi", decision).to_dict()
    assert activation["route"] == "conversation"
    assert activation["agent_ids"] == []
    assert activation["max_parallel"] == 0
