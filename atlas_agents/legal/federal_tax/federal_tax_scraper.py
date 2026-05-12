"""Federal tax bracket snapshot -> data_cache/federal_tax_latest.json."""

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
OUTPUT_STABLE_NAME = "federal_tax_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    brackets = [
        {"rate": 0.10, "single_min": 0, "single_max": 11925, "married_min": 0, "married_max": 23850},
        {"rate": 0.12, "single_min": 11926, "single_max": 48475, "married_min": 23851, "married_max": 96950},
        {"rate": 0.22, "single_min": 48476, "single_max": 103350, "married_min": 96951, "married_max": 206700},
        {"rate": 0.24, "single_min": 103351, "single_max": 197300, "married_min": 206701, "married_max": 394600},
        {"rate": 0.32, "single_min": 197301, "single_max": 250525, "married_min": 394601, "married_max": 501050},
        {"rate": 0.35, "single_min": 250526, "single_max": 626350, "married_min": 501051, "married_max": 751600},
        {"rate": 0.37, "single_min": 626351, "single_max": None, "married_min": 751601, "married_max": None},
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "irs_2026_baseline",
        "source_url": "https://www.irs.gov/",
        "year": 2026,
        "standard_deduction_single": 15000,
        "standard_deduction_married": 30000,
        "record_count": len(brackets),
        "brackets": brackets,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="federal_tax_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"federal tax brackets={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
