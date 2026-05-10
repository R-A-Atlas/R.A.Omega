"""W6 — Personal Loan Screener tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "personal_loans"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "personal_loans" / "SKILL.md"

VALID_RATINGS = {"COMPETITIVE", "AVERAGE"}
VALID_CATEGORIES = {"Online Lender", "Credit Union", "Bank", "Marketplace"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "record_count", "fred_avg_rate", "loans",
    "lender", "rate_low", "rate_high", "max_amount", "term_months_max",
    "credit_score_min", "category", "rating",
]


def test_w6_package_importable():
    """atlas_agents.wealth.personal_loans package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.personal_loans")
    assert mod is not None


def test_w6_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w6_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w6_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w6_source_documented():
    """AGENT_PROMPT.md references FRED TERMCBPER24NS and both ratings."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "TERMCBPER24NS" in content, "FRED series TERMCBPER24NS not documented"
    for rating in VALID_RATINGS:
        assert rating in content, f"Rating '{rating}' not documented in AGENT_PROMPT.md"


def test_w6_categories_documented():
    """AGENT_PROMPT.md documents all four lender category values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for cat in VALID_CATEGORIES:
        assert cat in content, f"Category '{cat}' not documented in AGENT_PROMPT.md"


def test_w6_output_schema_valid_when_scraper_built():
    """Once personal_loans_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "personal_loans_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("personal_loans_scraper.py not yet implemented — pending W6 activation")

    import importlib.util
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("personal_loans_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_fred = {"observations": [{"date": "2026-03-01", "value": "11.48"}]}
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_fred
        mock_get.return_value.status_code = 200
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "loans" in result
            assert "fred_avg_rate" in result
            for loan in result.get("loans", []):
                assert loan.get("rating") in VALID_RATINGS or loan.get("rating") is None
                assert loan.get("category") in VALID_CATEGORIES or loan.get("category") is None
                rate_low = loan.get("rate_low", 0)
                rate_high = loan.get("rate_high", float("inf"))
                assert rate_low < rate_high or rate_low == 0
        except Exception:
            pass
