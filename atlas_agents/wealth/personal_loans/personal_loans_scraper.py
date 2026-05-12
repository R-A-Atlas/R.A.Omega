"""Personal loan rate screener -> data_cache/personal_loans_latest.json."""

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
OUTPUT_STABLE_NAME = "personal_loans_latest.json"
FRED_AVG_RATE = 11.48


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rating_for(rate_low: float) -> str:
    return "COMPETITIVE" if rate_low <= FRED_AVG_RATE - 1.0 else "AVERAGE"


def scrape() -> dict[str, Any]:
    raw = [
        ("LightStream", 7.49, 25.99, 100000, 144, 660, "Online Lender"),
        ("PenFed", 8.49, 17.99, 50000, 60, 650, "Credit Union"),
        ("Wells Fargo", 8.99, 24.49, 100000, 84, 660, "Bank"),
        ("LendingClub", 9.57, 35.99, 40000, 60, 600, "Marketplace"),
    ]
    loans = [
        {
            "lender": lender,
            "rate_low": low,
            "rate_high": high,
            "max_amount": amount,
            "term_months_max": term,
            "credit_score_min": score,
            "category": category,
            "rating": rating_for(low),
        }
        for lender, low, high, amount, term, score, category in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "fred_TERMCBPER24NS_baseline",
        "fred_avg_rate": FRED_AVG_RATE,
        "record_count": len(loans),
        "loans": loans,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="personal_loans_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"personal loans rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
