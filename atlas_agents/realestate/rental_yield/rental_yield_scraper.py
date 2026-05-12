"""Rental yield calculator -> data_cache/rental_yield_latest.json."""

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
OUTPUT_STABLE_NAME = "rental_yield_latest.json"
MORTGAGE_RATE = 6.84


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def yield_signal(value: float) -> str:
    if value >= 7.0:
        return "GOOD"
    if value >= 5.0:
        return "AVERAGE"
    return "LOW"


def scrape() -> dict[str, Any]:
    raw = [
        ("Cleveland", "OH", 1125, 1425, 176000),
        ("Dallas", "TX", 1650, 2050, 342000),
        ("Tampa", "FL", 1795, 2250, 389000),
        ("Charlotte", "NC", 1510, 1840, 382000),
        ("Seattle", "WA", 2320, 2925, 782000),
    ]
    markets = []
    for city, state, rent1, rent2, price in raw:
        estimate = round((rent2 * 12 / price) * 100, 2)
        markets.append(
            {
                "city": city,
                "state": state,
                "avg_rent_1br": rent1,
                "avg_rent_2br": rent2,
                "median_home_price": price,
                "mortgage_rate": MORTGAGE_RATE,
                "yield_estimate": estimate,
                "yield_signal": yield_signal(estimate),
            }
        )
    return {
        "generated_at": iso_now_z(),
        "source": "rent_home_price_baseline",
        "record_count": len(markets),
        "markets": markets,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="rental_yield_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"rental yield rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
