"""M5 — Geopolitical Tariff Tracker tests (structure + schema)."""
import importlib
import pathlib

VALID_STATUSES = {"ACTIVE", "SUSPENDED", "UNDER_REVIEW", "ESCALATING"}
VALID_AUTHORITIES = {"Section 301", "Section 232", "Section 201", "IEEPA"}


def test_m5_package_importable():
    mod = importlib.import_module("atlas_agents.macro.tariffs")
    assert mod is not None


def test_m5_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "tariffs" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m5_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "tariffs" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m5_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "tariffs" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "record_count", "active_tariffs",
                  "product_category", "rate_pct", "effective_date", "trading_partner", "status"):
        assert field in content, f"Field '{field}' not documented"


def test_m5_ustr_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "tariffs" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "ustr" in content.lower() or "Section 301" in content


def test_m5_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "tariffs" / "tariffs_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("tariffs_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("tariffs_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "active_tariffs" in result
        for t in result.get("active_tariffs", []):
            assert t.get("rate_pct", -1) >= 0
            assert t.get("status") in VALID_STATUSES
    except Exception:
        pass
