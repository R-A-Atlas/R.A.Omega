"""D10 — Sector Rotation Agent: functional tests (schema + cache write)."""
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

VALID_SIGNALS = {"LEADING", "OUTPERFORMING", "NEUTRAL", "UNDERPERFORMING", "LAGGING"}


def test_d10_scraper_file_exists():
    p = REPO_ROOT / "atlas_agents" / "intelligence" / "sector_rotation" / "sector_rotation_scraper.py"
    assert p.exists(), f"Scraper missing: {p}"


def test_d10_scrape_valid_schema():
    from atlas_agents.intelligence.sector_rotation.sector_rotation_scraper import scrape
    result = scrape()
    assert isinstance(result, dict)
    for key in ("generated_at", "source", "record_count", "sectors", "leading_sectors", "lagging_sectors"):
        assert key in result, f"Missing key: {key}"
    assert isinstance(result["sectors"], list)
    assert result["record_count"] > 0


def test_d10_sector_fields():
    from atlas_agents.intelligence.sector_rotation.sector_rotation_scraper import scrape
    result = scrape()
    for sector in result["sectors"]:
        assert "sector" in sector
        assert "avg_change_pct" in sector
        assert "rotation_signal" in sector
        assert sector["rotation_signal"] in VALID_SIGNALS, \
            f"Invalid signal: {sector['rotation_signal']}"
        assert sector["ticker_count"] > 0


def test_d10_writes_valid_json_to_cache():
    from atlas_agents.intelligence.sector_rotation.sector_rotation_scraper import scrape, write_outputs
    payload = scrape()
    stable, stamped = write_outputs(payload)
    assert stable.exists()
    assert stamped.exists()
    data = json.loads(stable.read_text(encoding="utf-8"))
    assert "generated_at" in data
    assert "sectors" in data
    assert len(data["sectors"]) > 0
    assert data["record_count"] == len(data["sectors"])
