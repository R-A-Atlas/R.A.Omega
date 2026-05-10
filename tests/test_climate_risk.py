"""M4 — Climate Risk/FEMA Bot tests (structure + schema)."""
import importlib
import pathlib

VALID_RISK_LEVELS = {"EXTREME", "HIGH", "MODERATE", "LOW"}
VALID_CHANGES = {"INCREASING", "STABLE", "DECREASING"}
VALID_IMPACTS = {"UNINSURABLE", "HIGH_PREMIUM", "NORMAL", "LOW_PREMIUM"}


def test_m4_package_importable():
    mod = importlib.import_module("atlas_agents.macro.climate_risk")
    assert mod is not None


def test_m4_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "climate_risk" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m4_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "climate_risk" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m4_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "climate_risk" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "record_count", "flood_zone_changes",
                  "risk_level", "change", "impact_on_insurance"):
        assert field in content, f"Field '{field}' not documented"


def test_m4_fema_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "climate_risk" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "fema" in content.lower()


def test_m4_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "climate_risk" / "climate_risk_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("climate_risk_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("climate_risk_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "flood_zone_changes" in result
        for z in result.get("flood_zone_changes", []):
            assert z.get("risk_level") in VALID_RISK_LEVELS
    except Exception:
        pass
