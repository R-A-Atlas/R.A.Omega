"""Consumer protection alert monitor -> data_cache/consumer_alerts_latest.json."""

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
OUTPUT_STABLE_NAME = "consumer_alerts_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    alerts = [
        {"title": "Phone Scam Alert", "category": "Scam", "date": "2026-05-08", "severity": "HIGH", "source": "FTC", "description": "Callers impersonating tax agencies."},
        {"title": "Widget Recall", "category": "Recall", "date": "2026-05-07", "severity": "MEDIUM", "source": "CPSC", "description": "Fall hazard recall notice."},
        {"title": "Retail Data Breach", "category": "Data Breach", "date": "2026-05-05", "severity": "HIGH", "source": "FTC", "description": "Consumer account credentials exposed."},
        {"title": "Storm Price Gouging", "category": "Price Gouging", "date": "2026-05-04", "severity": "MEDIUM", "source": "FTC", "description": "Emergency supply pricing complaint spike."},
        {"title": "Payment App Fraud", "category": "Fraud", "date": "2026-05-03", "severity": "LOW", "source": "FTC", "description": "Peer payment impersonation warnings."},
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "ftc_cpsc_baseline",
        "source_urls": ["https://consumer.ftc.gov/", "https://www.cpsc.gov/"],
        "record_count": len(alerts),
        "alerts": alerts,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="consumer_alerts_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"consumer alerts rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
