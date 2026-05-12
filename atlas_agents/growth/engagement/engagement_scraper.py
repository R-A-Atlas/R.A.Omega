"""Engagement rater -> data_cache/engagement_latest.json."""

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
OUTPUT_STABLE_NAME = "engagement_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tier(followers: int) -> str:
    if followers < 10_000:
        return "NANO"
    if followers < 100_000:
        return "MICRO"
    if followers < 1_000_000:
        return "MID"
    return "MACRO"


def signal(rate: float) -> str:
    if rate >= 0.04:
        return "HIGH_ENGAGEMENT"
    if rate >= 0.015:
        return "AVERAGE"
    return "LOW"


def scrape() -> dict[str, Any]:
    raw = [("@financealice", "Instagram", 8500, 610, 42), ("@marketmentor", "TikTok", 126000, 4200, 315), ("@macrodesk", "X", 1_400_000, 9200, 540)]
    profiles = []
    for handle, platform, followers, likes, comments in raw:
        rate = round((likes + comments) / followers, 4)
        profiles.append({"handle": handle, "platform": platform, "followers": followers, "avg_likes": likes, "avg_comments": comments, "engagement_rate": rate, "tier": tier(followers), "signal": signal(rate)})
    return {"generated_at": iso_now_z(), "record_count": len(profiles), "profiles": profiles}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="engagement_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"engagement profiles={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
