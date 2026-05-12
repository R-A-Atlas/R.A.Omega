"""IRA, 401k and HSA contribution limit snapshot -> data_cache/retirement_limits_latest.json."""

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
OUTPUT_STABLE_NAME = "retirement_limits_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    return {
        "generated_at": iso_now_z(),
        "source": "irs_2026_limits_baseline",
        "source_url": "https://www.irs.gov/retirement-plans",
        "year": 2026,
        "ira_limit": 7000,
        "ira_catch_up_50plus": 1000,
        "k401_limit": 23500,
        "k401_catch_up_50plus": 7500,
        "hsa_individual": 4300,
        "hsa_family": 8550,
        "roth_income_phase_out_single_low": 150000,
        "roth_income_phase_out_single_high": 165000,
        "roth_income_phase_out_married_low": 236000,
        "roth_income_phase_out_married_high": 246000,
        "record_count": 1,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="retirement_limits_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"retirement limits year={payload['year']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
