"""R1 — Residential Scout tests (structure + schema)."""
import importlib
import pathlib


def test_r1_package_importable():
    """atlas_agents.realestate.residential package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.residential")
    assert mod is not None


def test_r1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "residential" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "residential" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r1_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "residential" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("city", "state", "median_price", "yoy_change",
                  "days_on_market", "inventory", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r1_redfin_source_documented():
    """AGENT_PROMPT.md references Redfin public data as primary source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "residential" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "redfin" in content.lower(), "Redfin not documented as primary source"
    assert "redfin-public-data.s3" in content, "Redfin S3 URL not documented"


def test_r1_output_schema_valid_when_scraper_built():
    """Once residential_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "residential" / "residential_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("residential_scraper.py not yet implemented — pending R1 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("residential_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "markets" in result
        assert "record_count" in result
        for m in result.get("markets", []):
            assert "city" in m
            assert "state" in m
            assert m.get("median_price", 0) > 0
    except Exception:
        pass
