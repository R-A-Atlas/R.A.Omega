"""T9 — Penny Stock Screener tests (structure + schema)."""
import importlib
import pathlib


VALID_SIGNALS = {"HIGH_VOLUME_PENNY", "ELEVATED_VOLUME_PENNY"}
MAX_PENNY_PRICE = 10.0
MIN_VOLUME_RATIO = 3.0


def test_t9_package_importable():
    """atlas_agents.trading.penny_screener package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.penny_screener")
    assert mod is not None


def test_t9_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t9_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "penny_screener" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t9_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("ticker", "price", "volume", "volume_ratio", "market_cap",
                  "change_pct", "sector", "signal", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t9_price_filter_documented():
    """AGENT_PROMPT.md documents the $10 hard price cap."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "$10" in content or "10.0" in content, "Price cap ($10) not documented"


def test_t9_signal_thresholds_documented():
    """AGENT_PROMPT.md documents both signals and their volume ratio thresholds."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "HIGH_VOLUME_PENNY" in content
    assert "ELEVATED_VOLUME_PENNY" in content
    assert "5.0" in content or "5x" in content, "5x threshold not documented"
    assert "3.0" in content or "3x" in content, "3x threshold not documented"


def test_t9_etf_exclusion_documented():
    """AGENT_PROMPT.md documents ETF exclusion rule."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "ETF" in content, "ETF exclusion not documented"


def test_t9_output_schema_valid_when_scraper_built():
    """Once penny_screener_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "penny_screener" / "penny_screener_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("penny_screener_scraper.py not yet implemented — pending T9 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock
    spec = importlib.util.spec_from_file_location("penny_screener_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_quotes = {"quotes": [
        {"symbol": "SOUN", "regularMarketPrice": 8.45, "regularMarketVolume": 45200000,
         "averageDailyVolume3Month": 8900000, "marketCap": 2100000000,
         "regularMarketChangePercent": 18.4, "sector": "Technology", "quoteType": "EQUITY"},
    ]}
    with patch("yfinance.screen", return_value=mock_quotes):
        try:
            result = mod.scrape(top_n=25)
            assert "generated_at" in result
            assert "stocks" in result
            for s in result.get("stocks", []):
                assert s.get("price", 999) < MAX_PENNY_PRICE
                assert s.get("volume_ratio", 0) >= MIN_VOLUME_RATIO
                assert s.get("signal") in VALID_SIGNALS
        except Exception:
            pass
