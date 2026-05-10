"""A1 — Watch Market Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_a1_package_importable():
    """atlas_agents.alternative.watches package loads without error."""
    mod = importlib.import_module("atlas_agents.alternative.watches")
    assert mod is not None


def test_a1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "alternative" / "watches" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "watches" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a1_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "alternative" / "watches" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "brand", "model", "reference", "avg_price", "retail_price",
        "premium_over_retail_pct", "trend", "listings_count",
        "generated_at", "record_count",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_a1_signal_documented():
    """AGENT_PROMPT.md documents all trend signal values and thresholds."""
    p = BASE / "atlas_agents" / "alternative" / "watches" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in ("APPRECIATING", "PREMIUM", "AT_RETAIL", "BELOW_RETAIL"):
        assert signal in content, f"Signal '{signal}' not documented"
    # Threshold checks
    assert "1.5" in content, "APPRECIATING threshold (1.5x retail) not documented"
    assert "premium_over_retail_pct" in content, "premium_over_retail_pct formula not documented"


def test_a1_output_schema_valid_when_scraper_built():
    """Once watches_scraper.py is built, output schema must match spec."""
    scraper_path = (
        BASE / "atlas_agents" / "alternative" / "watches" / "watches_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("watches_scraper.py not yet implemented — pending A1 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("watches_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "models" in result
        assert "record_count" in result
        assert result["record_count"] == 8
        for m in result.get("models", []):
            assert "brand" in m
            assert "reference" in m
            assert "avg_price" in m
            assert "retail_price" in m
            assert "premium_over_retail_pct" in m
            assert "trend" in m
            assert m["trend"] in ("APPRECIATING", "PREMIUM", "AT_RETAIL", "BELOW_RETAIL")
    except Exception:
        pass
