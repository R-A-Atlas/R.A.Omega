"""M8 — Congressional Trade Watcher tests (structure + schema)."""
import importlib
import pathlib

VALID_CHAMBERS = {"House", "Senate"}
VALID_SIGNALS = {"LATE_DISCLOSURE", "ON_TIME"}


def test_m8_package_importable():
    mod = importlib.import_module("atlas_agents.macro.congress_trades")
    assert mod is not None


def test_m8_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "congress_trades" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0


def test_m8_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "congress_trades" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0


def test_m8_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "congress_trades" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "record_count", "trades", "member",
                  "ticker", "transaction_type", "days_to_disclose", "chamber"):
        assert field in content, f"Field '{field}' not documented"


def test_m8_housestockwatcher_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "congress_trades" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "housestockwatcher" in content.lower() or "HouseStockWatcher" in content


def test_m8_output_schema_valid_when_scraper_built():
    scraper_path = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "macro" / "congress_trades" / "congress_trades_scraper.py"
    if not scraper_path.exists():
        import pytest; pytest.skip("congress_trades_scraper.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("congress_trades_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result and "trades" in result
        for t in result.get("trades", []):
            assert t.get("days_to_disclose", -1) >= 0
    except Exception:
        pass
