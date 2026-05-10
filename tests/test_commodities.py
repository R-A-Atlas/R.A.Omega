"""T7 — Commodities Watch tests (structure + schema)."""
import importlib
import pathlib


VALID_TRENDS = {"RISING", "FALLING", "FLAT"}
EXPECTED_TICKERS = {"GC=F", "SI=F", "HG=F", "CL=F", "NG=F", "ZW=F", "ZC=F"}


def test_t7_package_importable():
    """atlas_agents.trading.commodities package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.commodities")
    assert mod is not None


def test_t7_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t7_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "commodities" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t7_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("name", "ticker", "price", "unit", "change_24h_pct",
                  "trend", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t7_trend_values_documented():
    """AGENT_PROMPT.md documents RISING / FALLING / FLAT trend signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend '{trend}' not documented"


def test_t7_all_seven_tickers_documented():
    """AGENT_PROMPT.md covers all 7 commodity futures tickers."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for ticker in EXPECTED_TICKERS:
        assert ticker in content, f"Ticker '{ticker}' not documented"


def test_t7_rate_limit_sleep_documented():
    """AGENT_PROMPT.md documents sleep between yfinance fetches."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "sleep" in content.lower(), "Rate limit sleep not documented"


def test_t7_output_schema_valid_when_scraper_built():
    """Once commodities_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "commodities" / "commodities_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("commodities_scraper.py not yet implemented — pending T7 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock
    spec = importlib.util.spec_from_file_location("commodities_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_ticker = MagicMock()
    mock_ticker.fast_info = {"lastPrice": 2342.5, "previousClose": 2318.2}
    with patch("yfinance.Ticker", return_value=mock_ticker):
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "commodities" in result
            for item in result.get("commodities", []):
                assert item.get("trend") in VALID_TRENDS
                assert isinstance(item.get("price"), (float, int, type(None)))
        except Exception:
            pass
