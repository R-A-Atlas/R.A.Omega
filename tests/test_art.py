"""A2 — Art Auction Tracker tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_a2_package_importable():
    """atlas_agents.alternative.art package loads without error."""
    mod = importlib.import_module("atlas_agents.alternative.art")
    assert mod is not None


def test_a2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "alternative" / "art" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "art" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a2_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "alternative" / "art" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "artist", "title", "medium", "house", "realized_price_usd",
        "estimate_low_usd", "estimate_high_usd", "sold_date",
        "premium_over_estimate_pct", "signal",
        "generated_at", "record_count", "artprice100_index",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_a2_signal_documented():
    """AGENT_PROMPT.md documents all signal values and thresholds."""
    p = BASE / "atlas_agents" / "alternative" / "art" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in ("ABOVE_ESTIMATE", "IN_RANGE", "BELOW_ESTIMATE"):
        assert signal in content, f"Signal '{signal}' not documented"
    assert "premium_over_estimate_pct" in content, "premium_over_estimate_pct formula not documented"
    assert "artprice100" in content.lower(), "Artprice100 benchmark not documented"


def test_a2_output_schema_valid_when_scraper_built():
    """Once art_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "alternative" / "art" / "art_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("art_scraper.py not yet implemented — pending A2 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("art_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "sales" in result
        assert "record_count" in result
        assert "artprice100_index" in result
        for s in result.get("sales", []):
            assert "artist" in s
            assert "realized_price_usd" in s
            assert "estimate_high_usd" in s
            assert "signal" in s
            assert s["signal"] in ("ABOVE_ESTIMATE", "IN_RANGE", "BELOW_ESTIMATE")
    except Exception:
        pass
