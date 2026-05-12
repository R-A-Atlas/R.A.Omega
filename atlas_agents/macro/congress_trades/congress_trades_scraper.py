"""Congressional trade watcher -> data_cache/congress_trades_latest.json."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import REQUEST_TIMEOUT_S, requests_get_json, write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "congress_trades_latest.json"
HSW_TRANSACTIONS_URL = "https://housestockwatcher.com/api/transactions"

FALLBACK_TRADES: list[dict[str, Any]] = [
    {
        "member": "Fallback House Disclosure",
        "chamber": "House",
        "party": "",
        "state": "",
        "ticker": "NVDA",
        "transaction_type": "Purchase",
        "amount_range": "$15,001 - $50,000",
        "trade_date": "",
        "disclosed_date": "",
        "days_to_disclose": 28,
        "disclosure_signal": "ON_TIME",
    },
    {
        "member": "Fallback Senate Disclosure",
        "chamber": "Senate",
        "party": "",
        "state": "",
        "ticker": "AAPL",
        "transaction_type": "Sale",
        "amount_range": "$1,001 - $15,000",
        "trade_date": "",
        "disclosed_date": "",
        "days_to_disclose": 52,
        "disclosure_signal": "LATE_DISCLOSURE",
    },
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_house_trades(limit: int = 100) -> list[dict[str, Any]]:
    data = requests_get_json(HSW_TRANSACTIONS_URL, timeout_s=REQUEST_TIMEOUT_S)
    rows = data if isinstance(data, list) else data.get("data") or data.get("transactions") or []
    return list(rows)[:limit]


def compute_days_to_disclose(trade_date_str: str, disclosed_date_str: str) -> int:
    try:
        return (date.fromisoformat(disclosed_date_str[:10]) - date.fromisoformat(trade_date_str[:10])).days
    except Exception:
        return 0


def classify_disclosure(days: int) -> str:
    return "LATE_DISCLOSURE" if days > 45 else "ON_TIME"


def normalize_house_trade(raw: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(raw.get("ticker") or raw.get("asset_ticker") or "").upper().strip("- ")
    if not ticker or not ticker.isalpha() or len(ticker) > 5:
        return None
    trade_date = str(raw.get("transaction_date") or raw.get("trade_date") or raw.get("transactionDate") or "")
    disclosed_date = str(raw.get("disclosure_date") or raw.get("filed_date") or raw.get("disclosureDate") or trade_date)
    days = compute_days_to_disclose(trade_date, disclosed_date)
    return {
        "member": raw.get("representative") or raw.get("name") or raw.get("member") or "",
        "chamber": "House",
        "party": raw.get("party") or "",
        "state": raw.get("state") or "",
        "ticker": ticker,
        "transaction_type": raw.get("type") or raw.get("transaction_type") or "Purchase",
        "amount_range": raw.get("amount") or raw.get("amount_range") or "",
        "trade_date": trade_date[:10],
        "disclosed_date": disclosed_date[:10],
        "days_to_disclose": max(0, days),
        "disclosure_signal": classify_disclosure(days),
    }


def compute_most_traded_ticker(trades: list[dict[str, Any]]) -> str:
    tickers = [t["ticker"] for t in trades if t.get("ticker")]
    return Counter(tickers).most_common(1)[0][0] if tickers else ""


def build_output(trades: list[dict[str, Any]]) -> dict[str, Any]:
    late = sum(1 for t in trades if t.get("disclosure_signal") == "LATE_DISCLOSURE")
    return {
        "generated_at": iso_now_z(),
        "source": "housestockwatcher_public_api",
        "record_count": len(trades),
        "late_disclosure_count": late,
        "most_traded_ticker": compute_most_traded_ticker(trades),
        "trades": trades,
    }


def fallback_trades(limit: int = 50) -> list[dict[str, Any]]:
    today = date.today().isoformat()
    rows = [dict(row) for row in FALLBACK_TRADES[: max(1, limit)]]
    for row in rows:
        row["trade_date"] = row.get("trade_date") or today
        row["disclosed_date"] = row.get("disclosed_date") or today
    return rows


def scrape(limit: int = 50) -> dict[str, Any]:
    warning = ""
    try:
        raw_rows = fetch_house_trades(limit=limit)
    except Exception as exc:
        warning = f"housestockwatcher_fetch_failed:{exc}"
        raw_rows = []
    trades = [row for raw in raw_rows if (row := normalize_house_trade(raw))]
    out = build_output(trades)
    if not trades:
        fallback = fallback_trades(limit=limit)
        out = build_output(fallback)
        out["_meta"] = {
            "data_quality": "fallback",
            "fallback_used": True,
            "warning": warning or "HouseStockWatcher returned no usable rows.",
        }
    return out


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=OUTPUT_STABLE_NAME, stamped_prefix="congress_trades_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    payload = scrape(limit=args.limit)
    if not args.dry_run:
        write_outputs(payload)
    print(f"congress_trades rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
