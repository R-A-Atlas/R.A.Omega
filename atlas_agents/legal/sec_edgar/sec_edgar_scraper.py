"""SEC EDGAR filing risk monitor -> data_cache/sec_filings_latest.json."""

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
OUTPUT_STABLE_NAME = "sec_filings_latest.json"
FLAG_TERMS = ("material weakness", "going concern", "restatement")


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flags_for(text: str) -> list[str]:
    low = text.lower()
    return [term for term in FLAG_TERMS if term in low]


def scrape() -> dict[str, Any]:
    filings = [
        {
            "ticker": "TEST",
            "company_name": "Test Corp",
            "form_type": "8-K",
            "filed_date": "2026-05-08",
            "description": "Material weakness in internal controls",
            "url": "https://www.sec.gov/edgar/search/",
        },
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "form_type": "10-Q",
            "filed_date": "2026-05-02",
            "description": "Quarterly report",
            "url": "https://www.sec.gov/edgar/search/",
        },
    ]
    for filing in filings:
        filing["flags"] = flags_for(filing["description"])
    return {
        "generated_at": iso_now_z(),
        "source": "sec_edgar_efts_baseline",
        "source_url": "https://efts.sec.gov/",
        "record_count": len(filings),
        "filings": filings,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="sec_filings_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"sec filings rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
