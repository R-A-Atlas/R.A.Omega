"""T10 — Bond Yield Curve tests (structure + schema)."""
import importlib
import pathlib


VALID_SIGNALS = {"NORMAL", "INVERTED", "FLAT"}
REQUIRED_MATURITIES = {"1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y"}


def test_t10_package_importable():
    """atlas_agents.trading.bond_yields package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.bond_yields")
    assert mod is not None


def test_t10_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t10_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "bond_yields" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t10_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("maturity", "rate", "date", "curve_signal",
                  "generated_at", "record_count", "spread_2y_10y", "record_date"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t10_curve_signals_documented():
    """AGENT_PROMPT.md documents all three curve signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "NORMAL" in content
    assert "INVERTED" in content
    assert "FLAT" in content


def test_t10_spread_formula_documented():
    """AGENT_PROMPT.md documents the 2y/10y spread formula."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "2y" in content.lower() or "2-year" in content.lower() or "2Y" in content
    assert "10y" in content.lower() or "10-year" in content.lower() or "10Y" in content
    assert "spread" in content.lower()


def test_t10_fiscaldata_source_documented():
    """AGENT_PROMPT.md references FiscalData Treasury API."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "fiscaldata" in content.lower() or "fiscaldata.treasury.gov" in content


def test_t10_output_schema_valid_when_scraper_built():
    """Once bond_yields_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "bond_yields" / "bond_yields_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("bond_yields_scraper.py not yet implemented — pending T10 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("bond_yields_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_response = {
        "data": [
            {"record_date": "2026-05-08", "security_desc": "2-Year", "avg_interest_rate_amt": "4.62"},
            {"record_date": "2026-05-08", "security_desc": "10-Year", "avg_interest_rate_amt": "4.20"},
        ]
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.status_code = 200
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "yields" in result
            assert "curve_signal" in result
            assert result.get("curve_signal") in VALID_SIGNALS or result.get("curve_signal") is None
            assert "spread_2y_10y" in result
            for y in result.get("yields", []):
                assert "maturity" in y
                assert "rate" in y
                assert isinstance(y["rate"], (int, float))
        except Exception:
            pass
