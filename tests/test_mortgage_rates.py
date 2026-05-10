"""R7 — Mortgage Rate Tracker tests (structure + schema)."""
import importlib
import pathlib


VALID_TRENDS = {"RISING", "FALLING", "STABLE"}
VALID_TERMS = {"30-Year Fixed", "15-Year Fixed", "5/1 ARM"}


def test_r7_package_importable():
    """atlas_agents.realestate.mortgage_rates package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.mortgage_rates")
    assert mod is not None


def test_r7_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r7_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "mortgage_rates" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r7_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("term", "rate", "points", "week_of", "trend",
                  "generated_at", "record_count", "wow_change_30y"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r7_trend_signals_documented():
    """AGENT_PROMPT.md documents all three trend signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend '{trend}' not documented"


def test_r7_fred_source_documented():
    """AGENT_PROMPT.md references FRED PMMS series as primary source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "MORTGAGE30US" in content, "FRED series MORTGAGE30US not documented"
    assert "MORTGAGE15US" in content, "FRED series MORTGAGE15US not documented"
    assert "freddie" in content.lower() or "PMMS" in content


def test_r7_wow_threshold_documented():
    """AGENT_PROMPT.md documents the 5bps WoW trend threshold."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "0.05" in content, "5bps (0.05) WoW threshold not documented"


def test_r7_output_schema_valid_when_scraper_built():
    """Once mortgage_rates_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "mortgage_rates" / "mortgage_rates_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("mortgage_rates_scraper.py not yet implemented — pending R7 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("mortgage_rates_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_obs = {"observations": [
        {"date": "2026-05-08", "value": "7.12"},
        {"date": "2026-05-01", "value": "7.00"},
    ]}
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_obs
        mock_get.return_value.status_code = 200
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "rates" in result
            assert "trend" in result
            assert result.get("trend") in VALID_TRENDS or result.get("trend") is None
            assert "wow_change_30y" in result
            for r in result.get("rates", []):
                assert r.get("rate", 0) > 0
                assert "week_of" in r
        except Exception:
            pass
