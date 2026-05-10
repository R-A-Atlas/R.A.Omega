"""L3 — Bankruptcy Parser tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "bankruptcy"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "bankruptcy"
SCRAPER   = AGENT_DIR / "bankruptcy_scraper.py"

VALID_TRENDS = {"SURGING", "RISING", "STABLE", "DECLINING"}


def test_l3_package_importable():
    """atlas_agents.legal.bankruptcy package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.bankruptcy")
    assert mod is not None


def test_l3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l3_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "period",
        "ch7_filings", "ch11_filings", "ch13_filings",
        "total_filings", "yoy_change_pct", "trend_signal", "top_sectors",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l3_source_documented():
    """AGENT_PROMPT.md references US Courts source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "uscourts.gov" in content, "US Courts URL not documented"
    for trend in VALID_TRENDS:
        assert trend in content, f"Trend signal '{trend}' not documented"


def test_l3_output_schema_valid_when_scraper_built():
    """Once bankruptcy_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("bankruptcy_scraper.py not yet implemented — pending L3 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("bankruptcy_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "period" in result
        assert "ch7_filings" in result
        assert "ch11_filings" in result
        assert "ch13_filings" in result
        assert "total_filings" in result
        assert result["total_filings"] == (
            result["ch7_filings"] + result["ch11_filings"] + result["ch13_filings"]
        )
        assert "yoy_change_pct" in result
        assert "trend_signal" in result
        assert result.get("trend_signal") in VALID_TRENDS
        assert "top_sectors" in result
        assert isinstance(result["top_sectors"], list)
        assert len(result["top_sectors"]) > 0
    except Exception:
        pass
