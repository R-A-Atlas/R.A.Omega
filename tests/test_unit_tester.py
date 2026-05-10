"""E7 — Unit Tester smoke tests."""
import importlib
import pathlib
import re


def test_e7_package_importable():
    """atlas_agents.engineering.unit_tester package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.unit_tester")
    assert mod is not None


def test_e7_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "unit_tester"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e7_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "unit_tester"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"


def test_e7_five_test_standard_documented():
    """AGENT_PROMPT.md documents all 5 required test categories."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "unit_tester"
        / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    required = [
        "timeout",
        "429",
        "missing",
        "schema",
        "file output",
    ]
    for term in required:
        assert term.lower() in content.lower(), (
            f"5-test standard missing category: '{term}'"
        )


def test_e7_no_live_api_calls_in_existing_tests():
    """Existing test files must not contain bare requests.get() calls (mocking enforced)."""
    tests_root = pathlib.Path(__file__).resolve().parents[1] / "tests"
    violations = []
    for test_file in tests_root.rglob("test_*.py"):
        content = test_file.read_text(encoding="utf-8")
        # Allow 'requests.get' only inside the security suite (hits local server intentionally)
        if "security" in str(test_file):
            continue
        if test_file.name == "test_unit_tester.py":
            continue  # this file documents the pattern in docstrings — skip self-scan
        # Bare requests.get without a patch context is a live-API violation
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r"\brequests\.get\s*\(", stripped) and not stripped.startswith("#"):
                violations.append(f"{test_file.name}:{i} — {stripped[:80]}")
    assert not violations, (
        "Live API calls found in test files (use unittest.mock instead):\n"
        + "\n".join(violations)
    )


def test_e7_existing_scrapers_have_test_files():
    """Every built scraper agent has a corresponding test file."""
    root = pathlib.Path(__file__).resolve().parents[1]
    scrapers = {
        "crypto": "test_crypto_scraper.py",
        "equities": "test_equities_scraper.py",
    }
    for division, test_file in scrapers.items():
        assert (root / "tests" / test_file).exists(), (
            f"Missing test file for {division} scraper: tests/{test_file}"
        )


def test_e7_test_suite_structure_intact():
    """Core test directories and __init__.py files all exist."""
    root = pathlib.Path(__file__).resolve().parents[1]
    required = [
        "tests/__init__.py",
        "tests/security/__init__.py",
    ]
    for rel in required:
        assert (root / rel).exists(), f"Missing: {rel}"
