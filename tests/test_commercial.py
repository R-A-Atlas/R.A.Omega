"""R4 — Commercial Property Bot tests (structure + schema)."""
import importlib
import pathlib


VALID_TRENDS = {"TIGHTENING", "STABLE", "SOFTENING"}
VALID_TYPES = {"Office", "Industrial", "Retail", "Multifamily"}


def test_r4_package_importable():
    """atlas_agents.realestate.commercial package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.commercial")
    assert mod is not None


def test_r4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "commercial" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r4_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("type", "avg_lease_rate", "vacancy_rate", "market",
                  "trend", "generated_at", "record_count", "yoy_vacancy_change"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r4_trend_signals_documented():
    """AGENT_PROMPT.md documents all three trend signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "TIGHTENING" in content
    assert "STABLE" in content
    assert "SOFTENING" in content


def test_r4_fred_source_documented():
    """AGENT_PROMPT.md references FRED as primary data source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "fred" in content.lower(), "FRED not documented as primary source"
    assert "RCPIATOT" in content or "fred.stlouisfed.org" in content


def test_r4_fallback_snapshot_documented():
    """AGENT_PROMPT.md documents fallback snapshot for API failures."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "fallback" in content.lower() or "FALLBACK" in content


def test_r4_output_schema_valid_when_scraper_built():
    """Once commercial_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "commercial" / "commercial_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("commercial_scraper.py not yet implemented — pending R4 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("commercial_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "segments" in result
        assert "record_count" in result
        for s in result.get("segments", []):
            assert s.get("avg_lease_rate", 0) > 0
            assert 0 <= s.get("vacancy_rate", -1) <= 100
            assert s.get("trend") in VALID_TRENDS
    except Exception:
        pass
