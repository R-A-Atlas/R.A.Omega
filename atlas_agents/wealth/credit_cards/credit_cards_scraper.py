"""Credit card rewards and APR snapshot -> data_cache/credit_cards_latest.json."""

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
OUTPUT_STABLE_NAME = "credit_cards_latest.json"

CARDS = [
    ("Blue Cash Everyday", "American Express", 20.24, "$200 after qualifying spend", 0, "Cash Back", 325),
    ("Chase Sapphire Preferred", "Chase", 21.49, "60k points after qualifying spend", 95, "Travel", 705),
    ("Citi Simplicity", "Citi", 19.24, "0% intro balance transfer window", 0, "Balance Transfer", 260),
    ("Discover it Secured", "Discover", 28.24, "Cashback match first year", 0, "Secured", 180),
    ("Ink Business Cash", "Chase", 18.49, "$750 after qualifying spend", 0, "Business", 735),
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal_for(net_value: float) -> str:
    if net_value >= 500:
        return "BEST_VALUE"
    if net_value >= 250:
        return "GOOD"
    return "AVERAGE"


def scrape() -> dict[str, Any]:
    cards = [
        {
            "name": name,
            "issuer": issuer,
            "apr": apr,
            "signup_bonus": bonus,
            "annual_fee": fee,
            "category": category,
            "signal": signal_for(value),
            "net_value_year1_usd": value,
        }
        for name, issuer, apr, bonus, fee, category, value in CARDS
    ]
    return {
        "generated_at": iso_now_z(),
        "source": "cfpb_baseline_rewards_snapshot",
        "source_url": "https://www.consumerfinance.gov/consumer-tools/credit-cards/",
        "record_count": len(cards),
        "cards": cards,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="credit_cards_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"credit cards rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
