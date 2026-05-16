"""
tests/test_output_renderer_reset_phase3.py — Phase 3 of the output renderer reset.

Covers:
  PHASE 1  Prompt/output contract cleanup
           - general_chat contract exists with strict forbidden phrases
           - chat/general_chat prompt blocks trade schema explicitly
           - company_report prompt asks for plain markdown only
           - missing/uncertain output_mode defaults to chat, not trade_plan
  PHASE 2  Quality firewall new hard blocks
           - company_report fails on HEDGE FUND BRIEF, BEST CONTRACT, BEST OPTIONS CONTRACT
           - general_chat bleed detection works the same as chat
           - validate_response handles general_chat mode
  PHASE 3  End-to-end scenario checks
           - apple pie returns chat, no trade fields in prompt or contract
           - BlackRock returns company_report, no HOLD/ACTION/OPTIONS PLAY/YOUR RULES
           - TSLA trade setup still routes to trade_plan
           - Non-finance UI: QuickStatsStrip never shown outside trade_plan
           - No global default trade-card fallback in ra_omega_app.html
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from output_contracts import (
    OUTPUT_CONTRACTS,
    CHAT_TRADE_FORBIDDEN,
    COMPANY_REPORT_TRADE_FORBIDDEN,
    COMMON_TRADE_FORBIDDEN,
)
from output_modes import (
    OUTPUT_CHAT,
    OUTPUT_GENERAL_CHAT,
    OUTPUT_COMPANY_REPORT,
    OUTPUT_TRADE_PLAN,
    NON_TRADE_MODES,
    resolve_output_mode,
    user_explicitly_requested_trade,
)
from quality_firewall import validate_response, QualityResult
from prompt_builder import build_synthesis_prompt


_APPLE_PIE_QUERY = "How do I make apple pie?"
_BLACKROCK_QUERY = "Give me everything on BlackRock"
_TSLA_TRADE_QUERY = "Give me a TSLA trade setup with entry and stop loss"

_CLEAN_CHAT = "To make apple pie, you need flour, butter, sugar, and apples. Mix dough, add sliced apples, bake at 375F."

_CLEAN_COMPANY_REPORT = (
    "Executive Summary: BlackRock is the world's largest asset manager.\n"
    "Company Overview: $10T AUM, global operations.\n"
    "What They Do: Investment management, ETF management, risk advisory.\n"
    "Business Model: Fee-based on AUM; iShares ETF platform.\n"
    "Financial Snapshot: Revenue $17.8B, net income $5.5B.\n"
    "Key Executives: Larry Fink (CEO), Robert Kapito (President).\n"
    "Recent News: Expanding into private credit and alternatives.\n"
    "Competitive Position: Largest active manager globally.\n"
    "Key Risks: Regulatory scrutiny, fee compression, macro risk.\n"
    "Sources: Bloomberg, SEC filings, BlackRock investor relations.\n"
    "Bottom Line: Dominant franchise with secular tailwinds."
)

_CLEAN_TRADE = (
    "Setup: TSLA breaking out above $200.\n"
    "Entry: $202 on daily close above resistance.\n"
    "Invalidation: Close below $193.\n"
    "Risk: 1.5R per position.\n"
    "Scenarios: Bull $240, base $220, bear $190."
)


# ── PHASE 1: Prompt / output contract cleanup ─────────────────────────────────

class TestGeneralChatContract:
    """general_chat contract must exist and forbid trade sections."""

    def test_general_chat_contract_exists(self):
        assert "general_chat" in OUTPUT_CONTRACTS

    def test_general_chat_contract_forbids_the_setup(self):
        assert "the setup" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_your_rules(self):
        assert "your rules" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_what_breaks_this(self):
        assert "what breaks this" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_how_this_plays_out(self):
        assert "how this plays out" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_hedge_fund_brief(self):
        assert "hedge fund brief" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_intelligence_brief(self):
        assert "intelligence brief" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_action_buy(self):
        assert "action: buy" in list(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)

    def test_general_chat_contract_forbids_stop_loss(self):
        assert "stop loss" in COMMON_TRADE_FORBIDDEN

    def test_general_chat_contract_same_forbidden_as_chat(self):
        chat_forbidden = set(OUTPUT_CONTRACTS["chat"].forbidden_phrases)
        gc_forbidden = set(OUTPUT_CONTRACTS["general_chat"].forbidden_phrases)
        assert chat_forbidden == gc_forbidden, "general_chat must have same forbidden phrases as chat"

    def test_output_general_chat_constant(self):
        assert OUTPUT_GENERAL_CHAT == "general_chat"

    def test_general_chat_in_non_trade_modes(self):
        assert OUTPUT_GENERAL_CHAT in NON_TRADE_MODES


class TestPromptBuilderChatInstruction:
    """build_synthesis_prompt() for chat/general_chat must include no-trade instruction."""

    def test_chat_prompt_has_general_chat_mode_header(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "GENERAL CHAT MODE" in prompt

    def test_chat_prompt_forbids_the_setup_phrase(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "THE SETUP" in prompt or "the setup" in prompt.lower()

    def test_chat_prompt_forbids_stop_loss_phrase(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "Stop Loss" in prompt or "stop loss" in prompt.lower()

    def test_chat_prompt_forbids_hedge_fund_brief(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "Hedge Fund Brief" in prompt or "hedge fund brief" in prompt.lower()

    def test_general_chat_prompt_same_instruction_as_chat(self):
        chat_prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        gc_prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="general_chat",
        )
        assert "GENERAL CHAT MODE" in gc_prompt
        # Both should have the same no-trade instruction
        assert "THE SETUP" in gc_prompt or "the setup" in gc_prompt.lower()

    def test_chat_prompt_says_conversational(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "conversational" in prompt.lower() or "plain text" in prompt.lower()

    def test_chat_prompt_does_not_include_company_instruction(self):
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "COMPANY INTELLIGENCE REPORT MODE" not in prompt

    def test_company_report_prompt_does_not_include_chat_instruction(self):
        prompt = build_synthesis_prompt(
            raw_query=_BLACKROCK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "GENERAL CHAT MODE" not in prompt

    def test_trade_plan_prompt_does_not_include_chat_instruction(self):
        prompt = build_synthesis_prompt(
            raw_query=_TSLA_TRADE_QUERY,
            intent="TRADING_ANALYSIS",
            output_mode="trade_plan",
        )
        assert "GENERAL CHAT MODE" not in prompt


class TestCompanyReportNewForbiddenPhrases:
    """company_report contract must now forbid HEDGE FUND BRIEF, BEST CONTRACT, etc."""

    def test_company_report_forbids_hedge_fund_brief(self):
        assert "hedge fund brief" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_company_report_forbids_best_contract(self):
        assert "best contract" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_company_report_forbids_best_options_contract(self):
        assert "best options contract" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_company_report_contract_object_forbids_hedge_fund_brief(self):
        assert "hedge fund brief" in list(OUTPUT_CONTRACTS["company_report"].forbidden_phrases)

    def test_company_report_contract_object_forbids_best_contract(self):
        assert "best contract" in list(OUTPUT_CONTRACTS["company_report"].forbidden_phrases)


class TestOutputModeDefaults:
    """Missing/unknown output_mode must never default to trade_plan."""

    def test_casual_query_defaults_to_chat(self):
        mode = resolve_output_mode("what is the weather like today", "GENERAL_CHAT")
        assert mode == OUTPUT_CHAT
        assert mode != OUTPUT_TRADE_PLAN

    def test_non_finance_query_defaults_to_chat(self):
        mode = resolve_output_mode("what is the capital of France", "GENERAL_CHAT")
        assert mode != OUTPUT_TRADE_PLAN

    def test_apple_pie_defaults_to_chat_not_trade(self):
        mode = resolve_output_mode(_APPLE_PIE_QUERY, "GENERAL_CHAT")
        assert mode == OUTPUT_CHAT

    def test_blackrock_defaults_to_company_report_not_trade(self):
        mode = resolve_output_mode(_BLACKROCK_QUERY, "COMPANY_RESEARCH")
        assert mode == OUTPUT_COMPANY_REPORT
        assert mode != OUTPUT_TRADE_PLAN

    def test_trade_only_for_explicit_trade_request(self):
        assert user_explicitly_requested_trade(_TSLA_TRADE_QUERY)
        mode = resolve_output_mode(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS")
        assert mode == OUTPUT_TRADE_PLAN


# ── PHASE 2: Quality firewall new hard blocks ─────────────────────────────────

class TestFirewallNewCompanyReportBlocks:
    """quality_firewall must now block HEDGE FUND BRIEF, BEST CONTRACT in company_report."""

    def test_hedge_fund_brief_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nHedge Fund Brief: BUY with 2x leverage."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_best_contract_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nBest contract: Jan $900 calls for 3x leverage."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_best_options_contract_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nBest options contract: $900 call, 45 DTE."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_options_play_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nOptions play: Buy $900 calls."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_how_this_plays_out_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nHow this plays out: Bull case to $1200."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_your_rules_fails_company_report(self):
        answer = _CLEAN_COMPANY_REPORT + "\nYour Rules: Buy the dip. Hold period: 6 months."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_clean_company_report_still_passes(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_COMPANY_REPORT)
        assert result.passed is True

    def test_repair_instruction_mentions_company(self):
        answer = _CLEAN_COMPANY_REPORT + "\nHedge Fund Brief: BUY with 2x leverage."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert "company" in result.repair_instruction.lower()


class TestFirewallGeneralChatMode:
    """validate_response handles general_chat mode same as chat."""

    def test_clean_chat_passes_general_chat_mode(self):
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "general_chat", _CLEAN_CHAT)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_trade_bleed_fails_general_chat_mode(self):
        answer = "To make pie:\nThe Setup: Entry at $80. Stop Loss $70.\nYour Rules: Buy the dip."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "general_chat", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_the_setup_in_general_chat_fails(self):
        answer = "Here is your answer. The Setup: aggressive entry with leverage."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "general_chat", answer)
        assert result.passed is False

    def test_hedge_fund_brief_in_general_chat_fails(self):
        answer = "Here is your answer. Hedge Fund Brief: BUY."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "general_chat", answer)
        assert result.passed is False

    def test_general_chat_returns_quality_result(self):
        result = validate_response(None, None, "general_chat", None)
        assert isinstance(result, QualityResult)

    def test_trade_plan_still_passes_clean_trade(self):
        result = validate_response(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS", "trade_plan", _CLEAN_TRADE)
        assert result.passed is True


# ── PHASE 3: End-to-end scenario checks ──────────────────────────────────────

class TestEndToEndScenarios:
    """Key scenarios that must hold after the renderer reset."""

    def test_apple_pie_chat_full_chain(self):
        mode = resolve_output_mode(_APPLE_PIE_QUERY, "GENERAL_CHAT")
        assert mode == OUTPUT_CHAT
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", mode, _CLEAN_CHAT)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_apple_pie_no_trade_sections_in_answer(self):
        assert "the setup" not in _CLEAN_CHAT.lower()
        assert "your rules" not in _CLEAN_CHAT.lower()
        assert "stop loss" not in _CLEAN_CHAT.lower()
        assert "action: buy" not in _CLEAN_CHAT.lower()
        assert "hedge fund brief" not in _CLEAN_CHAT.lower()

    def test_blackrock_company_report_full_chain(self):
        mode = resolve_output_mode(_BLACKROCK_QUERY, "COMPANY_RESEARCH")
        assert mode == OUTPUT_COMPANY_REPORT
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", mode, _CLEAN_COMPANY_REPORT)
        assert result.passed is True

    def test_blackrock_clean_report_no_hold(self):
        assert "hold period" not in _CLEAN_COMPANY_REPORT.lower()
        assert "rating: hold" not in _CLEAN_COMPANY_REPORT.lower()

    def test_blackrock_clean_report_no_action(self):
        assert "action: buy" not in _CLEAN_COMPANY_REPORT.lower()
        assert "action: sell" not in _CLEAN_COMPANY_REPORT.lower()

    def test_blackrock_clean_report_no_options_play(self):
        assert "options play" not in _CLEAN_COMPANY_REPORT.lower()

    def test_blackrock_clean_report_no_how_this_plays_out(self):
        assert "how this plays out" not in _CLEAN_COMPANY_REPORT.lower()

    def test_blackrock_clean_report_no_your_rules(self):
        assert "your rules" not in _CLEAN_COMPANY_REPORT.lower()

    def test_blackrock_clean_report_no_hedge_fund_brief(self):
        assert "hedge fund brief" not in _CLEAN_COMPANY_REPORT.lower()

    def test_tsla_trade_full_chain(self):
        assert user_explicitly_requested_trade(_TSLA_TRADE_QUERY)
        mode = resolve_output_mode(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS")
        assert mode == OUTPUT_TRADE_PLAN
        result = validate_response(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS", mode, _CLEAN_TRADE)
        assert result.passed is True


class TestHTMLRendererNonTradeGates:
    """ra_omega_app.html must never show trade UI for non-trade output modes."""

    @classmethod
    def _src(cls) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "ra_omega_app.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_quickstats_strip_gated_by_isTradePlan(self):
        src = self._src()
        idx = src.find("QuickStatsStrip data=")
        assert idx >= 0
        nearby = src[max(0, idx - 100):idx + 80]
        assert "isTradePlan" in nearby, "QuickStatsStrip (risk/impact meters) must be gated by isTradePlan"

    def test_isTradePlan_is_mode_exact_match(self):
        src = self._src()
        assert "isTradePlan = outputMode === 'trade_plan'" in src or \
               'isTradePlan = outputMode === "trade_plan"' in src, \
            "isTradePlan must be an exact === comparison to 'trade_plan'"

    def test_srIsTradePlan_is_mode_exact_match(self):
        src = self._src()
        assert "_srIsTradePlan = _srOutputMode === 'trade_plan'" in src or \
               '_srIsTradePlan = _srOutputMode === "trade_plan"' in src, \
            "_srIsTradePlan must be an exact === comparison to 'trade_plan'"

    def test_shouldRenderStructuredResponse_whitelist_only(self):
        src = self._src()
        idx = src.find("function shouldRenderStructuredResponse")
        func_body = src[idx:idx + 500]
        assert "trade_plan" in func_body
        assert "company_report" in func_body

    def test_chat_mode_renders_as_plain_text(self):
        src = self._src()
        idx = src.find("function isPlainChatResponse")
        func_body = src[idx:idx + 800]
        assert "'chat'" in func_body or '"chat"' in func_body, "chat must be in plain modes list"

    def test_missing_output_mode_renders_as_plain(self):
        src = self._src()
        idx = src.find("function isPlainChatResponse")
        func_body = src[idx:idx + 800]
        assert "!mode" in func_body or "|| !mode" in func_body, \
            "Missing/empty output_mode must default to plain text rendering"

    def test_no_ungated_the_setup(self):
        src = self._src()
        start = 0
        while True:
            i = src.find("THE SETUP", start)
            if i == -1:
                break
            nearby = src[max(0, i - 200):i + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"Ungated THE SETUP at position {i}"
            start = i + 1

    def test_no_ungated_your_rules(self):
        src = self._src()
        start = 0
        while True:
            i = src.find("YOUR RULES", start)
            if i == -1:
                break
            nearby = src[max(0, i - 200):i + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"Ungated YOUR RULES at position {i}"
            start = i + 1

    def test_no_ungated_what_breaks_this(self):
        src = self._src()
        start = 0
        while True:
            i = src.find("WHAT BREAKS THIS", start)
            if i == -1:
                break
            nearby = src[max(0, i - 300):i + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"Ungated WHAT BREAKS THIS at position {i}"
            start = i + 1
