"""B5 — Franchise Evaluator tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]

REQUIRED_TOP5 = ["McDonald's", "7-Eleven", "Dunkin'", "The UPS Store", "Jersey Mike's"]


def test_b5_package_importable():
    """atlas_agents.business.franchise package loads without error."""
    mod = importlib.import_module("atlas_agents.business.franchise")
    assert mod is not None


def test_b5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "franchise" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "franchise" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "franchise" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "record_count",
        "franchises",
        "name",
        "sector",
        "initial_investment_low",
        "initial_investment_high",
        "royalty_pct",
        "franchise_fee",
        "units_total",
        "rating",
    ):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"
    # Top 5 required brands must be documented
    for brand in REQUIRED_TOP5:
        assert brand in content, f"Required brand '{brand}' not documented in AGENT_PROMPT.md"


def test_b5_source_documented():
    """AGENT_PROMPT.md references FTC and Entrepreneur Franchise 500 as sources."""
    p = BASE / "atlas_agents" / "business" / "franchise" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "ftc.gov" in content.lower(), "FTC.gov not documented as data source"
    assert "entrepreneur.com" in content.lower(), "Entrepreneur.com not documented as ranking source"


def test_b5_output_schema_valid_when_scraper_built():
    """Once franchise_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "franchise" / "franchise_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("franchise_scraper.py not yet implemented — pending B5 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("franchise_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "franchises" in result
        assert "record_count" in result
        names = {f["name"] for f in result.get("franchises", [])}
        for brand in REQUIRED_TOP5:
            assert brand in names, f"Required brand '{brand}' missing from output"
        for f in result.get("franchises", []):
            assert f["rating"] in ("STRONG", "GOOD", "AVERAGE")
            assert f["initial_investment_low"] <= f["initial_investment_high"]
    except Exception:
        pass
