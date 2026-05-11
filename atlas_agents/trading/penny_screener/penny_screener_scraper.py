"""Penny stock volume screener -> data_cache/penny_stocks_latest.json."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "penny_stocks_latest.json"
MAX_PRICE = 10.0
MAX_MARKET_CAP = 300_000_000
MIN_VOLUME_RATIO = 3.0


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_most_active_screener() -> list[dict[str, Any]]:
    data = yf.screen("most_actives")
    if isinstance(data, dict):
        if isinstance(data.get("quotes"), list):
            return data["quotes"]
        result = (((data.get("finance") or {}).get("result") or [{}])[0]).get("quotes")
        if isinstance(result, list):
            return result
    return []


def compute_volume_ratio(stock: dict[str, Any]) -> float:
    volume = _num(stock.get("regularMarketVolume") or stock.get("volume")) or 0.0
    avg = _num(
        stock.get("averageDailyVolume3Month")
        or stock.get("averageDailyVolume10Day")
        or stock.get("avg_volume_30d")
    ) or 0.0
    if avg <= 0:
        return 0.0
    return round(volume / avg, 4)


def classify_signal(ratio: float) -> str:
    return "HIGH_VOLUME_PENNY" if ratio >= 5.0 else "ELEVATED_VOLUME_PENNY"


def _row(stock: dict[str, Any]) -> dict[str, Any] | None:
    quote_type = str(stock.get("quoteType") or "").upper()
    if quote_type in {"ETF", "MUTUALFUND", "FUND"}:
        return None
    price = _num(stock.get("regularMarketPrice") or stock.get("price"))
    if price is None or price >= MAX_PRICE:
        return None
    ratio = compute_volume_ratio(stock)
    if ratio < MIN_VOLUME_RATIO:
        return None
    volume = _num(stock.get("regularMarketVolume") or stock.get("volume"))
    avg = _num(stock.get("averageDailyVolume3Month") or stock.get("averageDailyVolume10Day"))
    return {
        "ticker": str(stock.get("symbol") or stock.get("ticker") or "").upper(),
        "price": price,
        "volume": int(volume or 0),
        "avg_volume_30d": int(avg or 0),
        "volume_ratio": ratio,
        "market_cap": _num(stock.get("marketCap")),
        "change_pct": _num(stock.get("regularMarketChangePercent") or stock.get("change_pct")),
        "sector": stock.get("sector") or "",
        "signal": classify_signal(ratio),
    }


def filter_penny_criteria(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for stock in stocks if (row := _row(stock))]
    rows.sort(key=lambda x: (x.get("volume_ratio") or 0), reverse=True)
    return rows


def scrape(*, top_n: int = 25) -> dict[str, Any]:
    try:
        quotes = fetch_most_active_screener()
    except Exception:
        quotes = []
    stocks = filter_penny_criteria(quotes)[: max(1, min(100, int(top_n)))]
    return {
        "generated_at": iso_now_z(),
        "source": "yfinance_screener",
        "record_count": len(stocks),
        "stocks": stocks,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="penny_stocks_",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args(argv)
    payload = scrape(top_n=args.top_n)
    if not args.dry_run:
        write_outputs(payload)
    print(f"penny rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
