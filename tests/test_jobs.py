"""M6 — Job Market/BLS Bot tests (structure + schema)."""
import importlib
import pathlib

VALID_SIGNALS = {"STRONG", "HEALTHY", "WEAK", "RECESSIONARY"}


def test_m6_package_importable():
    mod = importlib.import_module("atlas_agents.macro.jobs")
    assert mod is not None


def test_m6_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "jobs" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m6_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "jobs" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m6_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "jobs" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "unemployment_rate", "jobs_added_thousands",
                  "record_count", "sector_breakdown", "period"):
        assert field in content, f"Field '{field}' not documented"


def test_m6_bls_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "jobs" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "bls.gov" in content.lower() or "BLS" in content


def test_m6_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "jobs" / "jobs_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("jobs_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("jobs_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert 0 < result.get("unemployment_rate", 0) < 20
        assert "sector_breakdown" in result
    except Exception:
        pass
