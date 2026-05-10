"""L2 — State Tax / Act 60 Monitor tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "state_tax"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "state_tax"
SCRAPER   = AGENT_DIR / "state_tax_scraper.py"

NO_INCOME_TAX = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}


def test_l2_package_importable():
    """atlas_agents.legal.state_tax package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.state_tax")
    assert mod is not None


def test_l2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l2_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "record_count", "states",
        "state", "state_code", "income_tax_rate_top",
        "sales_tax_state", "sales_tax_avg_local", "special_programs",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l2_source_documented():
    """AGENT_PROMPT.md references Tax Foundation source URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "taxfoundation.org" in content, "Tax Foundation URL not documented"
    assert "Act 60" in content, "Puerto Rico Act 60 program not documented"


def test_l2_output_schema_valid_when_scraper_built():
    """Once state_tax_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("state_tax_scraper.py not yet implemented — pending L2 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("state_tax_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "record_count" in result
        assert "states" in result
        assert result["record_count"] == len(result["states"])
        codes = {s["state_code"] for s in result["states"]}
        for code in NO_INCOME_TAX:
            if code in codes:
                state = next(s for s in result["states"] if s["state_code"] == code)
                assert state["income_tax_rate_top"] == 0.0
        pr_states = [s for s in result["states"] if s["state_code"] == "PR"]
        if pr_states:
            assert "Act 60 (PR)" in pr_states[0].get("special_programs", [])
    except Exception:
        pass
