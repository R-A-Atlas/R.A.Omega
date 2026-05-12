"""ROAS optimizer -> data_cache/roas_latest.json."""

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
OUTPUT_STABLE_NAME = "roas_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_roas(spend: float, revenue: float) -> float:
    return round(revenue / spend, 2) if spend > 0 else 0.0


def classify_signal(roas: float) -> str:
    if roas >= 2.0:
        return "PROFITABLE"
    if roas >= 0.8:
        return "BREAK_EVEN"
    return "LOSING"


def classify_recommendation(roas: float) -> str:
    if roas >= 3.0:
        return "SCALE"
    if roas >= 1.5:
        return "OPTIMIZE"
    if roas >= 0.8:
        return "MONITOR"
    return "PAUSE"


def scrape() -> dict[str, Any]:
    raw = [("AI Advisor Search", "Google", 4200, 16254, 61), ("Debt Relief Retarget", "Meta", 1800, 3100, 44), ("Brand Awareness", "TikTok", 2500, 900, 0)]
    campaigns = []
    for name, platform, spend, revenue, conversions in raw:
        r = compute_roas(spend, revenue)
        campaigns.append({"name": name, "platform": platform, "spend_usd": spend, "revenue_usd": revenue, "roas": r, "cpa_usd": round(spend / conversions, 2) if conversions else 0, "status": "ACTIVE", "signal": classify_signal(r), "recommendation": classify_recommendation(r)})
    return {"generated_at": iso_now_z(), "record_count": len(campaigns), "campaigns": campaigns}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="roas_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"roas campaigns={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
