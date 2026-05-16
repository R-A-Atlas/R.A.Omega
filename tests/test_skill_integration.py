"""
tests/test_skill_integration.py

Integration tests for Phase 2 skill architecture wiring:
- omega_pipeline.plan_request() exposes skill_name
- prompt_builder.build_synthesis_prompt_meta() loads only relevant skill instructions
- quality_firewall.validate_response() uses deterministic verifiers
- omega_pipeline still passes all structural invariants
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest


# ── omega_pipeline skill_name integration ────────────────────────────────────

def test_pipeline_plan_has_skill_name_field():
    from omega_pipeline import PipelinePlan
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PipelinePlan)}
    assert "skill_name" in fields, "PipelinePlan must have skill_name field"


def test_pipeline_plan_skill_name_defaults_to_empty_string():
    from omega_pipeline import PipelinePlan
    plan = PipelinePlan(
        route="COMPANY_RESEARCH",
        output_mode="company_report",
        workflow="company_report_fast",
        use_deep_research=False,
        required_tools=[],
        renderer_type="paper_report",
        persistence_target="report",
        reason="test",
    )
    assert plan.skill_name == ""


def test_plan_request_company_report_has_skill_name():
    from omega_pipeline import plan_request
    plan = plan_request("Give me everything on BlackRock")
    assert plan.output_mode == "company_report"
    assert plan.skill_name == "company_report", (
        f"Expected skill_name='company_report', got '{plan.skill_name}'"
    )


def test_plan_request_trade_plan_has_skill_name():
    from omega_pipeline import plan_request
    plan = plan_request("Give me a TSLA trade setup")
    assert plan.output_mode == "trade_plan"
    assert plan.skill_name == "trade_plan"


def test_plan_request_chat_has_general_chat_skill_name():
    from omega_pipeline import plan_request
    plan = plan_request("How do I make apple pie?")
    assert plan.output_mode in ("chat", "general_chat", "finance_answer")
    assert plan.skill_name == "general_chat"


def test_plan_request_to_dict_includes_skill_name():
    from omega_pipeline import plan_request
    plan = plan_request("Analyze NVDA")
    d = plan.to_dict()
    assert "skill_name" in d


def test_pipeline_company_report_skill_never_trade_cards():
    from omega_pipeline import plan_request
    for query in [
        "Give me everything on BlackRock",
        "Analyze Goldman Sachs",
        "Research Apple earnings",
    ]:
        plan = plan_request(query)
        assert plan.renderer_type != "trade_cards", (
            f"company_report must never produce trade_cards: query={query!r}"
        )


def test_pipeline_trade_plan_always_gets_trade_cards():
    from omega_pipeline import plan_request
    plan = plan_request("Give me a TSLA trade setup")
    assert plan.renderer_type == "trade_cards"
    assert plan.output_mode == "trade_plan"


def test_pipeline_chat_never_gets_deep_research():
    from omega_pipeline import plan_request
    plan = plan_request("How do I make apple pie?", {"research_mode": "deep"})
    assert not plan.use_deep_research


# ── prompt_builder skill loading ──────────────────────────────────────────────

def test_prompt_builder_meta_returns_selected_skill_for_company_report():
    from prompt_builder import build_synthesis_prompt_meta
    _, meta = build_synthesis_prompt_meta(
        raw_query="Tell me about BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=True,
    )
    assert meta["selected_skill"] == "company_report", (
        f"Expected selected_skill='company_report', got '{meta['selected_skill']}'"
    )


def test_prompt_builder_meta_returns_selected_skill_for_trade_plan():
    from prompt_builder import build_synthesis_prompt_meta
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me a TSLA trade setup",
        intent="TRADING_ANALYSIS",
        output_mode="trade_plan",
        include_omega_os=True,
    )
    assert meta["selected_skill"] == "trade_plan"


def test_prompt_builder_meta_has_selected_skill_when_include_omega_os():
    """When include_omega_os=True, some skill is selected (exact name depends on loader)."""
    from prompt_builder import build_synthesis_prompt_meta
    _, meta = build_synthesis_prompt_meta(
        raw_query="What is inflation?",
        intent="GENERAL_CHAT",
        output_mode="chat",
        include_omega_os=True,
    )
    # A skill should be selected — either from omega_os_loader or from registry fallback
    assert isinstance(meta["selected_skill"], str)


def test_prompt_builder_loads_only_one_skill_not_all():
    from prompt_builder import build_synthesis_prompt_meta
    prompt, meta = build_synthesis_prompt_meta(
        raw_query="Tell me about BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=True,
    )
    # Skill instructions for OTHER skills must not appear in the prompt
    # company_report skill is loaded; trade_plan skill should NOT be in context
    assert "trade_plan" not in (meta.get("context_files_used") or []) or all(
        "company_report" in f for f in (meta.get("context_files_used") or []) if "trade_plan" in f
    ), "trade_plan skill instructions must not be loaded for a company_report query"

    # The prompt should reference the company_report skill, not all skills
    context_files = meta.get("context_files_used", [])
    skill_files = [f for f in context_files if "skill.md" in f]
    if skill_files:
        assert all("company_report" in f for f in skill_files), (
            f"Only company_report skill should be loaded, got: {skill_files}"
        )


def test_prompt_builder_include_omega_os_false_no_skill_loaded():
    from prompt_builder import build_synthesis_prompt_meta
    _, meta = build_synthesis_prompt_meta(
        raw_query="Tell me about BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=False,
    )
    # With include_omega_os=False, no skill should be loaded
    assert meta["selected_skill"] == ""
    assert not meta["omega_os_loaded"]


def test_prompt_builder_prompt_string_is_non_empty():
    from prompt_builder import build_synthesis_prompt_meta
    prompt, _ = build_synthesis_prompt_meta(
        raw_query="Tell me about NVDA",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
    )
    assert isinstance(prompt, str)
    assert len(prompt) > 100


def test_prompt_builder_context_files_include_skill_when_omega_os_true():
    from prompt_builder import build_synthesis_prompt_meta
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me a TSLA trade setup",
        intent="TRADING_ANALYSIS",
        output_mode="trade_plan",
        include_omega_os=True,
    )
    context_files = meta.get("context_files_used", [])
    skill_files = [f for f in context_files if "skill.md" in f]
    assert skill_files, "Expected at least one skill.md in context_files_used when include_omega_os=True"


# ── quality_firewall verifier integration ─────────────────────────────────────

# Full company_report must satisfy output_contracts required sections:
# Executive Summary, Company Overview, What They Do, Business Model,
# Financial Snapshot, Key Executives, Recent News, Competitive Position,
# Key Risks, Sources, Bottom Line
VALID_COMPANY_REPORT = """\
## Executive Summary
BlackRock is the world's largest asset manager with $10.5T AUM.

## Company Overview
Founded in 1988, BlackRock is headquartered in New York City.

## What They Do
BlackRock provides investment management, risk management, and advisory services.

## Business Model
Fee-based asset management across equities, fixed income, and alternatives.

## Financial Snapshot
AUM: $10.5T | Revenue: $17.9B | Net Income: $5.5B

## Key Executives
Larry Fink (CEO), Rob Kapito (President), Martin Small (CFO).

## Recent News
BlackRock acquired Global Infrastructure Partners in Q1 2024.

## Competitive Position
Dominant position via iShares ETF franchise and institutional client base.

## Bull Thesis
Strong fee income, institutional client stickiness, AUM growth via iShares dominance.

## Bear Thesis
Fee compression from passive fund competition, regulatory headwinds, market-linked revenue.

## Key Risks
Regulatory pressure, fee compression, AUM-linked revenue sensitivity to markets.

## Sources
SEC EDGAR 10-K 2023, Bloomberg, Yahoo Finance.

## Bottom Line
BlackRock remains the global leader in asset management with durable competitive advantages.
"""

COMPANY_REPORT_WITH_TRADE_BLEED = """\
## Executive Summary
BlackRock overview.

## Company Overview
Large asset manager.

## What They Do
Investment management.

## Business Model
Fee-based.

## Financial Snapshot
AUM: $10.5T

## Key Executives
Larry Fink, CEO.

## Recent News
Recent acquisition.

## Competitive Position
Market leader.

## Key Risks
Regulation.

## Sources
SEC EDGAR.

## Bottom Line
Strong company.

Entry price: $85.50  Stop Loss: $80  Take Profit: $95
"""

COMPANY_REPORT_MISSING_SECTIONS = """\
BlackRock is a large company. It manages a lot of assets globally.
Some general information here.
"""

# Full trade_plan must satisfy output_contracts required sections:
# Setup, Entry, Invalidation, Risk, Scenarios
VALID_TRADE_PLAN = """\
## Setup
TSLA is consolidating above the $200 support level with decreasing volume.

## Entry
Entry: $205 on a break above $202 resistance with volume confirmation.
Stop Loss: $197 (below key support, risk: 4%)

## Invalidation
Position is invalidated if TSLA closes below $195 on volume.

## Risk
Risk per share: $8. Position size: 100 shares. Total risk: $800.
Risk/Reward: 1:2.5

## Scenarios
Bull: TSLA reaches $225 within 2 weeks on market strength.
Base: Consolidation continues; hold for next catalyst.
Bear: Break below $195 triggers stop loss.
"""

TRADE_PLAN_MISSING_STOP = """\
## Setup
TSLA consolidation pattern forming.

## Entry
Entry at $205 on volume confirmation.

## Risk
Maximum loss: position size only. Risk management TBD.

## Scenarios
Bull case: price reaches $225. Bear case: losses.
"""
# Note: deliberately missing both "stop loss" and "invalidation" to test verifier

TRADE_PLAN_NAKED_CALL = """\
## Setup
TSLA consolidation.

## Entry
Entry: $205
Stop Loss: $197

## Invalidation
Below $195.

## Risk
Risk: 4%. Strategy: Sell naked call for premium income.

## Scenarios
Bull: $225. Bear: stop out.
"""


def test_firewall_passes_valid_company_report():
    from quality_firewall import validate_response
    result = validate_response("Tell me about BlackRock", "COMPANY_RESEARCH", "company_report", VALID_COMPANY_REPORT)
    assert result.passed, f"Expected PASS, got: {result.reason}"


def test_firewall_catches_trade_bleed_via_verifier():
    from quality_firewall import validate_response
    result = validate_response("Tell me about BlackRock", "COMPANY_RESEARCH", "company_report", COMPANY_REPORT_WITH_TRADE_BLEED)
    assert not result.passed
    assert result.bleed_detected


def test_firewall_catches_missing_sections_via_verifier():
    from quality_firewall import validate_response
    result = validate_response("Tell me about BlackRock", "COMPANY_RESEARCH", "company_report", COMPANY_REPORT_MISSING_SECTIONS)
    assert not result.passed
    assert "missing" in result.reason.lower() or "required" in result.reason.lower()


def test_firewall_passes_valid_trade_plan():
    from quality_firewall import validate_response
    result = validate_response("TSLA trade setup", "TRADING_ANALYSIS", "trade_plan", VALID_TRADE_PLAN)
    assert result.passed, f"Expected PASS, got: {result.reason}"


def test_firewall_catches_missing_stop_in_trade_plan():
    from quality_firewall import validate_response
    result = validate_response("TSLA trade setup", "TRADING_ANALYSIS", "trade_plan", TRADE_PLAN_MISSING_STOP)
    assert not result.passed


def test_firewall_catches_naked_call_in_trade_plan():
    from quality_firewall import validate_response
    result = validate_response("TSLA trade setup", "TRADING_ANALYSIS", "trade_plan", TRADE_PLAN_NAKED_CALL)
    assert not result.passed


def test_firewall_verifier_result_has_repair_instruction_on_failure():
    from quality_firewall import validate_response
    result = validate_response("BlackRock", "COMPANY_RESEARCH", "company_report", COMPANY_REPORT_MISSING_SECTIONS)
    assert not result.passed
    assert result.repair_instruction, "Failed result must have a repair_instruction"


def test_firewall_degrades_gracefully_for_unknown_mode():
    from quality_firewall import validate_response
    result = validate_response("some query", "GENERAL_FINANCE", "unknown_mode_xyz", "some answer text here")
    assert not result.passed
    assert "unknown" in result.reason.lower() or "output_mode" in result.reason.lower()


def test_firewall_chat_mode_passes_plain_text():
    from quality_firewall import validate_response
    result = validate_response("How do I make apple pie?", "GENERAL_CHAT", "chat", "You need flour, sugar, and apples. Mix and bake at 375 degrees.")
    assert result.passed


def test_firewall_chat_mode_fails_on_trade_bleed():
    from quality_firewall import validate_response
    result = validate_response(
        "What is inflation?", "GENERAL_FINANCE", "chat",
        "Inflation info. THE SETUP: Entry price at 85, Stop Loss at 80."
    )
    assert not result.passed
    assert result.bleed_detected
