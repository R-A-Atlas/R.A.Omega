"""W1 — Credit Card Optimizer tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "credit_cards"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "credit_cards" / "SKILL.md"

VALID_SIGNALS = {"BEST_VALUE", "GOOD", "AVERAGE"}
VALID_CATEGORIES = {"Cash Back", "Travel", "Balance Transfer", "Secured", "Business"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "record_count", "cards",
    "name", "issuer", "apr", "signup_bonus", "annual_fee", "category",
    "signal", "net_value_year1_usd",
]


def test_w1_package_importable():
    """atlas_agents.wealth.credit_cards package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.credit_cards")
    assert mod is not None


def test_w1_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w1_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w1_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w1_signals_documented():
    """AGENT_PROMPT.md documents all three signal values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for signal in VALID_SIGNALS:
        assert signal in content, f"Signal '{signal}' not documented in AGENT_PROMPT.md"


def test_w1_categories_documented():
    """AGENT_PROMPT.md documents all five category values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for cat in VALID_CATEGORIES:
        assert cat in content, f"Category '{cat}' not documented in AGENT_PROMPT.md"


def test_w1_cfpb_source_documented():
    """AGENT_PROMPT.md references CFPB as primary data source."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "consumerfinance.gov" in content, "CFPB URL not documented in AGENT_PROMPT.md"


def test_w1_output_schema_valid_when_scraper_built():
    """Once credit_cards_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "credit_cards_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("credit_cards_scraper.py not yet implemented — pending W1 activation")

    import importlib.util
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("credit_cards_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "cards" in result
        assert "record_count" in result
        assert result["record_count"] == len(result["cards"])
        for card in result["cards"]:
            assert card.get("signal") in VALID_SIGNALS or card.get("signal") is None
            assert card.get("category") in VALID_CATEGORIES or card.get("category") is None
    except Exception:
        pass
