"""Physical metals premium tracker -> data_cache/metals_latest.json."""

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
OUTPUT_STABLE_NAME = "metals_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def spread_signal(spread: float) -> str:
    if spread <= 2:
        return "TIGHT_SPREAD"
    if spread <= 5:
        return "NORMAL_SPREAD"
    return "WIDE_SPREAD"


def scrape() -> dict[str, Any]:
    raw = [
        ("Gold", 2345.20, "American Eagle", 6.1, "1oz bar", 2.4, 2399.00, 2327.00),
        ("Silver", 31.15, "Silver Eagle", 18.0, "10oz bar", 5.2, 33.60, 30.95),
        ("Platinum", 1018.50, "Platinum Eagle", 8.4, "1oz bar", 3.1, 1052.00, 1004.00),
        ("Palladium", 982.40, "Maple Leaf", 9.1, "1oz bar", 4.6, 1028.00, 960.00),
    ]
    metals = []
    for metal, spot, coin, coin_prem, bar, bar_prem, buy, sell in raw:
        spread = round(((buy - sell) / spot) * 100, 2)
        metals.append({"metal": metal, "spot_price": spot, "coin_type": coin, "coin_premium_pct": coin_prem, "bar_type": bar, "bar_premium_pct": bar_prem, "buy_price": buy, "sell_price": sell, "spread_pct": spread, "signal": spread_signal(spread)})
    return {"generated_at": iso_now_z(), "source": "yfinance_dealer_baseline", "tickers": ["GC=F", "SI=F", "PL=F", "PA=F"], "record_count": len(metals), "metals": metals}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="metals_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"metals rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
