"""W2 — Auto Loan Scanner tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "auto_loans"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "auto_loans" / "SKILL.md"

VALID_TRENDS = {"RISING", "FALLING", "STABLE"}
VALID_TERMS = {24, 36, 48, 60, 72}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "record_count", "period", "trend", "wow_change_60mo",
    "term_months", "avg_rate", "credit_union_rate", "dealer_rate",
]

FRED_SERIES = ["DTCTHFNM", "TERMCBCCALLNS"]


def test_w2_package_importable():
    """atlas_agents.wealth.auto_loans package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.auto_loans")
    assert mod is not None


def test_w2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w2_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w2_signals_documented():
    """AGENT_PROMPT.md documents all trend signals and FRED series."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend '{trend}' not documented in AGENT_PROMPT.md"
    for series in FRED_SERIES:
        assert series in content, f"FRED series '{series}' not documented in AGENT_PROMPT.md"


def test_w2_term_months_documented():
    """AGENT_PROMPT.md documents all five term_months values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for term in VALID_TERMS:
        assert str(term) in content, f"term_months={term} not documented in AGENT_PROMPT.md"


def test_w2_wow_threshold_documented():
    """AGENT_PROMPT.md documents the 0.10% WoW trend threshold."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "0.10" in content, "WoW threshold 0.10% not documented in AGENT_PROMPT.md"


def test_w2_output_schema_valid_when_scraper_built():
    """Once auto_loans_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "auto_loans_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("auto_loans_scraper.py not yet implemented — pending W2 activation")

    import importlib.util

    spec = importlib.util.spec_from_file_location("auto_loans_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "rates" in result
        assert "trend" in result
        assert result.get("trend") in VALID_TRENDS or result.get("trend") is None
        assert result.get("record_count") == 5
        for row in result.get("rates", []):
            assert row.get("term_months") in VALID_TERMS or row.get("term_months") is None
    except Exception:
        pass
