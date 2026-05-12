"""Watch secondary market snapshot -> data_cache/watches_latest.json."""

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
OUTPUT_STABLE_NAME = "watches_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def trend(avg: float, retail: float) -> str:
    ratio = avg / retail if retail else 0
    if ratio >= 1.5:
        return "APPRECIATING"
    if ratio > 1.05:
        return "PREMIUM"
    if ratio >= 0.95:
        return "AT_RETAIL"
    return "BELOW_RETAIL"


def scrape() -> dict[str, Any]:
    raw = [
        ("Rolex", "Submariner Date", "126610LN", 14300, 10250, 128),
        ("Rolex", "Daytona", "126500LN", 32600, 15100, 93),
        ("Patek Philippe", "Nautilus", "5711/1A", 98000, 34890, 42),
        ("Audemars Piguet", "Royal Oak", "15500ST", 52500, 28800, 36),
        ("Omega", "Speedmaster Moonwatch", "310.30.42.50.01.002", 6900, 8000, 211),
        ("Cartier", "Santos Medium", "WSSA0029", 7100, 7350, 180),
        ("Tudor", "Black Bay 58", "M79030N", 3350, 4000, 155),
        ("Vacheron Constantin", "Overseas", "4500V", 24500, 25000, 28),
    ]
    models = []
    for brand, model, reference, avg, retail, listings in raw:
        models.append({
            "brand": brand,
            "model": model,
            "reference": reference,
            "avg_price": avg,
            "retail_price": retail,
            "premium_over_retail_pct": round(((avg - retail) / retail) * 100, 2),
            "trend": trend(avg, retail),
            "listings_count": listings,
        })
    return {"generated_at": iso_now_z(), "source": "watchcharts_baseline", "record_count": len(models), "models": models}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="watches_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"watches rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
