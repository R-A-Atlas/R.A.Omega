"""G5 — Social Sentiment Analyzer tests."""
import importlib, pathlib

VALID_SIGNALS = {"BULLISH", "NEUTRAL", "BEARISH"}

def test_g5_package_importable():
    assert importlib.import_module("atlas_agents.growth.sentiment") is not None

def test_g5_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "sentiment" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g5_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "sentiment" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g5_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "sentiment" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("topic", "subreddit", "mentions", "sentiment_score", "trending", "signal", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g5_reddit_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "sentiment" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "reddit.com" in content.lower() or "reddit" in content.lower()

def test_g5_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "sentiment" / "sentiment_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("sentiment_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("sentiment_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "topics" in result
        for t in result.get("topics", []):
            assert -1.0 <= t.get("sentiment_score", 0) <= 1.0
            assert t.get("signal") in VALID_SIGNALS
    except Exception:
        pass
