"""SBA grant and loan finder -> data_cache/sba_latest.json."""

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
OUTPUT_STABLE_NAME = "sba_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    programs = [
        {"name": "7(a) Loan", "type": "Loan", "max_amount": 5000000, "interest_rate_low": 8.0, "interest_rate_high": 13.5, "eligibility": "For-profit US small business", "term_years_max": 25, "url": "https://www.sba.gov/funding-programs/loans/7a-loans"},
        {"name": "504 Loan", "type": "Loan", "max_amount": 5500000, "interest_rate_low": 6.0, "interest_rate_high": 8.5, "eligibility": "Fixed asset expansion", "term_years_max": 25, "url": "https://www.sba.gov/funding-programs/loans/504-loans"},
        {"name": "Microloan", "type": "Loan", "max_amount": 50000, "interest_rate_low": 8.0, "interest_rate_high": 13.0, "eligibility": "Startup and small business borrowers", "term_years_max": 6, "url": "https://www.sba.gov/funding-programs/loans/microloans"},
        {"name": "Export Express", "type": "Line of Credit", "max_amount": 500000, "interest_rate_low": 8.5, "interest_rate_high": 14.0, "eligibility": "Export-capable small business", "term_years_max": 7, "url": "https://www.sba.gov/funding-programs/loans"},
        {"name": "SBIR/STTR", "type": "Grant", "max_amount": 1500000, "interest_rate_low": 0.0, "interest_rate_high": 0.0, "eligibility": "R&D-focused small business", "term_years_max": 0, "url": "https://www.sbir.gov/"},
    ]
    return {"generated_at": iso_now_z(), "source": "sba_grants_baseline", "source_urls": ["https://www.sba.gov/funding-programs/loans", "https://www.grants.gov/"], "record_count": len(programs), "programs": programs}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="sba_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"sba programs={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
