"""
tests/test_company_report_quarantine.py — Company report quarantine tests.

PHASE 1: company_report contract sections and forbidden phrases
PHASE 2: prompt builder company_report instruction
PHASE 3: UI card mapper (checks ra_omega_app.html source)
PHASE 4: quality firewall trade bleed detection and repair
PHASE 5: end-to-end routing → output_mode → contract
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from query_router import (
    INTENT_COMPANY_RESEARCH,
    INTENT_GENERAL_FINANCE,
    INTENT_MARKET_DEEP_DIVE,
    classify_intent_route,
    detect_company_name,
    resolve_output_mode,
)
from output_contracts import OUTPUT_CONTRACTS, COMPANY_REPORT_TRADE_FORBIDDEN
from output_modes import (
    OUTPUT_COMPANY_REPORT,
    OUTPUT_TRADE_PLAN,
    user_explicitly_requested_trade,
)
from quality_firewall import validate_response, QualityResult
from prompt_builder import build_synthesis_prompt


_BLACKROCK_QUERY = "give me everything on BlackRock"
_TSLA_TRADE_QUERY = "give me a trade setup for TSLA tomorrow"

# Synthetic company_report with trade bleed
_BLEED_REPORT = (
    "Company Overview: BlackRock is the world's largest asset manager.\n"
    "Business Model: Fee-based asset management.\n"
    "The Setup: Entry at $800, stop loss at $750.\n"
    "Your Rules: Buy the dip.\n"
    "What Breaks This: Fed rate hike.\n"
    "Financial Snapshot: AUM $10 trillion.\n"
    "Key Executives: Larry Fink, CEO.\n"
    "Recent News: Expanding into private credit.\n"
    "Competitive Position: Dominant in ETFs.\n"
    "Risks: Regulatory headwinds.\n"
    "Sources: Bloomberg, SEC filings.\n"
    "Bottom Line: Strong institutional franchise."
)

# Clean company_report without trade bleed
_CLEAN_REPORT = (
    "Executive Summary: BlackRock is the world's largest asset manager.\n"
    "Company Overview: BlackRock is the world's largest asset manager with $10T AUM.\n"
    "What They Do: Provides investment management, risk advisory, and financial planning.\n"
    "Business Model: Fee-based on AUM; institutional and retail segments.\n"
    "Financial Snapshot: Revenue $17.8B, net income $5.5B, AUM $10 trillion.\n"
    "Key Executives: Larry Fink (CEO), Robert Kapito (President).\n"
    "Recent News: Expanding into private credit and alternative assets.\n"
    "Competitive Position: Dominant in ETFs via iShares; largest active manager globally.\n"
    "Key Risks: Regulatory scrutiny, fee compression, macro market risk.\n"
    "Sources: Bloomberg, SEC filings, BlackRock investor relations.\n"
    "Bottom Line: Dominant franchise with secular tailwinds from passive investing growth."
)

# Clean trade plan for TSLA
_CLEAN_TRADE = (
    "Setup: TSLA breaking out of triangle pattern.\n"
    "Entry: $175 on confirmed daily close above resistance.\n"
    "Invalidation: Close below $165 invalidates setup.\n"
    "Risk: Risk 1.5R per trade; position size based on 1% account risk.\n"
    "Scenarios: Bull case $220 in 3 weeks; bear case back to $155."
)


# ── PHASE 1: Contract sections and forbidden phrases ─────────────────────────

class TestCompanyReportContract:
    """company_report contract must have correct required/forbidden sections."""

    def test_required_section_company_overview(self):
        assert "Company Overview" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_what_they_do(self):
        assert "What They Do" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_business_model(self):
        assert "Business Model" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_financial_snapshot(self):
        assert "Financial Snapshot" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_key_executives(self):
        assert "Key Executives" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_risks(self):
        assert "Key Risks" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_executive_summary(self):
        assert "Executive Summary" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_sources(self):
        assert "Sources" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_required_section_bottom_line(self):
        assert "Bottom Line" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_forbidden_the_setup(self):
        assert "the setup" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_your_rules(self):
        assert "your rules" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_what_breaks_this(self):
        assert "what breaks this" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_hold_period(self):
        assert "hold period" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_stop_loss(self):
        assert "stop loss" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_entry_price(self):
        assert "entry price" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_take_profit(self):
        assert "take profit" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_forbidden_execution_rules(self):
        assert "execution rules" in OUTPUT_CONTRACTS["company_report"].forbidden_phrases

    def test_company_report_trade_forbidden_is_superset_of_common(self):
        from output_contracts import COMMON_TRADE_FORBIDDEN
        for phrase in COMMON_TRADE_FORBIDDEN:
            assert phrase in COMPANY_REPORT_TRADE_FORBIDDEN, f"{phrase!r} missing from COMPANY_REPORT_TRADE_FORBIDDEN"

    def test_trade_plan_contract_still_has_required_trade_sections(self):
        contract = OUTPUT_CONTRACTS["trade_plan"]
        assert "Entry" in contract.required_sections
        assert "Risk" in contract.required_sections
        assert "Setup" in contract.required_sections


# ── PHASE 2: Prompt builder ──────────────────────────────────────────────────

class TestPromptBuilderCompanyReport:
    """build_synthesis_prompt() must include company_report-specific instructions."""

    def test_company_report_prompt_says_not_trade_plan(self):
        prompt = build_synthesis_prompt(
            raw_query=_BLACKROCK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            company_name="blackrock",
        )
        assert "not a trade plan" in prompt.lower()

    def test_company_report_prompt_forbids_trade_sections(self):
        prompt = build_synthesis_prompt(
            raw_query=_BLACKROCK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            company_name="blackrock",
        )
        assert "entries" in prompt.lower() or "entry" in prompt.lower()
        assert "execution rules" in prompt.lower()

    def test_company_report_prompt_lists_required_sections(self):
        prompt = build_synthesis_prompt(
            raw_query=_BLACKROCK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            company_name="blackrock",
        )
        assert "company overview" in prompt.lower()
        assert "business model" in prompt.lower()

    def test_trade_plan_prompt_does_not_include_company_report_instruction(self):
        prompt = build_synthesis_prompt(
            raw_query=_TSLA_TRADE_QUERY,
            intent="MARKET_DEEP_DIVE",
            output_mode="trade_plan",
        )
        assert "company intelligence report" not in prompt.lower()

    def test_company_report_prompt_without_company_name_still_has_instruction(self):
        prompt = build_synthesis_prompt(
            raw_query="Tell me about large asset managers",
            intent="GENERAL_FINANCE",
            output_mode="company_report",
        )
        assert "company intelligence report" in prompt.lower()


# ── PHASE 3: UI card mapper (source inspection) ──────────────────────────────

class TestUICardMapper:
    """ra_omega_app.html must gate trade cards for company_report output mode."""

    @classmethod
    def _get_src(cls) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "ra_omega_app.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_setup_card_gated_for_company_report(self):
        src = self._get_src()
        assert "isCompanyReport" in src, "isCompanyReport variable missing from ra_omega_app.html"
        assert "!isCompanyReport" in src, "Trade card gate missing from ra_omega_app.html"

    def test_your_rules_card_gated(self):
        src = self._get_src()
        # Both the React component and the standalone generator must gate YOUR RULES
        # React: "!isCompanyReport" guards "YOUR RULES"
        # Template: "!_srIsCompanyReport" guards "YOUR RULES"
        assert "!isCompanyReport" in src or "!_srIsCompanyReport" in src
        # Verify the guard is specifically near the YOUR RULES label
        assert "YOUR RULES" in src
        # The YOUR RULES string must appear only inside gated blocks
        assert ("!isCompanyReport" in src and "!_srIsCompanyReport" in src), \
            "Both React and template YOUR RULES must be gated (isCompanyReport / _srIsCompanyReport)"

    def test_what_breaks_this_gated_for_company_report(self):
        src = self._get_src()
        # failureModes card must be hidden (not shown) for company_report
        # Implementation: !isCompanyReport gate OR _srIsCompanyReport gate in standalone template
        assert "!isCompanyReport" in src or "_srIsCompanyReport" in src

    def test_quickstats_strip_renamed_for_company_report(self):
        src = self._get_src()
        assert "Research Confidence" in src
        assert "Data Freshness" in src

    def test_output_mode_extracted_from_data(self):
        src = self._get_src()
        assert "data._output_mode" in src

    def test_rating_suppressed_for_company_report(self):
        src = self._get_src()
        assert "!isCompanyReport" in src


# ── PHASE 4: Quality firewall trade bleed detection ──────────────────────────

class TestQualityFirewallCompanyReport:
    """validate_response() must detect and flag trade bleed in company_report."""

    def test_bleed_detected_the_setup(self):
        answer = "Company Overview: ... The Setup: Entry at $100. Stop Loss: $90."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_bleed_detected_your_rules(self):
        answer = "Company Overview: ... Your Rules: Buy the dip, hold period 2 weeks."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_bleed_detected_stop_loss(self):
        answer = "Company Overview: ... Action: Buy. Stop Loss: $90."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_bleed_repair_instruction_references_company_report(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _BLEED_REPORT)
        assert result.passed is False
        assert "company" in result.repair_instruction.lower() or "company_report" in result.repair_instruction.lower()

    def test_clean_company_report_passes(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_REPORT)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_clean_trade_plan_passes(self):
        result = validate_response(_TSLA_TRADE_QUERY, "MARKET_DEEP_DIVE", "trade_plan", _CLEAN_TRADE)
        assert result.passed is True

    def test_validate_response_never_raises(self):
        # Should always return a QualityResult, never raise
        result = validate_response(None, None, "company_report", None)
        assert isinstance(result, QualityResult)

    def test_bleed_detected_is_false_for_trade_plan(self):
        result = validate_response(_TSLA_TRADE_QUERY, "MARKET_DEEP_DIVE", "trade_plan", _CLEAN_TRADE)
        assert result.bleed_detected is False

    def test_quality_result_has_bleed_detected_field(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_REPORT)
        assert hasattr(result, "bleed_detected")


# ── PHASE 5: End-to-end routing → output_mode ────────────────────────────────

class TestEndToEndRouting:
    """BlackRock → company_report; TSLA trade setup → trade_plan."""

    def test_blackrock_routes_to_company_research(self):
        intent = classify_intent_route(_BLACKROCK_QUERY)
        assert intent in (INTENT_COMPANY_RESEARCH, INTENT_GENERAL_FINANCE)

    def test_blackrock_output_mode_is_company_report(self):
        intent = classify_intent_route(_BLACKROCK_QUERY)
        om = resolve_output_mode(_BLACKROCK_QUERY, intent)
        assert om == OUTPUT_COMPANY_REPORT

    def test_blackrock_not_trade_plan(self):
        intent = classify_intent_route(_BLACKROCK_QUERY)
        om = resolve_output_mode(_BLACKROCK_QUERY, intent)
        assert om != OUTPUT_TRADE_PLAN

    def test_blackrock_clean_report_passes_firewall(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_REPORT)
        assert result.passed is True

    def test_blackrock_bleed_report_fails_firewall(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _BLEED_REPORT)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_clean_report_no_the_setup(self):
        assert "the setup" not in _CLEAN_REPORT.lower()

    def test_clean_report_no_action_header(self):
        assert "action: buy" not in _CLEAN_REPORT.lower()
        assert "action: sell" not in _CLEAN_REPORT.lower()

    def test_clean_report_no_hold_period(self):
        assert "hold period" not in _CLEAN_REPORT.lower()

    def test_clean_report_no_size(self):
        assert "position size" not in _CLEAN_REPORT.lower()

    def test_clean_report_no_your_rules(self):
        assert "your rules" not in _CLEAN_REPORT.lower()

    def test_clean_report_has_company_overview(self):
        assert "company overview" in _CLEAN_REPORT.lower()

    def test_clean_report_has_business_model(self):
        assert "business model" in _CLEAN_REPORT.lower()

    def test_clean_report_has_financial_snapshot(self):
        assert "financial snapshot" in _CLEAN_REPORT.lower()

    def test_clean_report_has_risks(self):
        assert "risks" in _CLEAN_REPORT.lower()

    def test_clean_report_has_sources(self):
        assert "sources" in _CLEAN_REPORT.lower()

    def test_tsla_trade_setup_output_mode(self):
        intent = classify_intent_route(_TSLA_TRADE_QUERY)
        om = resolve_output_mode(_TSLA_TRADE_QUERY, intent)
        assert om == OUTPUT_TRADE_PLAN

    def test_tsla_trade_explicit_request_detected(self):
        assert user_explicitly_requested_trade(_TSLA_TRADE_QUERY)

    def test_tsla_clean_trade_plan_passes_firewall(self):
        result = validate_response(_TSLA_TRADE_QUERY, "MARKET_DEEP_DIVE", "trade_plan", _CLEAN_TRADE)
        assert result.passed is True
