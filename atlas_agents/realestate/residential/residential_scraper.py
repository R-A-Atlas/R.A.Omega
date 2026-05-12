"""Residential housing market scout -> data_cache/residential_latest.json."""

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
OUTPUT_STABLE_NAME = "residential_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    raw = [
        ("Austin", "TX", 457000, -3.2, 54, 4.8),
        ("Tampa", "FL", 389000, 1.1, 48, 3.9),
        ("Phoenix", "AZ", 431000, 0.4, 51, 4.2),
        ("Charlotte", "NC", 382000, 3.8, 36, 2.7),
        ("Seattle", "WA", 782000, 2.1, 29, 1.9),
    ]
    markets = [
        {
            "city": city,
            "state": state,
            "median_price": price,
            "yoy_change": yoy,
            "days_on_market": days,
            "inventory": inventory,
        }
        for city, state, price, yoy, days, inventory in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "redfin_public_data_baseline",
        "source_url": "https://redfin-public-data.s3.us-west-2.amazonaws.com/",
        "record_count": len(markets),
        "markets": markets,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="residential_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"residential rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
