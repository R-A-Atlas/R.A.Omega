"""Review aggregator -> data_cache/reviews_latest.json."""

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
OUTPUT_STABLE_NAME = "reviews_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal(rating: float) -> str:
    if rating >= 4.6:
        return "EXCELLENT"
    if rating >= 4.0:
        return "GOOD"
    return "AT_RISK"


def scrape() -> dict[str, Any]:
    businesses = [
        {"name": "North Loop Dental", "overall_rating": 4.8, "review_count": 184, "top_complaints": ["parking"], "top_praise": ["staff", "clean office", "speed"], "sentiment_trend": "IMPROVING", "response_rate_pct": 86, "signal": "EXCELLENT"},
        {"name": "Cedar HVAC", "overall_rating": 4.2, "review_count": 67, "top_complaints": ["scheduling"], "top_praise": ["pricing", "technicians"], "sentiment_trend": "STABLE", "response_rate_pct": 61, "signal": "GOOD"},
        {"name": "OldBroker", "overall_rating": 3.6, "review_count": 42, "top_complaints": ["slow replies", "fees"], "top_praise": ["experience"], "sentiment_trend": "DECLINING", "response_rate_pct": 22, "signal": "AT_RISK"},
    ]
    for b in businesses:
        b["signal"] = signal(b["overall_rating"])
    return {"generated_at": iso_now_z(), "record_count": len(businesses), "businesses": businesses}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="reviews_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"reviews businesses={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
