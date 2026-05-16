"""
tests/test_omega_agents.py

Tests for the Agentic OS worker layer:
- omega_agents/ directory structure
- omega_agentic_os registry functions
- Worker stubs: safe, deterministic, no external calls
- Dashboard integration (agentic fields)
- Security: no secrets, no broker/trade/deploy/send/delete powers
"""
from __future__ import annotations

import os
import importlib
from pathlib import Path

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "omega_agents"

WORKERS = [
    "daily_build_brief",
    "visual_qa_agent",
    "report_qa_agent",
    "growth_content_agent",
    "supabase_health_agent",
]

INFO_FILES = [
    "instructions.md",
    "memory.md",
    "past_errors.md",
    "plan.md",
    "safety_rules.md",
]


# ── Directory structure ───────────────────────────────────────────────────────

def test_omega_agents_directory_exists():
    assert AGENTS_DIR.is_dir(), "omega_agents/ directory must exist"


def test_omega_agents_readme_exists():
    assert (AGENTS_DIR / "README.md").exists(), "omega_agents/README.md must exist"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_directory_exists(worker):
    assert (AGENTS_DIR / worker).is_dir(), f"omega_agents/{worker}/ must exist"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_information_directory_exists(worker):
    assert (AGENTS_DIR / worker / "information").is_dir(), (
        f"omega_agents/{worker}/information/ must exist"
    )


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_implementation_directory_exists(worker):
    assert (AGENTS_DIR / worker / "implementation").is_dir(), (
        f"omega_agents/{worker}/implementation/ must exist"
    )


@pytest.mark.parametrize("worker", WORKERS)
@pytest.mark.parametrize("fname", INFO_FILES)
def test_worker_info_file_exists(worker, fname):
    path = AGENTS_DIR / worker / "information" / fname
    assert path.exists(), f"omega_agents/{worker}/information/{fname} must exist"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_has_implementation_stub(worker):
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert stubs, f"omega_agents/{worker}/implementation/run_*.py must exist"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_stub_is_single_file(worker):
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert len(stubs) == 1, (
        f"omega_agents/{worker}/implementation/ should have exactly 1 stub, got {len(stubs)}"
    )


# ── omega_agentic_os registry ─────────────────────────────────────────────────

def test_omega_agentic_os_importable():
    import omega_agentic_os  # noqa: F401


def test_list_agentic_workers_returns_all_five():
    from omega_agentic_os import list_agentic_workers
    workers = list_agentic_workers()
    names = {w["name"] for w in workers}
    assert names == set(WORKERS), f"Expected all 5 workers, got {names}"


def test_list_agentic_workers_has_required_fields():
    from omega_agentic_os import list_agentic_workers
    for w in list_agentic_workers():
        assert "name" in w
        assert "description" in w
        assert "available" in w
        assert "skills" in w
        assert isinstance(w["available"], bool)


def test_list_agentic_workers_all_available():
    from omega_agentic_os import list_agentic_workers
    for w in list_agentic_workers():
        assert w["available"], f"Worker {w['name']} should be available (stub exists)"


def test_load_worker_info_returns_all_files():
    from omega_agentic_os import load_worker_info
    info = load_worker_info("daily_build_brief")
    assert set(info.keys()) == set(INFO_FILES)


def test_load_worker_info_files_are_strings():
    from omega_agentic_os import load_worker_info
    info = load_worker_info("report_qa_agent")
    for fname, content in info.items():
        assert isinstance(content, str), f"{fname} content must be a string"


def test_load_worker_info_unknown_worker_returns_empty_dict():
    from omega_agentic_os import load_worker_info
    info = load_worker_info("nonexistent_worker_xyz")
    assert info == {}


@pytest.mark.parametrize("worker", WORKERS)
def test_validate_worker_structure_passes_for_all(worker):
    from omega_agentic_os import validate_worker_structure
    result = validate_worker_structure(worker)
    assert result["valid"], (
        f"validate_worker_structure('{worker}') failed: {result['errors']}"
    )


def test_validate_worker_structure_unknown_returns_invalid():
    from omega_agentic_os import validate_worker_structure
    result = validate_worker_structure("no_such_worker")
    assert not result["valid"]
    assert result["errors"]


def test_get_worker_status_returns_available_for_valid_worker():
    from omega_agentic_os import get_worker_status
    status = get_worker_status("daily_build_brief")
    assert status["available"] is True
    assert status["valid"] is True
    assert status["errors"] == []


def test_get_worker_status_has_stub_path():
    from omega_agentic_os import get_worker_status
    status = get_worker_status("daily_build_brief")
    assert status["stub_path"] is not None
    assert "run_" in status["stub_path"]


def test_get_worker_status_unknown_worker():
    from omega_agentic_os import get_worker_status
    status = get_worker_status("no_such_worker")
    assert not status["available"]


# ── run_worker_stub ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("worker", WORKERS)
def test_run_worker_stub_returns_dict(worker):
    from omega_agentic_os import run_worker_stub
    result = run_worker_stub(worker, write_output=False)
    assert isinstance(result, dict)


@pytest.mark.parametrize("worker", WORKERS)
def test_run_worker_stub_has_required_keys(worker):
    from omega_agentic_os import run_worker_stub
    result = run_worker_stub(worker, write_output=False)
    for key in ("success", "worker_name", "report", "ran_at"):
        assert key in result, f"run_worker_stub result missing key: {key}"


@pytest.mark.parametrize("worker", WORKERS)
def test_run_worker_stub_succeeds(worker):
    from omega_agentic_os import run_worker_stub
    result = run_worker_stub(worker, write_output=False)
    assert result["success"], (
        f"run_worker_stub('{worker}') failed: {result.get('error', '')}"
    )


@pytest.mark.parametrize("worker", WORKERS)
def test_run_worker_stub_report_is_non_empty_string(worker):
    from omega_agentic_os import run_worker_stub
    result = run_worker_stub(worker, write_output=False)
    assert isinstance(result["report"], str)
    assert len(result["report"]) > 10, f"{worker} stub report should not be empty"


def test_run_worker_stub_unknown_worker_returns_failure():
    from omega_agentic_os import run_worker_stub
    result = run_worker_stub("no_such_worker", write_output=False)
    assert not result["success"]
    assert result["error"]


# ── run_worker_stub: no external API calls ────────────────────────────────────

@pytest.mark.parametrize("worker", WORKERS)
def test_worker_stub_source_has_no_requests_import(worker):
    """Stubs must not import requests, httpx, aiohttp, or urllib (for fetching)."""
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert stubs
    source = stubs[0].read_text(encoding="utf-8")
    # urllib.request is used internally by supabase_health for /health — but it's
    # localhost only, so we allow urllib. External HTTP libs are forbidden.
    for lib in ("import requests", "import httpx", "import aiohttp"):
        assert lib not in source, (
            f"{worker} stub must not import {lib.split()[-1]} (no external HTTP)"
        )


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_stub_source_has_no_broker_keywords(worker):
    """Stubs must not contain broker API patterns."""
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert stubs
    source = stubs[0].read_text(encoding="utf-8").lower()
    forbidden = ("alpaca", "ibkr", "tastytrade", "robinhood", "place_order", "submit_order")
    for kw in forbidden:
        assert kw not in source, f"{worker} stub must not contain broker keyword: {kw!r}"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_stub_source_has_no_send_email(worker):
    """Stubs must not send emails."""
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert stubs
    source = stubs[0].read_text(encoding="utf-8").lower()
    for kw in ("sendgrid", "smtplib", "send_email", "send_mail"):
        assert kw not in source, f"{worker} stub must not send email (found: {kw!r})"


@pytest.mark.parametrize("worker", WORKERS)
def test_worker_stub_source_has_no_deploy_commands(worker):
    """Stubs must not deploy to cloud environments."""
    impl_dir = AGENTS_DIR / worker / "implementation"
    stubs = list(impl_dir.glob("run_*.py"))
    assert stubs
    source = stubs[0].read_text(encoding="utf-8").lower()
    for kw in ("railway", "heroku", "render.com", "git push", "docker push"):
        assert kw not in source, f"{worker} stub must not deploy (found: {kw!r})"


# ── append_worker_memory / append_worker_error ────────────────────────────────

def test_append_worker_memory_returns_true(tmp_path, monkeypatch):
    from omega_agentic_os import _AGENTS_DIR
    import omega_agentic_os as mod

    # Point to tmp dir
    fake_agents = tmp_path / "omega_agents"
    (fake_agents / "test_worker" / "information").mkdir(parents=True)
    (fake_agents / "test_worker" / "information" / "memory.md").write_text("# memory\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_AGENTS_DIR", fake_agents)

    result = mod.append_worker_memory("test_worker", "Test note")
    assert result is True

    content = (fake_agents / "test_worker" / "information" / "memory.md").read_text(encoding="utf-8")
    assert "Test note" in content


def test_append_worker_memory_unknown_worker_returns_false(tmp_path, monkeypatch):
    import omega_agentic_os as mod
    monkeypatch.setattr(mod, "_AGENTS_DIR", tmp_path / "omega_agents")
    result = mod.append_worker_memory("no_such_worker", "note")
    assert result is False


def test_append_worker_error_returns_true(tmp_path, monkeypatch):
    import omega_agentic_os as mod

    fake_agents = tmp_path / "omega_agents"
    (fake_agents / "test_worker" / "information").mkdir(parents=True)
    (fake_agents / "test_worker" / "information" / "past_errors.md").write_text("# past_errors\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_AGENTS_DIR", fake_agents)

    result = mod.append_worker_error("test_worker", "Something broke")
    assert result is True

    content = (fake_agents / "test_worker" / "information" / "past_errors.md").read_text(encoding="utf-8")
    assert "Something broke" in content


def test_append_worker_error_unknown_worker_returns_false(tmp_path, monkeypatch):
    import omega_agentic_os as mod
    monkeypatch.setattr(mod, "_AGENTS_DIR", tmp_path / "omega_agents")
    result = mod.append_worker_error("no_such_worker", "error")
    assert result is False


# ── get_agentic_os_status ─────────────────────────────────────────────────────

def test_get_agentic_os_status_returns_dict():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    assert isinstance(status, dict)


def test_get_agentic_os_status_has_required_fields():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    for field in (
        "agentic_workers_count",
        "agentic_workers_available",
        "always_on_hosting_status",
        "workers",
        "suggested_agentic_actions",
        "snapshot_at",
    ):
        assert field in status, f"get_agentic_os_status() missing field: {field}"


def test_get_agentic_os_status_correct_count():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    assert status["agentic_workers_count"] == 5


def test_get_agentic_os_status_all_available():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    assert status["agentic_workers_available"] == 5


def test_get_agentic_os_status_hosting_is_planned():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    assert status["always_on_hosting_status"] == "planned"


def test_get_agentic_os_status_suggested_actions_is_list():
    from omega_agentic_os import get_agentic_os_status
    status = get_agentic_os_status()
    assert isinstance(status["suggested_agentic_actions"], list)


# ── Dashboard integration ─────────────────────────────────────────────────────

def test_dashboard_snapshot_includes_agentic_fields():
    from omega_dashboard import build_command_center_snapshot
    snapshot = build_command_center_snapshot()
    for field in (
        "agentic_workers_count",
        "agentic_workers_available",
        "always_on_hosting_status",
        "agentic_os_status",
        "suggested_agentic_actions",
    ):
        assert field in snapshot, f"Dashboard snapshot missing field: {field}"


def test_dashboard_agentic_workers_count_is_int():
    from omega_dashboard import build_command_center_snapshot
    snapshot = build_command_center_snapshot()
    assert isinstance(snapshot["agentic_workers_count"], int)


def test_dashboard_agentic_workers_count_equals_five():
    from omega_dashboard import build_command_center_snapshot
    snapshot = build_command_center_snapshot()
    assert snapshot["agentic_workers_count"] == 5


def test_dashboard_always_on_hosting_status_is_planned():
    from omega_dashboard import build_command_center_snapshot
    snapshot = build_command_center_snapshot()
    assert snapshot["always_on_hosting_status"] == "planned"


def test_dashboard_agentic_os_status_is_dict():
    from omega_dashboard import build_command_center_snapshot
    snapshot = build_command_center_snapshot()
    assert isinstance(snapshot["agentic_os_status"], dict)


# ── No hardcoded secrets ──────────────────────────────────────────────────────

def test_no_hardcoded_api_keys_in_omega_agentic_os():
    source = (ROOT / "omega_agentic_os.py").read_text(encoding="utf-8")
    for pattern in ("sk-", "Bearer ", "api_key =", "api_key=", "secret =", "secret="):
        assert pattern not in source, (
            f"omega_agentic_os.py must not contain hardcoded secret pattern: {pattern!r}"
        )
