"""M7 — Global Liquidity (M2 Money Supply) tests."""
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_FILE = REPO_ROOT / "data_cache" / "global_liquidity_latest.json"
AGENT_DIR = REPO_ROOT / "atlas_agents" / "macro" / "global_liquidity"


def test_m7_package_importable():
    import importlib
    mod = importlib.import_module("atlas_agents.macro.global_liquidity")
    assert mod is not None


def test_m7_scraper_exists():
    assert (AGENT_DIR / "global_liquidity_scraper.py").exists()


def test_m7_scrape_returns_valid_schema():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from atlas_agents.macro.global_liquidity.global_liquidity_scraper import scrape
    result = scrape()
    assert isinstance(result, dict)
    assert "generated_at" in result
    assert "m2_billions_usd" in result
    assert "m2_trillions_usd" in result
    assert "yoy_change_pct" in result
    assert "liquidity_regime" in result
    assert result["liquidity_regime"] in {
        "EXPANSION", "MODERATE_GROWTH", "STAGNANT", "CONTRACTION"
    }
    assert result["m2_trillions_usd"] > 15.0, "M2 should be above $15T"
    assert isinstance(result.get("history"), list)
    assert result.get("record_count", 0) > 0


def test_m7_writes_cache_json():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from atlas_agents.macro.global_liquidity.global_liquidity_scraper import scrape, write_outputs
    payload = scrape()
    stable, stamped = write_outputs(payload)
    assert stable.exists()
    data = json.loads(stable.read_text())
    assert "generated_at" in data
    assert "liquidity_regime" in data
    assert data["m2_billions_usd"] > 0
