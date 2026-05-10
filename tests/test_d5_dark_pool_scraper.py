"""D5 — Dark Pool Monitor: functional scraper tests (schema + cache write)."""
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

VALID_SIGNALS = {"ELEVATED_DARK_POOL", "HIGH_DARK_POOL"}


def test_d5_scraper_file_exists():
    p = REPO_ROOT / "atlas_agents" / "trading" / "dark_pool" / "dark_pool_scraper.py"
    assert p.exists(), f"Scraper missing: {p}"


def test_d5_scrape_valid_schema():
    from atlas_agents.trading.dark_pool.dark_pool_scraper import scrape
    result = scrape(top_n=20)
    assert isinstance(result, dict)
    for key in ("generated_at", "source", "week_of", "record_count", "signals"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["signals"], list)
    assert result["record_count"] >= 0


def test_d5_signals_above_threshold():
    from atlas_agents.trading.dark_pool.dark_pool_scraper import scrape
    result = scrape(top_n=50)
    for sig in result["signals"]:
        assert sig["dark_pool_ratio"] >= 0.30, \
            f"{sig['ticker']} ratio {sig['dark_pool_ratio']} below threshold"
        assert sig["signal"] in VALID_SIGNALS
        assert sig["dark_pool_volume"] > 0
        assert sig["total_volume"] >= sig["dark_pool_volume"]


def test_d5_writes_valid_json_to_cache():
    from atlas_agents.trading.dark_pool.dark_pool_scraper import scrape, write_outputs
    payload = scrape()
    stable, stamped = write_outputs(payload)
    assert stable.exists()
    assert stamped.exists()
    data = json.loads(stable.read_text(encoding="utf-8"))
    assert "generated_at" in data
    assert "signals" in data
    assert data["record_count"] == len(data["signals"])
