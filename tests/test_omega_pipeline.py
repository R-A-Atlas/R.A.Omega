"""
tests/test_omega_pipeline.py — Central pipeline planner tests.

Covers:
  PHASE 1  PipelinePlan structure and constants
  PHASE 2  should_use_deep_research — opt-in only
  PHASE 3  select_output_mode — delegates to existing routing logic
  PHASE 4  select_workflow — output_mode + deep flag drives workflow
  PHASE 5  select_renderer_type — strict output_mode → renderer mapping
  PHASE 6  plan_request — full end-to-end scenarios
  PHASE 7  Invariants: company_report never trade_cards, chat never deep research
  PHASE 8  Buttons/toggles only override when explicitly set
"""
from __future__ import annotations

import os

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from omega_pipeline import (
    PipelinePlan,
    WORKFLOW_GENERAL_ANSWER,
    WORKFLOW_COMPANY_REPORT_FAST,
    WORKFLOW_TRADE_ANALYSIS,
    WORKFLOW_DEEP_RESEARCH,
    WORKFLOW_DOCUMENT_REPORT,
    WORKFLOW_HTML_ARTIFACT,
    WORKFLOW_MARKET_SNAPSHOT,
    RENDERER_CHAT_BUBBLE,
    RENDERER_PAPER_REPORT,
    RENDERER_TRADE_CARDS,
    RENDERER_DOCUMENT,
    RENDERER_HTML,
    plan_request,
    select_output_mode,
    select_workflow,
    should_use_deep_research,
    select_renderer_type,
)


# ── PHASE 1: Structure and constants ─────────────────────────────────────────

class TestPipelineStructure:

    def test_pipeline_plan_is_dataclass(self):
        plan = plan_request("hello")
        assert isinstance(plan, PipelinePlan)

    def test_pipeline_plan_has_all_fields(self):
        plan = plan_request("hello")
        assert hasattr(plan, "route")
        assert hasattr(plan, "output_mode")
        assert hasattr(plan, "workflow")
        assert hasattr(plan, "use_deep_research")
        assert hasattr(plan, "required_tools")
        assert hasattr(plan, "renderer_type")
        assert hasattr(plan, "persistence_target")
        assert hasattr(plan, "reason")

    def test_pipeline_plan_to_dict(self):
        plan = plan_request("hello")
        d = plan.to_dict()
        assert isinstance(d, dict)
        assert "route" in d
        assert "output_mode" in d
        assert "workflow" in d
        assert "use_deep_research" in d
        assert "required_tools" in d
        assert "renderer_type" in d
        assert "persistence_target" in d
        assert "reason" in d

    def test_required_tools_is_list(self):
        plan = plan_request("Give me everything on BlackRock")
        assert isinstance(plan.required_tools, list)

    def test_use_deep_research_is_bool(self):
        plan = plan_request("Give me everything on BlackRock")
        assert isinstance(plan.use_deep_research, bool)

    def test_workflow_constants_exist(self):
        assert WORKFLOW_GENERAL_ANSWER == "general_answer"
        assert WORKFLOW_COMPANY_REPORT_FAST == "company_report_fast"
        assert WORKFLOW_TRADE_ANALYSIS == "trade_analysis"
        assert WORKFLOW_DEEP_RESEARCH == "deep_research"
        assert WORKFLOW_DOCUMENT_REPORT == "document_report"

    def test_renderer_constants_exist(self):
        assert RENDERER_CHAT_BUBBLE == "chat_bubble"
        assert RENDERER_PAPER_REPORT == "paper_report"
        assert RENDERER_TRADE_CARDS == "trade_cards"
        assert RENDERER_DOCUMENT == "document"


# ── PHASE 2: should_use_deep_research — strict opt-in ────────────────────────

class TestShouldUseDeepResearch:

    def test_normal_blackrock_does_not_use_deep(self):
        assert should_use_deep_research("Give me everything on BlackRock", "company_report") is False

    def test_normal_tsla_does_not_use_deep(self):
        assert should_use_deep_research("Give me a TSLA trade setup", "trade_plan") is False

    def test_explicit_deep_phrase_uses_deep(self):
        assert should_use_deep_research("Do deep research on BlackRock", "company_report") is True

    def test_full_research_phrase_uses_deep(self):
        assert should_use_deep_research("Run full research on Apple", "company_report") is True

    def test_comprehensive_research_phrase_uses_deep(self):
        assert should_use_deep_research("Comprehensive research on TSLA", "company_report") is True

    def test_research_mode_deep_control_uses_deep(self):
        assert should_use_deep_research(
            "Give me everything on BlackRock", "company_report",
            request_controls={"research_mode": "deep"}
        ) is True

    def test_research_mode_normal_does_not_use_deep(self):
        assert should_use_deep_research(
            "Give me everything on BlackRock", "company_report",
            request_controls={"research_mode": "normal"}
        ) is False

    def test_research_mode_web_does_not_use_deep(self):
        assert should_use_deep_research(
            "What is BlackRock?", "company_report",
            request_controls={"research_mode": "web"}
        ) is False

    def test_chat_mode_cannot_use_deep_even_with_control(self):
        assert should_use_deep_research(
            "How do I make apple pie?", "chat",
            request_controls={"research_mode": "deep"}
        ) is False

    def test_general_chat_cannot_use_deep(self):
        assert should_use_deep_research(
            "How do I make apple pie?", "general_chat",
            request_controls={"research_mode": "deep"}
        ) is False

    def test_finance_answer_cannot_use_deep(self):
        assert should_use_deep_research(
            "What is a good savings rate?", "finance_answer",
            request_controls={"research_mode": "deep"}
        ) is False

    def test_casual_query_never_deep(self):
        assert should_use_deep_research("hey how are you", "chat") is False

    def test_empty_controls_does_not_trigger_deep(self):
        assert should_use_deep_research("Give me everything on BlackRock", "company_report", {}) is False


# ── PHASE 3: select_output_mode ────────────────────────────────────────────────

class TestSelectOutputMode:

    def test_blackrock_produces_company_report(self):
        mode = select_output_mode("Give me everything on BlackRock", "COMPANY_RESEARCH")
        assert mode == "company_report"

    def test_tsla_trade_setup_produces_trade_plan(self):
        mode = select_output_mode("Give me a TSLA trade setup", "MARKET_DEEP_DIVE")
        assert mode == "trade_plan"

    def test_apple_pie_produces_chat(self):
        mode = select_output_mode("How do I make apple pie?", "GENERAL_CHAT")
        assert mode == "chat"

    def test_pdf_report_produces_document(self):
        mode = select_output_mode("Make a PDF report on Microsoft", "DOCUMENT_GENERATION")
        assert mode == "document"

    def test_route_band_focused_analysis_blackrock(self):
        # Passing a route_band → falls back to classify_intent_route
        mode = select_output_mode("Give me everything on BlackRock", "focused_analysis")
        assert mode == "company_report"

    def test_route_band_quick_chat_apple_pie(self):
        mode = select_output_mode("How do I make apple pie?", "quick_chat")
        assert mode == "chat"

    def test_output_mode_override_respected(self):
        mode = select_output_mode(
            "How do I make apple pie?", "GENERAL_CHAT",
            request_controls={"output_mode_override": "company_report"}
        )
        assert mode == "company_report"

    def test_no_override_when_not_set(self):
        mode = select_output_mode(
            "How do I make apple pie?", "GENERAL_CHAT",
            request_controls={"research_mode": "normal"}
        )
        assert mode == "chat"

    def test_goldman_sachs_produces_company_report(self):
        mode = select_output_mode("Tell me about Goldman Sachs", "COMPANY_RESEARCH")
        assert mode == "company_report"


# ── PHASE 4: select_workflow ───────────────────────────────────────────────────

class TestSelectWorkflow:

    def test_company_report_normal_uses_fast_workflow(self):
        wf = select_workflow("Give me everything on BlackRock", "COMPANY_RESEARCH", "company_report")
        assert wf == WORKFLOW_COMPANY_REPORT_FAST

    def test_company_report_deep_uses_deep_research_workflow(self):
        wf = select_workflow(
            "Do deep research on BlackRock", "COMPANY_RESEARCH", "company_report",
            request_controls={"research_mode": "deep"}
        )
        assert wf == WORKFLOW_DEEP_RESEARCH

    def test_company_report_deep_phrase_uses_deep_research_workflow(self):
        wf = select_workflow(
            "Do deep research on BlackRock", "COMPANY_RESEARCH", "company_report"
        )
        assert wf == WORKFLOW_DEEP_RESEARCH

    def test_trade_plan_uses_trade_analysis_workflow(self):
        wf = select_workflow("Give me a TSLA trade setup", "MARKET_DEEP_DIVE", "trade_plan")
        assert wf == WORKFLOW_TRADE_ANALYSIS

    def test_chat_uses_general_answer_workflow(self):
        wf = select_workflow("How do I make apple pie?", "GENERAL_CHAT", "chat")
        assert wf == WORKFLOW_GENERAL_ANSWER

    def test_general_chat_uses_general_answer_workflow(self):
        wf = select_workflow("How do I make apple pie?", "GENERAL_CHAT", "general_chat")
        assert wf == WORKFLOW_GENERAL_ANSWER

    def test_finance_answer_uses_general_answer_workflow(self):
        wf = select_workflow("What is a good savings rate?", "GENERAL_FINANCE", "finance_answer")
        assert wf == WORKFLOW_GENERAL_ANSWER

    def test_document_uses_document_report_workflow(self):
        wf = select_workflow("Make a PDF report on Microsoft", "DOCUMENT_GENERATION", "document")
        assert wf == WORKFLOW_DOCUMENT_REPORT

    def test_html_artifact_uses_html_workflow(self):
        wf = select_workflow("Create an interactive dashboard", "HTML_ARTIFACT", "html_artifact")
        assert wf == WORKFLOW_HTML_ARTIFACT

    def test_market_snapshot_uses_snapshot_workflow(self):
        wf = select_workflow("Quick market overview", "MARKET_DATA", "market_snapshot")
        assert wf == WORKFLOW_MARKET_SNAPSHOT


# ── PHASE 5: select_renderer_type ────────────────────────────────────────────

class TestSelectRendererType:

    def test_trade_plan_gets_trade_cards(self):
        assert select_renderer_type("trade_plan", WORKFLOW_TRADE_ANALYSIS) == RENDERER_TRADE_CARDS

    def test_company_report_gets_paper_report(self):
        assert select_renderer_type("company_report", WORKFLOW_COMPANY_REPORT_FAST) == RENDERER_PAPER_REPORT

    def test_company_report_deep_gets_paper_report_not_trade_cards(self):
        assert select_renderer_type("company_report", WORKFLOW_DEEP_RESEARCH) == RENDERER_PAPER_REPORT

    def test_chat_gets_chat_bubble(self):
        assert select_renderer_type("chat", WORKFLOW_GENERAL_ANSWER) == RENDERER_CHAT_BUBBLE

    def test_general_chat_gets_chat_bubble(self):
        assert select_renderer_type("general_chat", WORKFLOW_GENERAL_ANSWER) == RENDERER_CHAT_BUBBLE

    def test_finance_answer_gets_chat_bubble(self):
        assert select_renderer_type("finance_answer", WORKFLOW_GENERAL_ANSWER) == RENDERER_CHAT_BUBBLE

    def test_document_gets_document_renderer(self):
        assert select_renderer_type("document", WORKFLOW_DOCUMENT_REPORT) == RENDERER_DOCUMENT

    def test_html_artifact_gets_html_renderer(self):
        assert select_renderer_type("html_artifact", WORKFLOW_HTML_ARTIFACT) == RENDERER_HTML

    def test_market_snapshot_gets_chat_bubble(self):
        assert select_renderer_type("market_snapshot", WORKFLOW_MARKET_SNAPSHOT) == RENDERER_CHAT_BUBBLE

    def test_unknown_mode_gets_chat_bubble(self):
        assert select_renderer_type("unknown_mode", "unknown_workflow") == RENDERER_CHAT_BUBBLE


# ── PHASE 6: plan_request — full end-to-end scenarios ────────────────────────

class TestPlanRequestScenarios:

    def test_blackrock_normal_plan(self):
        plan = plan_request("Give me everything on BlackRock")
        assert plan.output_mode == "company_report"
        assert plan.workflow == WORKFLOW_COMPANY_REPORT_FAST
        assert plan.renderer_type == RENDERER_PAPER_REPORT
        assert plan.use_deep_research is False

    def test_blackrock_deep_research_plan(self):
        plan = plan_request("Do deep research on BlackRock")
        assert plan.output_mode == "company_report"
        assert plan.workflow == WORKFLOW_DEEP_RESEARCH
        assert plan.renderer_type == RENDERER_PAPER_REPORT
        assert plan.use_deep_research is True

    def test_blackrock_deep_via_control(self):
        plan = plan_request(
            "Give me everything on BlackRock",
            request_controls={"research_mode": "deep"}
        )
        assert plan.output_mode == "company_report"
        assert plan.workflow == WORKFLOW_DEEP_RESEARCH
        assert plan.use_deep_research is True

    def test_tsla_trade_setup_plan(self):
        plan = plan_request("Give me a TSLA trade setup with entry and stop loss")
        assert plan.output_mode == "trade_plan"
        assert plan.workflow == WORKFLOW_TRADE_ANALYSIS
        assert plan.renderer_type == RENDERER_TRADE_CARDS
        assert plan.use_deep_research is False

    def test_apple_pie_plan(self):
        plan = plan_request("How do I make apple pie?")
        assert plan.output_mode == "chat"
        assert plan.workflow == WORKFLOW_GENERAL_ANSWER
        assert plan.renderer_type == RENDERER_CHAT_BUBBLE
        assert plan.use_deep_research is False

    def test_pdf_report_plan(self):
        plan = plan_request("Make a PDF report on Microsoft")
        assert plan.output_mode == "document"
        assert plan.workflow == WORKFLOW_DOCUMENT_REPORT
        assert plan.renderer_type == RENDERER_DOCUMENT

    def test_blackrock_word_document_plan(self):
        plan = plan_request("Give me everything on BlackRock in a Word document")
        assert plan.output_mode == "document"
        assert plan.workflow == WORKFLOW_DOCUMENT_REPORT
        assert plan.renderer_type == RENDERER_DOCUMENT

    def test_nvda_opinion_plan_plain_finance_answer(self):
        plan = plan_request("what do you think of NVDA in your personal opinion")
        assert plan.output_mode == "finance_answer"
        assert plan.workflow == WORKFLOW_GENERAL_ANSWER
        assert plan.renderer_type == RENDERER_CHAT_BUBBLE

    def test_apple_pie_deep_mode_button_does_not_trigger_deep(self):
        plan = plan_request(
            "How do I make apple pie?",
            request_controls={"research_mode": "deep"}
        )
        assert plan.use_deep_research is False
        assert plan.renderer_type == RENDERER_CHAT_BUBBLE

    def test_blackrock_normal_mode_does_not_trigger_deep(self):
        plan = plan_request(
            "Give me everything on BlackRock",
            request_controls={"research_mode": "normal"}
        )
        assert plan.use_deep_research is False
        assert plan.workflow == WORKFLOW_COMPANY_REPORT_FAST

    def test_tools_populated_for_company_report(self):
        plan = plan_request("Give me everything on BlackRock")
        assert len(plan.required_tools) > 0
        assert "omega_agent" in plan.required_tools

    def test_tools_empty_for_chat(self):
        plan = plan_request("How do I make apple pie?")
        assert plan.required_tools == []

    def test_persistence_report_for_company_report(self):
        plan = plan_request("Give me everything on BlackRock")
        assert plan.persistence_target == "report"

    def test_persistence_chat_log_for_chat(self):
        plan = plan_request("How do I make apple pie?")
        assert plan.persistence_target == "chat_log"

    def test_reason_string_not_empty(self):
        plan = plan_request("Give me everything on BlackRock")
        assert len(plan.reason) > 10
        assert "company_report" in plan.reason


# ── PHASE 7: Hard invariants ──────────────────────────────────────────────────

class TestHardInvariants:
    """These must hold for every possible query in the scenarios we care about."""

    def test_company_report_never_gets_trade_cards(self):
        queries = [
            "Give me everything on BlackRock",
            "Tell me about Goldman Sachs",
            "Research Apple Inc",
            "What is Microsoft's business model?",
        ]
        for q in queries:
            plan = plan_request(q)
            if plan.output_mode == "company_report":
                assert plan.renderer_type != RENDERER_TRADE_CARDS, \
                    f"company_report got trade_cards for: {q!r}"

    def test_chat_never_triggers_deep_research(self):
        queries = [
            "How do I make apple pie?",
            "What is the weather like?",
            "Tell me a joke",
            "Hey how are you",
        ]
        for q in queries:
            plan = plan_request(q)
            if plan.output_mode in ("chat", "general_chat"):
                assert plan.use_deep_research is False, \
                    f"chat mode triggered deep research for: {q!r}"

    def test_chat_never_gets_trade_cards(self):
        queries = [
            "How do I make apple pie?",
            "What is 2+2?",
            "Hello",
        ]
        for q in queries:
            plan = plan_request(q)
            assert plan.renderer_type != RENDERER_TRADE_CARDS, \
                f"chat query got trade_cards for: {q!r}"

    def test_explicit_trade_request_gets_trade_plan(self):
        plan = plan_request("Give me a TSLA trade setup with entry and stop loss")
        assert plan.output_mode == "trade_plan"
        assert plan.renderer_type == RENDERER_TRADE_CARDS

    def test_non_trade_queries_do_not_get_trade_cards(self):
        queries = [
            "How do I make apple pie?",
            "Give me everything on BlackRock",
            "What is the fed funds rate?",
        ]
        for q in queries:
            plan = plan_request(q)
            assert plan.renderer_type != RENDERER_TRADE_CARDS or plan.output_mode == "trade_plan", \
                f"Non-trade query got trade_cards for: {q!r}"


# ── PHASE 8: Button/toggle override behavior ──────────────────────────────────

class TestButtonToggleOverrides:
    """Buttons and toggles are optional overrides only — raw query governs by default."""

    def test_no_controls_uses_query_only(self):
        plan_no_controls = plan_request("Give me everything on BlackRock")
        plan_normal = plan_request(
            "Give me everything on BlackRock",
            request_controls={"research_mode": "normal"}
        )
        assert plan_no_controls.output_mode == plan_normal.output_mode
        assert plan_no_controls.renderer_type == plan_normal.renderer_type

    def test_deep_toggle_only_affects_workflow_not_output_mode(self):
        plan_normal = plan_request("Give me everything on BlackRock")
        plan_deep = plan_request(
            "Give me everything on BlackRock",
            request_controls={"research_mode": "deep"}
        )
        # output_mode stays company_report regardless of toggle
        assert plan_normal.output_mode == plan_deep.output_mode == "company_report"
        # But workflow changes
        assert plan_normal.workflow == WORKFLOW_COMPANY_REPORT_FAST
        assert plan_deep.workflow == WORKFLOW_DEEP_RESEARCH

    def test_output_mode_override_overrides_routing(self):
        plan = plan_request(
            "How do I make apple pie?",
            request_controls={"output_mode_override": "company_report"}
        )
        assert plan.output_mode == "company_report"

    def test_web_mode_does_not_trigger_deep_research(self):
        plan = plan_request(
            "Give me everything on BlackRock",
            request_controls={"research_mode": "web"}
        )
        assert plan.use_deep_research is False

    def test_deep_toggle_on_chat_query_still_no_deep(self):
        plan = plan_request(
            "How do I make apple pie?",
            request_controls={"research_mode": "deep"}
        )
        assert plan.use_deep_research is False
        assert plan.output_mode == "chat"
        assert plan.renderer_type == RENDERER_CHAT_BUBBLE
