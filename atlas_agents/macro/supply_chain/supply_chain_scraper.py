"""Supply chain freight index -> data_cache/supply_chain_latest.json."""

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
OUTPUT_STABLE_NAME = "supply_chain_latest.json"

BASELINE = [
    {"route": "Shanghai-LA", "rate_usd_40ft": 3240, "change_wow_pct": 2.1, "change_yoy_pct": -18.4},
    {"route": "Shanghai-Rotterdam", "rate_usd_40ft": 4180, "change_wow_pct": 6.5, "change_yoy_pct": 15.2},
    {"route": "Rotterdam-NY", "rate_usd_40ft": 1850, "change_wow_pct": -1.3, "change_yoy_pct": -5.8},
    {"route": "Global Composite", "rate_usd_40ft": 2890, "change_wow_pct": 3.8, "change_yoy_pct": -4.2},
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_trend(wow_pct: float | None) -> str:
    v = float(wow_pct or 0)
    if v >= 20:
        return "SPIKING"
    if v >= 5:
        return "RISING"
    if v <= -20:
        return "COLLAPSING"
    if v <= -5:
        return "FALLING"
    return "STABLE"


def build_output(indices: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{**row, "trend": classify_trend(row.get("change_wow_pct"))} for row in indices]
    global_row = next((r for r in rows if r.get("route") == "Global Composite"), None)
    return {
        "generated_at": iso_now_z(),
        "data_source": "baseline_public_freight_index_snapshot",
        "record_count": len(rows),
        "global_trend": (global_row or {}).get("trend", "STABLE"),
        "indices": rows,
    }


def scrape() -> dict[str, Any]:
    return build_output(list(BASELINE))


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="supply_chain_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"supply_chain rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
