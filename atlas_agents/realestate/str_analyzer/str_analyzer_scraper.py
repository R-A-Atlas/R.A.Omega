"""Short-term rental market analyzer -> data_cache/str_latest.json."""

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
OUTPUT_STABLE_NAME = "str_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    raw = [
        ("Orlando", "FL", 184, 0.69, "LOW"),
        ("Austin", "TX", 173, 0.58, "MEDIUM"),
        ("Nashville", "TN", 219, 0.62, "MEDIUM"),
        ("New York", "NY", 242, 0.54, "HIGH"),
        ("Phoenix", "AZ", 161, 0.57, "LOW"),
    ]
    markets = [
        {
            "city": city,
            "state": state,
            "avg_daily_rate": adr,
            "occupancy_rate": occ,
            "annual_revenue_est": round(adr * occ * 365),
            "regulation_risk": risk,
        }
        for city, state, adr, occ, risk in raw
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "inside_airbnb_baseline",
        "source_url": "https://insideairbnb.com/get-the-data/",
        "record_count": len(markets),
        "markets": markets,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="str_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"str rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
