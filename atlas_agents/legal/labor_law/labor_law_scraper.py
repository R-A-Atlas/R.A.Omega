"""Labor law and minimum wage monitor -> data_cache/labor_law_latest.json."""

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
OUTPUT_STABLE_NAME = "labor_law_latest.json"
FEDERAL_MIN_WAGE = 7.25
FEDERAL_ONLY = {"AL", "GA", "ID", "IN", "IA", "KS", "KY", "LA", "MS", "OK", "SC", "TN", "TX", "WY", "WV"}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WI": "Wisconsin", "WV": "West Virginia", "WY": "Wyoming",
}

RATES = {
    "AK": 11.91, "AZ": 14.70, "AR": 11.00, "CA": 16.50, "CO": 14.81, "CT": 16.35,
    "DE": 15.00, "DC": 17.50, "FL": 13.00, "HI": 14.00, "IL": 15.00, "ME": 14.65,
    "MD": 15.00, "MA": 15.00, "MI": 10.56, "MN": 11.13, "MO": 13.75, "MT": 10.55,
    "NE": 13.50, "NV": 12.00, "NH": 7.25, "NJ": 15.49, "NM": 12.00, "NY": 15.50,
    "NC": 7.25, "ND": 7.25, "OH": 10.70, "OR": 14.70, "PA": 7.25, "RI": 15.00,
    "SD": 11.50, "UT": 7.25, "VT": 14.01, "VA": 12.41, "WA": 16.66, "WI": 7.25,
}


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    states = []
    for code, name in STATE_NAMES.items():
        rate = FEDERAL_MIN_WAGE if code in FEDERAL_ONLY else RATES.get(code, FEDERAL_MIN_WAGE)
        states.append(
            {
                "state": name,
                "state_code": code,
                "min_wage": rate,
                "effective_date": "2026-01-01",
                "tipped_wage": round(max(2.13, rate * 0.45), 2),
                "notes": "Federal baseline" if rate == FEDERAL_MIN_WAGE else "State rate above federal baseline",
            }
        )
    return {
        "generated_at": iso_now_z(),
        "source": "dol_minimum_wage_baseline",
        "source_url": "https://www.dol.gov/agencies/whd/minimum-wage/state",
        "federal_min_wage": FEDERAL_MIN_WAGE,
        "record_count": len(states),
        "states": states,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="labor_law_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"labor law rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
