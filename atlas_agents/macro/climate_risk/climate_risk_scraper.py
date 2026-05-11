"""Climate/FEMA risk monitor -> data_cache/climate_risk_latest.json."""

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
OUTPUT_STABLE_NAME = "climate_risk_latest.json"

BASELINE_ZONES = [
    {"region": "Gulf Coast", "state": "LA", "risk_level": "EXTREME", "change": "INCREASING", "annual_premium_avg": 3200},
    {"region": "Southeast", "state": "FL", "risk_level": "HIGH", "change": "INCREASING", "annual_premium_avg": 2800},
    {"region": "Mid-Atlantic", "state": "NJ", "risk_level": "MODERATE", "change": "STABLE", "annual_premium_avg": 1100},
    {"region": "Great Plains", "state": "KS", "risk_level": "LOW", "change": "STABLE", "annual_premium_avg": 450},
    {"region": "Pacific Northwest", "state": "WA", "risk_level": "HIGH", "change": "INCREASING", "annual_premium_avg": 1900},
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_insurance_impact(premium: float, risk_level: str, change: str) -> str:
    if risk_level == "EXTREME" and change == "INCREASING" and premium > 5000:
        return "UNINSURABLE"
    if premium > 1500:
        return "HIGH_PREMIUM"
    if premium >= 500:
        return "NORMAL"
    return "LOW_PREMIUM"


def classify_national_trend(zones: list[dict[str, Any]]) -> str:
    counts = {"INCREASING": 0, "DECREASING": 0, "STABLE": 0}
    for zone in zones:
        counts[str(zone.get("change") or "STABLE")] = counts.get(str(zone.get("change") or "STABLE"), 0) + 1
    if counts["INCREASING"] > counts["DECREASING"] and counts["INCREASING"] > counts["STABLE"]:
        return "INCREASING"
    if counts["DECREASING"] > counts["INCREASING"] and counts["DECREASING"] > counts["STABLE"]:
        return "DECREASING"
    return "STABLE"


def scrape() -> dict[str, Any]:
    rows = []
    for row in BASELINE_ZONES:
        premium = float(row["annual_premium_avg"])
        rows.append(
            {
                **row,
                "impact_on_insurance": classify_insurance_impact(
                    premium, str(row["risk_level"]), str(row["change"])
                ),
            }
        )
    return {
        "generated_at": iso_now_z(),
        "source": "openfema_region_baseline",
        "record_count": len(rows),
        "national_flood_risk_trend": classify_national_trend(rows),
        "flood_zone_changes": rows,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="climate_risk_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"climate rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
