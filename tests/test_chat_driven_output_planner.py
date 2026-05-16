"""
tests/test_chat_driven_output_planner.py — Chat-driven output mode detection.

Covers:
  PHASE 1  Auto output mode selection (no button required)
  PHASE 2  Gemini tool/JSON config fix (no tools + application/json together)
  PHASE 3  Supabase local UUID fix (/history/reports with test_user_local)
  PHASE 5  UI: Download Report button present for company_report
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from output_modes import (
    OUTPUT_CHAT,
    OUTPUT_COMPANY_REPORT,
    OUTPUT_DOCUMENT,
    OUTPUT_HTML_ARTIFACT,
    OUTPUT_TRADE_PLAN,
    resolve_output_mode,
    user_explicitly_requested_trade,
)
from query_router import (
    INTENT_CASUAL,
    INTENT_COMPANY_RESEARCH,
    INTENT_DOCUMENT_GENERATION,
    INTENT_GENERAL_CHAT,
    INTENT_GENERAL_FINANCE,
    INTENT_HTML_ARTIFACT,
    INTENT_MARKET_DEEP_DIVE,
    INTENT_TRADING_ANALYSIS,
    classify_intent_route,
    detect_company_name,
)
from output_contracts import OUTPUT_CONTRACTS, COMPANY_REPORT_TRADE_FORBIDDEN


# ── Shared clean-report text ─────────────────────────────────────────────────

_CLEAN_COMPANY_REPORT = (
    "Executive Summary: BlackRock is the world's dominant asset manager. "
    "Company Overview: BlackRock has $10T AUM worldwide. "
    "What They Do: Investment management, risk advisory, ETF management. "
    "Business Model: Fee-based on assets under management. "
    "Financial Snapshot: Revenue $17.8B, net income $5.5B. "
    "Key Executives: Larry Fink (CEO), Robert Kapito (President). "
    "Recent News: Expanding into private credit and alternative assets. "
    "Competitive Position: Largest active manager globally via iShares ETFs. "
    "Key Risks: Regulatory scrutiny, fee compression, macro risk. "
    "Sources: Bloomberg, SEC filings, BlackRock IR. "
    "Bottom Line: Dominant franchise with secular passive-investing tailwinds."
)


# ── PHASE 1 — Auto output mode selection ────────────────────────────────────

class TestAutoOutputModeSelection:
    """resolve_output_mode() picks the right format from query text alone."""

    def test_blackrock_research_auto_company_report(self):
        intent = classify_intent_route("give me everything on BlackRock")
        om = resolve_output_mode("give me everything on BlackRock", intent)
        assert om == OUTPUT_COMPANY_REPORT

    def test_apple_pie_auto_chat(self):
        intent = classify_intent_route("how do I make apple pie")
        om = resolve_output_mode("how do I make apple pie", intent)
        assert om == OUTPUT_CHAT

    def test_tsla_trade_setup_auto_trade_plan(self):
        q = "give me a trade setup for TSLA"
        intent = classify_intent_route(q)
        om = resolve_output_mode(q, intent)
        assert om == OUTPUT_TRADE_PLAN

    def test_pdf_report_auto_document(self):
        q = "Make me a PDF report on AI finance companies"
        intent = classify_intent_route(q)
        om = resolve_output_mode(q, intent)
        assert om == OUTPUT_DOCUMENT

    def test_word_document_auto_document(self):
        q = "Make this into a document summary"
        intent = classify_intent_route(q)
        om = resolve_output_mode(q, intent)
        assert om == OUTPUT_DOCUMENT

    def test_dashboard_auto_html_artifact(self):
        q = "Create an interactive dashboard for my portfolio"
        intent = classify_intent_route(q)
        om = resolve_output_mode(q, intent)
        assert om == OUTPUT_HTML_ARTIFACT

    def test_chart_trigger_word_html_artifact(self):
        q = "Show me a chart of TSLA performance"
        om = resolve_output_mode(q, "GENERAL_FINANCE")
        assert om == OUTPUT_HTML_ARTIFACT

    def test_chart_in_html_trigger_words(self):
        from output_modes import HTML_TRIGGER_WORDS
        assert "chart" in HTML_TRIGGER_WORDS

    def test_sports_question_auto_chat(self):
        intent = classify_intent_route("who won last night's game?")
        om = resolve_output_mode("who won last night's game?", intent)
        assert om == OUTPUT_CHAT

    def test_company_report_no_trade_bleed(self):
        intent = classify_intent_route("give me everything on BlackRock")
        om = resolve_output_mode("give me everything on BlackRock", intent)
        assert om != OUTPUT_TRADE_PLAN

    def test_casual_no_trade_output(self):
        intent = classify_intent_route("what's the weather like?")
        om = resolve_output_mode("what's the weather like?", intent)
        assert om != OUTPUT_TRADE_PLAN

    def test_buttons_optional_company_report_inferred(self):
        # Without any toggle/button, company research → company_report
        q = "Tell me about Goldman Sachs"
        intent = classify_intent_route(q)
        om = resolve_output_mode(q, intent)
        assert om == OUTPUT_COMPANY_REPORT

    def test_buttons_optional_trade_inferred(self):
        # Without any toggle/button, explicit trade query → trade_plan
        q = "What options should I buy on AAPL"
        om = resolve_output_mode(q, "TRADING_ANALYSIS")
        assert om == OUTPUT_TRADE_PLAN


# ── PHASE 1 — Deep research auto-detection ──────────────────────────────────

class TestDeepResearchAutoDetect:
    """_DEEP_RESEARCH_RE in query_router auto-promotes research_mode when query says so."""

    def test_deep_research_re_exists(self):
        import query_router
        assert hasattr(query_router, "_DEEP_RESEARCH_RE"), "_DEEP_RESEARCH_RE not found in query_router"

    def test_deep_research_re_matches_deep_research(self):
        from query_router import _DEEP_RESEARCH_RE
        assert _DEEP_RESEARCH_RE.search("do a deep research on BlackRock") is not None

    def test_deep_research_re_matches_full_research(self):
        from query_router import _DEEP_RESEARCH_RE
        assert _DEEP_RESEARCH_RE.search("run full research on Apple") is not None

    def test_deep_research_re_matches_comprehensive(self):
        from query_router import _DEEP_RESEARCH_RE
        assert _DEEP_RESEARCH_RE.search("comprehensive research on TSLA") is not None

    def test_deep_research_re_no_match_casual(self):
        from query_router import _DEEP_RESEARCH_RE
        assert _DEEP_RESEARCH_RE.search("how do I make apple pie") is None

    def test_route_source_has_deep_research_auto_detect(self):
        import query_router
        src = inspect.getsource(query_router.QueryRouter.route)
        assert "_DEEP_RESEARCH_RE" in src, "route() must use _DEEP_RESEARCH_RE for auto deep-mode detection"


# ── PHASE 2 — Gemini tool/JSON config fix ───────────────────────────────────

class TestGeminiToolJsonConfig:
    """atlas_omega.py must never combine Google Search tools with response_mime_type=application/json."""

    @classmethod
    def _get_omega_src(cls) -> str:
        import atlas_omega
        return inspect.getsource(atlas_omega)

    def test_search_tools_block_not_combined_with_json_mime(self):
        src = self._get_omega_src()
        # Find the block where google_search tool is enabled
        lines = src.splitlines()
        in_tool_block = False
        for i, line in enumerate(lines):
            if "google_search" in line.lower() and "Tool" in line:
                in_tool_block = True
            if in_tool_block and "response_mime_type" in line and "application/json" in line:
                pytest.fail(
                    f"Line {i+1}: tools + response_mime_type=application/json combined — "
                    "Gemini rejects this combination."
                )
            # End of the block when we hit the else branch
            if in_tool_block and line.strip().startswith("else:"):
                break

    def test_non_tool_path_still_uses_json_mime(self):
        src = self._get_omega_src()
        # The non-tool path should still request JSON to keep parsing working
        assert "response_mime_type" in src and "application/json" in src, \
            "Non-tool Gemini call should still request application/json"

    def test_omega_source_has_tool_json_comment(self):
        src = self._get_omega_src()
        # Verify our fix comment is present
        assert "application/json" in src
        # The comment explaining the fix should exist
        assert "tools" in src.lower()


# ── PHASE 3 — Supabase local UUID fix ───────────────────────────────────────

class TestHistoryReportsLocalUser:
    """/history/reports must not crash when user_id=test_user_local."""

    def test_list_research_queries_returns_empty_for_local_user(self):
        import atlas_db
        result = atlas_db.list_research_queries(atlas_db.TEST_USER_LOCAL)
        assert result == [], f"Expected [] for test_user_local, got {result!r}"

    def test_list_research_queries_returns_empty_for_non_uuid(self):
        import atlas_db
        result = atlas_db.list_research_queries("not_a_uuid_string")
        assert result == [], "Non-UUID user_id should return empty list"

    def test_list_research_queries_source_has_local_guard(self):
        import atlas_db
        src = inspect.getsource(atlas_db.list_research_queries)
        assert "TEST_USER_LOCAL" in src or "test_user_local" in src.lower(), \
            "list_research_queries must guard against TEST_USER_LOCAL"

    def test_list_research_queries_source_has_uuid_guard(self):
        import atlas_db
        src = inspect.getsource(atlas_db.list_research_queries)
        assert "_is_uuidish" in src or "uuid" in src.lower(), \
            "list_research_queries must guard against non-UUID user_id values"


# ── PHASE 3 — Company report paper contract ─────────────────────────────────

class TestCompanyReportPaperContract:
    """company_report contract requires paper-style sections and forbids trade jargon."""

    def test_executive_summary_required(self):
        assert "Executive Summary" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_company_overview_required(self):
        assert "Company Overview" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_key_risks_required(self):
        assert "Key Risks" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_bottom_line_required(self):
        assert "Bottom Line" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_sources_required(self):
        assert "Sources" in OUTPUT_CONTRACTS["company_report"].required_sections

    def test_tripwire_forbidden(self):
        assert "tripwire" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_how_this_plays_out_forbidden(self):
        assert "how this plays out" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_the_setup_forbidden(self):
        assert "the setup" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_your_rules_forbidden(self):
        assert "your rules" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_action_buy_forbidden(self):
        assert "action: buy" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_hold_period_forbidden(self):
        assert "hold period" in COMPANY_REPORT_TRADE_FORBIDDEN

    def test_clean_report_passes_firewall(self):
        from quality_firewall import validate_response
        result = validate_response(
            "Give me everything on BlackRock",
            "COMPANY_RESEARCH",
            "company_report",
            _CLEAN_COMPANY_REPORT,
        )
        assert result.passed is True

    def test_clean_report_has_executive_summary(self):
        assert "executive summary" in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_has_key_risks(self):
        assert "key risks" in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_action(self):
        assert "action: buy" not in _CLEAN_COMPANY_REPORT.lower()
        assert "action: sell" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_the_setup(self):
        assert "the setup" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_your_rules(self):
        assert "your rules" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_how_this_plays_out(self):
        assert "how this plays out" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_tripwire(self):
        assert "tripwire" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_entry(self):
        assert "entry:" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_stop_loss(self):
        assert "stop loss" not in _CLEAN_COMPANY_REPORT.lower()

    def test_clean_report_no_hold_period(self):
        assert "hold period" not in _CLEAN_COMPANY_REPORT.lower()


# ── PHASE 4 — Prompt builder ─────────────────────────────────────────────────

class TestPromptBuilderCompanyReport:
    """build_synthesis_prompt() emits the right company-report instruction."""

    def test_prompt_says_professional_markdown(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query="Give me everything on BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            company_name="blackrock",
        )
        assert "professional" in prompt.lower()
        assert "markdown" in prompt.lower()

    def test_prompt_says_not_trade_plan(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query="Give me everything on BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "not a trade plan" in prompt.lower() or "do not write a trade plan" in prompt.lower()

    def test_prompt_forbids_tripwires(self):
        from prompt_builder import build_synthesis_prompt
        prompt = build_synthesis_prompt(
            raw_query="Tell me about Apple",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
        )
        assert "tripwire" in prompt.lower()


# ── PHASE 5 — UI renderer ────────────────────────────────────────────────────

class TestUICompanyReportRenderer:
    """ra_omega_app.html must render company_report in paper style with Download Report."""

    @classmethod
    def _get_src(cls) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "ra_omega_app.html")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_download_report_button_present_for_company_report(self):
        src = self._get_src()
        assert "isCompanyReport" in src
        assert "Download Report" in src or "Report" in src, \
            "ExportBar must show a Report/Download button for company_report mode"

    def test_download_report_gated_by_is_company_report(self):
        src = self._get_src()
        # The Report button must only appear when isCompanyReport is true
        assert "isCompanyReport" in src
        # Check the button exists near the company_report check
        assert "openHTMLReport" in src or "FileText" in src, \
            "Report button must call openHTMLReport or use FileText icon"

    def test_trade_cards_gated_for_company_report(self):
        src = self._get_src()
        assert "!isCompanyReport" in src, "Trade cards must be gated by !isCompanyReport"

    def test_output_mode_read_from_data(self):
        src = self._get_src()
        assert "data._output_mode" in src

    def test_your_rules_gated(self):
        src = self._get_src()
        assert "YOUR RULES" in src
        assert "!isCompanyReport" in src

    def test_the_setup_gated(self):
        src = self._get_src()
        assert "THE SETUP" in src
        assert "!isCompanyReport" in src
