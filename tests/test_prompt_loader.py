"""
tests/test_prompt_loader.py — Tests for atlas_prompts.prompt_loader and intent routing.
No real API calls made.
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from atlas_prompts.prompt_loader import get_agent_prompt, get_domain_prompt
from query_router import (
    INTENT_CASUAL,
    INTENT_COMPANY_RESEARCH,
    INTENT_GENERAL_FINANCE,
    INTENT_MARKET_DEEP_DIVE,
    classify_intent_route,
)


# ── prompt_loader tests ────────────────────────────────────────────────────────

def test_get_agent_prompt_finance_analyst_returns_nonempty():
    result = get_agent_prompt("finance_analyst", "test query")
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_agent_prompt_injects_query():
    result = get_agent_prompt("finance_analyst", "what is the yield curve")
    assert "what is the yield curve" in result


def test_get_agent_prompt_unknown_type_returns_fallback():
    result = get_agent_prompt("nonexistent_agent_xyz", "test")
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_domain_prompt_general_finance_returns_finance_analyst():
    result = get_domain_prompt("GENERAL_FINANCE")
    assert isinstance(result, str)
    assert len(result) > 0
    # Should reference analyst / financial content
    assert any(word in result.lower() for word in ["analyst", "financial", "finance", "investment"])


def test_get_domain_prompt_real_estate_returns_appropriate_prompt():
    result = get_domain_prompt("REAL_ESTATE_SCAN")
    assert isinstance(result, str)
    assert len(result) > 0
    # REAL_ESTATE_SCAN maps to finance_analyst archetype
    assert any(word in result.lower() for word in ["analyst", "financial", "finance", "investment"])


def test_get_domain_prompt_unknown_domain_returns_empty():
    result = get_domain_prompt("DOES_NOT_EXIST_SCAN")
    assert result == ""


# ── intent routing tests ───────────────────────────────────────────────────────

def test_apple_pie_recipe_does_not_route_to_general_finance():
    """Word-boundary fix: 'apple' in 'apple pie recipe' must NOT trigger GENERAL_FINANCE via company check."""
    result = classify_intent_route("apple pie recipe")
    # Should NOT be GENERAL_FINANCE (apple pie is not Apple Inc.)
    assert result != INTENT_GENERAL_FINANCE


def test_apple_revenue_routes_to_general_finance():
    """'Apple' in a finance context routes to COMPANY_RESEARCH or GENERAL_FINANCE."""
    result = classify_intent_route("Tell me about Apple revenue and growth prospects")
    assert result in (INTENT_GENERAL_FINANCE, INTENT_COMPANY_RESEARCH)


def test_hey_how_are_you_routes_to_casual():
    result = classify_intent_route("hey how are you")
    assert result == INTENT_CASUAL


def test_hello_routes_to_casual():
    result = classify_intent_route("hello")
    assert result == INTENT_CASUAL


def test_weather_question_routes_to_casual():
    result = classify_intent_route("weather today")
    assert result == INTENT_CASUAL


def test_nvda_analyze_routes_to_market_deep_dive():
    result = classify_intent_route("Analyze NVDA current setup and trade plan")
    assert result == INTENT_MARKET_DEEP_DIVE


def test_blackrock_aum_routes_to_general_finance():
    result = classify_intent_route("What is BlackRock's current AUM?")
    assert result in (INTENT_GENERAL_FINANCE, INTENT_COMPANY_RESEARCH)


def test_microsoft_routes_to_general_finance():
    result = classify_intent_route("Tell me about Microsoft earnings")
    assert result in (INTENT_GENERAL_FINANCE, INTENT_COMPANY_RESEARCH)


def test_casual_constant_value():
    assert INTENT_CASUAL == "CASUAL"
