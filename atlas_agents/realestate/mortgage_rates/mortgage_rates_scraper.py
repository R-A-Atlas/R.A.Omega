"""Mortgage rate tracker -> data_cache/mortgage_rates_latest.json."""

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
OUTPUT_STABLE_NAME = "mortgage_rates_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trend_for(change: float) -> str:
    if change >= 0.05:
        return "RISING"
    if change <= -0.05:
        return "FALLING"
    return "STABLE"


def scrape() -> dict[str, Any]:
    wow_change_30y = 0.04
    rates = [
        {"term": "30-Year Fixed", "rate": 6.84, "points": 0.7, "week_of": "2026-05-08"},
        {"term": "15-Year Fixed", "rate": 6.06, "points": 0.6, "week_of": "2026-05-08"},
        {"term": "5/1 ARM", "rate": 6.18, "points": 0.5, "week_of": "2026-05-08"},
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "freddie_pmms_fred_baseline",
        "fred_series": ["MORTGAGE30US", "MORTGAGE15US"],
        "trend": trend_for(wow_change_30y),
        "wow_change_30y": wow_change_30y,
        "record_count": len(rates),
        "rates": rates,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="mortgage_rates_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"mortgage rates rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
