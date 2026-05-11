"""Forex radar -> data_cache/forex_latest.json."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import REQUEST_TIMEOUT_S, requests_get_json, write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "forex_latest.json"
PAIRS = ["EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "MXN"]
FRANKFURTER_URL = "https://api.frankfurter.app"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_current_rates() -> dict[str, float]:
    data = requests_get_json(
        f"{FRANKFURTER_URL}/latest",
        params={"from": "USD", "to": ",".join(PAIRS)},
        timeout_s=REQUEST_TIMEOUT_S,
    )
    return {k: float(v) for k, v in (data.get("rates") or {}).items() if k in PAIRS}


def fetch_previous_rates(days_back: int = 1) -> dict[str, float]:
    target = date.today() - timedelta(days=max(1, days_back))
    data = requests_get_json(
        f"{FRANKFURTER_URL}/{target.isoformat()}",
        params={"from": "USD", "to": ",".join(PAIRS)},
        timeout_s=REQUEST_TIMEOUT_S,
    )
    return {k: float(v) for k, v in (data.get("rates") or {}).items() if k in PAIRS}


def compute_change(curr: float | None, prev: float | None) -> tuple[float | None, float | None]:
    if curr is None or prev in (None, 0):
        return None, None
    change = curr - prev
    return round(change, 6), round((change / prev) * 100, 4)


def classify_volatility(change_pct: float | None) -> str:
    if change_pct is None:
        return "UNKNOWN"
    mag = abs(float(change_pct))
    if mag >= 1.0:
        return "HIGH_VOLATILITY"
    if mag >= 0.5:
        return "ELEVATED"
    return "STABLE"


def compute_dxy_proxy(rates: dict[str, float]) -> float | None:
    weights = {"EUR": 0.576, "JPY": 0.136, "GBP": 0.119, "CAD": 0.091, "CHF": 0.036}
    present = [(ccy, rates.get(ccy), w) for ccy, w in weights.items() if rates.get(ccy)]
    if not present:
        return None
    weighted = sum((rate or 0) * w for ccy, rate, w in present)
    norm = sum(w for _, _, w in present) or 1.0
    return round((weighted / norm) * 100, 4)


def scrape() -> dict[str, Any]:
    generated_at = iso_now_z()
    try:
        current = fetch_current_rates()
    except Exception:
        current = {}
    try:
        previous = fetch_previous_rates()
    except Exception:
        previous = {}

    rows: list[dict[str, Any]] = []
    for ccy in PAIRS:
        rate = current.get(ccy)
        prev_rate = previous.get(ccy)
        change, change_pct = compute_change(rate, prev_rate)
        rows.append(
            {
                "pair": f"USD/{ccy}",
                "rate": rate,
                "prev_rate": prev_rate,
                "change_24h": change,
                "change_24h_pct": change_pct,
                "volatility_signal": classify_volatility(change_pct),
            }
        )
    return {
        "generated_at": generated_at,
        "source": "frankfurter_ecb",
        "base": "USD",
        "record_count": len(rows),
        "dxy_proxy": compute_dxy_proxy(current),
        "pairs": rows,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="forex_",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"forex rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
