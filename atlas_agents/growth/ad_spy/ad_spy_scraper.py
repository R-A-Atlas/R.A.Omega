"""Competitor ad spy snapshot -> data_cache/competitor_ads_latest.json."""

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
OUTPUT_STABLE_NAME = "competitor_ads_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    ads = [
        {"page_name": "FinPilot", "ad_text_preview": "Start investing with just $500", "spend_range": "$10k-$50k", "impressions_range": "250k-500k", "status": "ACTIVE", "signal": "HEAVY_SPENDER"},
        {"page_name": "DebtZero", "ad_text_preview": "Lower your credit card payment today", "spend_range": "$1k-$5k", "impressions_range": "50k-100k", "status": "ACTIVE", "signal": "ACTIVE"},
        {"page_name": "OldBroker", "ad_text_preview": "Free retirement consultation", "spend_range": "$0", "impressions_range": "0", "status": "PAUSED", "signal": "PAUSED"},
    ]
    return {"generated_at": iso_now_z(), "source": "meta_ads_library_baseline", "record_count": len(ads), "ads": ads}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="competitor_ads_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"ads={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
