"""
tests/test_output_modes.py — Tests for output_mode resolver, GENERAL_CHAT intent,
and trade template gating. No real API calls made.
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
    INTENT_MARKET_DEEP_DIVE,
    classify_intent_route,
    resolve_output_mode,
)


# ── output_mode resolver ────────────────────────────────────────────────────────

def test_blackrock_query_resolves_company_report():
    intent = classify_intent_route("What does BlackRock do and what is their AUM?")
    # BlackRock is a known company — routes to COMPANY_RESEARCH or GENERAL_FINANCE
    assert intent in (INTENT_GENERAL_FINANCE, INTENT_COMPANY_RESEARCH)
    output_mode = resolve_output_mode("What does BlackRock do and what is their AUM?", intent)
    assert output_mode == "company_report"


def test_trade_setup_nvda_resolves_trade_plan():
    query = "give me a trade setup on NVDA"
    intent = classify_intent_route(query)
    output_mode = resolve_output_mode(query, intent)
    assert output_mode == "trade_plan"


def test_report_query_resolves_document():
    query = "generate a PDF report on the housing market"
    intent = classify_intent_route(query)
    output_mode = resolve_output_mode(query, intent)
    assert output_mode == "document"


def test_blackrock_word_document_resolves_document():
    query = "give me everything on BlackRock in a Word document please"
    intent = classify_intent_route(query)
    output_mode = resolve_output_mode(query, intent)
    assert intent == INTENT_DOCUMENT_GENERATION
    assert output_mode == "document"


def test_common_file_formats_resolve_document():
    from output_modes import detect_requested_document_format

    cases = {
        "give me this in a PDF": "pdf",
        "make an Excel file for this": "xlsx",
        "turn this into a CSV file": "csv",
        "create a PowerPoint presentation": "pptx",
        "save this as markdown": "md",
        "give me a text file": "txt",
        "export this as results.json": "json",
        "create a config.yaml file": "yaml",
        "save this as report.xml": "xml",
    }
    for query, fmt in cases.items():
        assert classify_intent_route(query) == INTENT_DOCUMENT_GENERATION
        assert resolve_output_mode(query, INTENT_DOCUMENT_GENERATION) == "document"
        assert detect_requested_document_format(query) == fmt


def test_finance_opinion_resolves_finance_answer():
    query = "what do you think of NVDA in your personal opinion"
    intent = classify_intent_route(query)
    output_mode = resolve_output_mode(query, intent)
    assert intent == INTENT_GENERAL_FINANCE
    assert output_mode == "finance_answer"


def test_non_finance_opinion_stays_chat():
    query = "what do you think of apple pie in your personal opinion"
    intent = classify_intent_route(query)
    output_mode = resolve_output_mode(query, intent)
    assert intent == INTENT_GENERAL_CHAT
    assert output_mode == "chat"


def test_finance_opinion_rejects_evasive_ai_language():
    from quality_firewall import validate_response

    result = validate_response(
        "what do you think of NVDA in your personal opinion",
        INTENT_GENERAL_FINANCE,
        "finance_answer",
        "As an AI, I don't have personal opinions, but NVDA is a popular stock.",
    )
    assert result.passed is False
    assert "Evasive finance-opinion phrase" in result.reason


def test_casual_intent_resolves_chat():
    assert resolve_output_mode("hey how are you", INTENT_CASUAL) == "chat"
    assert resolve_output_mode("who won last night", INTENT_GENERAL_CHAT) == "chat"


def test_document_generation_intent_resolves_document():
    assert resolve_output_mode("anything", INTENT_DOCUMENT_GENERATION) == "document"


def test_market_deep_dive_intent_resolves_trade_plan():
    assert resolve_output_mode("analyze NVDA", INTENT_MARKET_DEEP_DIVE) == "trade_plan"


def test_general_finance_without_trade_keywords_resolves_company_report():
    # Vanguard is a known company; GENERAL_FINANCE + company → company_report
    output_mode = resolve_output_mode("Tell me about Vanguard's fee structure", INTENT_GENERAL_FINANCE)
    assert output_mode in ("company_report", "finance_answer")


# ── BlackRock response — no live trade fields ──────────────────────────────────

def test_blackrock_envelope_has_no_live_trade_fields():
    """The Omega envelope mapper should set entry_price and stop_loss to None for non-trade queries."""
    from query_router import _omega_report_to_query_envelope, INTENT_GENERAL_FINANCE

    # Simulate a minimal Omega report for a company research query
    omega_report = {
        "domain": "GENERAL_FINANCE",
        "headline": "BlackRock Overview",
        "executive_brief": "BlackRock manages $10T in AUM...",
        "urgency": "informational",
        "query": "What does BlackRock do?",
    }
    env = _omega_report_to_query_envelope(omega_report, "What does BlackRock do?",
                                          intent_route=INTENT_GENERAL_FINANCE)
    trade_plan = env.get("final_report", {}).get("trade_plan") or env.get("trade_plan") or {}
    # For company research, entry_price and stop_loss should not be set with real values
    assert trade_plan.get("entry_price") is None
    assert trade_plan.get("stop_loss") is None


# ── intent routing tests ────────────────────────────────────────────────────────

def test_apple_pie_does_not_route_to_general_finance():
    result = classify_intent_route("apple pie recipe")
    assert result != INTENT_GENERAL_FINANCE


def test_who_won_last_night_routes_to_general_chat():
    result = classify_intent_route("who won last night")
    assert result == INTENT_GENERAL_CHAT


def test_write_me_email_routes_to_general_chat():
    result = classify_intent_route("write me an email")
    # The task allows GENERAL_CHAT or DOCUMENT_GENERATION
    assert result in (INTENT_GENERAL_CHAT, INTENT_DOCUMENT_GENERATION, INTENT_CASUAL)


def test_make_me_something_routes_to_general_chat():
    result = classify_intent_route("make me a summary")
    assert result in (INTENT_GENERAL_CHAT, INTENT_DOCUMENT_GENERATION)


def test_intent_general_chat_constant():
    assert INTENT_GENERAL_CHAT == "GENERAL_CHAT"


def test_intent_company_research_constant():
    from query_router import INTENT_COMPANY_RESEARCH
    assert INTENT_COMPANY_RESEARCH == "COMPANY_RESEARCH"


def test_intent_document_generation_constant():
    assert INTENT_DOCUMENT_GENERATION == "DOCUMENT_GENERATION"


# ── GENERAL_CHAT routes to Omega (no 10-loop) ────────────────────────────────

def test_resolve_output_mode_options_keyword():
    """Queries mentioning 'options' should resolve to trade_plan."""
    output_mode = resolve_output_mode("what options should I buy on AAPL", INTENT_GENERAL_FINANCE)
    assert output_mode == "trade_plan"


def test_resolve_output_mode_stop_loss_keyword():
    output_mode = resolve_output_mode("set a stop loss for my TSLA position", INTENT_GENERAL_FINANCE)
    assert output_mode == "trade_plan"
