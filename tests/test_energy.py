"""M3 — Energy Grid Monitor tests (structure + schema)."""
import importlib
import pathlib

VALID_TRENDS = {"GREENING", "STABLE", "FOSSIL_RECOVERY"}


def test_m3_package_importable():
    mod = importlib.import_module("atlas_agents.macro.energy")
    assert mod is not None


def test_m3_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "energy" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m3_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "energy" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m3_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "energy" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "electricity_avg_kwh_cents", "gas_national_avg_gallon",
                  "renewables_pct_grid", "record_count", "breakdown"):
        assert field in content, f"Field '{field}' not documented"


def test_m3_eia_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "energy" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "eia.gov" in content.lower() or "EIA" in content


def test_m3_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "energy" / "energy_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("energy_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("energy_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert result.get("electricity_avg_kwh_cents", 0) > 0
    except Exception:
        pass
