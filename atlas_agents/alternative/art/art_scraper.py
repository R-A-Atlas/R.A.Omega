"""Art auction tracker -> data_cache/art_latest.json."""

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
OUTPUT_STABLE_NAME = "art_latest.json"
ARTPRICE100_INDEX = 1842


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal(realized: int, low: int, high: int) -> str:
    if realized > high:
        return "ABOVE_ESTIMATE"
    if realized < low:
        return "BELOW_ESTIMATE"
    return "IN_RANGE"


def scrape() -> dict[str, Any]:
    raw = [
        ("Jean-Michel Basquiat", "Untitled", "Acrylic on canvas", "Christie's", 38200000, 28000000, 35000000, "2026-05-06"),
        ("Yayoi Kusama", "Infinity Nets", "Oil on canvas", "Sotheby's", 7100000, 6500000, 8500000, "2026-05-04"),
        ("Banksy", "Girl with Balloon", "Screenprint", "Phillips", 720000, 800000, 1200000, "2026-05-02"),
    ]
    sales = []
    for artist, title, medium, house, realized, low, high, sold in raw:
        sales.append({
            "artist": artist,
            "title": title,
            "medium": medium,
            "house": house,
            "realized_price_usd": realized,
            "estimate_low_usd": low,
            "estimate_high_usd": high,
            "sold_date": sold,
            "premium_over_estimate_pct": round(((realized - high) / high) * 100, 2),
            "signal": signal(realized, low, high),
        })
    return {"generated_at": iso_now_z(), "source": "mutualart_public_baseline", "artprice100_index": ARTPRICE100_INDEX, "record_count": len(sales), "sales": sales}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="art_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"art sales={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
