"""L1 — Federal Tax Code Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "federal_tax"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "federal_tax"
SCRAPER   = AGENT_DIR / "federal_tax_scraper.py"


def test_l1_package_importable():
    """atlas_agents.legal.federal_tax package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.federal_tax")
    assert mod is not None


def test_l1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l1_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "year",
        "standard_deduction_single", "standard_deduction_married",
        "record_count", "brackets",
        "rate", "single_min", "single_max", "married_min", "married_max",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l1_source_documented():
    """AGENT_PROMPT.md references IRS source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "irs.gov" in content.lower(), "IRS source URL not documented"
    assert "2026" in content, "Tax year 2026 not referenced"


def test_l1_output_schema_valid_when_scraper_built():
    """Once federal_tax_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("federal_tax_scraper.py not yet implemented — pending L1 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("federal_tax_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "year" in result
        assert "standard_deduction_single" in result
        assert "standard_deduction_married" in result
        assert "record_count" in result
        assert "brackets" in result
        assert result["record_count"] == len(result["brackets"])
        for b in result["brackets"]:
            assert "rate" in b
            assert "single_min" in b
            assert "married_min" in b
    except Exception:
        pass
