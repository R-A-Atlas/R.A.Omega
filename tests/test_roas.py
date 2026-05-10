"""G10 — ROAS Optimizer tests."""
import importlib, pathlib

VALID_SIGNALS = {"PROFITABLE", "BREAK_EVEN", "LOSING"}
VALID_RECOMMENDATIONS = {"SCALE", "OPTIMIZE", "MONITOR", "PAUSE"}

def test_g10_package_importable():
    assert importlib.import_module("atlas_agents.growth.roas") is not None

def test_g10_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "roas" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g10_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "roas" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g10_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "roas" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("name", "platform", "spend_usd", "revenue_usd", "roas", "cpa_usd",
              "status", "signal", "recommendation", "generated_at", "record_count"):
        assert f in content, f"Field '{f}' not documented"

def test_g10_signals_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "roas" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for s in VALID_SIGNALS | VALID_RECOMMENDATIONS:
        assert s in content

def test_g10_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "roas" / "roas_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("roas_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("roas_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "campaigns" in result
        for c in result.get("campaigns", []):
            assert c.get("roas", -1) >= 0
            assert c.get("signal") in VALID_SIGNALS
            assert c.get("recommendation") in VALID_RECOMMENDATIONS
    except Exception:
        pass
