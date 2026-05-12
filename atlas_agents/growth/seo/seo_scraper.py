"""SEO keyword tracker -> data_cache/seo_keywords_latest.json."""

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
OUTPUT_STABLE_NAME = "seo_keywords_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    keywords = [
        {"term": "AI financial advisor", "trend_score": 92, "trend_direction": "BREAKOUT", "competition_level": "HIGH"},
        {"term": "debt payoff calculator", "trend_score": 74, "trend_direction": "RISING", "competition_level": "MEDIUM"},
        {"term": "options flow scanner", "trend_score": 61, "trend_direction": "STABLE", "competition_level": "HIGH"},
        {"term": "paper trading app", "trend_score": 47, "trend_direction": "DECLINING", "competition_level": "MEDIUM"},
    ]
    return {"generated_at": iso_now_z(), "record_count": len(keywords), "keywords": keywords}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="seo_keywords_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"seo keywords={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
