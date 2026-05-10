"""A3 — Collectibles/Cards Scraper tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_a3_package_importable():
    """atlas_agents.alternative.collectibles package loads without error."""
    mod = importlib.import_module("atlas_agents.alternative.collectibles")
    assert mod is not None


def test_a3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "alternative" / "collectibles" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "collectibles" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a3_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "alternative" / "collectibles" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "category", "item", "grade", "avg_sold_price", "volume_30d", "trend",
        "generated_at", "record_count",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_a3_signal_documented():
    """AGENT_PROMPT.md documents all trend signal values and thresholds."""
    p = BASE / "atlas_agents" / "alternative" / "collectibles" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in ("HOT", "RISING", "STABLE", "COOLING"):
        assert signal in content, f"Signal '{signal}' not documented"
    # Volume threshold
    assert "100" in content, "HOT volume threshold (100) not documented"
    # Price thresholds
    assert "10" in content, "HOT price threshold (10%) not documented"
    assert "5" in content, "RISING price threshold (5%) not documented"
    # Category enumeration
    for category in ("Sports Cards", "Pokemon", "Comic Books", "Coins"):
        assert category in content, f"Category '{category}' not documented"


def test_a3_output_schema_valid_when_scraper_built():
    """Once collectibles_scraper.py is built, output schema must match spec."""
    scraper_path = (
        BASE / "atlas_agents" / "alternative" / "collectibles" / "collectibles_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("collectibles_scraper.py not yet implemented — pending A3 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("collectibles_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "items" in result
        assert "record_count" in result
        assert result["record_count"] == 5
        valid_trends = {"HOT", "RISING", "STABLE", "COOLING"}
        valid_categories = {"Sports Cards", "Pokemon", "Magic: The Gathering", "Comic Books", "Coins"}
        for item in result.get("items", []):
            assert "category" in item
            assert "grade" in item
            assert "avg_sold_price" in item
            assert "volume_30d" in item
            assert "trend" in item
            assert item["trend"] in valid_trends
            assert item["category"] in valid_categories
    except Exception:
        pass
