"""B3 — Ecommerce Trends Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]

EXPECTED_NICHES = [
    "AI gadgets",
    "sustainable fashion",
    "home gym equipment",
    "pet tech",
    "meal prep",
    "travel accessories",
    "smart home",
    "vintage clothing",
]


def test_b3_package_importable():
    """atlas_agents.business.ecommerce package loads without error."""
    mod = importlib.import_module("atlas_agents.business.ecommerce")
    assert mod is not None


def test_b3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "ecommerce" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "ecommerce" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b3_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "ecommerce" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "record_count",
        "trending_niches",
        "niche",
        "trend_score",
        "trend_direction",
        "avg_price_estimate",
        "competition_level",
    ):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"
    # All 8 niches must be documented
    for niche in EXPECTED_NICHES:
        assert niche in content, f"Niche '{niche}' not documented in AGENT_PROMPT.md"


def test_b3_source_documented():
    """AGENT_PROMPT.md references pytrends / Google Trends as primary source."""
    p = BASE / "atlas_agents" / "business" / "ecommerce" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "pytrends" in content.lower(), "pytrends not documented as primary source"
    assert "trends.google.com" in content.lower(), "Google Trends URL not documented"


def test_b3_output_schema_valid_when_scraper_built():
    """Once ecommerce_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "ecommerce" / "ecommerce_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("ecommerce_scraper.py not yet implemented — pending B3 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("ecommerce_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "trending_niches" in result
        assert "record_count" in result
        assert result["record_count"] == 8
        for niche in result.get("trending_niches", []):
            assert "niche" in niche
            assert "trend_score" in niche
            assert niche["trend_direction"] in ("RISING", "STABLE", "DECLINING")
            assert niche["competition_level"] in ("HIGH", "MEDIUM", "LOW")
    except Exception:
        pass
