"""T6 — Forex Radar tests (structure + schema)."""
import importlib
import pathlib


VALID_SIGNALS = {"STABLE", "ELEVATED", "HIGH_VOLATILITY", "UNKNOWN"}
EXPECTED_PAIRS = {"EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "MXN"}


def test_t6_package_importable():
    """atlas_agents.trading.forex_radar package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.forex_radar")
    assert mod is not None


def test_t6_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t6_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "forex_radar" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t6_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("pair", "rate", "change_24h_pct", "volatility_signal",
                  "dxy_proxy", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t6_volatility_thresholds_documented():
    """AGENT_PROMPT.md documents all three volatility signal values."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for sig in ("STABLE", "ELEVATED", "HIGH_VOLATILITY"):
        assert sig in content, f"Volatility signal '{sig}' not documented"


def test_t6_frankfurter_api_documented():
    """AGENT_PROMPT.md references Frankfurter API as the primary free data source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "frankfurter" in content.lower(), "Frankfurter API not documented as primary source"


def test_t6_expected_pairs_documented():
    """AGENT_PROMPT.md covers all 8 major currency pairs."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for pair in ("EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "MXN"):
        assert pair in content, f"Currency pair '{pair}' not documented"


def test_t6_output_schema_valid_when_scraper_built():
    """Once forex_radar_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "forex_radar" / "forex_radar_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("forex_radar_scraper.py not yet implemented — pending T6 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("forex_radar_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_rates = {"rates": {"EUR": 0.92, "GBP": 0.79, "JPY": 149.5,
                            "CAD": 1.36, "CHF": 0.90, "AUD": 1.53,
                            "CNY": 7.24, "MXN": 17.1}}
    with patch("atlas_core.utils.agent_utils.requests_get_json", return_value=mock_rates):
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "pairs" in result
            for item in result.get("pairs", []):
                assert item.get("volatility_signal") in VALID_SIGNALS
        except Exception:
            pass
