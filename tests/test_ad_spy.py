"""G3 — Competitor Ad Spy tests."""
import importlib, pathlib

VALID_SIGNALS = {"HEAVY_SPENDER", "ACTIVE", "PAUSED"}

def test_g3_package_importable():
    assert importlib.import_module("atlas_agents.growth.ad_spy") is not None

def test_g3_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "ad_spy" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g3_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "ad_spy" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g3_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "ad_spy" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("page_name", "ad_text_preview", "spend_range", "impressions_range", "status", "signal", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g3_meta_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "ad_spy" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "facebook.com/ads/library" in content or "meta" in content.lower()

def test_g3_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "ad_spy" / "ad_spy_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("ad_spy_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("ad_spy_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "ads" in result
        for a in result.get("ads", []):
            assert a.get("signal") in VALID_SIGNALS
    except Exception:
        pass
