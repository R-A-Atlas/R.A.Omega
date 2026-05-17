from __future__ import annotations

from omega_agents.supabase_health_agent.implementation import run_supabase_health as mod


def test_supabase_health_report_mentions_schema_and_auth_checks(monkeypatch):
    monkeypatch.setattr(mod, "_check_health_endpoint", lambda: mod.HealthCheck("GET /health endpoint", True, "HTTP 200"))
    monkeypatch.setattr(mod, "_check_supabase_schema", lambda live=False: mod.HealthCheck("Supabase schema probe", True, "Configured"))

    result = mod.run(write_output=False)

    assert result.success
    assert "Supabase schema probe" in result.report
    assert "Authenticated GET /sessions" in result.report
    assert "Authenticated GET /watchlist" in result.report
    assert "Production Auth Flow Checklist" in result.report


def test_supabase_health_skips_auth_without_token(monkeypatch):
    monkeypatch.setattr(mod, "_check_health_endpoint", lambda: mod.HealthCheck("GET /health endpoint", True, "HTTP 200"))
    monkeypatch.setattr(mod, "_check_supabase_schema", lambda live=False: mod.HealthCheck("Supabase schema probe", True, "Configured"))

    result = mod.run(write_output=False, bearer_token="")

    auth_checks = [check for check in result.checks if check.name.startswith("Authenticated")]
    assert auth_checks
    assert all(check.passed for check in auth_checks)
    assert all("Skipped" in check.detail for check in auth_checks)


def test_supabase_health_watchlist_roundtrip_uses_safe_test_ticker(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(path, *, bearer_token="", method="GET", body=None):
        calls.append((path, method, body))
        return 200, '{"ok":true}'

    monkeypatch.setattr(mod, "_request_json", fake_request)

    check = mod._check_watchlist_roundtrip(bearer_token="token")

    assert check.passed
    assert ("/watchlist", "POST", {"ticker": "OMEGATEST"}) in calls
    assert ("/watchlist/OMEGATEST", "DELETE", None) in calls
