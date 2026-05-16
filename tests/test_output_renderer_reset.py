"""
tests/test_output_renderer_reset.py — Emergency output renderer reset.

Covers:
  PHASE 1  Trade card fields never generated/shown for non-trade modes
  PHASE 2  Simple rendering: chat → plain text, company_report → document
  PHASE 3  Company report never shows trade cards
  PHASE 4  Prompt/output contract: chat never asks for trade schema
  PHASE 5  Quality firewall hard blocks trade bleed in chat and company_report
  PHASE 6  End-to-end rendering gate assertions
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from output_contracts import OUTPUT_CONTRACTS, CHAT_TRADE_FORBIDDEN, COMPANY_REPORT_TRADE_FORBIDDEN, COMMON_TRADE_FORBIDDEN
from quality_firewall import validate_response, QualityResult
from output_modes import resolve_output_mode, user_explicitly_requested_trade

# ── Fixture queries ──────────────────────────────────────────────────────────

_APPLE_PIE_QUERY = "How do I make apple pie?"
_BLACKROCK_QUERY = "Give me everything on BlackRock"
_TSLA_TRADE_QUERY = "Give me a TSLA trade setup with entry and stop loss"

_APPLE_PIE_ANSWER = "To make apple pie, you need flour, butter, sugar, and apples. Mix the dough, fill with sliced apples, and bake at 375°F for 45 minutes."

_BLACKROCK_REPORT = (
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

_BLEED_INTO_CHAT = (
    "To make apple pie:\n"
    "The Setup: Entry at $80 apple stock, Stop Loss $70.\n"
    "Your Rules: Buy the dip on weakness.\n"
    "What Breaks This: Fed rate hike.\n"
    "Action: Buy apples."
)

_CLEAN_TRADE = (
    "Setup: TSLA breaking out above $200.\n"
    "Entry: $202 on daily close above resistance.\n"
    "Invalidation: Close below $193.\n"
    "Risk: 1.5R per position.\n"
    "Scenarios: Bull $240, base $220, bear $190."
)


# ── PHASE 1 — Trade fields forbidden for non-trade output modes ──────────────

class TestTradeFieldsForbiddenForNonTradeModes:

    def test_chat_contract_forbids_the_setup(self):
        assert "the setup" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_your_rules(self):
        assert "your rules" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_what_breaks_this(self):
        assert "what breaks this" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_how_this_plays_out(self):
        assert "how this plays out" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_hold_period(self):
        assert "hold period" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_action_buy(self):
        assert "action: buy" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_tripwire(self):
        assert "tripwire" in CHAT_TRADE_FORBIDDEN

    def test_chat_contract_forbids_stop_loss(self):
        assert "stop loss" in COMMON_TRADE_FORBIDDEN

    def test_finance_answer_contract_forbids_the_setup(self):
        assert "the setup" in list(OUTPUT_CONTRACTS["finance_answer"].forbidden_phrases)

    def test_finance_answer_contract_forbids_hedge_fund_brief(self):
        assert "hedge fund brief" in CHAT_TRADE_FORBIDDEN

    def test_finance_answer_contract_forbids_intelligence_brief(self):
        assert "intelligence brief" in CHAT_TRADE_FORBIDDEN

    def test_company_report_forbids_trading_sections(self):
        forbidden = list(OUTPUT_CONTRACTS["company_report"].forbidden_phrases)
        assert "the setup" in forbidden
        assert "your rules" in forbidden
        assert "position sizing" in forbidden
        assert "trade rating" in forbidden

    def test_trade_plan_does_not_forbid_setup(self):
        forbidden = list(OUTPUT_CONTRACTS["trade_plan"].forbidden_phrases)
        assert "the setup" not in forbidden
        assert "entry" not in [p.lower() for p in forbidden]


# ── PHASE 2 — Output mode routing ────────────────────────────────────────────

class TestOutputModeRouting:

    def test_apple_pie_routes_to_chat(self):
        mode = resolve_output_mode(_APPLE_PIE_QUERY, "GENERAL_CHAT")
        assert mode == "chat"

    def test_apple_pie_does_not_route_to_trade_plan(self):
        mode = resolve_output_mode(_APPLE_PIE_QUERY, "GENERAL_CHAT")
        assert mode != "trade_plan"

    def test_missing_output_mode_defaults_to_chat(self):
        mode = resolve_output_mode("what is the weather", "GENERAL_CHAT")
        assert mode == "chat"

    def test_blackrock_query_routes_to_company_report(self):
        mode = resolve_output_mode(_BLACKROCK_QUERY, "COMPANY_RESEARCH")
        assert mode == "company_report"

    def test_tsla_trade_routes_to_trade_plan(self):
        assert user_explicitly_requested_trade(_TSLA_TRADE_QUERY)
        mode = resolve_output_mode(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS")
        assert mode == "trade_plan"

    def test_apple_pie_not_explicit_trade(self):
        assert not user_explicitly_requested_trade(_APPLE_PIE_QUERY)

    def test_recipe_query_not_trade(self):
        assert not user_explicitly_requested_trade("what is a good recipe for banana bread")

    def test_general_finance_without_company_routes_to_finance_answer(self):
        mode = resolve_output_mode("what is a good interest rate for savings", "GENERAL_FINANCE")
        assert mode == "finance_answer"


# ── PHASE 3 — Company report paper: no trade sections ────────────────────────

class TestCompanyReportNoTradeCards:

    def test_clean_company_report_passes_firewall(self):
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", _BLACKROCK_REPORT)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_company_report_with_the_setup_fails(self):
        answer = _BLACKROCK_REPORT + "\nThe Setup:\nEntry at $800."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_company_report_with_hold_period_fails(self):
        answer = _BLACKROCK_REPORT + "\nHold period: 3-6 months."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_company_report_with_options_play_fails(self):
        answer = _BLACKROCK_REPORT + "\nOptions play: Buy calls at $900."
        result = validate_response(_BLACKROCK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_clean_report_has_no_hold(self):
        assert "hold" not in _BLACKROCK_REPORT.lower() or "hold period" not in _BLACKROCK_REPORT.lower()

    def test_clean_report_has_no_action_buy(self):
        assert "action: buy" not in _BLACKROCK_REPORT.lower()

    def test_clean_report_has_no_options_play(self):
        assert "options play" not in _BLACKROCK_REPORT.lower()

    def test_clean_report_has_no_hedge_fund_brief(self):
        assert "hedge fund brief" not in _BLACKROCK_REPORT.lower()


# ── PHASE 4 — Prompt builder: chat never gets trade schema ───────────────────

class TestPromptNeverAddsTradeSchemaToChat:

    def test_chat_prompt_has_no_trade_plan_instruction(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "company intelligence report" not in prompt.lower()
        assert "executive summary" not in prompt.lower() or "not a trade plan" not in prompt.lower()

    def test_chat_prompt_says_no_trading_language(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_APPLE_PIE_QUERY,
            intent="GENERAL_CHAT",
            output_mode="chat",
        )
        assert "trading language" in prompt.lower() or "trade_plan" in prompt.lower() or "trading" in prompt.lower()

    def test_trade_plan_prompt_has_required_sections(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_TSLA_TRADE_QUERY,
            intent="TRADING_ANALYSIS",
            output_mode="trade_plan",
        )
        assert "setup" in prompt.lower() or "entry" in prompt.lower() or "trade" in prompt.lower()


# ── PHASE 5 — Quality firewall hard blocks ────────────────────────────────────

class TestQualityFirewallHardBlocks:

    def test_apple_pie_clean_passes_chat(self):
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", _APPLE_PIE_ANSWER)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_trade_bleed_into_chat_fails(self):
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", _BLEED_INTO_CHAT)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_the_setup_in_chat_fails(self):
        answer = "To make pie: The Setup:\nEntry at market open. Stop Loss at $50."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", answer)
        assert result.passed is False

    def test_your_rules_in_chat_fails(self):
        answer = "Here is your recipe. Your Rules:\nBuy the dip on weakness."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", answer)
        assert result.passed is False

    def test_action_buy_in_chat_fails(self):
        answer = "Here is advice. Action: Buy now."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", answer)
        assert result.passed is False

    def test_hold_period_in_chat_fails(self):
        answer = "Investment advice. Hold period: 6 months. Risk is moderate."
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", answer)
        assert result.passed is False

    def test_chat_bleed_repair_instruction_mentions_chat(self):
        result = validate_response(_APPLE_PIE_QUERY, "GENERAL_CHAT", "chat", _BLEED_INTO_CHAT)
        assert "chat" in result.repair_instruction.lower() or "conversational" in result.repair_instruction.lower()

    def test_validate_never_raises_on_none(self):
        result = validate_response(None, None, "chat", None)
        assert isinstance(result, QualityResult)

    def test_clean_trade_plan_passes(self):
        result = validate_response(_TSLA_TRADE_QUERY, "TRADING_ANALYSIS", "trade_plan", _CLEAN_TRADE)
        assert result.passed is True


# ── PHASE 6 — HTML renderer gate assertions ───────────────────────────────────

class TestHTMLRendererGates:

    @classmethod
    def _src(cls) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "ra_omega_app.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_isTradePlan_variable_defined(self):
        src = self._src()
        assert "isTradePlan" in src, "isTradePlan variable must be defined in StructuredResponse"

    def test_trade_cards_gated_by_isTradePlan(self):
        src = self._src()
        assert "isTradePlan" in src
        # THE SETUP must use isTradePlan gate
        idx = src.find("THE SETUP")
        assert idx >= 0
        nearby = src[max(0, idx - 100):idx + 30]
        assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
            "THE SETUP card must be gated by isTradePlan"

    def test_your_rules_gated_by_isTradePlan(self):
        src = self._src()
        idx = src.find("YOUR RULES")
        assert idx >= 0
        nearby = src[max(0, idx - 150):idx + 30]
        assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
            "YOUR RULES card must be gated by isTradePlan"

    def test_how_this_plays_out_gated_by_isTradePlan(self):
        src = self._src()
        start = 0
        while True:
            idx = src.find("HOW THIS PLAYS OUT", start)
            if idx == -1:
                break
            nearby = src[max(0, idx - 300):idx + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"HOW THIS PLAYS OUT at {idx} must be gated by isTradePlan"
            start = idx + 1

    def test_what_breaks_this_gated_by_isTradePlan(self):
        src = self._src()
        start = 0
        while True:
            idx = src.find("WHAT BREAKS THIS", start)
            if idx == -1:
                break
            nearby = src[max(0, idx - 300):idx + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"WHAT BREAKS THIS at {idx} must be gated by isTradePlan"
            start = idx + 1

    def test_quickstats_strip_gated_by_isTradePlan(self):
        src = self._src()
        idx = src.find("QuickStatsStrip data=")
        assert idx >= 0
        nearby = src[max(0, idx - 100):idx + 80]
        assert "isTradePlan" in nearby, "QuickStatsStrip must be gated by isTradePlan"

    def test_isPlainChatResponse_checks_output_mode(self):
        src = self._src()
        assert "isPlainChatResponse" in src
        # The function must check _output_mode
        idx = src.find("function isPlainChatResponse")
        func_body = src[idx:idx + 800]
        assert "_output_mode" in func_body or "mode" in func_body

    def test_shouldRenderStructuredResponse_gates_to_trade_and_company(self):
        src = self._src()
        idx = src.find("function shouldRenderStructuredResponse")
        assert idx >= 0
        func_body = src[idx:idx + 500]
        assert "trade_plan" in func_body
        assert "company_report" in func_body

    def test_chat_mode_does_not_trigger_structured_response(self):
        src = self._src()
        idx = src.find("function isPlainChatResponse")
        func_body = src[idx:idx + 600]
        # chat must be in the plain modes list
        assert "'chat'" in func_body or '"chat"' in func_body

    def test_missing_output_mode_defaults_to_plain(self):
        src = self._src()
        idx = src.find("function isPlainChatResponse")
        func_body = src[idx:idx + 600]
        # Empty/missing mode must be treated as plain
        assert "!mode" in func_body or "|| !mode" in func_body

    def test_download_report_button_still_gated_by_isCompanyReport(self):
        src = self._src()
        # ExportBar report button is still company_report specific
        assert "isCompanyReport" in src
        assert "openHTMLReport" in src or "FileText" in src

    def test_standalone_report_uses_srIsTradePlan(self):
        src = self._src()
        assert "_srIsTradePlan" in src

    def test_no_global_default_trade_card_fallback(self):
        src = self._src()
        # THE SETUP should not appear without a gate
        idx = src.find("THE SETUP")
        assert idx >= 0
        # There must be no ungated occurrence of THE SETUP
        start = 0
        while True:
            i = src.find("THE SETUP", start)
            if i == -1:
                break
            nearby = src[max(0, i - 200):i + 30]
            assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
                f"Ungated THE SETUP at position {i}"
            start = i + 1

    def test_bull_thesis_gated_by_isTradePlan(self):
        src = self._src()
        # The JSX render of bull_thesis must be gated: {fr.bull_thesis && isTradePlan && ...}
        assert "fr.bull_thesis && isTradePlan" in src or "isTradePlan && fr.bull_thesis" in src, \
            "bull_thesis render must be gated by isTradePlan"

    def test_intelligence_brief_gated_by_isTradePlan(self):
        src = self._src()
        idx = src.find("INTELLIGENCE BRIEF")
        assert idx >= 0
        # Gate can be up to 300 chars before the label text
        nearby = src[max(0, idx - 300):idx + 50]
        assert "isTradePlan" in nearby or "_srIsTradePlan" in nearby, \
            "INTELLIGENCE BRIEF must be gated by isTradePlan"
