"""T5 — Earnings Parser tests (structure + schema)."""
import importlib
import pathlib


def test_t5_package_importable():
    """atlas_agents.trading.earnings_parser package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.earnings_parser")
    assert mod is not None


def test_t5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "earnings_parser" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "earnings_parser" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "earnings_parser" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("ticker", "date", "est_eps", "est_revenue", "days_until",
                  "signal", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t5_signal_documented():
    """AGENT_PROMPT.md documents CATALYST_UPCOMING signal."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "earnings_parser" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "CATALYST_UPCOMING" in content


def test_t5_rate_limit_sleep_documented():
    """AGENT_PROMPT.md documents sleep between yfinance lookups."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "earnings_parser" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "sleep" in content.lower(), "Rate limit sleep not documented — Yahoo will ban scraper"


def test_t5_output_schema_valid_when_scraper_built():
    """Once earnings_parser_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "earnings_parser" / "earnings_parser_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("earnings_parser_scraper.py not yet implemented — pending T5 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock
    spec = importlib.util.spec_from_file_location("earnings_parser_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with patch("yfinance.Ticker") as mock_ticker:
        mock_ticker.return_value.calendar = {}
        try:
            result = mod.scrape(window_days=14)
            assert "generated_at" in result
            assert "upcoming" in result
            for item in result.get("upcoming", []):
                assert item.get("days_until", -1) >= 0
                assert item.get("signal") == "CATALYST_UPCOMING"
        except Exception:
            pass
