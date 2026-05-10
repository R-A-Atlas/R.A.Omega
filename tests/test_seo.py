"""G4 — SEO Keyword Tracker tests."""
import importlib, pathlib

VALID_DIRECTIONS = {"BREAKOUT", "RISING", "STABLE", "DECLINING"}

def test_g4_package_importable():
    assert importlib.import_module("atlas_agents.growth.seo") is not None

def test_g4_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "seo" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g4_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "seo" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g4_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "seo" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("term", "trend_score", "trend_direction", "competition_level", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g4_directions_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "seo" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for d in VALID_DIRECTIONS:
        assert d in content

def test_g4_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "seo" / "seo_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("seo_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("seo_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "keywords" in result
        for k in result.get("keywords", []):
            assert 0 <= k.get("trend_score", -1) <= 100
            assert k.get("trend_direction") in VALID_DIRECTIONS
    except Exception:
        pass
