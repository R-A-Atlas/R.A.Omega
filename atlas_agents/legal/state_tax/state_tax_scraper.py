"""State tax monitor -> data_cache/state_tax_latest.json."""

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
OUTPUT_STABLE_NAME = "state_tax_latest.json"

NO_INCOME_TAX = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    raw = [
        ("Alabama", "AL", 5.0, 4.0, 5.29), ("Alaska", "AK", 0.0, 0.0, 1.82),
        ("Arizona", "AZ", 2.5, 5.6, 2.77), ("California", "CA", 13.3, 7.25, 1.6),
        ("Colorado", "CO", 4.4, 2.9, 4.91), ("Florida", "FL", 0.0, 6.0, 1.02),
        ("New York", "NY", 10.9, 4.0, 4.53), ("Puerto Rico", "PR", 33.0, 10.5, 1.0),
        ("Texas", "TX", 0.0, 6.25, 1.95), ("Washington", "WA", 0.0, 6.5, 2.94),
    ]
    states = []
    for state, code, income, sales, local in raw:
        programs = ["Act 60 (PR)"] if code == "PR" else []
        if code in NO_INCOME_TAX:
            income = 0.0
        states.append(
            {
                "state": state,
                "state_code": code,
                "income_tax_rate_top": income,
                "sales_tax_state": sales,
                "sales_tax_avg_local": local,
                "special_programs": programs,
            }
        )
    return {
        "generated_at": iso_now_z(),
        "source": "tax_foundation_baseline",
        "source_url": "https://taxfoundation.org/",
        "record_count": len(states),
        "states": states,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="state_tax_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"state tax rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
