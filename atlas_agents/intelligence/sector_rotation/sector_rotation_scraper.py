"""
Sector Rotation Agent (D10) -> data_cache/sector_rotation_latest.json

Reads data_cache/equities_latest.json (written by D2 Equities Scanner) and
classifies which GICS sectors are leading/lagging. No external HTTP calls needed.
Fallback: if equities file missing, uses realistic mock sector data.
"""

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
OUTPUT_STABLE_NAME = "sector_rotation_latest.json"
EQUITIES_FILE = DATA_CACHE_DIR / "equities_latest.json"

# Ticker -> GICS Sector mapping (S&P 500 representative sample)
TICKER_SECTOR: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "AVGO": "Technology", "AMD": "Technology", "ADBE": "Technology",
    "CRM": "Technology", "CSCO": "Technology", "TXN": "Technology",
    "IBM": "Technology", "ORCL": "Technology", "INTU": "Technology",
    "PANW": "Technology", "ADI": "Technology", "MU": "Technology",
    "NOW": "Technology",
    # Communication Services
    "GOOGL": "Communication Services", "META": "Communication Services",
    "NFLX": "Communication Services",
    # Consumer Discretionary
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "V": "Financials",
    "MA": "Financials", "GS": "Financials", "AXP": "Financials",
    "SPGI": "Financials", "MMC": "Financials",
    # Health Care
    "LLY": "Health Care", "UNH": "Health Care", "JNJ": "Health Care",
    "MRK": "Health Care", "ABBV": "Health Care", "TMO": "Health Care",
    "AMGN": "Health Care", "ISRG": "Health Care", "REGN": "Health Care",
    "VRTX": "Health Care", "DHR": "Health Care", "SYK": "Health Care",
    "ELV": "Health Care",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples", "PM": "Consumer Staples",
    # Energy
    "XOM": "Energy", "CVX": "Energy",
    # Industrials
    "GE": "Industrials", "RTX": "Industrials",
    "CAT": "Industrials", "ACN": "Industrials",
    # Utilities
    "NEE": "Utilities",
    # Materials
    "LIN": "Materials",
    # Financials (BRK)
    "BRK-B": "Financials",
}

SECTOR_ORDER = [
    "Technology", "Communication Services", "Consumer Discretionary",
    "Financials", "Health Care", "Consumer Staples", "Energy",
    "Industrials", "Utilities", "Materials", "Real Estate",
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_rotation_signal(avg_change_pct: float, bullish_ratio: float) -> str:
    if avg_change_pct >= 2.0 and bullish_ratio >= 0.6:
        return "LEADING"
    if avg_change_pct >= 0.5:
        return "OUTPERFORMING"
    if avg_change_pct >= -0.5:
        return "NEUTRAL"
    if avg_change_pct >= -2.0:
        return "UNDERPERFORMING"
    return "LAGGING"


def _load_equities() -> list[dict[str, Any]]:
    """Load all tickers from equities_latest.json (gainers + losers)."""
    import json
    if not EQUITIES_FILE.is_file():
        return []
    try:
        raw = json.loads(EQUITIES_FILE.read_text(encoding="utf-8"))
        all_tickers: list[dict[str, Any]] = []
        for bucket in ("gainers", "losers", "active"):
            all_tickers.extend(raw.get(bucket) or [])
        return all_tickers
    except Exception:
        return []


def _mock_sector_data() -> list[dict[str, Any]]:
    """Realistic mock equities data for 2026 — AI/tech rally environment."""
    import random
    random.seed(int(datetime.now(timezone.utc).strftime("%Y%m%d")))

    mock = []
    sector_bias = {
        "Technology": (3.5, 1.8),
        "Communication Services": (2.1, 1.5),
        "Consumer Discretionary": (1.2, 1.8),
        "Financials": (0.8, 1.2),
        "Health Care": (0.5, 1.0),
        "Consumer Staples": (-0.2, 0.6),
        "Energy": (-0.8, 1.5),
        "Industrials": (0.4, 0.9),
        "Utilities": (-0.5, 0.7),
        "Materials": (0.1, 1.1),
    }
    for ticker, sector in TICKER_SECTOR.items():
        mean, std = sector_bias.get(sector, (0.0, 1.0))
        chg_pct = random.gauss(mean, std)
        mock.append({
            "ticker": ticker,
            "change_pct": round(chg_pct, 4),
            "signal": "BULLISH_MOMENTUM" if chg_pct > 0.5 else ("BEARISH" if chg_pct < -0.5 else "NEUTRAL"),
        })
    return mock


def analyze(equities_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate per-ticker data into sector-level rotation signals."""
    from collections import defaultdict

    sector_changes: dict[str, list[float]] = defaultdict(list)
    sector_signals: dict[str, dict[str, int]] = defaultdict(lambda: {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0})
    sector_tickers: dict[str, list[str]] = defaultdict(list)

    for row in equities_rows:
        ticker = str(row.get("ticker") or "").upper()
        sector = TICKER_SECTOR.get(ticker)
        if not sector:
            continue
        chg = row.get("change_pct")
        if chg is None:
            continue
        try:
            chg_f = float(chg)
        except (TypeError, ValueError):
            continue

        sector_changes[sector].append(chg_f)
        sector_tickers[sector].append(ticker)
        sig = str(row.get("signal") or "")
        if "BULLISH" in sig:
            sector_signals[sector]["BULLISH"] += 1
        elif "BEARISH" in sig:
            sector_signals[sector]["BEARISH"] += 1
        else:
            sector_signals[sector]["NEUTRAL"] += 1

    results = []
    for sector in SECTOR_ORDER:
        changes = sector_changes.get(sector, [])
        if not changes:
            continue
        avg_chg = round(sum(changes) / len(changes), 3)
        sigs = sector_signals[sector]
        total_sigs = sigs["BULLISH"] + sigs["BEARISH"] + sigs["NEUTRAL"] or 1
        bullish_ratio = round(sigs["BULLISH"] / total_sigs, 3)
        rotation_signal = _classify_rotation_signal(avg_chg, bullish_ratio)

        results.append({
            "sector": sector,
            "avg_change_pct": avg_chg,
            "ticker_count": len(changes),
            "bullish_count": sigs["BULLISH"],
            "bearish_count": sigs["BEARISH"],
            "neutral_count": sigs["NEUTRAL"],
            "bullish_ratio": bullish_ratio,
            "rotation_signal": rotation_signal,
            "top_tickers": sector_tickers[sector][:5],
        })

    # Sort: LEADING > OUTPERFORMING > NEUTRAL > UNDERPERFORMING > LAGGING
    signal_rank = {
        "LEADING": 0, "OUTPERFORMING": 1, "NEUTRAL": 2,
        "UNDERPERFORMING": 3, "LAGGING": 4
    }
    results.sort(key=lambda x: (signal_rank.get(x["rotation_signal"], 9), -x["avg_change_pct"]))
    return results


def scrape() -> dict[str, Any]:
    rows = _load_equities()
    source = "equities_latest_json"

    # Check coverage: need at least 10 tickers in our sector map
    matched = [r for r in rows if str(r.get("ticker") or "").upper() in TICKER_SECTOR]
    if len(matched) < 10:
        rows = _mock_sector_data()
        source = "mock_sector_2026" if not matched else "equities_augmented_mock_2026"
    else:
        rows = matched

    sectors = analyze(rows)

    leading = [s["sector"] for s in sectors if s["rotation_signal"] == "LEADING"]
    lagging = [s["sector"] for s in sectors if s["rotation_signal"] == "LAGGING"]

    return {
        "generated_at": iso_now_z(),
        "source": source,
        "record_count": len(sectors),
        "leading_sectors": leading,
        "lagging_sectors": lagging,
        "sectors": sectors,
        "_meta": {
            "input_file": "data_cache/equities_latest.json",
            "sector_classification": "GICS",
        },
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="sector_rotation_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sector Rotation -> data_cache JSON")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape()
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(
            f"sectors={out.get('record_count')} "
            f"leading={out.get('leading_sectors')} "
            f"source={out.get('source')}"
        )
        return 0
    except Exception as e:
        print(f"sector_rotation_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
