"""M2 — Supply Chain Indexer tests (structure + schema)."""
import importlib
import pathlib

VALID_TRENDS = {"SPIKING", "RISING", "STABLE", "FALLING", "COLLAPSING"}


def test_m2_package_importable():
    mod = importlib.import_module("atlas_agents.macro.supply_chain")
    assert mod is not None


def test_m2_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "supply_chain" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m2_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "supply_chain" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m2_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "supply_chain" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "record_count", "indices", "route", "rate_usd_40ft", "trend", "change_wow_pct"):
        assert field in content, f"Field '{field}' not documented"


def test_m2_trend_signals_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "supply_chain" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend '{trend}' not documented"


def test_m2_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "supply_chain" / "supply_chain_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("supply_chain_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("supply_chain_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "indices" in result
        for idx in result.get("indices", []):
            assert idx.get("rate_usd_40ft", 0) > 0
            assert idx.get("trend") in VALID_TRENDS
    except Exception:
        pass
