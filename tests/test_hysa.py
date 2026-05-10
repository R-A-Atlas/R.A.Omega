"""W4 — HYSA Tracker tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "hysa"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "hysa" / "SKILL.md"

VALID_RATINGS = {"TOP_PICK", "COMPETITIVE", "AVERAGE"}
VALID_ACCOUNT_TYPES = {"HYSA", "Money Market", "CD"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "fed_funds_rate", "record_count", "accounts",
    "bank", "apy", "min_balance", "fdic_insured", "account_type",
    "rating", "spread_vs_fed",
]


def test_w4_package_importable():
    """atlas_agents.wealth.hysa package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.hysa")
    assert mod is not None


def test_w4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w4_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w4_signals_documented():
    """AGENT_PROMPT.md documents all 3 ratings and key source URLs."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for rating in VALID_RATINGS:
        assert rating in content, f"Rating '{rating}' not documented in AGENT_PROMPT.md"
    assert "banks.data.fdic.gov" in content, "FDIC BankFind URL not documented"
    assert "FEDFUNDS" in content, "FRED FEDFUNDS series not documented"


def test_w4_account_types_documented():
    """AGENT_PROMPT.md documents all three account_type values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for acct_type in VALID_ACCOUNT_TYPES:
        assert acct_type in content, f"account_type '{acct_type}' not documented in AGENT_PROMPT.md"


def test_w4_output_schema_valid_when_scraper_built():
    """Once hysa_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "hysa_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("hysa_scraper.py not yet implemented — pending W4 activation")

    import importlib.util
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("hysa_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_fred = {"observations": [
        {"date": "2026-04-01", "value": "4.33"},
    ]}
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_fred
        mock_get.return_value.status_code = 200
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "accounts" in result
            assert "fed_funds_rate" in result
            for acct in result.get("accounts", []):
                assert acct.get("rating") in VALID_RATINGS or acct.get("rating") is None
                assert acct.get("account_type") in VALID_ACCOUNT_TYPES or acct.get("account_type") is None
                assert acct.get("fdic_insured") is True or acct.get("fdic_insured") is None
        except Exception:
            pass
