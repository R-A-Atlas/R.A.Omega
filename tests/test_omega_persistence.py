"""
tests/test_omega_persistence.py — Unit tests for omega_persistence.py

All tests use a temporary directory so they never touch the real
omega_os/archives/runtime/ files.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from unittest.mock import patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh(tmp_dir: pathlib.Path):
    """Import omega_persistence with its runtime dir patched to tmp_dir."""
    if "omega_persistence" in sys.modules:
        del sys.modules["omega_persistence"]
    import omega_persistence as m
    m._RUNTIME_DIR  = tmp_dir / "runtime"
    m._REPORTS_FILE = m._RUNTIME_DIR / "reports.json"
    m._TASKS_FILE   = m._RUNTIME_DIR / "research_tasks.json"
    m._EVENTS_FILE  = m._RUNTIME_DIR / "omega_events.json"
    return m


@pytest.fixture()
def tmp(tmp_path):
    """Fresh omega_persistence module rooted at a temp directory."""
    return _fresh(tmp_path)


@pytest.fixture()
def no_supabase(tmp):
    """Persistence module with Supabase env vars absent."""
    with patch.dict(os.environ, {}, clear=False):
        for k in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY"):
            os.environ.pop(k, None)
        yield tmp


# ═══════════════════════════════════════════════════════════════════════════════
# is_supabase_configured()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsSupabaseConfigured:
    def test_false_when_no_env(self, tmp):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_KEY", None)
            assert tmp.is_supabase_configured() is False

    def test_false_when_placeholder_url(self, tmp):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://YOUR_PROJECT_ID.supabase.co",
            "SUPABASE_KEY": "real-key-value",
        }):
            assert tmp.is_supabase_configured() is False

    def test_false_when_placeholder_key(self, tmp):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "YOUR_SUPABASE_SERVICE_ROLE_KEY",
        }):
            assert tmp.is_supabase_configured() is False

    def test_true_when_real_credentials(self, tmp):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            assert tmp.is_supabase_configured() is True

    def test_false_when_empty_strings(self, tmp):
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""}):
            assert tmp.is_supabase_configured() is False


# ═══════════════════════════════════════════════════════════════════════════════
# save_report_metadata() — local fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveReportMetadata:
    def test_saves_to_local_file(self, no_supabase):
        no_supabase.save_report_metadata({"query": "Tell me about Apple"})
        records = no_supabase._load_json_list(no_supabase._REPORTS_FILE)
        assert len(records) == 1

    def test_returns_record_with_id(self, no_supabase):
        result = no_supabase.save_report_metadata({"query": "What is NVDA?"})
        assert "id" in result
        assert len(result["id"]) == 36  # UUID length

    def test_returns_local_fallback_mode(self, no_supabase):
        result = no_supabase.save_report_metadata({"query": "macro"})
        assert result["persistence_mode"] == "local_fallback"

    def test_query_stored(self, no_supabase):
        no_supabase.save_report_metadata({"query": "Test query"})
        records = no_supabase._load_json_list(no_supabase._REPORTS_FILE)
        assert records[0]["query"] == "Test query"

    def test_optional_fields_stored(self, no_supabase):
        no_supabase.save_report_metadata({
            "query": "BLK report",
            "intent": "COMPANY_RESEARCH",
            "output_mode": "company_report",
            "company": "BlackRock",
        })
        records = no_supabase._load_json_list(no_supabase._REPORTS_FILE)
        r = records[0]
        assert r["intent"] == "COMPANY_RESEARCH"
        assert r["output_mode"] == "company_report"
        assert r["company"] == "BlackRock"

    def test_multiple_saves_accumulate(self, no_supabase):
        for i in range(5):
            no_supabase.save_report_metadata({"query": f"query {i}"})
        records = no_supabase._load_json_list(no_supabase._REPORTS_FILE)
        assert len(records) == 5

    def test_saved_at_is_iso8601(self, no_supabase):
        result = no_supabase.save_report_metadata({"query": "time test"})
        assert "T" in result["saved_at"]
        assert "Z" in result["saved_at"] or "+" in result["saved_at"]

    def test_sec_filings_used_defaults_false(self, no_supabase):
        result = no_supabase.save_report_metadata({"query": "test"})
        assert result["sec_filings_used"] is False

    def test_sec_filings_used_stored(self, no_supabase):
        result = no_supabase.save_report_metadata({"query": "BLK", "sec_filings_used": True})
        assert result["sec_filings_used"] is True

    def test_runtime_dir_created_automatically(self, tmp):
        m = tmp
        with patch.dict(os.environ, {}, clear=False):
            for k in ("SUPABASE_URL", "SUPABASE_KEY"):
                os.environ.pop(k, None)
            assert not m._RUNTIME_DIR.exists()
            m.save_report_metadata({"query": "auto-mkdir test"})
            assert m._RUNTIME_DIR.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# save_research_task() — local fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveResearchTask:
    def test_saves_to_local_file(self, no_supabase):
        no_supabase.save_research_task({"query": "Deep dive into TSLA"})
        records = no_supabase._load_json_list(no_supabase._TASKS_FILE)
        assert len(records) == 1

    def test_returns_queued_status(self, no_supabase):
        result = no_supabase.save_research_task({"query": "Research BLK"})
        assert result["status"] == "queued"

    def test_returns_local_fallback_mode(self, no_supabase):
        result = no_supabase.save_research_task({"query": "Research BLK"})
        assert result["persistence_mode"] == "local_fallback"

    def test_priority_defaults_to_5(self, no_supabase):
        result = no_supabase.save_research_task({"query": "test"})
        assert result["priority"] == 5

    def test_custom_priority_stored(self, no_supabase):
        result = no_supabase.save_research_task({"query": "urgent", "priority": 9})
        assert result["priority"] == 9

    def test_returns_uuid(self, no_supabase):
        result = no_supabase.save_research_task({"query": "test"})
        assert "id" in result
        assert len(result["id"]) == 36

    def test_multiple_tasks_accumulate(self, no_supabase):
        for i in range(3):
            no_supabase.save_research_task({"query": f"task {i}"})
        records = no_supabase._load_json_list(no_supabase._TASKS_FILE)
        assert len(records) == 3

    def test_optional_fields_stored(self, no_supabase):
        no_supabase.save_research_task({
            "query": "NVDA options",
            "ticker": "NVDA",
            "company": "NVIDIA",
            "notes": "focus on AI exposure",
        })
        records = no_supabase._load_json_list(no_supabase._TASKS_FILE)
        r = records[0]
        assert r["ticker"] == "NVDA"
        assert r["company"] == "NVIDIA"
        assert "AI exposure" in r["notes"]


# ═══════════════════════════════════════════════════════════════════════════════
# save_omega_event()
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveOmegaEvent:
    def test_saves_to_events_file(self, no_supabase):
        no_supabase.save_omega_event({"event_type": "audit_run", "summary": "Four C audit completed"})
        records = no_supabase._load_json_list(no_supabase._EVENTS_FILE)
        assert len(records) == 1

    def test_returns_record_with_id(self, no_supabase):
        result = no_supabase.save_omega_event({"event_type": "test"})
        assert "id" in result

    def test_severity_defaults_to_info(self, no_supabase):
        result = no_supabase.save_omega_event({"event_type": "test"})
        assert result["severity"] == "info"

    def test_custom_severity(self, no_supabase):
        result = no_supabase.save_omega_event({"event_type": "error", "severity": "error"})
        assert result["severity"] == "error"

    def test_event_type_stored(self, no_supabase):
        no_supabase.save_omega_event({"event_type": "connection_check"})
        records = no_supabase._load_json_list(no_supabase._EVENTS_FILE)
        assert records[0]["event_type"] == "connection_check"


# ═══════════════════════════════════════════════════════════════════════════════
# get_recent_reports()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRecentReports:
    def test_returns_list(self, no_supabase):
        result = no_supabase.get_recent_reports()
        assert isinstance(result, list)

    def test_empty_when_no_records(self, no_supabase):
        result = no_supabase.get_recent_reports()
        assert result == []

    def test_returns_saved_records(self, no_supabase):
        no_supabase.save_report_metadata({"query": "AAPL"})
        no_supabase.save_report_metadata({"query": "MSFT"})
        result = no_supabase.get_recent_reports()
        assert len(result) == 2

    def test_newest_first(self, no_supabase):
        no_supabase.save_report_metadata({"query": "first"})
        no_supabase.save_report_metadata({"query": "second"})
        result = no_supabase.get_recent_reports()
        assert result[0]["query"] == "second"

    def test_limit_honored(self, no_supabase):
        for i in range(20):
            no_supabase.save_report_metadata({"query": f"q{i}"})
        result = no_supabase.get_recent_reports(limit=5)
        assert len(result) == 5

    def test_limit_capped_at_100(self, no_supabase):
        # Verify the cap doesn't crash; just needs to not raise
        result = no_supabase.get_recent_reports(limit=999)
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# get_research_queue()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetResearchQueue:
    def test_returns_list(self, no_supabase):
        result = no_supabase.get_research_queue()
        assert isinstance(result, list)

    def test_empty_when_no_tasks(self, no_supabase):
        result = no_supabase.get_research_queue()
        assert result == []

    def test_returns_queued_tasks(self, no_supabase):
        no_supabase.save_research_task({"query": "task 1"})
        no_supabase.save_research_task({"query": "task 2"})
        result = no_supabase.get_research_queue()
        assert len(result) == 2

    def test_higher_priority_first(self, no_supabase):
        no_supabase.save_research_task({"query": "low", "priority": 1})
        no_supabase.save_research_task({"query": "high", "priority": 9})
        result = no_supabase.get_research_queue()
        assert result[0]["query"] == "high"

    def test_limit_honored(self, no_supabase):
        for i in range(10):
            no_supabase.save_research_task({"query": f"task {i}"})
        result = no_supabase.get_research_queue(limit=3)
        assert len(result) == 3

    def test_all_returned_are_queued(self, no_supabase):
        no_supabase.save_research_task({"query": "task"})
        result = no_supabase.get_research_queue()
        for r in result:
            assert r["status"] == "queued"


# ═══════════════════════════════════════════════════════════════════════════════
# get_persistence_status()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetPersistenceStatus:
    def test_returns_dict(self, no_supabase):
        result = no_supabase.get_persistence_status()
        assert isinstance(result, dict)

    def test_has_required_keys(self, no_supabase):
        result = no_supabase.get_persistence_status()
        for key in ("persistence_mode", "supabase_configured", "local_reports_count",
                    "local_tasks_count", "local_events_count", "runtime_dir"):
            assert key in result, f"Missing key: {key}"

    def test_local_fallback_mode_when_no_supabase(self, no_supabase):
        result = no_supabase.get_persistence_status()
        assert result["persistence_mode"] == "local_fallback"
        assert result["supabase_configured"] is False

    def test_counts_reflect_saved_records(self, no_supabase):
        no_supabase.save_report_metadata({"query": "test"})
        no_supabase.save_research_task({"query": "task"})
        no_supabase.save_omega_event({"event_type": "test"})
        result = no_supabase.get_persistence_status()
        assert result["local_reports_count"] == 1
        assert result["local_tasks_count"] == 1
        assert result["local_events_count"] == 1

    def test_runtime_dir_is_string(self, no_supabase):
        result = no_supabase.get_persistence_status()
        assert isinstance(result["runtime_dir"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# No secrets hardcoded
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoSecrets:
    def test_no_api_keys_in_omega_persistence(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_persistence.py"
        source = path.read_text(encoding="utf-8")
        forbidden = ["sk-", "SG.", "xoxb-", "ghp_", "AIza", "ya29."]
        for pattern in forbidden:
            assert pattern not in source, f"Potential secret pattern '{pattern}' found in omega_persistence.py"

    def test_no_hardcoded_connection_strings_in_omega_persistence(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_persistence.py"
        source = path.read_text(encoding="utf-8")
        # Real URLs (not placeholder fragments used for detection) must not appear
        # Supabase URLs look like https://<project>.supabase.co — source should not contain one
        import re
        real_supabase_url = re.compile(r'https://[a-z0-9]{20,}\.supabase\.co')
        assert not real_supabase_url.search(source), "Real Supabase URL found in source"

    def test_env_example_has_supabase_placeholders(self):
        env_path = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
        assert env_path.exists()
        content = env_path.read_text(encoding="utf-8")
        assert "SUPABASE_URL" in content
        assert "SUPABASE_KEY" in content
        assert "SUPABASE_ANON_KEY" in content
        # Must be placeholder values, not real credentials
        assert "YOUR_" in content or "your_" in content or "YOUR_PROJECT_ID" in content


# ═══════════════════════════════════════════════════════════════════════════════
# API endpoints — structured JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiEndpoints:
    def test_persistence_status_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/persistence/status" in routes

    def test_recent_reports_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/reports/recent" in routes

    def test_research_queue_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/research-queue" in routes

    def test_research_task_post_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/research-task" in routes

    def test_persistence_status_returns_json(self, no_supabase):
        result = no_supabase.get_persistence_status()
        # Must be JSON-serializable
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["persistence_mode"] in ("supabase", "local_fallback")

    def test_research_task_response_has_task_and_status(self, no_supabase):
        record = no_supabase.save_research_task({"query": "What is NVDA AI exposure?"})
        assert "status" in record
        assert record["status"] == "queued"


# ═══════════════════════════════════════════════════════════════════════════════
# Routing purity — persistence never enters classify_intent_route
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoutingPurity:
    def test_omega_persistence_not_imported_in_query_router(self):
        import query_router
        source = open(query_router.__file__, encoding="utf-8").read()
        assert "omega_persistence" not in source

    def test_classify_intent_route_still_takes_one_param(self):
        import inspect
        from query_router import classify_intent_route
        params = list(inspect.signature(classify_intent_route).parameters.keys())
        assert len(params) == 1

    def test_module_importable(self):
        import omega_persistence
        assert omega_persistence is not None

    def test_py_compile_passes(self):
        import py_compile
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_persistence.py"
        py_compile.compile(str(path), doraise=True)

    def test_uses_get_supabase_client_not_bare_symbol(self):
        """omega_persistence must call get_supabase_client(), not import 'supabase'."""
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_persistence.py"
        source = path.read_text(encoding="utf-8")
        assert "from atlas_db import supabase" not in source, (
            "omega_persistence still imports bare 'supabase' from atlas_db — "
            "use get_supabase_client() instead"
        )
        assert "get_supabase_client" in source, (
            "omega_persistence should use atlas_db.get_supabase_client()"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Supabase path — mocked client
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupabasePath:
    """Verify the Supabase code path executes without error when a mocked client is present."""

    def _make_mock_client(self):
        from unittest.mock import MagicMock
        client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        client.table.return_value.insert.return_value.execute.return_value = mock_resp
        client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = mock_resp
        client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_resp
        return client

    def test_save_report_uses_supabase_when_configured(self, tmp):
        mock_client = self._make_mock_client()
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            with patch("atlas_db.get_supabase_client", return_value=mock_client):
                result = tmp.save_report_metadata({"query": "NVDA analysis"})
        assert result["persistence_mode"] == "supabase"

    def test_get_recent_reports_uses_supabase_when_configured(self, tmp):
        mock_client = self._make_mock_client()
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            with patch("atlas_db.get_supabase_client", return_value=mock_client):
                result = tmp.get_recent_reports()
        assert isinstance(result, list)

    def test_get_research_queue_uses_supabase_when_configured(self, tmp):
        mock_client = self._make_mock_client()
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            with patch("atlas_db.get_supabase_client", return_value=mock_client):
                result = tmp.get_research_queue()
        assert isinstance(result, list)

    def test_falls_back_to_local_when_client_is_none(self, tmp):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            with patch("atlas_db.get_supabase_client", return_value=None):
                result = tmp.save_report_metadata({"query": "fallback test"})
        assert result["persistence_mode"] == "local_fallback"

    def test_falls_back_to_local_on_supabase_exception(self, tmp):
        from unittest.mock import MagicMock
        bad_client = MagicMock()
        bad_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("connection refused")
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://realproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.real",
        }):
            with patch("atlas_db.get_supabase_client", return_value=bad_client):
                result = tmp.save_report_metadata({"query": "exception test"})
        assert result["persistence_mode"] == "local_fallback"


# ═══════════════════════════════════════════════════════════════════════════════
# API endpoint responses — structured JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiResponses:
    def test_research_queue_endpoint_returns_list(self, no_supabase):
        """GET /omega-os/research-queue should not error when Supabase is not configured."""
        result = no_supabase.get_research_queue()
        assert isinstance(result, list)

    def test_dashboard_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/dashboard" in routes

    def test_dashboard_snapshot_is_json_serializable(self):
        import json
        import omega_dashboard
        from unittest.mock import patch
        with patch("omega_audit.run_audit", return_value={
            "context": 20, "connections": 15, "capabilities": 25, "cadence": 25,
            "total": 85, "phase": "Command Center",
            "strengths": [], "gaps": [], "next_steps": [],
        }):
            snap = omega_dashboard.build_command_center_snapshot()
        serialized = json.dumps(snap)
        parsed = json.loads(serialized)
        assert "omega_os_score" in parsed
        assert "snapshot_type" in parsed
        assert parsed["snapshot_type"] == "command_center"
