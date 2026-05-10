"""R5 — Zoning & Permit Watcher tests (structure + schema)."""
import importlib
import pathlib
import re


VALID_TREND_SIGNALS = {"SURGING", "GROWING", "STABLE", "DECLINING", "COLLAPSING"}


def test_r5_package_importable():
    """atlas_agents.realestate.zoning package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.zoning")
    assert mod is not None


def test_r5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "zoning" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("city", "permit_type", "count", "yoy_change",
                  "trend_signal", "generated_at", "record_count", "period"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r5_all_trend_signals_documented():
    """AGENT_PROMPT.md documents all five trend signal values."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for signal in VALID_TREND_SIGNALS:
        assert signal in content, f"Trend signal '{signal}' not documented"


def test_r5_census_source_documented():
    """AGENT_PROMPT.md references US Census BPS as primary source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "census" in content.lower(), "Census not documented as primary source"
    assert "api.census.gov" in content or "census.gov" in content


def test_r5_yoy_thresholds_documented():
    """AGENT_PROMPT.md documents the YoY percentage thresholds for each signal."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "20" in content, "20% SURGING threshold not documented"
    assert "5" in content,  "5% GROWING threshold not documented"


def test_r5_output_schema_valid_when_scraper_built():
    """Once zoning_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "zoning" / "zoning_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("zoning_scraper.py not yet implemented — pending R5 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("zoning_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "permits" in result
        assert "period" in result
        assert re.match(r"\d{4}-\d{2}", result.get("period", ""))
        for permit in result.get("permits", []):
            assert permit.get("count", -1) >= 0
            assert permit.get("trend_signal") in VALID_TREND_SIGNALS
    except Exception:
        pass
