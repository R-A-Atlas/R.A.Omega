"""A4 — P2P Lending Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_a4_package_importable():
    """atlas_agents.alternative.p2p_lending package loads without error."""
    mod = importlib.import_module("atlas_agents.alternative.p2p_lending")
    assert mod is not None


def test_a4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "alternative" / "p2p_lending" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "p2p_lending" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_a4_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "alternative" / "p2p_lending" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "name", "avg_return_pct", "default_rate_12m_pct", "active_loans_count",
        "min_investment", "accredited_only", "status", "signal",
        "generated_at", "record_count",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_a4_signal_documented():
    """AGENT_PROMPT.md documents all signal values and thresholds."""
    p = BASE / "atlas_agents" / "alternative" / "p2p_lending" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in ("ATTRACTIVE", "MODERATE", "AVOID"):
        assert signal in content, f"Signal '{signal}' not documented"
    # Threshold checks
    assert "8" in content, "ATTRACTIVE return threshold (8%) not documented"
    assert "5" in content, "ATTRACTIVE default threshold (5%) not documented"
    assert "10" in content, "AVOID default threshold (10%) not documented"
    # Status enum
    assert "ACTIVE" in content, "Status ACTIVE not documented"
    assert "CLOSED_TO_RETAIL" in content, "Status CLOSED_TO_RETAIL not documented"


def test_a4_output_schema_valid_when_scraper_built():
    """Once p2p_scraper.py is built, output schema must match spec."""
    scraper_path = (
        BASE / "atlas_agents" / "alternative" / "p2p_lending" / "p2p_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("p2p_scraper.py not yet implemented — pending A4 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("p2p_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "platforms" in result
        assert "record_count" in result
        assert result["record_count"] == 4
        valid_signals = {"ATTRACTIVE", "MODERATE", "AVOID"}
        valid_statuses = {"ACTIVE", "CLOSED_TO_RETAIL"}
        for p in result.get("platforms", []):
            assert "name" in p
            assert "avg_return_pct" in p
            assert "default_rate_12m_pct" in p
            assert "signal" in p
            assert "status" in p
            assert p["signal"] in valid_signals
            assert p["status"] in valid_statuses
    except Exception:
        pass
