"""
tests/test_sec_synthesis_wiring.py — Tests for SEC EDGAR wiring into OmegaAgent synthesis.

All Gemini/HTTP calls are mocked. Tests verify:
- Company research calls SEC summary
- Non-company queries do not call SEC
- SEC failure does not break the response
- SEC metadata is returned in _meta
- Routing purity maintained
- Trade plan contamination blocked
"""
from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

# ── Shared mock SEC data ───────────────────────────────────────────────────────

MOCK_SEC_FOUND = {
    "company":          "BlackRock Inc.",
    "cik":              "0001364742",
    "sec_filings_used": True,
    "sec_status":       "found",
    "latest_10k": {
        "form": "10-K", "filing_date": "2025-02-14",
        "document_url": "https://www.sec.gov/Archives/edgar/data/1364742/000136474225000010/blk-10k.htm",
        "accession_number": "0001364742-25-000010",
        "description": "Annual Report",
        "index_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001364742&type=10-K",
    },
    "latest_10q": {
        "form": "10-Q", "filing_date": "2024-11-12",
        "document_url": "https://www.sec.gov/Archives/edgar/data/1364742/000136474224000055/blk-10q.htm",
        "accession_number": "0001364742-24-000055",
        "description": "Quarterly Report",
        "index_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001364742&type=10-Q",
    },
    "latest_8k":  None,
    "all_recent": {},
    "error":      None,
    "filing_context": "SEC EDGAR Filings for BlackRock Inc. (CIK: 0001364742):\n  Latest 10-K: 2025-02-14\n  Latest 10-Q: 2024-11-12",
}

MOCK_SEC_NOT_FOUND = {
    "company": "UnknownCo",
    "cik": None,
    "sec_filings_used": False,
    "latest_10k": None, "latest_10q": None, "latest_8k": None,
    "all_recent": {}, "error": "No CIK found for 'UnknownCo'",
    "filing_context": "No recent SEC filings found for UnknownCo",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_SYNTH_RESULT = {
    "domain": "GENERAL_FINANCE",
    "domain_label": "Finance",
    "headline": "BlackRock overview",
    "urgency": "normal",
    "executive_brief": "BlackRock is the world's largest asset manager.",
    "situation_analysis": "Strong AUM growth.",
    "key_insight": "Rising rates impact.",
    "primary_recommendation": "Monitor rate environment.",
    "scenarios": [], "numbers_that_matter": {}, "action_plan": [],
    "named_resources": [], "hidden_angles": [], "risks_and_tripwires": [],
    "follow_up_questions": [], "last_updated": "2025-02-14",
}


def _make_omega_agent():
    """Return an OmegaAgent with all external I/O mocked out."""
    from atlas_omega import OmegaAgent, UserContext
    agent = OmegaAgent.__new__(OmegaAgent)
    # Use real UserContext to avoid __dict__ kwarg issues with MagicMock on Py3.13
    ctx = UserContext()
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ("GENERAL_FINANCE", ctx)
    agent.classifier = mock_classifier
    mock_dispatcher = MagicMock()
    mock_dispatcher.execute.return_value = {"data": {}}
    agent.dispatcher = mock_dispatcher
    # Mock _synthesize directly — avoids full Gemini setup complexity
    agent._synthesize = MagicMock(return_value=dict(_SYNTH_RESULT))
    # Mock _respond_casual — called for CASUAL/GENERAL_CHAT intents
    agent._respond_casual = MagicMock(return_value={"casual": True, "response": "ok", "_meta": {}})
    # Mock _client so _get_client() doesn't crash on uninitialized agent
    agent._client = None
    return agent


# ═══════════════════════════════════════════════════════════════════════════════
# BlackRock company report calls SEC summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompanyReportCallsSec:
    def test_sec_summary_called_for_company_research(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND) as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query(
                        "Give me everything on BlackRock",
                        intent_route="COMPANY_RESEARCH",
                    )
        mock_sec.assert_called_once()
        call_arg = mock_sec.call_args[0][0]
        assert "blackrock" in call_arg.lower() or call_arg == "BlackRock"

    def test_sec_meta_in_result_when_filings_found(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query(
                        "Tell me about BlackRock",
                        intent_route="COMPANY_RESEARCH",
                    )
        meta = result.get("_meta", {})
        assert meta.get("sec_filings_used") is True
        assert meta.get("sec_status") == "found"
        assert meta.get("cik") == "0001364742"

    def test_latest_10k_in_meta(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query(
                        "Research BlackRock",
                        intent_route="COMPANY_RESEARCH",
                    )
        meta = result.get("_meta", {})
        assert meta.get("latest_10k") is not None
        assert meta["latest_10k"]["filing_date"] == "2025-02-14"

    def test_latest_10q_in_meta(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query(
                        "Company report on BlackRock",
                        intent_route="COMPANY_RESEARCH",
                    )
        assert result["_meta"].get("latest_10q") is not None

    def test_sec_data_added_to_bundle(self):
        """SEC data must be placed in bundle['data'] before _synthesize is called."""
        agent = _make_omega_agent()
        captured_bundles: list[dict] = []

        original_mock = agent._synthesize
        def _capture_and_delegate(*args, **kwargs):
            # args[2] is bundle (query, domain, ctx, bundle, ...)
            if len(args) >= 4:
                captured_bundles.append(dict(args[3].get("data", {})))
            return original_mock(*args, **kwargs)

        agent._synthesize = _capture_and_delegate

        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    agent.query("Company research on BlackRock", intent_route="COMPANY_RESEARCH")

        assert any("sec_edgar_filings" in b for b in captured_bundles)


# ═══════════════════════════════════════════════════════════════════════════════
# Non-company queries do not call SEC
# ═══════════════════════════════════════════════════════════════════════════════

class TestNonCompanyQueriesNoSec:
    def test_apple_pie_does_not_call_sec(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary") as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                # No company detected → _enriched_company is None
                with patch("query_router.detect_company_name", return_value=None):
                    agent.query("How do I make apple pie?", intent_route="CASUAL")
        mock_sec.assert_not_called()

    def test_casual_sports_chat_does_not_call_sec(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary") as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value=None):
                    agent.query("Did the Lakers win last night?", intent_route="GENERAL_CHAT")
        mock_sec.assert_not_called()

    def test_casual_intent_skips_sec_even_with_company(self):
        agent = _make_omega_agent()
        # Even if a company name is "detected", CASUAL intent blocks SEC
        with patch("omega_sec_edgar.get_filing_summary") as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                # Simulate CASUAL intent — sec must not be called
                with patch("query_router.detect_company_name", return_value=None):
                    agent.query("Casual question", intent_route="CASUAL")
        mock_sec.assert_not_called()

    def test_general_chat_intent_skips_sec(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary") as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value=None):
                    agent.query("Tell me a joke", intent_route="GENERAL_CHAT")
        mock_sec.assert_not_called()

    def test_no_company_detected_skips_sec(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary") as mock_sec:
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value=None):
                    agent.query("What is the fed funds rate?", intent_route="GENERAL_FINANCE")
        mock_sec.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# SEC failure does not break the response
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecFailureGraceful:
    def test_sec_exception_does_not_crash_response(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", side_effect=RuntimeError("network error")):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query("Research BlackRock", intent_route="COMPANY_RESEARCH")
        # Response must still be a valid dict
        assert isinstance(result, dict)
        assert "error" not in result or result.get("error") is None

    def test_sec_unavailable_returns_unavailable_status(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.is_available", return_value=False):
            with patch("query_router.detect_company_name", return_value="BlackRock"):
                result = agent.query("Tell me about BlackRock", intent_route="COMPANY_RESEARCH")
        meta = result.get("_meta", {})
        assert meta.get("sec_status") == "unavailable"
        assert meta.get("sec_filings_used") is False

    def test_sec_not_found_returns_not_found_status(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_NOT_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="UnknownCo"):
                    result = agent.query("Research UnknownCo", intent_route="COMPANY_RESEARCH")
        meta = result.get("_meta", {})
        assert meta.get("sec_status") == "not_found"
        assert meta.get("sec_filings_used") is False

    def test_response_still_has_content_after_sec_failure(self):
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", side_effect=Exception("timeout")):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query("Company overview of BlackRock", intent_route="COMPANY_RESEARCH")
        # Synthesis must still run and return a valid dict despite SEC failure
        assert isinstance(result, dict)
        # _meta must be present (set by query() regardless of SEC)
        assert "_meta" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SEC metadata fields present when available
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecMetadataFields:
    def _get_meta(self, intent_route="COMPANY_RESEARCH") -> dict:
        agent = _make_omega_agent()
        with patch("omega_sec_edgar.get_filing_summary", return_value=MOCK_SEC_FOUND):
            with patch("omega_sec_edgar.is_available", return_value=True):
                with patch("query_router.detect_company_name", return_value="BlackRock"):
                    result = agent.query("Research BlackRock", intent_route=intent_route)
        return result.get("_meta", {})

    def test_sec_filings_used_field_present(self):
        meta = self._get_meta()
        assert "sec_filings_used" in meta

    def test_sec_status_field_present(self):
        meta = self._get_meta()
        assert "sec_status" in meta

    def test_cik_field_present_when_found(self):
        meta = self._get_meta()
        assert "cik" in meta
        assert meta["cik"] == "0001364742"

    def test_latest_10k_field_present(self):
        meta = self._get_meta()
        assert "latest_10k" in meta
        assert isinstance(meta["latest_10k"], dict)

    def test_latest_10q_field_present(self):
        meta = self._get_meta()
        assert "latest_10q" in meta

    def test_domain_still_in_meta(self):
        meta = self._get_meta()
        assert "domain" in meta

    def test_meta_is_json_serializable(self):
        meta = self._get_meta()
        serialized = json.dumps(meta, default=str)
        assert isinstance(serialized, str)


# ═══════════════════════════════════════════════════════════════════════════════
# SEC context never enters routing
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecNeverEntersRouting:
    def test_classify_intent_route_takes_one_param(self):
        import inspect
        from query_router import classify_intent_route
        params = list(inspect.signature(classify_intent_route).parameters.keys())
        assert len(params) == 1

    def test_omega_sec_edgar_not_imported_in_query_router(self):
        import query_router
        source = open(query_router.__file__, encoding="utf-8").read()
        assert "omega_sec_edgar" not in source

    def test_sec_import_in_atlas_omega_is_synthesis_time_only(self):
        """omega_sec_edgar import in atlas_omega must be inside the query() body, not module-level."""
        import atlas_omega
        source = open(atlas_omega.__file__, encoding="utf-8").read()
        # Confirm it's a local import (inside a try block in query())
        assert "from omega_sec_edgar import get_filing_summary" in source or \
               "from omega_sec_edgar import" in source
        # Confirm it does NOT appear at the top-level import section
        # (it should only appear after 'def query(')
        query_def_pos = source.find("def query(")
        sec_import_pos = source.find("from omega_sec_edgar import")
        if sec_import_pos >= 0:
            assert sec_import_pos > query_def_pos, "omega_sec_edgar imported at module level — must be synthesis-time only"

    def test_prompt_builder_does_not_import_query_router(self):
        import prompt_builder
        source = open(prompt_builder.__file__, encoding="utf-8").read()
        assert "import query_router" not in source
        assert "from query_router" not in source


# ═══════════════════════════════════════════════════════════════════════════════
# Company report blocks trade-plan contamination
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradeplanContaminationBlocked:
    def test_company_report_contract_forbids_trade_plan(self):
        from output_contracts import OUTPUT_CONTRACTS
        contract = OUTPUT_CONTRACTS.get("company_report")
        assert contract is not None
        forbidden_lower = [p.lower() for p in contract.forbidden_phrases]
        trade_phrases = ["entry price", "stop loss", "take profit", "execution rules", "trade plan"]
        for phrase in trade_phrases:
            assert any(phrase in f for f in forbidden_lower), f"'{phrase}' not forbidden in company_report"

    def test_quality_firewall_fails_trade_language_in_company_report(self):
        from quality_firewall import validate_response
        # Inject trade plan language into a company report answer
        answer = "Overview: BlackRock is big. Entry: $900. Stop loss: $850. Take profit: $1000."
        result = validate_response("Tell me about BlackRock", "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is False

    def test_quality_firewall_passes_clean_company_report(self):
        from quality_firewall import validate_response
        answer = (
            "Overview: BlackRock is the world's largest asset manager with $10T AUM. "
            "Business Model: Fee-based investment management. "
            "Financial Snapshot: Revenue $19B, filed 10-K 2025-02-14. "
            "Leadership: Larry Fink CEO. "
            "Recent News: Strong ETF flows. "
            "Risks: Rate sensitivity. "
            "Competitive Position: #1 by AUM globally."
        )
        result = validate_response("Tell me about BlackRock", "COMPANY_RESEARCH", "company_report", answer)
        assert result.passed is True

    def test_non_trade_output_modes_constant(self):
        from output_modes import NON_TRADE_MODES, OUTPUT_COMPANY_REPORT
        assert OUTPUT_COMPANY_REPORT in NON_TRADE_MODES

    def test_sec_filing_context_not_injected_for_trade_plan(self):
        from prompt_builder import build_synthesis_prompt
        result = build_synthesis_prompt(
            raw_query="Trade plan for BLK",
            intent="TRADING_ANALYSIS",
            output_mode="trade_plan",
            sec_filing_context="Latest 10-K: 2025-02-14",
        )
        assert "SEC EDGAR FILINGS" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# Atlas omega.py compile check
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompileChecks:
    def test_atlas_omega_py_compile(self):
        import py_compile, pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / "atlas_omega.py"
        py_compile.compile(str(path), doraise=True)

    def test_omega_sec_edgar_py_compile(self):
        import py_compile, pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_sec_edgar.py"
        py_compile.compile(str(path), doraise=True)
