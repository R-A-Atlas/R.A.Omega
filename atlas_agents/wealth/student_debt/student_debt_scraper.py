"""Student debt policy and federal loan snapshot -> data_cache/student_debt_latest.json."""

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
OUTPUT_STABLE_NAME = "student_debt_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    programs = [
        {"name": "PSLF", "status": "ACTIVE", "note": "Public service forgiveness track remains available."},
        {"name": "IBR", "status": "ACTIVE", "note": "Income-based repayment fallback for eligible borrowers."},
        {"name": "SAVE", "status": "PAUSED", "note": "Court and policy uncertainty requires status checking."},
        {"name": "PAYE", "status": "CLOSED", "note": "Closed to most new enrollments."},
        {"name": "ICR", "status": "ACTIVE", "note": "Useful for parent PLUS consolidation scenarios."},
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "studentaid_baseline",
        "source_url": "https://api.studentaid.gov/",
        "aid_year": "2026-2027",
        "federal_rate_undergrad": 6.39,
        "federal_rate_grad": 7.94,
        "federal_rate_plus": 8.94,
        "total_borrowers_millions": 42.7,
        "total_debt_billions": 1630.0,
        "forgiveness_programs": programs,
        "record_count": len(programs),
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="student_debt_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"student debt programs={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
