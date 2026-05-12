"""Social sentiment analyzer -> data_cache/sentiment_latest.json."""

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
OUTPUT_STABLE_NAME = "sentiment_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal(score: float) -> str:
    if score >= 0.25:
        return "BULLISH"
    if score <= -0.25:
        return "BEARISH"
    return "NEUTRAL"


def scrape() -> dict[str, Any]:
    raw = [("NVDA", "stocks", 1840, 0.62, True), ("TSLA", "wallstreetbets", 2210, -0.18, True), ("mortgage rates", "RealEstate", 430, -0.34, False)]
    topics = [{"topic": t, "subreddit": sub, "mentions": m, "sentiment_score": score, "trending": tr, "signal": signal(score)} for t, sub, m, score, tr in raw]
    return {"generated_at": iso_now_z(), "source": "reddit_baseline", "record_count": len(topics), "topics": topics}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="sentiment_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"sentiment topics={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
