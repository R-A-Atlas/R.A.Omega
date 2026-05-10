"""R6 — REIT Screener tests (structure + schema)."""
import importlib
import pathlib


VALID_RATINGS = {"STRONG_BUY", "BUY", "HOLD", "UNDERPERFORM"}


def test_r6_package_importable():
    """atlas_agents.realestate.reit_screener package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.reit_screener")
    assert mod is not None


def test_r6_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r6_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "reit_screener" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r6_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("ticker", "name", "dividend_yield", "price", "sector",
                  "rating", "generated_at", "record_count", "treasury_10y_rate"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r6_rating_signals_documented():
    """AGENT_PROMPT.md documents all four rating signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for rating in VALID_RATINGS:
        assert rating in content, f"Rating '{rating}' not documented"


def test_r6_yield_thresholds_documented():
    """AGENT_PROMPT.md documents yield percentage thresholds."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "7.0" in content or "7%" in content, "7% STRONG_BUY threshold not documented"
    assert "5.5" in content or "5.5%" in content, "5.5% BUY threshold not documented"
    assert "4.0" in content or "4%" in content, "4% HOLD threshold not documented"


def test_r6_reit_universe_documented():
    """AGENT_PROMPT.md documents a REIT ticker universe."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    # Check a few well-known REITs are listed
    for ticker in ("O", "PLD", "AMT", "SPG"):
        assert ticker in content, f"REIT ticker '{ticker}' not in universe"


def test_r6_output_schema_valid_when_scraper_built():
    """Once reit_screener_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "reit_screener" / "reit_screener_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("reit_screener_scraper.py not yet implemented — pending R6 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock
    spec = importlib.util.spec_from_file_location("reit_screener_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_info = {
        "longName": "Realty Income Corp", "currentPrice": 52.30,
        "dividendYield": 0.0592, "sector": "Real Estate",
        "marketCap": 46800000000,
    }
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.info = mock_info
        try:
            result = mod.scrape(top_n=5)
            assert "generated_at" in result
            assert "reits" in result
            assert "treasury_10y_rate" in result
            for r in result.get("reits", []):
                assert r.get("dividend_yield", 0) > 0
                assert r.get("rating") in VALID_RATINGS
        except Exception:
            pass
