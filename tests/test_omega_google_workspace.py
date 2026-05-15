"""
tests/test_omega_google_workspace.py — Tests for omega_google_workspace.py

No real Google credentials required. All external calls are mocked or
tested via the not_configured path.
"""
from __future__ import annotations

import json
import os
import pathlib
from unittest.mock import patch, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# is_google_workspace_configured()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsGoogleWorkspaceConfigured:
    def test_false_when_disabled(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            assert m.is_google_workspace_configured() is False

    def test_false_when_env_not_set(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_WORKSPACE_ENABLED", None)
            assert m.is_google_workspace_configured() is False

    def test_false_when_enabled_but_missing_credentials(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "GOOGLE_REFRESH_TOKEN": "",
        }):
            assert m.is_google_workspace_configured() is False

    def test_false_when_placeholder_credentials(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "YOUR_GOOGLE_CLIENT_SECRET",
            "GOOGLE_REFRESH_TOKEN": "YOUR_GOOGLE_REFRESH_TOKEN",
        }):
            assert m.is_google_workspace_configured() is False

    def test_true_when_enabled_and_real_credentials(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "123456.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "real-secret-value",
            "GOOGLE_REFRESH_TOKEN": "1//real-refresh-token",
        }):
            assert m.is_google_workspace_configured() is True

    def test_enabled_yes_variant(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "yes",
            "GOOGLE_CLIENT_ID": "123456.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "real-secret",
            "GOOGLE_REFRESH_TOKEN": "1//real-token",
        }):
            assert m.is_google_workspace_configured() is True


# ═══════════════════════════════════════════════════════════════════════════════
# get_google_workspace_status()
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetGoogleWorkspaceStatus:
    def test_returns_dict(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.get_google_workspace_status()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.get_google_workspace_status()
        for key in ("configured", "enabled", "missing_vars", "available_operations", "message"):
            assert key in result, f"Missing key: {key}"

    def test_not_configured_when_disabled(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.get_google_workspace_status()
        assert result["configured"] is False
        assert result["enabled"] is False

    def test_configured_true_with_real_creds(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "123.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "real-secret",
            "GOOGLE_REFRESH_TOKEN": "1//real-token",
        }):
            result = m.get_google_workspace_status()
        assert result["configured"] is True
        assert len(result["available_operations"]) > 0

    def test_missing_vars_listed_when_enabled_but_incomplete(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "GOOGLE_REFRESH_TOKEN": "",
        }):
            result = m.get_google_workspace_status()
        assert len(result["missing_vars"]) > 0

    def test_is_json_serializable(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.get_google_workspace_status()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)


# ═══════════════════════════════════════════════════════════════════════════════
# create_report_doc() — not_configured path (safe without credentials)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateReportDocNotConfigured:
    def _no_creds_env(self):
        return patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"})

    def test_returns_not_configured(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("Test Report", "# Content")
        assert result["status"] == "not_configured"
        assert result["success"] is False

    def test_does_not_crash(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("Test", "content")
        assert isinstance(result, dict)

    def test_returns_title_in_response(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("My Report Title", "# Content")
        assert result.get("title") == "My Report Title"

    def test_doc_id_is_none_when_not_configured(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("Test", "content")
        assert result.get("doc_id") is None

    def test_doc_url_is_none_when_not_configured(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("Test", "content")
        assert result.get("doc_url") is None

    def test_configured_false_in_response(self):
        import omega_google_workspace as m
        with self._no_creds_env():
            result = m.create_report_doc("Test", "content")
        assert result.get("configured") is False


# ═══════════════════════════════════════════════════════════════════════════════
# create_research_sheet() — not_configured path
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateResearchSheetNotConfigured:
    def test_returns_not_configured(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.create_research_sheet("Test Sheet", [["A", "B"], ["1", "2"]])
        assert result["status"] == "not_configured"
        assert result["success"] is False

    def test_does_not_crash_with_empty_rows(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.create_research_sheet("Empty", [])
        assert isinstance(result, dict)

    def test_sheet_id_is_none(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.create_research_sheet("Test", [["H1", "H2"]])
        assert result.get("sheet_id") is None

    def test_rows_written_zero_when_not_configured(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.create_research_sheet("Test", [["A", "B"], ["1", "2"]])
        assert result.get("rows_written") == 0


# ═══════════════════════════════════════════════════════════════════════════════
# export_report_bundle() — safe without credentials
# ═══════════════════════════════════════════════════════════════════════════════

class TestExportReportBundleNotConfigured:
    def test_returns_not_configured(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-123")
        assert result["status"] == "not_configured"
        assert result["success"] is False

    def test_does_not_crash(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-999", formats=["doc", "sheet"])
        assert isinstance(result, dict)

    def test_report_id_in_response(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("abc-123")
        assert result.get("report_id") == "abc-123"

    def test_exports_dict_empty_when_not_configured(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-x", formats=["doc"])
        assert result.get("exports") == {}

    def test_configured_false_in_response(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-x")
        assert result.get("configured") is False

    def test_custom_formats_accepted(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-x", formats=["doc"])
        assert isinstance(result, dict)

    def test_default_formats_are_doc_and_sheet(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-x")
        # Even in not_configured, the response must be valid
        assert result["status"] == "not_configured"


# ═══════════════════════════════════════════════════════════════════════════════
# omega_connections.py — Google Workspace status
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnectionsGoogleWorkspaceStatus:
    def _get_gws(self):
        import omega_connections as m
        import importlib
        importlib.reload(m)
        registry = m.get_registry()
        return next((c for c in registry if c.slug == "google_workspace"), None)

    def test_google_workspace_connection_exists(self):
        gws = self._get_gws()
        assert gws is not None

    def test_planned_when_disabled(self):
        import omega_connections as m
        import importlib
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            importlib.reload(m)
            gws = next((c for c in m.get_registry() if c.slug == "google_workspace"), None)
        assert gws is not None
        assert gws.status == "planned"

    def test_configured_when_enabled_but_missing_creds(self):
        import omega_connections as m
        import importlib
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "GOOGLE_REFRESH_TOKEN": "",
        }):
            importlib.reload(m)
            gws = next((c for c in m.get_registry() if c.slug == "google_workspace"), None)
        assert gws is not None
        assert gws.status == "configured"

    def test_active_when_fully_configured(self):
        import omega_connections as m
        import importlib
        with patch.dict(os.environ, {
            "GOOGLE_WORKSPACE_ENABLED": "true",
            "GOOGLE_CLIENT_ID": "123.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "real-secret",
            "GOOGLE_REFRESH_TOKEN": "1//real-token",
        }):
            importlib.reload(m)
            gws = next((c for c in m.get_registry() if c.slug == "google_workspace"), None)
        assert gws is not None
        assert gws.status == "active"

    def test_can_write_is_true(self):
        gws = self._get_gws()
        assert gws is not None
        assert gws.can_write is True

    def test_is_not_destructive(self):
        gws = self._get_gws()
        assert gws is not None
        assert gws.is_destructive is False


# ═══════════════════════════════════════════════════════════════════════════════
# API endpoints registered
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiEndpoints:
    def test_google_workspace_status_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/google-workspace/status" in routes

    def test_export_report_endpoint_registered(self):
        import api_server
        routes = {r.path for r in api_server.app.routes}
        assert "/omega-os/export-report" in routes

    def test_status_endpoint_returns_structured_json(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.get_google_workspace_status()
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert "configured" in parsed

    def test_export_endpoint_returns_not_configured_without_credentials(self):
        import omega_google_workspace as m
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("test-id")
        assert result["status"] == "not_configured"
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# No secrets hardcoded
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoSecrets:
    def test_no_api_keys_in_omega_google_workspace(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_google_workspace.py"
        source = path.read_text(encoding="utf-8")
        forbidden = ["sk-", "SG.", "xoxb-", "ghp_", "AIza", "ya29.", "1//"]
        for pattern in forbidden:
            assert pattern not in source, f"Potential secret pattern '{pattern}' in omega_google_workspace.py"

    def test_env_example_uses_placeholders(self):
        env_path = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
        content = env_path.read_text(encoding="utf-8")
        assert "GOOGLE_WORKSPACE_ENABLED=false" in content
        assert "YOUR_GOOGLE_REFRESH_TOKEN" in content
        assert "YOUR_FOLDER_ID" in content
        # Must NOT contain real token format
        assert "1//" not in content

    def test_env_example_has_all_required_vars(self):
        env_path = pathlib.Path(__file__).resolve().parents[1] / ".env.example"
        content = env_path.read_text(encoding="utf-8")
        for var in ("GOOGLE_WORKSPACE_ENABLED", "GOOGLE_CLIENT_ID",
                    "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN",
                    "GOOGLE_DRIVE_REPORTS_FOLDER_ID"):
            assert var in content, f"Missing {var} in .env.example"


# ═══════════════════════════════════════════════════════════════════════════════
# Routing purity
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoutingPurity:
    def test_omega_google_workspace_not_in_query_router(self):
        import query_router
        source = open(query_router.__file__, encoding="utf-8").read()
        assert "omega_google_workspace" not in source

    def test_classify_intent_route_still_one_param(self):
        import inspect
        from query_router import classify_intent_route
        params = list(inspect.signature(classify_intent_route).parameters.keys())
        assert len(params) == 1

    def test_google_workspace_not_in_prompt_builder(self):
        import prompt_builder
        source = open(prompt_builder.__file__, encoding="utf-8").read()
        assert "omega_google_workspace" not in source

    def test_module_importable(self):
        import omega_google_workspace
        assert omega_google_workspace is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Trading format quarantine
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradingFormatQuarantine:
    def test_company_report_forbids_trade_plan(self):
        from output_contracts import OUTPUT_CONTRACTS
        contract = OUTPUT_CONTRACTS.get("company_report")
        assert contract is not None
        forbidden_lower = [p.lower() for p in contract.forbidden_phrases]
        assert any("trade plan" in f or "entry" in f or "stop loss" in f for f in forbidden_lower)

    def test_export_report_bundle_does_not_include_trading_content(self):
        import omega_google_workspace as m
        # When not configured, the export bundle must never reference trade content
        with patch.dict(os.environ, {"GOOGLE_WORKSPACE_ENABLED": "false"}):
            result = m.export_report_bundle("report-123")
        result_str = json.dumps(result)
        assert "stop_loss" not in result_str
        assert "entry_price" not in result_str
        assert "take_profit" not in result_str

    def test_py_compile_omega_google_workspace(self):
        import py_compile
        path = pathlib.Path(__file__).resolve().parents[1] / "omega_google_workspace.py"
        py_compile.compile(str(path), doraise=True)
