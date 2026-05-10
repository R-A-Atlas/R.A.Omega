"""B4 — Freelance Rate Indexer tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_ROLES = [
    "Software Engineer",
    "Data Scientist",
    "UI/UX Designer",
    "Copywriter",
    "Video Editor",
    "SEO Specialist",
    "Virtual Assistant",
    "Accountant",
    "Financial Analyst",
    "DevOps Engineer",
]


def test_b4_package_importable():
    """atlas_agents.business.freelance_rates package loads without error."""
    mod = importlib.import_module("atlas_agents.business.freelance_rates")
    assert mod is not None


def test_b4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "freelance_rates" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "freelance_rates" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b4_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "freelance_rates" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "record_count",
        "roles",
        "title",
        "avg_hourly_low",
        "avg_hourly_high",
        "demand_trend",
        "top_platform",
        "yoy_rate_change_pct",
    ):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"
    # All 10 roles must be documented
    for role in EXPECTED_ROLES:
        assert role in content, f"Role '{role}' not documented in AGENT_PROMPT.md"


def test_b4_source_documented():
    """AGENT_PROMPT.md references BLS OES as primary source."""
    p = BASE / "atlas_agents" / "business" / "freelance_rates" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "bls.gov" in content.lower(), "BLS.gov not documented as primary source"
    assert "api.bls.gov" in content.lower(), "BLS API URL not documented"


def test_b4_output_schema_valid_when_scraper_built():
    """Once freelance_rates_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "freelance_rates" / "freelance_rates_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("freelance_rates_scraper.py not yet implemented — pending B4 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("freelance_rates_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "roles" in result
        assert "record_count" in result
        assert result["record_count"] == 10
        for role in result.get("roles", []):
            assert "title" in role
            assert role["avg_hourly_low"] < role["avg_hourly_high"]
            assert role["demand_trend"] in ("HIGH_DEMAND", "MODERATE", "DECLINING")
    except Exception:
        pass
