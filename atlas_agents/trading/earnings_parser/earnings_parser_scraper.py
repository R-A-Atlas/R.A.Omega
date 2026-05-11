"""Upcoming earnings parser -> data_cache/earnings_latest.json."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "earnings_latest.json"
WINDOW_DAYS = 14

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "AVGO", "JPM"]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_sp500_tickers(limit: int = 80) -> list[str]:
    try:
        import pandas as pd

        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        symbols = tables[0]["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
        return symbols[:limit]
    except Exception:
        return DEFAULT_TICKERS[:limit]


def _date_from_value(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (list, tuple)) and value:
        return _date_from_value(value[0])
    try:
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime().date()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _calendar_field(calendar: Any, *names: str) -> Any:
    if isinstance(calendar, dict):
        for name in names:
            if name in calendar:
                return calendar[name]
    try:
        for name in names:
            if name in getattr(calendar, "index", []):
                return calendar.loc[name][0]
    except Exception:
        pass
    return None


def fetch_earnings_for_ticker(ticker: str) -> dict[str, Any] | None:
    tk = yf.Ticker(ticker)
    calendar = getattr(tk, "calendar", {}) or {}
    earnings_date = _date_from_value(_calendar_field(calendar, "Earnings Date", "Earnings Date(s)"))
    if not earnings_date:
        try:
            df = tk.get_earnings_dates(limit=4)
            if df is not None and not df.empty:
                earnings_date = _date_from_value(df.index[0])
        except Exception:
            pass
    if not earnings_date:
        return None
    info = getattr(tk, "fast_info", {}) or {}
    return {
        "ticker": ticker.upper(),
        "company_name": getattr(tk, "info", {}).get("shortName", "") if hasattr(tk, "info") else "",
        "date": earnings_date.isoformat(),
        "time": "UNKNOWN",
        "est_eps": _to_float(_calendar_field(calendar, "EPS Estimate")),
        "est_revenue": _to_int(_calendar_field(calendar, "Revenue Estimate")),
        "sector": info.get("sector") if isinstance(info, dict) else None,
        "days_until": (earnings_date - date.today()).days,
        "signal": "CATALYST_UPCOMING",
    }


def _to_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return None if value is None else int(float(value))
    except (TypeError, ValueError):
        return None


def scrape(*, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    upcoming: list[dict[str, Any]] = []
    for ticker in load_sp500_tickers():
        try:
            item = fetch_earnings_for_ticker(ticker)
            if item and 0 <= int(item.get("days_until", -1)) <= window_days:
                upcoming.append(item)
        except Exception:
            pass
        time.sleep(0.1)
    upcoming.sort(key=lambda row: (row.get("days_until", 999), row.get("ticker", "")))
    return {
        "generated_at": iso_now_z(),
        "source": "yfinance_calendar",
        "window_days": window_days,
        "record_count": len(upcoming),
        "upcoming": upcoming,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="earnings_",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS)
    args = parser.parse_args(argv)
    payload = scrape(window_days=args.window_days)
    if not args.dry_run:
        write_outputs(payload)
    print(f"earnings rows={payload['record_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
