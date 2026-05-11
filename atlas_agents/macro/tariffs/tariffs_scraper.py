"""Tariff tracker -> data_cache/tariffs_latest.json."""

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
OUTPUT_STABLE_NAME = "tariffs_latest.json"
VALID_STATUSES = {"ACTIVE", "SUSPENDED", "UNDER_REVIEW", "ESCALATING"}

HARDCODED_TARIFFS = [
    {"product_category": "Electronics", "rate_pct": 25.0, "effective_date": "2018-07-06", "trading_partner": "China", "authority": "Section 301", "status": "ACTIVE"},
    {"product_category": "Consumer Goods", "rate_pct": 7.5, "effective_date": "2020-02-14", "trading_partner": "China", "authority": "Section 301", "status": "ACTIVE"},
    {"product_category": "Steel", "rate_pct": 25.0, "effective_date": "2018-03-23", "trading_partner": "Global", "authority": "Section 232", "status": "ACTIVE"},
    {"product_category": "Aluminum", "rate_pct": 10.0, "effective_date": "2018-03-23", "trading_partner": "Global", "authority": "Section 232", "status": "ACTIVE"},
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_output(active_tariffs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [t for t in active_tariffs if t.get("status") in VALID_STATUSES and float(t.get("rate_pct") or 0) >= 0]
    return {
        "generated_at": iso_now_z(),
        "source": "ustr_confirmed_baseline",
        "record_count": len(rows),
        "active_count": sum(1 for t in rows if t.get("status") == "ACTIVE"),
        "escalating_count": sum(1 for t in rows if t.get("status") == "ESCALATING"),
        "active_tariffs": rows,
    }


def scrape() -> dict[str, Any]:
    return build_output([dict(t) for t in HARDCODED_TARIFFS])


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="tariffs_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"tariffs rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
