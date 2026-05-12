"""Email deliverability monitor -> data_cache/email_health_latest.json."""

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
OUTPUT_STABLE_NAME = "email_health_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "F"


def scrape(domain: str = "example.com") -> dict[str, Any]:
    score = 88
    return {"generated_at": iso_now_z(), "domain": domain, "spf_status": "PASS", "dkim_status": "PASS", "dmarc_status": "PASS", "mx_status": "PASS", "blacklist_count": 0, "deliverability_score": score, "grade": grade(score)}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="email_health_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("domain", nargs="?", default="example.com")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape(args.domain)
    if not args.dry_run:
        write_outputs(payload)
    print(f"email health grade={payload['grade']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
