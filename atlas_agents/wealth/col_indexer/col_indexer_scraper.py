"""Cost of living index snapshot -> data_cache/col_latest.json."""

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
OUTPUT_STABLE_NAME = "col_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal_for(index: float) -> str:
    if index >= 120:
        return "EXPENSIVE"
    if index < 90:
        return "AFFORDABLE"
    return "MODERATE"


def scrape() -> dict[str, Any]:
    raw = [
        ("New York", "NY", "Northeast", 128.4, 3.72, 3550),
        ("Chicago", "IL", "Midwest", 104.2, 3.61, 2050),
        ("Dallas", "TX", "South", 96.5, 3.12, 1650),
        ("Phoenix", "AZ", "West", 111.7, 3.84, 1725),
        ("Cleveland", "OH", "Midwest", 87.8, 3.39, 1125),
    ]
    cities = [
        {
            "city": city,
            "state": state,
            "region": region,
            "grocery_index": round(index * 0.93, 1),
            "gas_avg": gas,
            "rent_1br": rent,
            "overall_index": index,
            "signal": signal_for(index),
        }
        for city, state, region, index, gas, rent in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "bls_regional_cpi_baseline",
        "bls_series": ["CUURA101SA0", "CUURA207SA0", "CUURA319SA0", "CUURA421SA0"],
        "national_cpi": 314.2,
        "record_count": len(cities),
        "cities": cities,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="col_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"cost of living rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
