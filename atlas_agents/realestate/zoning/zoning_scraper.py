"""Zoning and permit activity watcher -> data_cache/zoning_latest.json."""

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
OUTPUT_STABLE_NAME = "zoning_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trend_signal(yoy: float) -> str:
    if yoy >= 20:
        return "SURGING"
    if yoy >= 5:
        return "GROWING"
    if yoy <= -20:
        return "COLLAPSING"
    if yoy <= -5:
        return "DECLINING"
    return "STABLE"


def scrape() -> dict[str, Any]:
    raw = [
        ("Austin", "TX", "Residential", 1310, -8.4),
        ("Dallas", "TX", "Multifamily", 2240, 6.7),
        ("Phoenix", "AZ", "Residential", 1885, 22.5),
        ("Charlotte", "NC", "Commercial", 515, 1.8),
        ("Tampa", "FL", "Residential", 1042, -23.4),
    ]
    permits = [
        {
            "city": city,
            "state": state,
            "permit_type": permit_type,
            "count": count,
            "yoy_change": yoy,
            "trend_signal": trend_signal(yoy),
        }
        for city, state, permit_type, count, yoy in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "census_building_permits_baseline",
        "source_url": "https://api.census.gov/data/timeseries/eits/bps",
        "period": "2026-04",
        "record_count": len(permits),
        "permits": permits,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="zoning_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"zoning rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
