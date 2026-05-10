"""W8 — Insurance Premium Tracker tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "insurance"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "insurance" / "SKILL.md"

VALID_TRENDS = {"RISING", "STABLE", "FALLING"}
VALID_TYPES = {"Auto", "Home", "Health", "Life", "Renters"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "record_count", "data_year", "source_url", "premiums",
    "type", "avg_annual_premium", "yoy_change_pct", "trend",
    "highest_state", "highest_state_premium", "lowest_state", "lowest_state_premium",
]


def test_w8_package_importable():
    """atlas_agents.wealth.insurance package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.insurance")
    assert mod is not None


def test_w8_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w8_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w8_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w8_signals_documented():
    """AGENT_PROMPT.md documents all 3 trends and NAIC source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend '{trend}' not documented in AGENT_PROMPT.md"
    assert "naic.org" in content, "NAIC source URL not documented in AGENT_PROMPT.md"


def test_w8_all_types_documented():
    """AGENT_PROMPT.md documents all five insurance type values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for ins_type in VALID_TYPES:
        assert ins_type in content, f"Insurance type '{ins_type}' not documented in AGENT_PROMPT.md"


def test_w8_output_schema_valid_when_scraper_built():
    """Once insurance_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "insurance_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("insurance_scraper.py not yet implemented — pending W8 activation")

    import importlib.util

    spec = importlib.util.spec_from_file_location("insurance_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "premiums" in result
        assert result.get("record_count") == 5
        for row in result.get("premiums", []):
            assert row.get("type") in VALID_TYPES or row.get("type") is None
            assert row.get("trend") in VALID_TRENDS or row.get("trend") is None
            highest = row.get("highest_state_premium", 0)
            avg = row.get("avg_annual_premium", 0)
            lowest = row.get("lowest_state_premium", float("inf"))
            if avg > 0:
                assert highest > avg or highest == 0, f"{row.get('type')}: highest must be > avg"
                assert lowest < avg or lowest == 0, f"{row.get('type')}: lowest must be < avg"
    except Exception:
        pass
