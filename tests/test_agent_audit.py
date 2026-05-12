from pathlib import Path

from fastapi.testclient import TestClient

import agent_audit
import api_server


def test_agent_audit_summary_is_consistent():
    report = agent_audit.collect_agent_audit()
    summary = report["summary"]

    assert report["ok"] is True
    assert summary["total_agents"] >= 100
    assert len(report["agents"]) == summary["total_agents"]
    assert summary["with_logic"] == summary["built_verified"] + summary["built_unverified"]
    assert (
        summary["total_agents"]
        == summary["built_verified"] + summary["built_unverified"] + summary["prompt_only"]
    )
    assert "trading" in report["divisions"]
    assert "wealth" in report["divisions"]


def test_agent_audit_detects_prompt_only_agent(tmp_path: Path):
    agents = tmp_path / "atlas_agents"
    tests = tmp_path / "tests"
    agent_dir = agents / "division" / "prompt_only"
    agent_dir.mkdir(parents=True)
    tests.mkdir()
    (agent_dir / "AGENT_PROMPT.md").write_text("Prompt", encoding="utf-8")
    (agent_dir / "__init__.py").write_text("", encoding="utf-8")

    report = agent_audit.collect_agent_audit(agents_root=agents, tests_root=tests)

    assert report["summary"]["total_agents"] == 1
    assert report["summary"]["prompt_only"] == 1
    assert report["agents"][0]["status"] == "prompt_only"


def test_agent_status_endpoint_returns_audit_payload(monkeypatch):
    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    client = TestClient(api_server.app)

    response = client.get("/agents/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["summary"]["total_agents"] >= 100
    assert isinstance(payload["agents"], list)
