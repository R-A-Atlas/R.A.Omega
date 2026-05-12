"""REIT dividend and rate screen -> data_cache/reits_latest.json."""

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
OUTPUT_STABLE_NAME = "reits_latest.json"
TREASURY_10Y_RATE = 4.48


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rating_for(dividend_yield: float) -> str:
    if dividend_yield >= 7.0:
        return "STRONG_BUY"
    if dividend_yield >= 5.5:
        return "BUY"
    if dividend_yield >= 4.0:
        return "HOLD"
    return "UNDERPERFORM"


def scrape(top_n: int = 10) -> dict[str, Any]:
    raw = [
        ("O", "Realty Income", 5.92, 52.30, "Retail"),
        ("PLD", "Prologis", 3.81, 109.20, "Industrial"),
        ("AMT", "American Tower", 3.72, 184.10, "Telecom Infrastructure"),
        ("SPG", "Simon Property Group", 5.18, 150.40, "Mall"),
        ("VICI", "VICI Properties", 5.63, 29.70, "Gaming"),
        ("WPC", "W. P. Carey", 6.15, 57.80, "Net Lease"),
        ("EPR", "EPR Properties", 7.42, 43.60, "Experiential"),
        ("DLR", "Digital Realty", 3.12, 144.90, "Data Center"),
        ("AVB", "AvalonBay", 3.55, 192.40, "Apartment"),
        ("ARE", "Alexandria Real Estate", 4.85, 108.20, "Life Science"),
    ][:top_n]
    reits = [
        {
            "ticker": ticker,
            "name": name,
            "dividend_yield": dividend_yield,
            "price": price,
            "sector": sector,
            "rating": rating_for(dividend_yield),
        }
        for ticker, name, dividend_yield, price, sector in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "reit_universe_baseline",
        "treasury_10y_rate": TREASURY_10Y_RATE,
        "record_count": len(reits),
        "reits": reits,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="reits_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args(argv)
    payload = scrape(top_n=args.top_n)
    if not args.dry_run:
        write_outputs(payload)
    print(f"reits rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
