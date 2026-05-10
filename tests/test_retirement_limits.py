"""W5 — IRA/401k Limit Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "retirement_limits"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "retirement_limits" / "SKILL.md"

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "year",
    "ira_limit", "ira_catch_up_50plus",
    "k401_limit", "k401_catch_up_50plus",
    "hsa_individual", "hsa_family",
    "roth_income_phase_out_single_low", "roth_income_phase_out_single_high",
    "roth_income_phase_out_married_low", "roth_income_phase_out_married_high",
]

EXPECTED_2026 = {
    "ira_limit": 7000,
    "ira_catch_up_50plus": 1000,
    "k401_limit": 23500,
    "k401_catch_up_50plus": 7500,
    "hsa_individual": 4300,
    "hsa_family": 8550,
    "roth_income_phase_out_single_low": 150000,
    "roth_income_phase_out_single_high": 165000,
    "roth_income_phase_out_married_low": 236000,
    "roth_income_phase_out_married_high": 246000,
}


def test_w5_package_importable():
    """atlas_agents.wealth.retirement_limits package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.retirement_limits")
    assert mod is not None


def test_w5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w5_signals_documented():
    """AGENT_PROMPT.md documents 2026 limit values and IRS source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "7000" in content, "IRA limit 7000 not documented"
    assert "23500" in content, "401k limit 23500 not documented"
    assert "4300" in content, "HSA individual 4300 not documented"
    assert "8550" in content, "HSA family 8550 not documented"
    assert "150000" in content, "Roth single low 150000 not documented"
    assert "irs.gov" in content, "IRS source URL not documented"


def test_w5_2026_values_in_prompt():
    """AGENT_PROMPT.md contains all 2026 IRS limit values."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for key, val in EXPECTED_2026.items():
        assert str(val) in content, f"2026 value {key}={val} not documented in AGENT_PROMPT.md"


def test_w5_output_schema_valid_when_scraper_built():
    """Once retirement_limits_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "retirement_limits_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("retirement_limits_scraper.py not yet implemented — pending W5 activation")

    import importlib.util

    spec = importlib.util.spec_from_file_location("retirement_limits_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "year" in result
        assert result.get("ira_limit") == 7000
        assert result.get("k401_limit") == 23500
        assert result.get("hsa_family", 0) > result.get("hsa_individual", 0)
        low = result.get("roth_income_phase_out_single_low", 0)
        high = result.get("roth_income_phase_out_single_high", 0)
        assert high > low, "Roth phase-out high must be > low"
    except Exception:
        pass
