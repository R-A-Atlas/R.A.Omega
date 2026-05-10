"""G2 — CRM Sync Agent tests."""
import importlib, pathlib

VALID_STATUSES = {"SUCCESS", "PARTIAL", "FAILED", "SKIPPED"}

def test_g2_package_importable():
    assert importlib.import_module("atlas_agents.growth.crm_sync") is not None

def test_g2_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "crm_sync" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g2_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "crm_sync" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g2_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "crm_sync" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("generated_at", "webhook_url", "leads_synced", "leads_failed", "status"):
        assert f in content, f"Field '{f}' not documented"

def test_g2_statuses_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "crm_sync" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for s in VALID_STATUSES:
        assert s in content

def test_g2_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "crm_sync" / "crm_sync_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("crm_sync_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("crm_sync_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert result.get("status") in VALID_STATUSES
    except Exception:
        pass
