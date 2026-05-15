"""
tests/test_omega_sec_edgar.py — Unit tests for omega_sec_edgar.py

All SEC EDGAR network calls are mocked — no live requests made.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_TICKERS: dict[str, dict] = {
    "0": {"cik_str": "1364742", "ticker": "BLK",  "title": "BlackRock Inc."},
    "1": {"cik_str": "789019",  "ticker": "MSFT", "title": "Microsoft Corp"},
    "2": {"cik_str": "320193",  "ticker": "AAPL", "title": "Apple Inc."},
}

MOCK_SUBMISSIONS: dict[str, Any] = {
    "name": "BlackRock Inc.",
    "cik": "1364742",
    "sic": "6282",
    "stateOfIncorporation": "DE",
    "fiscalYearEnd": "1231",
    "filings": {
        "recent": {
            "form":            ["10-K", "10-Q", "10-Q", "8-K", "8-K"],
            "filingDate":      ["2025-02-14", "2024-11-12", "2024-08-09", "2025-01-15", "2024-12-01"],
            "accessionNumber": [
                "0001364742-25-000010",
                "0001364742-24-000055",
                "0001364742-24-000033",
                "0001364742-25-000001",
                "0001364742-24-000099",
            ],
            "primaryDocument": ["blk-10k.htm", "blk-10q.htm", "blk-10q-q2.htm", "blk-8k.htm", "blk-8k-dec.htm"],
            "items":           ["Annual Report", "Quarterly Report", "Quarterly Report", "Earnings Release", "Board Change"],
        }
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_module():
    """Import omega_sec_edgar with a clean lru_cache (reload each time)."""
    if "omega_sec_edgar" in sys.modules:
        del sys.modules["omega_sec_edgar"]
    import omega_sec_edgar  # noqa: PLC0415
    # Clear any session-level CIK cache
    omega_sec_edgar._cik_cache.clear()
    return omega_sec_edgar


# ═══════════════════════════════════════════════════════════════════════════════
# CIK normalization
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeCik:
    def test_pads_short_cik(self):
        import omega_sec_edgar
        assert omega_sec_edgar._normalize_cik("12345") == "0000012345"

    def test_pads_integer(self):
        import omega_sec_edgar
        assert omega_sec_edgar._normalize_cik(789019) == "0000789019"

    def test_already_padded_passthrough(self):
        import omega_sec_edgar
        assert omega_sec_edgar._normalize_cik("0001364742") == "0001364742"

    def test_strips_whitespace(self):
        import omega_sec_edgar
        assert omega_sec_edgar._normalize_cik(" 999 ") == "0000000999"


# ═══════════════════════════════════════════════════════════════════════════════
# is_available()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsAvailable:
    def test_false_when_env_not_set(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEC_USER_AGENT", None)
            assert omega_sec_edgar.is_available() is False

    def test_false_when_placeholder(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {"SEC_USER_AGENT": "R.A. Omega contact@example.com"}):
            assert omega_sec_edgar.is_available() is False

    def test_true_when_real_agent(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {"SEC_USER_AGENT": "MyApp admin@mycompany.com"}):
            assert omega_sec_edgar.is_available() is True

    def test_false_when_empty_string(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {"SEC_USER_AGENT": "   "}):
            assert omega_sec_edgar.is_available() is False


# ═══════════════════════════════════════════════════════════════════════════════
# _get_user_agent()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUserAgent:
    def test_returns_env_value(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {"SEC_USER_AGENT": "TestApp test@test.com"}):
            assert omega_sec_edgar._get_user_agent() == "TestApp test@test.com"

    def test_returns_default_when_not_set(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEC_USER_AGENT", None)
            ua = omega_sec_edgar._get_user_agent()
            assert "omega" in ua.lower() or "example.com" in ua.lower()

    def test_strips_whitespace(self):
        import omega_sec_edgar
        with patch.dict(os.environ, {"SEC_USER_AGENT": "  MyApp admin@test.com  "}):
            assert omega_sec_edgar._get_user_agent() == "MyApp admin@test.com"


# ═══════════════════════════════════════════════════════════════════════════════
# search_company_cik()
# ═══════════════════════════════════════════════════════════════════════════════

class TestSearchCompanyCik:
    def _mock_ticker_data(self):
        result = {}
        for entry in MOCK_TICKERS.values():
            ticker = entry["ticker"].upper()
            title  = entry["title"].lower()
            cik    = str(entry["cik_str"])
            result[ticker] = {"cik": cik, "ticker": ticker, "title": title}
            result[title]  = {"cik": cik, "ticker": ticker, "title": title}
        return result

    def test_ticker_lookup_exact(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("BLK")
        assert cik == "0001364742"

    def test_ticker_case_insensitive(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("blk")
        assert cik == "0001364742"

    def test_name_lookup_lowercase(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("blackrock inc.")
        assert cik == "0001364742"

    def test_partial_name_match(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("BlackRock")
        # Either exact or partial match — must return a CIK
        assert cik is not None
        assert len(cik) == 10

    def test_not_found_returns_none(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("ZZNOTACOMPANY99")
        assert cik is None

    def test_empty_ticker_map_returns_none(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value={}):
            cik = mod.search_company_cik("MSFT")
        assert cik is None

    def test_cik_result_zero_padded(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()):
            cik = mod.search_company_cik("AAPL")
        assert cik == "0000320193"

    def test_cache_used_on_second_call(self):
        mod = _fresh_module()
        with patch.object(mod, "_load_company_tickers", return_value=self._mock_ticker_data()) as mock_load:
            mod.search_company_cik("BLK")
            mod.search_company_cik("BLK")
        # _load_company_tickers called — but _cik_cache should short-circuit the second lookup
        assert "BLK" in mod._cik_cache


# ═══════════════════════════════════════════════════════════════════════════════
# get_company_submissions()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCompanySubmissions:
    def test_returns_dict_on_success(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_company_submissions("1364742")
        assert isinstance(result, dict)
        assert result["name"] == "BlackRock Inc."

    def test_returns_none_on_failure(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=None):
            result = omega_sec_edgar.get_company_submissions("1364742")
        assert result is None

    def test_returns_none_for_non_dict_response(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=["unexpected"]):
            result = omega_sec_edgar.get_company_submissions("1364742")
        assert result is None

    def test_url_uses_zero_padded_cik(self):
        import omega_sec_edgar
        captured_urls: list[str] = []

        def _capture(url, **kwargs):
            captured_urls.append(url)
            return MOCK_SUBMISSIONS

        with patch.object(omega_sec_edgar, "_rate_limited_get", side_effect=_capture):
            omega_sec_edgar.get_company_submissions("12345")

        assert len(captured_urls) == 1
        assert "0000012345" in captured_urls[0]


# ═══════════════════════════════════════════════════════════════════════════════
# get_recent_filings()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRecentFilings:
    def test_returns_10k_10q_8k_by_default(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742")
        assert "10-K" in result
        assert "10-Q" in result
        assert "8-K" in result

    def test_10k_present_and_dated(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742")
        assert len(result["10-K"]) >= 1
        assert result["10-K"][0]["filing_date"] == "2025-02-14"

    def test_10q_multiple_entries(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742")
        assert len(result["10-Q"]) == 2

    def test_max_per_form_honored(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742", max_per_form=1)
        assert len(result["10-Q"]) == 1

    def test_document_url_format(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742")
        url = result["10-K"][0]["document_url"]
        assert "sec.gov" in url
        assert "blk-10k.htm" in url

    def test_empty_on_failed_submissions(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=None):
            result = omega_sec_edgar.get_recent_filings("1364742")
        assert result["10-K"] == []
        assert result["10-Q"] == []
        assert result["8-K"] == []

    def test_custom_forms(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742", forms=["10-K"])
        assert "10-K" in result
        assert "10-Q" not in result
        assert "8-K" not in result

    def test_filing_dict_has_required_keys(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "get_company_submissions", return_value=MOCK_SUBMISSIONS):
            result = omega_sec_edgar.get_recent_filings("1364742")
        for form_list in result.values():
            for filing in form_list:
                assert "form" in filing
                assert "filing_date" in filing
                assert "accession_number" in filing
                assert "description" in filing
                assert "document_url" in filing
                assert "index_url" in filing


# ═══════════════════════════════════════════════════════════════════════════════
# get_filing_summary()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetFilingSummary:
    def _mock_all(self, mod=None):
        """Return patch context that mocks CIK lookup and submissions."""
        import omega_sec_edgar as m
        if mod:
            m = mod

        ticker_data = {}
        for entry in MOCK_TICKERS.values():
            ticker = entry["ticker"].upper()
            title  = entry["title"].lower()
            cik    = str(entry["cik_str"])
            ticker_data[ticker] = {"cik": cik, "ticker": ticker, "title": title}
            ticker_data[title]  = {"cik": cik, "ticker": ticker, "title": title}
        return ticker_data

    def test_returns_all_keys(self):
        import omega_sec_edgar
        td = self._mock_all()
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        for key in ("company", "cik", "sec_filings_used", "latest_10k",
                    "latest_10q", "latest_8k", "all_recent", "error", "filing_context"):
            assert key in result, f"Missing key: {key}"

    def test_sec_filings_used_true_when_filings_found(self):
        import omega_sec_edgar
        td = self._mock_all()
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert result["sec_filings_used"] is True

    def test_latest_10k_populated(self):
        import omega_sec_edgar
        td = self._mock_all()
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert result["latest_10k"] is not None
        assert result["latest_10k"]["filing_date"] == "2025-02-14"

    def test_error_set_when_company_not_found(self):
        import omega_sec_edgar
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value={}):
            omega_sec_edgar._cik_cache.clear()
            result = omega_sec_edgar.get_filing_summary("ZZNOTEXIST")
        assert result["error"] is not None
        assert result["sec_filings_used"] is False

    def test_filing_context_contains_cik(self):
        import omega_sec_edgar
        td = self._mock_all()
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert result["cik"] in result["filing_context"]

    def test_filing_context_mentions_10k_date(self):
        import omega_sec_edgar
        td = self._mock_all()
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=MOCK_SUBMISSIONS):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert "2025-02-14" in result["filing_context"]

    def test_no_filings_returns_fallback_context(self):
        import omega_sec_edgar
        td = self._mock_all()
        empty_subs = {
            "name": "TestCo",
            "cik": "1364742",
            "filings": {"recent": {"form": [], "filingDate": [], "accessionNumber": [], "primaryDocument": [], "items": []}}
        }
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=empty_subs):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert "No recent" in result["filing_context"] or result["filing_context"] != ""

    def test_sec_filings_used_false_when_no_filings(self):
        import omega_sec_edgar
        td = self._mock_all()
        empty_subs = {
            "name": "TestCo",
            "cik": "1364742",
            "filings": {"recent": {"form": [], "filingDate": [], "accessionNumber": [], "primaryDocument": [], "items": []}}
        }
        with patch.object(omega_sec_edgar, "_load_company_tickers", return_value=td):
            with patch.object(omega_sec_edgar, "_rate_limited_get", return_value=empty_subs):
                omega_sec_edgar._cik_cache.clear()
                result = omega_sec_edgar.get_filing_summary("BLK")
        assert result["sec_filings_used"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# prompt_builder integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptBuilderSECIntegration:
    def test_sec_context_injected_for_company_report(self):
        from prompt_builder import build_synthesis_prompt
        result = build_synthesis_prompt(
            raw_query="Tell me about BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            sec_filing_context="Latest 10-K filed 2025-02-14",
        )
        assert "SEC EDGAR" in result
        assert "2025-02-14" in result

    def test_sec_context_NOT_injected_for_trade_plan(self):
        from prompt_builder import build_synthesis_prompt
        result = build_synthesis_prompt(
            raw_query="Trade plan for BLK",
            intent="TRADING_ANALYSIS",
            output_mode="trade_plan",
            sec_filing_context="Latest 10-K filed 2025-02-14",
        )
        assert "SEC EDGAR FILINGS" not in result

    def test_sec_context_NOT_injected_for_chat(self):
        from prompt_builder import build_synthesis_prompt
        result = build_synthesis_prompt(
            raw_query="What is BlackRock?",
            intent="GENERAL_CHAT",
            output_mode="chat",
            sec_filing_context="Latest 10-K filed 2025-02-14",
        )
        assert "SEC EDGAR FILINGS" not in result

    def test_empty_sec_context_no_injection(self):
        from prompt_builder import build_synthesis_prompt
        result = build_synthesis_prompt(
            raw_query="Tell me about BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            sec_filing_context="",
        )
        assert "SEC EDGAR FILINGS" not in result

    def test_meta_returns_sec_keys(self):
        from prompt_builder import build_synthesis_prompt_meta
        prompt, meta = build_synthesis_prompt_meta(
            raw_query="Tell me about BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            include_sec_filings=False,
        )
        assert "sec_filings_used" in meta
        assert "latest_10k" in meta
        assert "latest_10q" in meta
        assert "latest_8k" in meta

    def test_meta_sec_filings_used_false_when_not_requested(self):
        from prompt_builder import build_synthesis_prompt_meta
        _, meta = build_synthesis_prompt_meta(
            raw_query="Tell me about BlackRock",
            intent="COMPANY_RESEARCH",
            output_mode="company_report",
            include_sec_filings=False,
        )
        assert meta["sec_filings_used"] is False

    def test_meta_sec_filings_only_for_company_report(self):
        from prompt_builder import build_synthesis_prompt_meta
        _, meta = build_synthesis_prompt_meta(
            raw_query="What is the fed rate?",
            intent="GENERAL_FINANCE",
            output_mode="finance_answer",
            include_sec_filings=True,
            company_name="BlackRock",
        )
        # Not a company_report — SEC filings must not be used
        assert meta["sec_filings_used"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Routing purity — SEC never enters classify_intent_route
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoutingPurity:
    def test_classify_intent_route_takes_only_raw_query(self):
        import inspect
        from query_router import classify_intent_route
        params = list(inspect.signature(classify_intent_route).parameters.keys())
        assert len(params) == 1, f"Expected 1 param, got {params}"
        forbidden = {"sec", "filing", "context", "omega", "memory", "edgar"}
        for p in params:
            for f in forbidden:
                assert f not in p.lower(), f"Forbidden keyword '{f}' in param name '{p}'"

    def test_omega_sec_edgar_not_imported_in_query_router(self):
        import query_router
        source = open(query_router.__file__, encoding="utf-8").read()
        assert "omega_sec_edgar" not in source

    def test_sec_filing_context_not_passed_to_routing(self):
        """prompt_builder must not import query_router — routing is always upstream."""
        import prompt_builder
        source = open(prompt_builder.__file__, encoding="utf-8").read()
        # prompt_builder must never import the router module
        assert "import query_router" not in source
        assert "from query_router" not in source


# ═══════════════════════════════════════════════════════════════════════════════
# omega_connections — SEC EDGAR status
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnectionsSecStatus:
    def _get_sec(self, mod=None):
        import omega_connections as m
        if mod:
            m = mod
        registry = m.get_registry()
        return next((c for c in registry if c.slug == "sec_edgar"), None)

    def test_sec_edgar_connection_exists(self):
        sec = self._get_sec()
        assert sec is not None

    def test_sec_edgar_active_when_real_agent(self):
        import omega_connections as m
        import importlib
        with patch.dict(os.environ, {"SEC_USER_AGENT": "TestApp admin@mycompany.com"}):
            importlib.reload(m)
            sec = self._get_sec(m)
        assert sec is not None
        assert sec.status == "active"

    def test_sec_edgar_configured_when_placeholder(self):
        import omega_connections as m
        import importlib
        with patch.dict(os.environ, {"SEC_USER_AGENT": "R.A. Omega contact@example.com"}):
            importlib.reload(m)
            sec = self._get_sec(m)
        assert sec is not None
        assert sec.status in ("configured", "planned")

    def test_sec_edgar_no_write(self):
        sec = self._get_sec()
        assert sec is not None
        assert sec.can_write is False
        assert sec.is_destructive is False


# ═══════════════════════════════════════════════════════════════════════════════
# Module import and API endpoint registration
# ═══════════════════════════════════════════════════════════════════════════════

class TestModuleImport:
    def test_omega_sec_edgar_importable(self):
        import omega_sec_edgar
        assert omega_sec_edgar is not None

    def test_required_functions_present(self):
        import omega_sec_edgar
        for fn in ("search_company_cik", "get_company_submissions",
                   "get_recent_filings", "get_filing_summary", "is_available"):
            assert hasattr(omega_sec_edgar, fn), f"Missing function: {fn}"

    def test_api_server_has_sec_endpoint(self):
        import api_server
        routes = [r.path for r in api_server.app.routes]
        sec_routes = [r for r in routes if "sec" in r.lower()]
        assert len(sec_routes) >= 1, f"No SEC endpoint found in routes: {routes}"

    def test_env_example_has_sec_user_agent(self):
        import pathlib
        env_example = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
        assert env_example.exists()
        content = env_example.read_text(encoding="utf-8")
        assert "SEC_USER_AGENT" in content

    def test_py_compile_omega_sec_edgar(self):
        import py_compile, pathlib
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_sec_edgar.py"
        py_compile.compile(str(path), doraise=True)
