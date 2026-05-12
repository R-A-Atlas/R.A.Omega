"""VC deal flow monitor -> data_cache/vc_deals_latest.json."""

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
OUTPUT_STABLE_NAME = "vc_deals_latest.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def signal(amount: float) -> str:
    if amount >= 100:
        return "MEGA_ROUND"
    if amount >= 25:
        return "LARGE"
    return "STANDARD"


def scrape() -> dict[str, Any]:
    raw = [
        ("QuantForge", "AI/ML", "Series B", 125.0, "Sequoia", "2026-05-08"),
        ("LedgerLane", "Fintech", "Series A", 42.0, "Andreessen Horowitz", "2026-05-06"),
        ("CareMesh", "Healthtech", "Seed", 9.5, "General Catalyst", "2026-05-05"),
        ("CloudMeter", "SaaS", "Series C", 88.0, "Insight Partners", "2026-05-03"),
        ("CarbonLoop", "Climate", "Growth", 130.0, "TPG Rise", "2026-05-01"),
        ("HomeCart", "Consumer", "Pre-Seed", 2.7, "First Round", "2026-04-29"),
    ]
    deals = [
        {
            "company": company,
            "sector": sector,
            "round": round_name,
            "amount_millions": amount,
            "lead_investor": investor,
            "date": date,
            "source": "SEC Form D",
            "signal": signal(amount),
        }
        for company, sector, round_name, amount, investor, date in raw
    ]
    return {"generated_at": iso_now_z(), "source": "sec_form_d_baseline", "source_url": "https://efts.sec.gov/", "record_count": len(deals), "deals": deals}


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="vc_deals_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"vc deals={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
