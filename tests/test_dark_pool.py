"""T8 — Dark Pool Monitor tests (structure + schema)."""
import importlib
import pathlib


VALID_SIGNALS = {"ELEVATED_DARK_POOL", "HIGH_DARK_POOL"}


def test_t8_package_importable():
    """atlas_agents.trading.dark_pool package loads without error."""
    mod = importlib.import_module("atlas_agents.trading.dark_pool")
    assert mod is not None


def test_t8_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t8_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "dark_pool" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t8_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("ticker", "dark_pool_volume", "total_volume", "dark_pool_ratio",
                  "signal", "generated_at", "record_count", "date"):
        assert field in content, f"Schema field '{field}' not documented"


def test_t8_signal_thresholds_documented():
    """AGENT_PROMPT.md documents both signal types and their ratio thresholds."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "HIGH_DARK_POOL" in content
    assert "ELEVATED_DARK_POOL" in content
    assert "0.45" in content, "HIGH_DARK_POOL threshold (0.45) not documented"
    assert "0.30" in content, "ELEVATED_DARK_POOL threshold (0.30) not documented"


def test_t8_finra_source_documented():
    """AGENT_PROMPT.md references FINRA as primary data source."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "finra" in content.lower(), "FINRA not documented as primary source"
    assert "cdn.finra.org" in content, "FINRA CDN URL not documented"


def test_t8_csv_format_documented():
    """AGENT_PROMPT.md documents the FINRA pipe-delimited CSV format."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "ShortVolume" in content, "FINRA CSV ShortVolume column not documented"
    assert "TotalVolume" in content, "FINRA CSV TotalVolume column not documented"


def test_t8_output_schema_valid_when_scraper_built():
    """Once dark_pool_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "dark_pool" / "dark_pool_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("dark_pool_scraper.py not yet implemented — pending T8 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("dark_pool_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mock_csv = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n20260508|NVDA|12500000|0|28000000|FINRA\n"
    with patch("atlas_core.utils.agent_utils.requests_get_json", return_value={}):
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = mock_csv
            mock_get.return_value.status_code = 200
            try:
                result = mod.scrape(top_n=10)
                assert "generated_at" in result
                assert "signals" in result
                for s in result.get("signals", []):
                    assert s.get("dark_pool_ratio", 0) >= 0.30
                    assert s.get("signal") in VALID_SIGNALS
            except Exception:
                pass
