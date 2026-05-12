"""
ATLAS equities market movers snapshot -> data_cache/equities_latest.json.

Uses Yahoo Finance's public screener endpoint through requests only. No paid API
keys, no browser automation, no LLM.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import (  # noqa: E402
    REQUEST_TIMEOUT_S,
    requests_get_json,
    write_cache_json_pair,
)

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "equities_latest.json"
YAHOO_SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"

SCREENS = {
    "gainers": "day_gainers",
    "losers": "day_losers",
    "active": "most_actives",
}


FALLBACK_QUOTES: dict[str, list[dict[str, Any]]] = {
    "gainers": [
        {
            "symbol": "NVDA",
            "shortName": "NVIDIA Corporation",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
        {
            "symbol": "AMD",
            "shortName": "Advanced Micro Devices, Inc.",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
    ],
    "losers": [
        {
            "symbol": "TSLA",
            "shortName": "Tesla, Inc.",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
        {
            "symbol": "SMCI",
            "shortName": "Super Micro Computer, Inc.",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
    ],
    "active": [
        {
            "symbol": "AAPL",
            "shortName": "Apple Inc.",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
        {
            "symbol": "MSFT",
            "shortName": "Microsoft Corporation",
            "regularMarketPrice": 0,
            "regularMarketChange": 0,
            "regularMarketChangePercent": 0,
            "regularMarketVolume": 0,
            "marketCap": None,
        },
    ],
}


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(v: Any) -> float | int | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f.is_integer():
        return int(f)
    return f


def _quote_row(q: dict[str, Any], *, bucket: str, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "ticker": str(q.get("symbol") or "").upper(),
        "name": q.get("shortName") or q.get("longName") or "",
        "exchange": q.get("fullExchangeName") or q.get("exchange") or "",
        "market": q.get("market") or "us_market",
        "price": _num(q.get("regularMarketPrice")),
        "change": _num(q.get("regularMarketChange")),
        "change_pct": _num(q.get("regularMarketChangePercent")),
        "volume": _num(q.get("regularMarketVolume")),
        "avg_volume_3m": _num(q.get("averageDailyVolume3Month")),
        "market_cap": _num(q.get("marketCap")),
        "bucket": bucket,
        "signal": {
            "gainers": "BULLISH_MOMENTUM",
            "losers": "BEARISH_MOMENTUM",
            "active": "HIGH_ACTIVITY",
        }.get(bucket, "EQUITY_MOVER"),
    }


def _fallback_bucket(bucket: str, *, count: int) -> list[dict[str, Any]]:
    return [
        _quote_row(q, bucket=bucket, rank=i + 1)
        for i, q in enumerate(FALLBACK_QUOTES.get(bucket, [])[: max(1, count)])
    ]


def fetch_yahoo_screen(screen_id: str, *, count: int) -> list[dict[str, Any]]:
    data = requests_get_json(
        YAHOO_SCREENER_URL,
        params={"scrIds": screen_id, "count": max(1, min(count, 100))},
        headers={
            "User-Agent": "Mozilla/5.0 ATLAS-EquitiesScanner/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
        retries=3,
        timeout_s=REQUEST_TIMEOUT_S,
    )
    result = (data.get("finance") or {}).get("result") or []
    if not result:
        return []
    quotes = result[0].get("quotes") or []
    return [q for q in quotes if isinstance(q, dict) and q.get("symbol")]


def scrape(*, count_per_bucket: int = 25) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []
    for bucket, screen_id in SCREENS.items():
        try:
            quotes = fetch_yahoo_screen(screen_id, count=count_per_bucket)
        except Exception as e:
            warnings.append(f"{bucket}_fetch_failed:{e}")
            quotes = []
        rows = [
            _quote_row(q, bucket=bucket, rank=i + 1)
            for i, q in enumerate(quotes[: max(1, count_per_bucket)])
        ]
        if not rows:
            warnings.append(f"{bucket}_fallback_used:live_source_empty")
            rows = _fallback_bucket(bucket, count=count_per_bucket)
        buckets[bucket] = rows

    seen: set[str] = set()
    combined: list[dict[str, Any]] = []
    for bucket in ("gainers", "losers", "active"):
        for row in buckets[bucket]:
            ticker = row.get("ticker")
            if not ticker or ticker in seen:
                continue
            seen.add(str(ticker))
            combined.append(row)

    payload: dict[str, Any] = {
        "generated_at": iso_now_z(),
        "source": "yahoo_finance_public_screener",
        "record_count": len(combined),
        "gainers": buckets["gainers"],
        "losers": buckets["losers"],
        "active": buckets["active"],
        "most_active": buckets["active"],
        "most_actives": buckets["active"],
        "combined": combined,
    }
    if warnings:
        payload["_meta"] = {
            "warnings": warnings,
            "data_quality": "fallback" if any("fallback_used" in w for w in warnings) else "live",
        }
    return payload


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="equities_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Equities movers snapshot -> data_cache JSON")
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape(count_per_bucket=max(1, args.count))
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"rows={out.get('record_count')}")
        return 0
    except Exception as e:
        print(f"equities_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
