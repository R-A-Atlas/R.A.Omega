"""
tests/test_brief_requirements.py — Tests for the ra_omega_claude_code_implementation_brief.md.
Covers: routing matrix, output contracts, quality firewall, progress state, prompt builder.
No real API calls made.
"""
from __future__ import annotations

import os
os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from query_router import (
    INTENT_CASUAL,
    INTENT_COMPANY_RESEARCH,
    INTENT_DOCUMENT_GENERATION,
    INTENT_GENERAL_CHAT,
    INTENT_GENERAL_FINANCE,
    INTENT_HTML_ARTIFACT,
    INTENT_MARKET_DATA,
    INTENT_MARKET_DEEP_DIVE,
    INTENT_TRADING_ANALYSIS,
    classify_intent_route,
    detect_company_name,
    resolve_output_mode,
)
from output_modes import (
    OUTPUT_CHAT,
    OUTPUT_COMPANY_REPORT,
    OUTPUT_DOCUMENT,
    OUTPUT_HTML_ARTIFACT,
    OUTPUT_TRADE_PLAN,
    user_explicitly_requested_trade,
)
from output_contracts import OUTPUT_CONTRACTS, COMMON_TRADE_FORBIDDEN
from quality_firewall import validate_response, QualityResult
from response_judge import judge_response, JudgeResult
from progress_state import JobProgress, ProgressState, TERMINAL_STATES
from prompt_builder import build_synthesis_prompt


# ── Intent constants ───────────────────────────────────────────────────────────

def test_intent_constants_exist():
    assert INTENT_GENERAL_CHAT == "GENERAL_CHAT"
    assert INTENT_COMPANY_RESEARCH == "COMPANY_RESEARCH"
    assert INTENT_DOCUMENT_GENERATION == "DOCUMENT_GENERATION"
    assert INTENT_HTML_ARTIFACT == "HTML_ARTIFACT"
    assert INTENT_MARKET_DATA == "MARKET_DATA"
    assert INTENT_TRADING_ANALYSIS == "TRADING_ANALYSIS"


# ── Company detection ──────────────────────────────────────────────────────────

def test_blackrock_detected_as_company():
    assert detect_company_name("Give me everything on BlackRock") == "blackrock"

def test_blk_alias_detected():
    assert detect_company_name("What is BLK trading at today?") == "blackrock"

def test_apple_pie_not_company():
    assert detect_company_name("how do I make apple pie") is None

def test_apple_inc_detected():
    assert detect_company_name("Tell me about Apple Inc revenue") == "apple"

def test_amazon_rainforest_not_company():
    assert detect_company_name("amazon rainforest deforestation") is None

def test_tesla_coil_not_company():
    assert detect_company_name("how does a tesla coil work") is None

def test_tsla_ticker_detected():
    assert detect_company_name("What do you know about TSLA stock") == "tesla"

def test_vanguard_detected():
    assert detect_company_name("What is the Vanguard fee structure?") == "vanguard"


# ── Routing matrix (matches brief Section 20) ──────────────────────────────────

def test_blackrock_routes_to_company_research():
    intent = classify_intent_route("Give me everything on BlackRock")
    assert intent in (INTENT_COMPANY_RESEARCH, INTENT_GENERAL_FINANCE)

def test_blackrock_output_mode_company_report():
    intent = classify_intent_route("Give me everything on BlackRock")
    om = resolve_output_mode("Give me everything on BlackRock", intent)
    assert om == OUTPUT_COMPANY_REPORT

def test_blackrock_not_trade_plan():
    intent = classify_intent_route("Give me everything on BlackRock")
    om = resolve_output_mode("Give me everything on BlackRock", intent)
    assert om != OUTPUT_TRADE_PLAN

def test_apple_pie_routes_to_general_chat():
    intent = classify_intent_route("how do I make apple pie")
    assert intent in (INTENT_GENERAL_CHAT, INTENT_CASUAL)

def test_apple_pie_output_mode_chat():
    intent = classify_intent_route("how do I make apple pie")
    om = resolve_output_mode("how do I make apple pie", intent)
    assert om == OUTPUT_CHAT

def test_sports_chat_routes_to_general_chat():
    intent = classify_intent_route("who won last night's game?")
    assert intent in (INTENT_GENERAL_CHAT, INTENT_CASUAL)

def test_sports_chat_output_mode_chat():
    q = "who won last night's game?"
    intent = classify_intent_route(q)
    om = resolve_output_mode(q, intent)
    assert om == OUTPUT_CHAT

def test_pdf_report_routes_to_document():
    q = "Make me a PDF report on AI finance companies"
    intent = classify_intent_route(q)
    assert intent == INTENT_DOCUMENT_GENERATION

def test_pdf_report_output_mode_document():
    q = "Make me a PDF report on AI finance companies"
    intent = classify_intent_route(q)
    om = resolve_output_mode(q, intent)
    assert om == OUTPUT_DOCUMENT

def test_html_dashboard_routes_to_html_artifact():
    q = "Create a high-visual HTML dashboard for my finance model"
    intent = classify_intent_route(q)
    assert intent == INTENT_HTML_ARTIFACT

def test_html_dashboard_output_mode_html_artifact():
    q = "Create a high-visual HTML dashboard for my finance model"
    intent = classify_intent_route(q)
    om = resolve_output_mode(q, intent)
    assert om == OUTPUT_HTML_ARTIFACT

def test_tsla_trade_setup_routes_to_trade_plan():
    q = "give me a trade setup for TSLA tomorrow"
    intent = classify_intent_route(q)
    om = resolve_output_mode(q, intent)
    assert om == OUTPUT_TRADE_PLAN

def test_tsla_trade_not_company_research():
    q = "give me a trade setup for TSLA tomorrow"
    intent = classify_intent_route(q)
    assert intent != INTENT_COMPANY_RESEARCH


# ── Output contracts ───────────────────────────────────────────────────────────

def test_company_report_contract_has_required_sections():
    contract = OUTPUT_CONTRACTS["company_report"]
    assert "Overview" in contract.required_sections
    assert "Business Model" in contract.required_sections
    assert "Leadership" in contract.required_sections

def test_company_report_contract_forbids_trade_plan():
    contract = OUTPUT_CONTRACTS["company_report"]
    assert any("trade plan" in p.lower() for p in contract.forbidden_phrases)

def test_trade_plan_contract_has_required_sections():
    contract = OUTPUT_CONTRACTS["trade_plan"]
    assert "Entry" in contract.required_sections
    assert "Risk" in contract.required_sections

def test_chat_contract_forbids_trade_language():
    contract = OUTPUT_CONTRACTS["chat"]
    assert any("trade plan" in p.lower() for p in contract.forbidden_phrases)


# ── Quality firewall ───────────────────────────────────────────────────────────

def test_quality_firewall_blocks_trade_bleed_on_company_report():
    result = validate_response(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        answer="Trade Plan: Entry at $100. Stop loss at $90. Take profit at $120.",
    )
    assert result.passed is False

def test_quality_firewall_passes_clean_company_report():
    result = validate_response(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        answer=(
            "Overview: BlackRock is the world's largest asset manager. "
            "Business Model: They earn management fees on AUM. "
            "Financial Snapshot: $10T AUM. "
            "Leadership: Larry Fink, CEO. "
            "Recent News: Expansion into private credit. "
            "Risks: Regulatory scrutiny. "
            "Competitive Position: Largest in the industry."
        ),
    )
    assert result.passed is True

def test_quality_firewall_passes_trade_plan_with_trade_language():
    result = validate_response(
        raw_query="give me a trade setup for TSLA",
        intent="TRADING_ANALYSIS",
        output_mode="trade_plan",
        answer=(
            "Setup: Bullish breakout above $200 resistance. "
            "Entry at $202 on confirmed breakout. "
            "Invalidation: close below $195. "
            "Risk: 3.5% max loss per position. "
            "Scenarios: bull scenario $240, base case $225, bear case $195."
        ),
    )
    assert result.passed is True

def test_quality_firewall_blocks_trade_bleed_on_chat():
    result = validate_response(
        raw_query="who won last night?",
        intent="GENERAL_CHAT",
        output_mode="chat",
        answer="Trade Plan: Buy at $50. Stop loss at $45.",
    )
    assert result.passed is False

def test_quality_firewall_fails_empty_answer():
    result = validate_response("anything", "GENERAL_CHAT", "chat", "")
    assert result.passed is False


# ── Response judge ─────────────────────────────────────────────────────────────

def test_response_judge_passes_clean_answer():
    result = judge_response(
        raw_query="who won last night?",
        intent="GENERAL_CHAT",
        output_mode="chat",
        answer="The Lakers won 112-105 in a comeback game.",
    )
    assert result.verdict == "PASS"

def test_response_judge_fails_trade_bleed():
    result = judge_response(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        answer="Trade Plan: Entry $100. Stop loss $90. Take profit $120.",
    )
    assert result.verdict == "FAIL"
    assert result.repair_instruction != ""


# ── Progress state ─────────────────────────────────────────────────────────────

def test_progress_state_transitions():
    jp = JobProgress(job_id="test-job-1")
    assert jp.state == ProgressState.QUEUED
    jp.transition(ProgressState.ROUTING, "Routing query")
    assert jp.state == ProgressState.ROUTING
    jp.transition(ProgressState.SYNTHESIZING, "Synthesizing")
    assert jp.state == ProgressState.SYNTHESIZING

def test_progress_state_complete_is_terminal():
    jp = JobProgress(job_id="test-job-2")
    jp.transition(ProgressState.COMPLETE, "Complete")
    assert jp.is_done is True
    assert jp.state in TERMINAL_STATES

def test_progress_state_cannot_leave_terminal():
    jp = JobProgress(job_id="test-job-3")
    jp.transition(ProgressState.COMPLETE, "Complete")
    jp.transition(ProgressState.ROUTING, "Should not happen")
    assert jp.state == ProgressState.COMPLETE

def test_progress_error_is_terminal():
    jp = JobProgress(job_id="test-job-4")
    jp.transition(ProgressState.ERROR, "Something went wrong", error="timeout")
    assert jp.is_done is True
    assert jp.error == "timeout"

def test_progress_emit_callback():
    emitted = []
    jp = JobProgress(job_id="test-job-5", _emit=emitted.append)
    jp.transition(ProgressState.SYNTHESIZING, "Working")
    assert len(emitted) == 1
    assert emitted[0]["state"] == "SYNTHESIZING"

def test_progress_complete_emits_complete_state():
    emitted = []
    jp = JobProgress(job_id="test-job-6", _emit=emitted.append)
    jp.transition(ProgressState.SYNTHESIZING)
    jp.transition(ProgressState.COMPLETE, "Complete")
    assert emitted[-1]["state"] == "COMPLETE"


# ── Prompt builder ─────────────────────────────────────────────────────────────

def test_prompt_builder_includes_query():
    prompt = build_synthesis_prompt(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
    )
    assert "Give me everything on BlackRock" in prompt

def test_prompt_builder_includes_company_instruction():
    prompt = build_synthesis_prompt(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        company_name="blackrock",
    )
    assert "blackrock" in prompt.lower()
    assert "LIVE COMPANY RESEARCH REQUIRED" in prompt

def test_prompt_builder_includes_forbidden_sections():
    prompt = build_synthesis_prompt(
        raw_query="who won last night?",
        intent="GENERAL_CHAT",
        output_mode="chat",
    )
    assert "FORBIDDEN" in prompt

def test_prompt_builder_does_not_include_memory_in_routing():
    # Memory must only appear in the synthesis prompt, not passed into routing
    prompt = build_synthesis_prompt(
        raw_query="anything",
        intent="GENERAL_CHAT",
        output_mode="chat",
        memory_context="User likes tech stocks",
    )
    assert "User likes tech stocks" in prompt  # present in synthesis prompt
    # But routing (classify_intent_route) never receives memory:
    intent = classify_intent_route("anything")
    assert intent in (INTENT_GENERAL_CHAT, INTENT_CASUAL)


# ── user_explicitly_requested_trade ───────────────────────────────────────────

def test_trade_detection_options_buy():
    assert user_explicitly_requested_trade("what options should I buy on AAPL") is True

def test_trade_detection_stop_loss():
    assert user_explicitly_requested_trade("set a stop loss for my TSLA position") is True

def test_trade_detection_negative_casual():
    assert user_explicitly_requested_trade("who won last night") is False

def test_trade_detection_negative_company():
    assert user_explicitly_requested_trade("Give me everything on BlackRock") is False
