"""Lead generation scanner -> data_cache/leads_latest.json."""

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
OUTPUT_STABLE_NAME = "leads_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lead_signal(rating: float, reviews: int, modern: bool) -> str:
    if rating >= 4.5 and reviews >= 100 and not modern:
        return "HOT_LEAD"
    if rating >= 4.0:
        return "WARM_LEAD"
    return "COLD_LEAD"


def scrape() -> dict[str, Any]:
    raw = [
        ("North Loop Dental", "212 Market St", "555-0101", "http://northloopdental.example", 4.8, 184, False),
        ("Cedar HVAC", "88 Industrial Rd", "555-0102", "https://cedarhvac.example", 4.3, 67, True),
        ("Prime Auto Detail", "510 Main Ave", "555-0103", "", 4.7, 129, False),
    ]
    leads = [{"business_name": n, "address": a, "phone": p, "website": w, "rating": r, "review_count": c, "has_modern_site": m, "signal": lead_signal(r, c, m)} for n, a, p, w, r, c, m in raw]
    return {"generated_at": iso_now_z(), "record_count": len(leads), "leads": leads}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="leads_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"leads={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
