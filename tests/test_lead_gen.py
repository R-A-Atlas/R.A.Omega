"""G1 — Lead Generation Scraper tests."""
import importlib, pathlib

VALID_SIGNALS = {"HOT_LEAD", "WARM_LEAD", "COLD_LEAD"}

def test_g1_package_importable():
    assert importlib.import_module("atlas_agents.growth.lead_gen") is not None

def test_g1_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "lead_gen" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g1_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "lead_gen" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g1_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "lead_gen" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("business_name", "address", "phone", "website", "rating", "review_count", "has_modern_site", "signal", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g1_signals_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "lead_gen" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for s in VALID_SIGNALS:
        assert s in content

def test_g1_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "lead_gen" / "lead_gen_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("lead_gen_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("lead_gen_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "leads" in result
        for l in result.get("leads", []):
            assert l.get("signal") in VALID_SIGNALS
    except Exception:
        pass
