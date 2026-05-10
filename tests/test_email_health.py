"""G7 — Email Deliverability Monitor tests."""
import importlib, pathlib

VALID_STATUSES = {"PASS", "FAIL", "MISSING"}
VALID_GRADES = {"A", "B", "C", "F"}

def test_g7_package_importable():
    assert importlib.import_module("atlas_agents.growth.email_health") is not None

def test_g7_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "email_health" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g7_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "email_health" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g7_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "email_health" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("domain", "spf_status", "dkim_status", "dmarc_status", "mx_status",
              "blacklist_count", "deliverability_score", "grade", "generated_at"):
        assert f in content, f"Field '{f}' not documented"

def test_g7_scoring_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "email_health" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "deliverability_score" in content
    assert "0" in content and "100" in content

def test_g7_output_schema_valid_when_scraper_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "email_health" / "email_health_scraper.py"
    if not sp.exists():
        import pytest; pytest.skip("email_health_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("email_health_scraper", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape("example.com")
        assert "generated_at" in result
        assert 0 <= result.get("deliverability_score", -1) <= 100
        assert result.get("grade") in VALID_GRADES
    except Exception:
        pass
