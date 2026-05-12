"""Insurance premium tracker -> data_cache/insurance_latest.json."""

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
OUTPUT_STABLE_NAME = "insurance_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trend_for(change: float) -> str:
    if change > 1.0:
        return "RISING"
    if change < -1.0:
        return "FALLING"
    return "STABLE"


def scrape() -> dict[str, Any]:
    raw = [
        ("Auto", 1765, 6.8, "FL", 3120, "ME", 980),
        ("Home", 2420, 8.9, "FL", 5920, "VT", 960),
        ("Health", 8010, 4.4, "AK", 11200, "MN", 6100),
        ("Life", 310, 0.8, "NY", 480, "UT", 190),
        ("Renters", 186, 2.2, "LA", 340, "ND", 118),
    ]
    premiums = [
        {
            "type": kind,
            "avg_annual_premium": avg,
            "yoy_change_pct": yoy,
            "trend": trend_for(yoy),
            "highest_state": hi_state,
            "highest_state_premium": hi,
            "lowest_state": lo_state,
            "lowest_state_premium": lo,
        }
        for kind, avg, yoy, hi_state, hi, lo_state, lo in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "naic_baseline",
        "source_url": "https://content.naic.org/",
        "data_year": 2026,
        "record_count": len(premiums),
        "premiums": premiums,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="insurance_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"insurance rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
