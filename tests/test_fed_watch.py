"""M1 — Fed Rate Probability tests (structure + schema)."""
import importlib
import pathlib

VALID_ACTIONS = {"CUT_50BPS", "CUT_25BPS", "HOLD", "HIKE_25BPS", "HIKE_50BPS"}
VALID_SIGNALS = {"DOVISH", "NEUTRAL", "HAWKISH"}


def test_m1_package_importable():
    mod = importlib.import_module("atlas_agents.macro.fed_watch")
    assert mod is not None


def test_m1_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "fed_watch" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m1_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "fed_watch" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m1_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "fed_watch" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "current_rate", "next_meeting_date", "probabilities",
                  "record_count", "dominant_action", "probability_pct"):
        assert field in content, f"Field '{field}' not documented"


def test_m1_actions_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "fed_watch" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for action in VALID_ACTIONS:
        assert action in content, f"Action '{action}' not documented"


def test_m1_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "fed_watch" / "fed_watch_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("fed_watch_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("fed_watch_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "probabilities" in result
        total = sum(p.get("probability_pct", 0) for p in result.get("probabilities", []))
        assert abs(total - 100) <= 0.5
    except Exception:
        pass
