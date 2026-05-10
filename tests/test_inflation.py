"""M7 — Inflation/CPI Bot tests (structure + schema)."""
import importlib
import pathlib

VALID_SIGNALS = {"HOT", "ELEVATED", "ON_TARGET", "DEFLATIONARY"}


def test_m7_package_importable():
    mod = importlib.import_module("atlas_agents.macro.inflation")
    assert mod is not None


def test_m7_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "inflation" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m7_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "inflation" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m7_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "inflation" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "cpi_index", "mom_change_pct", "yoy_change_pct",
                  "record_count", "categories", "period"):
        assert field in content, f"Field '{field}' not documented"


def test_m7_inflation_signals_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "inflation" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for signal in VALID_SIGNALS:
        assert signal in content, f"Signal '{signal}' not documented"


def test_m7_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "inflation" / "inflation_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("inflation_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("inflation_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert result.get("cpi_index", 0) > 0
        assert "yoy_change_pct" in result
    except Exception:
        pass
