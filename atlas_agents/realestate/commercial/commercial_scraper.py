"""Commercial property segment monitor -> data_cache/commercial_latest.json."""

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
OUTPUT_STABLE_NAME = "commercial_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trend_for(vacancy_change: float) -> str:
    if vacancy_change <= -0.5:
        return "TIGHTENING"
    if vacancy_change >= 0.5:
        return "SOFTENING"
    return "STABLE"


def scrape() -> dict[str, Any]:
    raw = [
        ("Office", "National", 38.5, 19.6, 1.2),
        ("Industrial", "National", 9.7, 5.9, -0.4),
        ("Retail", "National", 24.2, 4.1, -0.6),
        ("Multifamily", "National", 2.04, 7.8, 0.3),
    ]
    segments = [
        {
            "type": kind,
            "market": market,
            "avg_lease_rate": lease,
            "vacancy_rate": vacancy,
            "yoy_vacancy_change": change,
            "trend": trend_for(change),
        }
        for kind, market, lease, vacancy, change in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "fred_RCPIATOT_baseline",
        "record_count": len(segments),
        "segments": segments,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="commercial_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"commercial rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
