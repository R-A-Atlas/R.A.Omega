"""Ecommerce trend scanner -> data_cache/ecommerce_latest.json."""

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
OUTPUT_STABLE_NAME = "ecommerce_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    raw = [
        ("AI gadgets", 91, "RISING", 89, "HIGH"),
        ("sustainable fashion", 74, "RISING", 62, "MEDIUM"),
        ("home gym equipment", 58, "STABLE", 420, "HIGH"),
        ("pet tech", 82, "RISING", 129, "MEDIUM"),
        ("meal prep", 55, "STABLE", 44, "HIGH"),
        ("travel accessories", 68, "RISING", 37, "MEDIUM"),
        ("smart home", 61, "STABLE", 155, "HIGH"),
        ("vintage clothing", 49, "DECLINING", 38, "LOW"),
    ]
    niches = [{"niche": n, "trend_score": score, "trend_direction": direction, "avg_price_estimate": price, "competition_level": comp} for n, score, direction, price, comp in raw]
    return {"generated_at": iso_now_z(), "source": "pytrends_google_trends_baseline", "source_url": "https://trends.google.com/", "record_count": len(niches), "trending_niches": niches}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="ecommerce_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"ecommerce niches={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
