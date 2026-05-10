"""E9 — Dependency Watcher smoke tests."""
import importlib
import pathlib


def test_e9_package_importable():
    """atlas_agents.engineering.dep_watcher package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.dep_watcher")
    assert mod is not None


def test_e9_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "dep_watcher"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e9_dependency_report_exists():
    """dependency_report.md exists and contains the required table header."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "dep_watcher"
        / "dependency_report.md"
    )
    assert p.exists(), f"Missing dependency_report.md: {p}"
    content = p.read_text(encoding="utf-8")
    assert "Package" in content, "Report missing table header"
    assert "Status" in content, "Report missing Status column"
    assert "Action" in content, "Report missing Action column"


def test_e9_requirements_txt_exists():
    """requirements.txt exists — dep_watcher must never delete it."""
    p = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
    assert p.exists(), "requirements.txt missing — E9 guardrail violated"
    assert p.stat().st_size > 0, "requirements.txt is empty"


def test_e9_requirements_no_packages_removed():
    """All original critical packages still present in requirements.txt."""
    p = pathlib.Path(__file__).resolve().parents[1] / "requirements.txt"
    content = p.read_text(encoding="utf-8")
    required = [
        "yfinance",
        "fastapi",
        "google-genai",
        "pydantic",
        "supabase",
        "pytest",
        "chromadb",
        "requests",
    ]
    for pkg in required:
        assert pkg in content, f"Package removed from requirements.txt: {pkg}"


def test_e9_report_flags_critical_holds():
    """dependency_report.md flags yfinance and google-genai as HOLD."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "dep_watcher"
        / "dependency_report.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "yfinance" in content, "yfinance not assessed in dependency report"
    assert "google-genai" in content, "google-genai not assessed in dependency report"
    assert "HOLD" in content, "No HOLD flags in dependency report — critical packages missed"
