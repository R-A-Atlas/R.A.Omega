"""P2P lending platform snapshot -> data_cache/p2p_latest.json."""

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
OUTPUT_STABLE_NAME = "p2p_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal(avg: float, default: float) -> str:
    if avg >= 8 and default <= 5:
        return "ATTRACTIVE"
    if default >= 10:
        return "AVOID"
    return "MODERATE"


def scrape() -> dict[str, Any]:
    raw = [
        ("Prosper", 7.4, 5.8, 68400, 25, False, "ACTIVE"),
        ("Upstart", 8.2, 6.8, 45000, 100, True, "ACTIVE"),
        ("LendingClub Notes", 6.1, 4.9, 0, 25, False, "CLOSED_TO_RETAIL"),
        ("Funding Circle", 9.6, 11.2, 12000, 5000, True, "ACTIVE"),
    ]
    platforms = [{"name": n, "avg_return_pct": avg, "default_rate_12m_pct": d, "active_loans_count": c, "min_investment": m, "accredited_only": a, "status": st, "signal": signal(avg, d)} for n, avg, d, c, m, a, st in raw]
    return {"generated_at": iso_now_z(), "source": "p2p_quarterly_baseline", "record_count": len(platforms), "platforms": platforms}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="p2p_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"p2p platforms={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
