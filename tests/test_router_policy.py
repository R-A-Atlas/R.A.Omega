from orchestration.router_policy import decide_route


def test_router_policy_routes_greeting_to_quick_chat():
    d = decide_route("hi")
    assert d.route_band == "quick_chat"
    assert d.tool_budget == 0
    assert "low_information_chat" in d.reasons


def test_router_policy_routes_snapshot():
    d = decide_route("what does the market look like today?")
    assert d.route_band == "market_snapshot"
    assert d.tool_budget == 2


def test_router_policy_routes_broad_markets_question_to_snapshot():
    d = decide_route("can you tell me about the markets")
    assert d.route_band == "market_snapshot"
    assert d.tool_budget == 2


def test_router_policy_routes_focused_analysis():
    d = decide_route("Analyze NVDA support, resistance, options flow, and catalysts")
    assert d.route_band == "focused_analysis"
    assert d.tool_budget == 5


def test_router_policy_routes_explicit_deep_research():
    d = decide_route("Deep research the best 10 stocks for AI infrastructure", forced_mode="deep")
    assert d.route_band == "deep_research"
    assert d.background_ok is True
    assert d.max_steps == 10


def test_router_policy_routes_compliance_escalation():
    d = decide_route("Tell me what I should buy as a guaranteed risk-free trade")
    assert d.route_band == "compliance_escalation"
    assert "advice_or_prohibited_claim_risk" in d.compliance_flags
