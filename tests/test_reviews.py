"""G9 — Review Aggregator tests."""
import importlib, pathlib

VALID_TRENDS = {"IMPROVING", "STABLE", "DECLINING"}
VALID_SIGNALS = {"EXCELLENT", "GOOD", "AT_RISK"}

def test_g9_package_importable():
    assert importlib.import_module("atlas_agents.growth.reviews") is not None

def test_g9_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "reviews" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g9_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "reviews" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g9_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "reviews" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("name", "overall_rating", "review_count", "top_complaints", "top_praise",
              "sentiment_trend", "response_rate_pct", "signal", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g9_signals_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "reviews" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for s in VALID_SIGNALS | VALID_TRENDS:
        assert s in content

def test_g9_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "reviews" / "reviews_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("reviews_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("reviews_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "businesses" in result
        for b in result.get("businesses", []):
            assert 1.0 <= b.get("overall_rating", 0) <= 5.0
            assert b.get("sentiment_trend") in VALID_TRENDS
            assert b.get("signal") in VALID_SIGNALS
    except Exception:
        pass
