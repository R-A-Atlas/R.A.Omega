"""E3 — API Integrator smoke tests."""
import importlib
import pathlib


def test_e3_package_importable():
    """atlas_agents.engineering.api_integrator package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.api_integrator")
    assert mod is not None


def test_e3_connectors_package_importable():
    """atlas_core.connectors package loads without error."""
    mod = importlib.import_module("atlas_core.connectors")
    assert mod is not None


def test_e3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "api_integrator"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "api_integrator"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"


def test_e3_connectors_dir_exists():
    """atlas_core/connectors/ directory exists and has __init__.py."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_core"
        / "connectors"
        / "__init__.py"
    )
    assert p.exists(), f"Missing connectors package: {p}"


def test_connector_template_references_agent_utils():
    """AGENT_PROMPT.md references requests_get_json (connectors must use agent_utils)."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "api_integrator"
        / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "requests_get_json" in content, "Prompt must reference requests_get_json"
    assert "agent_utils" in content, "Prompt must reference agent_utils"
