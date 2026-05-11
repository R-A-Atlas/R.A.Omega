"""Commodities futures snapshot -> data_cache/commodities_latest.json."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "commodities_latest.json"

TICKERS = {
    "Gold": ("GC=F", "USD/troy oz"),
    "Silver": ("SI=F", "USD/troy oz"),
    "Copper": ("HG=F", "USD/lb"),
    "WTI Oil": ("CL=F", "USD/barrel"),
    "Nat Gas": ("NG=F", "USD/MMBtu"),
    "Wheat": ("ZW=F", "USD/bushel"),
    "Corn": ("ZC=F", "USD/bushel"),
}


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_trend(change_pct: float | None) -> str:
    if change_pct is None:
        return "FLAT"
    if change_pct >= 0.5:
        return "RISING"
    if change_pct <= -0.5:
        return "FALLING"
    return "FLAT"


def fetch_commodity(name: str, ticker: str, unit: str) -> dict[str, Any] | None:
    tk = yf.Ticker(ticker)
    info = getattr(tk, "fast_info", {}) or {}
    price = _num(info.get("lastPrice") or info.get("last_price"))
    prev = _num(info.get("previousClose") or info.get("previous_close"))
    if price is None:
        try:
            hist = tk.history(period="5d", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes):
                price = float(closes.iloc[-1])
            if len(closes) >= 2 and prev is None:
                prev = float(closes.iloc[-2])
        except Exception:
            pass
    change = round(price - prev, 4) if price is not None and prev not in (None, 0) else None
    change_pct = round((change / prev) * 100, 4) if change is not None and prev else None
    return {
        "name": name,
        "ticker": ticker,
        "price": price,
        "unit": unit,
        "prev_close": prev,
        "change_24h": change,
        "change_24h_pct": change_pct,
        "trend": classify_trend(change_pct),
    }


def scrape() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, (ticker, unit) in TICKERS.items():
        try:
            row = fetch_commodity(name, ticker, unit)
            if row:
                rows.append(row)
        except Exception:
            pass
        time.sleep(0.1)
    return {
        "generated_at": iso_now_z(),
        "source": "yfinance_futures",
        "record_count": len(rows),
        "commodities": rows,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="commodities_",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = scrape()
    if not args.dry_run:
        write_outputs(payload)
    print(f"commodities rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
