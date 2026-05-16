"""
tests/test_deep_query_control.py — Tests for multi-phase deep query control fixes.

PHASE 1: Stopword expansion (ONN, TV, AH, USA, API, PDF, HTML)
PHASE 2: Research mode gate — MARKET_DEEP_DIVE → Omega in normal/web mode
PHASE 3: Job completion state — final_response_available flag
PHASE 4: Quality firewall safety — always returns a response
"""
from __future__ import annotations

import os
import inspect

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

from query_router import (
    QueryParser,
    _EXPLICIT_TRADE_RE,
    INTENT_GENERAL_FINANCE,
    INTENT_MARKET_DEEP_DIVE,
    classify_intent_route,
)
from orchestration.research_jobs import activity_from_job
from quality_firewall import validate_response


# ── PHASE 1: Stopword expansion ───────────────────────────────────────────────

class TestStopwordExpansion:
    """ONN, TV, AH, USA, API, PDF, HTML must not be extracted as tickers."""

    @pytest.mark.parametrize("word", ["ONN", "TV", "AH", "USA", "API", "PDF", "HTML"])
    def test_new_words_in_stopwords(self, word):
        assert word in QueryParser._STOPWORDS, f"{word} missing from _STOPWORDS"

    def test_onn_not_extracted_from_natural_sentence(self):
        parser = QueryParser()
        parsed = parser.parse("ONN is moving — should I buy?")
        assert "ONN" not in parsed.tickers, f"ONN extracted as ticker from natural sentence: {parsed.tickers}"

    def test_tv_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("What's on TV tonight?")
        assert "TV" not in parsed.tickers

    def test_ah_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("After hours TSLA up 3%")
        assert "AH" not in parsed.tickers

    def test_tsla_still_extracted_when_ah_ignored(self):
        parser = QueryParser()
        parsed = parser.parse("After hours TSLA up 3%")
        assert "TSLA" in parsed.tickers

    def test_usa_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("The USA economy is recovering")
        assert "USA" not in parsed.tickers

    def test_api_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("Does this API support real-time data?")
        assert "API" not in parsed.tickers

    def test_pdf_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("Generate a PDF report for AAPL")
        assert "PDF" not in parsed.tickers

    def test_html_not_extracted(self):
        parser = QueryParser()
        parsed = parser.parse("Make me an HTML dashboard for NVDA")
        assert "HTML" not in parsed.tickers


# ── PHASE 2: Research mode gate ───────────────────────────────────────────────

class TestRoutingGate:
    """Verify the non-deep MARKET_DEEP_DIVE → GENERAL_FINANCE gate exists in route()."""

    def test_route_method_accepts_research_mode_param(self):
        """router.route() must have a research_mode kwarg."""
        from query_router import QueryRouter
        sig = inspect.signature(QueryRouter.route)
        assert "research_mode" in sig.parameters, "research_mode param missing from route()"

    def test_route_source_contains_non_deep_gate(self):
        """Source of route() must redirect MARKET_DEEP_DIVE → GENERAL_FINANCE for non-explicit-trade in normal mode."""
        from query_router import QueryRouter
        src = inspect.getsource(QueryRouter.route)
        # Gate requires these symbols to be present in the routing logic
        assert "INTENT_GENERAL_FINANCE" in src, "INTENT_GENERAL_FINANCE not found in route()"
        assert "INTENT_MARKET_DEEP_DIVE" in src, "INTENT_MARKET_DEEP_DIVE not found in route()"
        # The gate uses _EXPLICIT_TRADE_RE to preserve explicit trade requests
        assert "_EXPLICIT_TRADE_RE" in src, "_EXPLICIT_TRADE_RE gate missing from route()"

    def test_api_server_passes_research_mode_to_route(self):
        """api_server.py must pass research_mode=mode to router.route()."""
        path = os.path.join(os.path.dirname(__file__), "..", "api_server.py")
        with open(path, encoding="utf-8") as f:
            src = f.read()
        assert "research_mode=mode" in src, "api_server.py must pass research_mode=mode to router.route()"

    def test_deep_mode_classify_returns_market_deep_dive(self):
        """Score-based query yields MARKET_DEEP_DIVE from classify_intent_route()."""
        # "analyze NVDA" → mkt += 2.5 → MARKET_DEEP_DIVE from raw classify
        intent = classify_intent_route("analyze NVDA")
        assert intent == INTENT_MARKET_DEEP_DIVE

    def test_explicit_trade_re_matches_trade_setup(self):
        """_EXPLICIT_TRADE_RE must match a user explicitly requesting a trade setup."""
        assert _EXPLICIT_TRADE_RE.search("give me a trade setup for NVDA")

    def test_explicit_trade_re_does_not_match_analysis_query(self):
        """_EXPLICIT_TRADE_RE must NOT match a plain analysis query."""
        assert not _EXPLICIT_TRADE_RE.search("analyze NVDA")

    def test_general_finance_not_market_deep_dive_for_casual(self):
        """Casual queries must not route to MARKET_DEEP_DIVE."""
        intent = classify_intent_route("how are you doing today?")
        assert intent != INTENT_MARKET_DEEP_DIVE


# ── PHASE 3: Job completion state ────────────────────────────────────────────

class TestJobCompletionState:
    """activity_from_job() must set final_response_available correctly."""

    def _make_job(self, status: str) -> dict:
        return {
            "job_id": "test_job_001",
            "user_id": "user_abc",
            "status": status,
            "route_band": "deep_research",
            "progress_pct": 100,
            "current_stage": "Done",
            "current_message": "",
            "search_count": 5,
            "query": "test query",
            "plan": [],
            "events": [],
            "sources": [],
            "artifacts": [],
        }

    def test_completed_job_has_final_response_available_true(self):
        activity = activity_from_job(self._make_job("completed"))
        assert activity["final_response_available"] is True

    def test_failed_job_has_final_response_available_true(self):
        activity = activity_from_job(self._make_job("failed"))
        assert activity["final_response_available"] is True

    def test_cancelled_job_has_final_response_available_true(self):
        activity = activity_from_job(self._make_job("cancelled"))
        assert activity["final_response_available"] is True

    def test_in_progress_job_has_final_response_available_false(self):
        activity = activity_from_job(self._make_job("in_progress"))
        assert activity["final_response_available"] is False

    def test_queued_job_has_final_response_available_false(self):
        activity = activity_from_job(self._make_job("queued"))
        assert activity["final_response_available"] is False

    def test_activity_from_job_preserves_status(self):
        activity = activity_from_job(self._make_job("completed"))
        assert activity["status"] == "completed"

    def test_build_research_activity_has_final_response_available(self):
        """_build_research_activity_payload() should include final_response_available: True."""
        import api_server as _api
        from orchestration.router_policy import decide_route
        decision = decide_route("analyze NVDA", forced_mode="normal")
        activity = _api._build_research_activity_payload("analyze NVDA", decision)
        if activity:  # quick_chat returns {}
            assert activity.get("final_response_available") is True

    def test_research_jobs_update_sets_completed_at(self):
        """update_job(status='completed') must set completed_at."""
        from orchestration import research_jobs
        from orchestration.router_policy import decide_route
        dec = decide_route("test query")
        job = research_jobs.create_job(
            user_id="test_user",
            query="test query",
            route_decision=dec.to_dict(),
            activity={"status": "queued"},
        )
        updated = research_jobs.update_job(
            job["job_id"],
            user_id="test_user",
            status="completed",
            progress_pct=100,
        )
        assert updated is not None
        assert updated.get("completed_at") is not None
        assert updated["status"] == "completed"


# ── PHASE 4: Quality firewall safety ─────────────────────────────────────────

class TestQualityFirewallSafety:
    """Quality firewall must never block a response — always return a QualityResult."""

    def test_validate_response_returns_result_not_exception(self):
        result = validate_response("what is NVDA", "COMPANY_RESEARCH", "company_report", "Some answer")
        assert hasattr(result, "passed")

    def test_validate_response_with_unknown_output_mode_returns_result(self):
        result = validate_response("test", "GENERAL_FINANCE", "unknown_mode_xyz", "answer")
        assert result.passed is False
        assert "Unknown output_mode" in result.reason

    def test_validate_response_passes_for_chat_mode(self):
        result = validate_response("hello", "GENERAL_CHAT", "chat", "Hi there, how can I help?")
        assert result.passed is True

    def test_validate_response_forbidden_phrase_caught(self):
        result = validate_response(
            "tell me about NVDA",
            "COMPANY_RESEARCH",
            "company_report",
            "Here is the company report. Entry price: $150.",
        )
        assert result.passed is False
        assert result.repair_instruction != ""

    def test_validate_response_empty_answer_fails_gracefully(self):
        result = validate_response("what is AAPL", "COMPANY_RESEARCH", "finance_answer", "")
        assert result.passed is False
        assert result.reason != ""

    def test_quality_result_has_repair_instruction(self):
        result = validate_response("test", "GENERAL_FINANCE", "company_report", "short")
        assert hasattr(result, "repair_instruction")
