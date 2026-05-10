"""E1 — Skill Scripter smoke tests."""
import importlib
import pathlib


def test_e1_package_importable():
    """atlas_agents.engineering.skill_scripter package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.skill_scripter")
    assert mod is not None


def test_e1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "skill_scripter"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "skill_scripter"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"
