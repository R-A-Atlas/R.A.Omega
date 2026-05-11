"""Energy grid monitor -> data_cache/energy_latest.json."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import REQUEST_TIMEOUT_S, requests_get_json, write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "energy_latest.json"
EIA_BASE = "https://api.eia.gov/v2"
RENEWABLE_SOURCES = {"Wind", "Solar", "Hydro", "Other"}

BASELINE_BREAKDOWN = [
    {"source": "Coal", "pct_of_grid": 16.2, "yoy_change_pct": -3.1},
    {"source": "Natural Gas", "pct_of_grid": 43.5, "yoy_change_pct": 1.2},
    {"source": "Nuclear", "pct_of_grid": 18.4, "yoy_change_pct": 0.0},
    {"source": "Wind", "pct_of_grid": 10.2, "yoy_change_pct": 2.4},
    {"source": "Solar", "pct_of_grid": 6.8, "yoy_change_pct": 3.1},
    {"source": "Hydro", "pct_of_grid": 6.4, "yoy_change_pct": -0.5},
    {"source": "Other", "pct_of_grid": 2.5, "yoy_change_pct": 0.2},
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_electricity_price() -> float:
    data = requests_get_json(
        f"{EIA_BASE}/electricity/retail-sales/data/",
        params={
            "frequency": "monthly",
            "data[0]": "price",
            "facets[sectorName][]": "all-sectors",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 1,
        },
        timeout_s=REQUEST_TIMEOUT_S,
    )
    rows = (data.get("response") or {}).get("data") or []
    return float(rows[0]["price"]) if rows else 16.0


def fetch_gas_price() -> float:
    data = requests_get_json(
        f"{EIA_BASE}/petroleum/pri/gnd/data/",
        params={
            "frequency": "weekly",
            "data[0]": "value",
            "facets[duoarea][]": "NUS",
            "facets[product][]": "EPM0",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 1,
        },
        timeout_s=REQUEST_TIMEOUT_S,
    )
    rows = (data.get("response") or {}).get("data") or []
    return float(rows[0]["value"]) if rows else 3.5


def classify_grid_trend(breakdown: list[dict[str, Any]]) -> str:
    delta = sum(float(b.get("yoy_change_pct") or 0) for b in breakdown if b.get("source") in RENEWABLE_SOURCES)
    if delta >= 2.0:
        return "GREENING"
    if delta <= -2.0:
        return "FOSSIL_RECOVERY"
    return "STABLE"


def build_output(electricity_price: float, gas_price: float, breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    renewables_pct = sum(float(b.get("pct_of_grid") or 0) for b in breakdown if b.get("source") in RENEWABLE_SOURCES)
    return {
        "generated_at": iso_now_z(),
        "electricity_avg_kwh_cents": round(float(electricity_price), 2),
        "gas_national_avg_gallon": round(float(gas_price), 3),
        "renewables_pct_grid": round(renewables_pct, 2),
        "grid_trend": classify_grid_trend(breakdown),
        "record_count": len(breakdown),
        "breakdown": breakdown,
    }


def scrape() -> dict[str, Any]:
    try:
        electricity = fetch_electricity_price()
    except Exception:
        electricity = 16.0
    try:
        gas = fetch_gas_price()
    except Exception:
        gas = 3.5
    return build_output(electricity, gas, list(BASELINE_BREAKDOWN))


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="energy_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"energy rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
