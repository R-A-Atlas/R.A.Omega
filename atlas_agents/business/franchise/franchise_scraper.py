"""Franchise evaluator -> data_cache/franchise_latest.json."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "franchise_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rating(units: int, low: int, high: int) -> str:
    avg = (low + high) / 2
    if units >= 10000 and avg <= 1500000:
        return "STRONG"
    if units >= 1000:
        return "GOOD"
    return "AVERAGE"


def scrape() -> dict[str, Any]:
    raw = [
        ("McDonald's", "Food", 1464000, 2503500, 4.0, 45000, 41000),
        ("7-Eleven", "Convenience", 53000, 1163000, 0.0, 0, 84000),
        ("Dunkin'", "Food", 121000, 1978000, 5.9, 40000, 13200),
        ("The UPS Store", "Business Services", 138400, 470000, 5.0, 29950, 5300),
        ("Jersey Mike's", "Food", 194000, 954000, 6.5, 18500, 2800),
        ("Ace Hardware", "Retail", 300000, 2200000, 0.0, 5000, 5600),
        ("Taco Bell", "Food", 576000, 3370000, 5.5, 45000, 8200),
    ]
    franchises = [
        {
            "name": name,
            "sector": sector,
            "initial_investment_low": low,
            "initial_investment_high": high,
            "royalty_pct": royalty,
            "franchise_fee": fee,
            "units_total": units,
            "rating": rating(units, low, high),
        }
        for name, sector, low, high, royalty, fee, units in raw
    ]
    return {"generated_at": iso_now_z(), "source": "entrepreneur_franchise_500_ftc_baseline", "source_urls": ["https://www.entrepreneur.com/franchise/rankings", "https://www.ftc.gov/tips-advice/business-center/guidance/franchise-rule"], "record_count": len(franchises), "franchises": franchises}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="franchise_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"franchises={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
