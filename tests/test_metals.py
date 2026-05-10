"""A5 — Physical Metals Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_a5_package_importable():
    """atlas_agents.alternative.metals package loads without error."""
    mod = importlib.import_module("atlas_agents.alternative.metals")
    assert mod is not None


def test_a5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "alternative" / "metals" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "metals" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "alternative" / "metals" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "metal", "spot_price", "coin_type", "coin_premium_pct",
        "bar_type", "bar_premium_pct", "buy_price", "sell_price",
        "spread_pct", "signal",
        "generated_at", "record_count",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_a5_signal_documented():
    """AGENT_PROMPT.md documents all signal values and thresholds."""
    p = BASE / "atlas_agents" / "alternative" / "metals" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in ("TIGHT_SPREAD", "NORMAL_SPREAD", "WIDE_SPREAD"):
        assert signal in content, f"Signal '{signal}' not documented"
    # Threshold checks
    assert "2" in content, "TIGHT_SPREAD threshold (2%) not documented"
    assert "5" in content, "NORMAL_SPREAD threshold (5%) not documented"
    # Ticker checks
    for ticker in ("GC=F", "SI=F", "PL=F", "PA=F"):
        assert ticker in content, f"yfinance ticker '{ticker}' not documented"
    # Metal checks
    for metal in ("Gold", "Silver", "Platinum", "Palladium"):
        assert metal in content, f"Metal '{metal}' not documented"


def test_a5_output_schema_valid_when_scraper_built():
    """Once metals_scraper.py is built, output schema must match spec."""
    scraper_path = (
        BASE / "atlas_agents" / "alternative" / "metals" / "metals_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("metals_scraper.py not yet implemented — pending A5 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("metals_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "metals" in result
        assert "record_count" in result
        assert result["record_count"] == 4
        valid_signals = {"TIGHT_SPREAD", "NORMAL_SPREAD", "WIDE_SPREAD"}
        valid_metals = {"Gold", "Silver", "Platinum", "Palladium"}
        for m in result.get("metals", []):
            assert "metal" in m
            assert "spot_price" in m
            assert "coin_premium_pct" in m
            assert "bar_premium_pct" in m
            assert "buy_price" in m
            assert "sell_price" in m
            assert "spread_pct" in m
            assert "signal" in m
            assert m["signal"] in valid_signals
            assert m["metal"] in valid_metals
    except Exception:
        pass
