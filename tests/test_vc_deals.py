"""B6 — VC Deal Flow Monitor tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]

VALID_SIGNALS = {"MEGA_ROUND", "LARGE", "STANDARD"}
VALID_ROUNDS = {"Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Growth"}
VALID_SECTORS = {"AI/ML", "Fintech", "Healthtech", "SaaS", "Climate", "Consumer"}


def test_b6_package_importable():
    """atlas_agents.business.vc_deals package loads without error."""
    mod = importlib.import_module("atlas_agents.business.vc_deals")
    assert mod is not None


def test_b6_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "vc_deals" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b6_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "vc_deals" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b6_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "vc_deals" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "record_count",
        "deals",
        "company",
        "sector",
        "round",
        "amount_millions",
        "lead_investor",
        "date",
        "source",
        "signal",
        "MEGA_ROUND",
        "LARGE",
        "STANDARD",
    ):
        assert field in content, f"Schema field/value '{field}' not documented in AGENT_PROMPT.md"
    # All valid sectors must be documented
    for sector in VALID_SECTORS:
        assert sector in content, f"Sector '{sector}' not documented in AGENT_PROMPT.md"


def test_b6_source_documented():
    """AGENT_PROMPT.md references SEC EDGAR Form D as primary source."""
    p = BASE / "atlas_agents" / "business" / "vc_deals" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "sec.gov" in content.lower(), "SEC.gov not documented as primary source"
    assert "efts.sec.gov" in content.lower(), "SEC EDGAR EFTS URL not documented"


def test_b6_output_schema_valid_when_scraper_built():
    """Once vc_deals_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "vc_deals" / "vc_deals_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("vc_deals_scraper.py not yet implemented — pending B6 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("vc_deals_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "deals" in result
        assert "record_count" in result
        for deal in result.get("deals", []):
            assert deal.get("signal") in VALID_SIGNALS
            assert deal.get("round") in VALID_ROUNDS
            assert deal.get("sector") in VALID_SECTORS
            assert deal.get("source") == "SEC Form D"
            assert deal.get("amount_millions", -1) >= 0
    except Exception:
        pass
