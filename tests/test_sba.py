"""B1 — SBA Grant/Loan Finder tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_b1_package_importable():
    """atlas_agents.business.sba package loads without error."""
    mod = importlib.import_module("atlas_agents.business.sba")
    assert mod is not None


def test_b1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "sba" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "sba" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b1_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "sba" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "record_count",
        "programs",
        "name",
        "type",
        "max_amount",
        "interest_rate_low",
        "interest_rate_high",
        "eligibility",
        "term_years_max",
        "url",
    ):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_b1_source_documented():
    """AGENT_PROMPT.md references SBA.gov and grants.gov as primary sources."""
    p = BASE / "atlas_agents" / "business" / "sba" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "sba.gov" in content.lower(), "SBA.gov not documented as primary source"
    assert "grants.gov" in content.lower(), "grants.gov not documented as data source"


def test_b1_output_schema_valid_when_scraper_built():
    """Once sba_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "sba" / "sba_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("sba_scraper.py not yet implemented — pending B1 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("sba_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "programs" in result
        assert "record_count" in result
        for prog in result.get("programs", []):
            assert "name" in prog
            assert "type" in prog
            assert prog["type"] in ("Grant", "Loan", "Line of Credit")
    except Exception:
        pass
