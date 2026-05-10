"""
US Treasury curve snapshot -> data_cache/bond_yields_latest.json.

Primary: Yahoo Finance proxies (^IRX ~3–4Mo bill, optional 2YY=F for 2Y, ^FVX, ^TNX, ^TYX);
standard maturities (1M..30Y) filled by linear interpolation in years among anchors.

Fallback: Treasury Fiscal Data v2 Bills/Notes/Bonds aggregates (fewer knots).
"""

from __future__ import annotations

import argparse
import bisect
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import (
    REQUEST_TIMEOUT_S,
    requests_get_json,
    write_cache_json_pair,
)

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "bond_yields_latest.json"
FISCAL_RATES_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/"
    "od/avg_interest_rates?sort=-record_date&page[size]=10"
)


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yf_last_yield(symbol: str) -> float | None:
    tk = yf.Ticker(symbol)
    try:
        df = tk.history(period="5d", interval="1d")
        if df is not None and not df.empty:
            return float(df["Close"].dropna().iloc[-1])
    except Exception:
        pass
    try:
        info = tk.fast_info  # noqa: F841
        last = tk.fast_info.get("last_price")
        if last is not None:
            return float(last)
    except Exception:
        pass
    return None


def classify_curve_signal(
    yields: list[dict[str, Any]],
) -> tuple[str, float]:
    m = {}
    for row in yields:
        if not isinstance(row, dict):
            continue
        mat = row.get("maturity")
        if mat in ("2Y", "10Y"):
            try:
                m[str(mat)] = float(row["rate"])
            except (TypeError, ValueError, KeyError):
                continue
    y2 = m.get("2Y")
    y10 = m.get("10Y")
    if y2 is None or y10 is None:
        return "NORMAL", 0.0
    spread = round(y10 - y2, 4)
    if spread < 0:
        curve = "INVERTED"
    elif abs(spread) <= 0.25:
        curve = "FLAT"
    else:
        curve = "NORMAL"
    return curve, spread


def _interp_curve(ys: dict[float, float], years: float) -> float:
    xv = sorted(ys.keys())
    if not xv:
        return 0.0
    if years <= xv[0]:
        # Short-end extrapolation: soften toward zero maturity
        return ys[xv[0]]
    if years >= xv[-1]:
        return ys[xv[-1]]
    i = bisect.bisect_left(xv, years)
    xa, xb = xv[i - 1], xv[i]
    ya, yb = ys[xa], ys[xb]
    w = (years - xa) / (xb - xa) if xb != xa else 0.0
    return ya + w * (yb - ya)


def _build_curve_from_yahoo(record_date: str) -> tuple[list[dict[str, Any]], str, float]:
    anchors: dict[float, float | None] = {
        0.25: _yf_last_yield("^IRX"),
        2.0: _yf_last_yield("2YY=F"),
        5.0: _yf_last_yield("^FVX"),
        10.0: _yf_last_yield("^TNX"),
        30.0: _yf_last_yield("^TYX"),
    }

    ys: dict[float, float] = {}
    if anchors[0.25] is not None:
        ys[0.25] = anchors[0.25]
    if anchors[5.0] is not None:
        ys[5.0] = anchors[5.0]
    if anchors[10.0] is not None:
        ys[10.0] = anchors[10.0]
    if anchors[30.0] is not None:
        ys[30.0] = anchors[30.0]
    if anchors[2.0] is not None:
        ys[2.0] = anchors[2.0]
    elif anchors[0.25] is not None and anchors[5.0] is not None:
        ys[2.0] = anchors[0.25] + (anchors[5.0] - anchors[0.25]) * ((2 - 0.25) / (5 - 0.25))

    if len(ys) < 3:
        return [], "yahoo_insufficient", 0.0

    MATURITY_YEARS = {
        "1M": 1 / 12,
        "3M": 0.25,
        "6M": 0.5,
        "1Y": 1.0,
        "2Y": 2.0,
        "5Y": 5.0,
        "10Y": 10.0,
        "20Y": 20.0,
        "30Y": 30.0,
    }

    yields_out: list[dict[str, Any]] = []
    for lab, yrs in MATURITY_YEARS.items():
        rates = _interp_curve(ys, yrs)
        yields_out.append({"maturity": lab, "rate": round(float(rates), 4), "date": record_date})

    curve_sig, spread = classify_curve_signal(yields_out)
    return yields_out, curve_sig, spread


def _fiscal_aggregate_fallback() -> dict[str, Any] | None:
    try:
        data = requests_get_json(FISCAL_RATES_URL, timeout_s=REQUEST_TIMEOUT_S)
    except Exception:
        return None
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    rd = str(rows[0].get("record_date") or "")[:10]
    rates: dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        desc = str(r.get("security_desc") or "").lower()
        if str(r.get("record_date") or "")[:10] != rd:
            continue
        try:
            v = float(r.get("avg_interest_rate_amt"))
        except (TypeError, ValueError):
            continue
        if "bill" in desc:
            rates["Bills"] = v
        elif "note" in desc:
            rates["Notes"] = v
        elif "bond" in desc:
            rates["Bonds"] = v
    if len(rates) < 3:
        return None
    return {
        "generated_at": iso_now_z(),
        "source": "fiscaldata_treasury_gov",
        "record_date": rd,
        "record_count": 3,
        "curve_signal": "NORMAL",
        "spread_2y_10y": 0.0,
        "_meta": {
            "warning": (
                "YahooFinance curve unavailable — FiscalData aggregate Bills/Notes/Bonds only; "
                "2y/10y inversion signal not inferred."
            )
        },
        "yields": [
            {"maturity": k, "rate": v, "date": rd} for k, v in sorted(rates.items())
        ],
    }


def scrape() -> dict[str, Any]:
    record_date = iso_now_z()[:10]
    ylist, curve_sig, spread = _build_curve_from_yahoo(record_date)
    if ylist:
        return {
            "generated_at": iso_now_z(),
            "source": "yahoo_fed_curve_interpolated",
            "record_date": record_date,
            "record_count": len(ylist),
            "curve_signal": curve_sig,
            "spread_2y_10y": spread,
            "yields": ylist,
        }
    fb = _fiscal_aggregate_fallback()
    if fb:
        return fb
    return {
        "generated_at": iso_now_z(),
        "source": "bond_yields_unavailable",
        "record_date": "",
        "record_count": 0,
        "curve_signal": "NORMAL",
        "spread_2y_10y": 0.0,
        "_meta": {"error": "no_yield_sources"},
        "yields": [],
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="bond_yields_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Treasury curve -> data_cache JSON")
    p.add_argument("--dry-run", action="store_true", help="don't write disk")
    args = p.parse_args(argv)
    try:
        out = scrape()
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"yields={out.get('record_count')} curve={out.get('curve_signal')}")
        return 0
    except Exception as e:
        print(f"bond_yields_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
