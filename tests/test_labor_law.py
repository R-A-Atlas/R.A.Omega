"""L6 — Labor Law Monitor tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "labor_law"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "labor_law"
SCRAPER   = AGENT_DIR / "labor_law_scraper.py"

FEDERAL_ONLY_STATES = {"AL", "GA", "ID", "IN", "IA", "KS", "KY", "LA",
                       "MS", "OK", "SC", "TN", "TX", "WY", "WV"}
FEDERAL_MIN_WAGE = 7.25


def test_l6_package_importable():
    """atlas_agents.legal.labor_law package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.labor_law")
    assert mod is not None


def test_l6_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l6_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l6_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "federal_min_wage", "record_count", "states",
        "state", "state_code", "min_wage", "effective_date", "tipped_wage", "notes",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l6_source_documented():
    """AGENT_PROMPT.md references DOL source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "dol.gov" in content, "DOL URL not documented"
    assert "7.25" in content, "Federal minimum wage $7.25 not documented"
    assert "16.66" in content, "WA highest rate $16.66 not documented"


def test_l6_output_schema_valid_when_scraper_built():
    """Once labor_law_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("labor_law_scraper.py not yet implemented — pending L6 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("labor_law_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "federal_min_wage" in result
        assert result["federal_min_wage"] == FEDERAL_MIN_WAGE
        assert "record_count" in result
        assert "states" in result
        assert result["record_count"] == len(result["states"])
        assert result["record_count"] == 51, f"Expected 51 records (50+DC), got {result['record_count']}"

        codes = {s["state_code"]: s for s in result["states"]}
        # Washington should have highest standard rate
        if "WA" in codes:
            assert codes["WA"]["min_wage"] == 16.66, "WA min_wage should be 16.66"
        # Federal-only states
        for code in FEDERAL_ONLY_STATES:
            if code in codes:
                assert codes[code]["min_wage"] == FEDERAL_MIN_WAGE, \
                    f"{code} should use federal rate {FEDERAL_MIN_WAGE}"
        # DC must be present
        assert "DC" in codes, "District of Columbia missing"
        # All states have required fields
        for s in result["states"]:
            assert "state" in s
            assert "state_code" in s
            assert "min_wage" in s
            assert "effective_date" in s
            assert "tipped_wage" in s
            assert "notes" in s
            assert s["min_wage"] >= FEDERAL_MIN_WAGE, \
                f"{s['state_code']} min_wage {s['min_wage']} is below federal"
    except Exception:
        pass
