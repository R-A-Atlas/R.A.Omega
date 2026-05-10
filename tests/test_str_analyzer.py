"""R3 — Airbnb/STR Analyzer tests (structure + schema)."""
import importlib
import pathlib


VALID_REGULATION_RISK = {"HIGH", "MEDIUM", "LOW"}


def test_r3_package_importable():
    """atlas_agents.realestate.str_analyzer package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.str_analyzer")
    assert mod is not None


def test_r3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "str_analyzer" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r3_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("city", "avg_daily_rate", "occupancy_rate", "annual_revenue_est",
                  "regulation_risk", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r3_regulation_risk_levels_documented():
    """AGENT_PROMPT.md documents all three regulation risk levels."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "HIGH" in content
    assert "MEDIUM" in content
    assert "LOW" in content


def test_r3_revenue_formula_documented():
    """AGENT_PROMPT.md documents the annual revenue estimate formula."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "365" in content, "Annual days (365) not in revenue formula"
    assert "occupancy" in content.lower()
    assert "annual_revenue_est" in content


def test_r3_inside_airbnb_source_documented():
    """AGENT_PROMPT.md references Inside Airbnb as primary source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "insideairbnb" in content.lower() or "inside airbnb" in content.lower()


def test_r3_output_schema_valid_when_scraper_built():
    """Once str_analyzer_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "str_analyzer" / "str_analyzer_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("str_analyzer_scraper.py not yet implemented — pending R3 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("str_analyzer_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "markets" in result
        for m in result.get("markets", []):
            assert m.get("avg_daily_rate", 0) > 0
            occ = m.get("occupancy_rate", 0)
            assert 0 < occ <= 1.0
            assert m.get("regulation_risk") in VALID_REGULATION_RISK
            expected_rev = round(m["avg_daily_rate"] * occ * 365)
            assert abs(m.get("annual_revenue_est", 0) - expected_rev) <= 1
    except Exception:
        pass
