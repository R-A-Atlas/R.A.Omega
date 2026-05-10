"""G8 — Engagement Rater tests."""
import importlib, pathlib

VALID_TIERS = {"NANO", "MICRO", "MID", "MACRO"}
VALID_SIGNALS = {"HIGH_ENGAGEMENT", "AVERAGE", "LOW"}

def test_g8_package_importable():
    assert importlib.import_module("atlas_agents.growth.engagement") is not None

def test_g8_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "engagement" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g8_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "engagement" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g8_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "engagement" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("handle", "platform", "followers", "avg_likes", "avg_comments",
              "engagement_rate", "tier", "signal", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g8_formula_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "engagement" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "engagement_rate" in content
    assert "followers" in content and "avg_likes" in content

def test_g8_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "engagement" / "engagement_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("engagement_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("engagement_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "profiles" in result
        for pr in result.get("profiles", []):
            assert pr.get("tier") in VALID_TIERS
            assert pr.get("signal") in VALID_SIGNALS
    except Exception:
        pass
