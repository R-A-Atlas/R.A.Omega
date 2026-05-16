"""
tests/test_company_report_paper_renderer.py — Company report paper renderer.

Covers:
  PHASE 1  Paper contract required/forbidden sections
  PHASE 3  UI renderer — trade cards hidden, Download Report shown
  PHASE 4  Quality firewall bleed detection + repair_response()
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from output_contracts import OUTPUT_CONTRACTS, COMPANY_REPORT_TRADE_FORBIDDEN
from quality_firewall import validate_response, repair_response, QualityResult

_BLK_QUERY = "give me everything on BlackRock"
_TSLA_QUERY = "give me a trade setup for TSLA tomorrow"

# Comprehensive clean company report (all 11 required sections present)
_CLEAN_REPORT = (
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

# Report with trade bleed
_BLEED_REPORT = (
    "Company Overview: BlackRock is big.\n"
    "The Setup: Entry at $800, stop loss at $750.\n"
    "Your Rules: Buy the dip on weakness.\n"
    "What Breaks This: Fed rate hike.\n"
    "Sources: Bloomberg.\n"
    "Bottom Line: Strong."
)

# Clean trade plan for TSLA
_CLEAN_TRADE = (
    "Setup: TSLA breaking out above $200.\n"
    "Entry: $202 on daily close above resistance.\n"
    "Invalidation: Close below $193.\n"
    "Risk: 1.5R per position.\n"
    "Scenarios: Bull $240, base $220, bear $190."
)


# ── PHASE 1 — Paper contract ─────────────────────────────────────────────────

class TestCompanyReportPaperContract:

    def test_executive_summary_required(self):
        assert "Executive Summary" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_company_overview_required(self):
        assert "Company Overview" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_business_model_required(self):
        assert "Business Model" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_financial_snapshot_required(self):
        assert "Financial Snapshot" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_key_risks_required(self):
        assert "Key Risks" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_sources_required(self):
        assert "Sources" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_bottom_line_required(self):
        assert "Bottom Line" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_the_setup_forbidden(self):
        assert "the setup" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_your_rules_forbidden(self):
        assert "your rules" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_what_breaks_this_forbidden(self):
        assert "what breaks this" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_how_this_plays_out_forbidden(self):
        assert "how this plays out" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_hold_period_forbidden(self):
        assert "hold period" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_action_buy_forbidden(self):
        assert "action: buy" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_action_sell_forbidden(self):
        assert "action: sell" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_stop_loss_forbidden(self):
        from output_contracts import COMMON_TRADE_FORBIDDEN
        assert "stop loss" in COMMON_TRADE_FORBIDDEN

    def test_take_profit_forbidden(self):
        from output_contracts import COMMON_TRADE_FORBIDDEN
        assert "take profit" in COMMON_TRADE_FORBIDDEN

    def test_execution_rules_forbidden(self):
        from output_contracts import COMMON_TRADE_FORBIDDEN
        assert "execution rules" in COMMON_TRADE_FORBIDDEN

    def test_tripwire_forbidden(self):
        assert "tripwire" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_position_sizing_forbidden(self):
        assert "position sizing" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_trade_rating_forbidden(self):
        assert "trade rating" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_trade_plan_contract_still_requires_trade_sections(self):
        contract = OUTPUT_CONTRACTS["trade_plan"]
        assert "Setup" in contract.required_sections
        assert "Entry" in contract.required_sections
        assert "Risk" in contract.required_sections


# ── PHASE 2 — Prompt builder ─────────────────────────────────────────────────

class TestPromptBuilderPaperReport:

    def test_prompt_says_clean_markdown(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_BLK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "clean markdown" in prompt.lower()

    def test_prompt_forbids_trade_plan(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_BLK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "not a trade plan" in prompt.lower()

    def test_prompt_forbids_tripwires(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_BLK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "tripwire" in prompt.lower()

    def test_prompt_forbids_position_sizing(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_BLK_QUERY,
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "position sizing" in prompt.lower() or "position sizing" in prompt.lower()

    def test_trade_plan_prompt_no_company_report_instruction(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query=_TSLA_QUERY,
            intent="MARKET_DEEP_DIVE",
            output_mode="trade_plan",
        )
        assert "company intelligence report" not in prompt.lower()


# ── PHASE 3 — UI renderer ────────────────────────────────────────────────────

class TestUICompanyReportPaperRenderer:

    @classmethod
    def _src(cls) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "ra_omega_app.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_scenarios_card_gated_for_company_report(self):
        src = self._src()
        # HOW THIS PLAYS OUT must only render when !isCompanyReport
        assert "!isCompanyReport" in src
        # Check that every occurrence of HOW THIS PLAYS OUT is gated
        # (JSX uses isCompanyReport; standalone template uses _srIsCompanyReport)
        start = 0
        while True:
            idx = src.find("HOW THIS PLAYS OUT", start)
            if idx == -1:
                break
            nearby = src[max(0, idx - 300):idx + 50]
            assert "isCompanyReport" in nearby or "_srIsCompanyReport" in nearby, \
                f"HOW THIS PLAYS OUT at {idx} must be gated by isCompanyReport"
            start = idx + 1

    def test_failure_modes_card_gated_for_company_report(self):
        src = self._src()
        # WHAT BREAKS THIS must only render when !isCompanyReport
        # Check that every occurrence is gated
        start = 0
        while True:
            idx = src.find("WHAT BREAKS THIS", start)
            if idx == -1:
                break
            nearby = src[max(0, idx - 400):idx + 50]
            assert "isCompanyReport" in nearby or "_srIsCompanyReport" in nearby, \
                f"WHAT BREAKS THIS at {idx} must be gated by isCompanyReport"
            start = idx + 1

    def test_quickstats_strip_gated_for_company_report(self):
        src = self._src()
        # QuickStatsStrip must be conditionally rendered
        assert "!isCompanyReport" in src
        # Check that QuickStatsStrip is conditional
        idx = src.find("QuickStatsStrip data=")
        nearby = src[max(0, idx - 100):idx + 80]
        assert "isCompanyReport" in nearby, \
            "QuickStatsStrip must be gated by isCompanyReport (hidden for company_report)"

    def test_the_setup_gated_for_company_report(self):
        src = self._src()
        assert "THE SETUP" in src
        # Check that every THE SETUP occurrence is gated
        start = 0
        while True:
            idx = src.find("THE SETUP", start)
            if idx == -1:
                break
            nearby = src[max(0, idx - 200):idx + 50]
            assert "isCompanyReport" in nearby or "_srIsCompanyReport" in nearby, \
                f"THE SETUP at {idx} must be gated by isCompanyReport"
            start = idx + 1

    def test_your_rules_gated_for_company_report(self):
        src = self._src()
        assert "YOUR RULES" in src
        assert "!isCompanyReport" in src

    def test_download_report_button_for_company_report(self):
        src = self._src()
        # ExportBar must show a download/report button gated by isCompanyReport
        assert "isCompanyReport" in src
        assert "openHTMLReport" in src or "FileText" in src, \
            "Must show a Download/Report button for company_report"

    def test_output_mode_extracted_from_data(self):
        src = self._src()
        assert "data._output_mode" in src

    def test_standalone_report_scenarios_gated(self):
        src = self._src()
        # In generateStandaloneReport, scenarios must be gated
        assert "_srIsCompanyReport" in src
        idx = src.find("HOW THIS PLAYS OUT")
        # Find last occurrence (standalone report version)
        all_idxs = []
        start = 0
        while True:
            i = src.find("HOW THIS PLAYS OUT", start)
            if i == -1:
                break
            all_idxs.append(i)
            start = i + 1
        for idx in all_idxs:
            nearby = src[max(0, idx - 300):idx + 50]
            assert "_srIsCompanyReport" in nearby or "!isCompanyReport" in nearby, \
                f"HOW THIS PLAYS OUT at position {idx} is not gated by company_report check"


# ── PHASE 4 — Quality firewall bleed + repair ────────────────────────────────

class TestQualityFirewallBleedAndRepair:

    def test_clean_report_passes(self):
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_REPORT)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_the_setup_bleed_detected(self):
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", _BLEED_REPORT)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_your_rules_bleed_detected(self):
        answer = "Company Overview: ... Your Rules: Buy the dip. Sources: x. Bottom Line: y."
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False
        assert result.bleed_detected is True

    def test_stop_loss_bleed_detected(self):
        answer = "Company Overview: Big. Stop Loss: $100. Sources: x. Bottom Line: y."
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_position_sizing_bleed_detected(self):
        answer = "Company Overview: Big. Position sizing: 2% max. Sources: x. Bottom Line: y."
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_trade_rating_bleed_detected(self):
        answer = "Company Overview: Big. Trade rating: BUY. Sources: x. Bottom Line: y."
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_how_this_plays_out_bleed_detected(self):
        answer = "Company Overview: Big. How This Plays Out: Bullish. Sources: x. Bottom Line: y."
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_bleed_repair_instruction_mentions_company_report(self):
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", _BLEED_REPORT)
        assert "company" in result.repair_instruction.lower()

    def test_clean_trade_plan_passes(self):
        result = validate_response(_TSLA_QUERY, "MARKET_DEEP_DIVE", "trade_plan", _CLEAN_TRADE)
        assert result.passed is True
        assert result.bleed_detected is False

    def test_quality_result_has_bleed_field(self):
        result = validate_response(_BLK_QUERY, "COMPANY_RESEARCH", "company_report", _CLEAN_REPORT)
        assert hasattr(result, "bleed_detected")

    def test_validate_response_never_raises(self):
        result = validate_response(None, None, "company_report", None)
        assert isinstance(result, QualityResult)


class TestRepairResponse:

    def test_repair_response_exists(self):
        from quality_firewall import repair_response
        assert callable(repair_response)

    def test_repair_removes_the_setup_section(self):
        bleed = "Company Overview: Big.\nThe Setup:\nEntry at $800. Stop at $750.\nBottom Line: Strong."
        repaired, ok = repair_response(bleed, "company_report")
        assert ok is True
        assert "the setup" not in repaired.lower()

    def test_repair_removes_your_rules_section(self):
        bleed = "Company Overview: Big.\nYour Rules:\nBuy the dip.\nBottom Line: Strong."
        repaired, ok = repair_response(bleed, "company_report")
        assert ok is True
        assert "your rules" not in repaired.lower()

    def test_repair_preserves_company_overview(self):
        bleed = "Company Overview: Big corp.\nThe Setup:\nEntry at $800.\nBottom Line: Strong."
        repaired, ok = repair_response(bleed, "company_report")
        assert "company overview" in repaired.lower()

    def test_repair_returns_original_for_non_company_report(self):
        text = "Entry at $200. Stop Loss: $180."
        repaired, ok = repair_response(text, "trade_plan")
        assert ok is False
        assert repaired == text

    def test_repair_returns_tuple(self):
        result = repair_response("Some text", "company_report")
        assert isinstance(result, tuple) and len(result) == 2

    def test_repair_never_raises_on_empty(self):
        repaired, ok = repair_response("", "company_report")
        assert isinstance(repaired, str)
        assert ok is False

    def test_repair_never_raises_on_none(self):
        repaired, ok = repair_response(None, "company_report")  # type: ignore[arg-type]
        assert isinstance(repaired, str)

    def test_repair_one_pass_max_source(self):
        import quality_firewall
        src = inspect.getsource(quality_firewall.repair_response)
        assert "repair_response" in src
        # Must not call itself recursively — check for call pattern repair_response(
        call_lines = [l for l in src.splitlines() if "repair_response(" in l and "def " not in l]
        assert len(call_lines) == 0, "repair_response must not call itself (one pass max)"


# ── Clean report content assertions ─────────────────────────────────────────

class TestCleanReportContent:
    """Verify _CLEAN_REPORT does not contain any forbidden phrases."""

    def test_no_action_header(self):
        assert "action: buy" not in _CLEAN_REPORT.lower()
        assert "action: sell" not in _CLEAN_REPORT.lower()

    def test_no_hold_period(self):
        assert "hold period" not in _CLEAN_REPORT.lower()

    def test_no_the_setup(self):
        assert "the setup" not in _CLEAN_REPORT.lower()

    def test_no_your_rules(self):
        assert "your rules" not in _CLEAN_REPORT.lower()

    def test_no_how_this_plays_out(self):
        assert "how this plays out" not in _CLEAN_REPORT.lower()

    def test_no_what_breaks_this(self):
        assert "what breaks this" not in _CLEAN_REPORT.lower()

    def test_no_tripwire(self):
        assert "tripwire" not in _CLEAN_REPORT.lower()

    def test_no_entry(self):
        assert "entry:" not in _CLEAN_REPORT.lower()

    def test_no_stop_loss(self):
        assert "stop loss" not in _CLEAN_REPORT.lower()

    def test_has_executive_summary(self):
        assert "executive summary" in _CLEAN_REPORT.lower()

    def test_has_company_overview(self):
        assert "company overview" in _CLEAN_REPORT.lower()

    def test_has_business_model(self):
        assert "business model" in _CLEAN_REPORT.lower()

    def test_has_financial_snapshot(self):
        assert "financial snapshot" in _CLEAN_REPORT.lower()

    def test_has_key_risks(self):
        assert "key risks" in _CLEAN_REPORT.lower()

    def test_has_sources(self):
        assert "sources" in _CLEAN_REPORT.lower()

    def test_has_bottom_line(self):
        assert "bottom line" in _CLEAN_REPORT.lower()
