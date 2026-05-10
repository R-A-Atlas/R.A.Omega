"""
BLS CPI snapshot -> data_cache/cpi_latest.json (no LLM).
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

from atlas_core.utils.agent_utils import (
    write_cache_json_pair,
    requests_post_json,
)

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "cpi_latest.json"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
CATEGORY_NAMES = {
    "CUUR0000SAF1": "Food",
    "CUUR0000SA0E": "Energy",
    "CUUR0000SEHA": "Shelter",
    "CUUR0000SAM": "Medical Care",
}
CATEGORY_SERIES = list(CATEGORY_NAMES.keys())

CATEGORY_WEIGHTS = {
    "Food": 0.138,
    "Energy": 0.073,
    "Shelter": 0.365,
    "Medical Care": 0.092,
}


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_latest_three(series_data: list[dict[str, Any]]) -> tuple[
    dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None,
]:
    if not series_data:
        return None, None, None
    sd = sorted(
        series_data,
        key=lambda x: (str(x.get("year", "")), str(x.get("period", ""))),
        reverse=True,
    )
    latest = sd[0]
    prior = sd[1] if len(sd) > 1 else None
    ly = str(int(latest["year"]) - 1)
    lp = str(latest.get("period"))
    yo = next(
        (
            x
            for x in sd
            if str(x.get("year")) == ly and str(x.get("period")) == lp
        ),
        None,
    )
    return latest, prior, yo


def classify_signal(yoy_pct: float) -> str:
    if yoy_pct >= 4.0:
        return "HOT"
    if yoy_pct >= 2.5:
        return "ELEVATED"
    if yoy_pct >= 1.5:
        return "ON_TARGET"
    return "DEFLATIONARY"


def compute_contribution(category_name: str, yoy_pct: float) -> float:
    w = CATEGORY_WEIGHTS.get(category_name, 0.05)
    return round(w * yoy_pct / 100 * 100, 4)


def fetch_cpi_series(series_ids: list[str], *, start_year: str, end_year: str) -> dict[str, Any]:
    body = {"seriesid": series_ids, "startyear": start_year, "endyear": end_year}
    resp = requests_post_json(BLS_API_URL, json_body=body, retries=3)
    if not isinstance(resp, dict) or resp.get("status") != "REQUEST_SUCCEEDED":
        msg = str(resp.get("message", resp))[:500] if isinstance(resp, dict) else str(resp)
        raise RuntimeError(f"BLS CPI error: {msg}")
    out: dict[str, Any] = {}
    series_list = (resp.get("Results") or {}).get("series")
    if not isinstance(series_list, list):
        return out
    for entry in series_list:
        sid = entry.get("seriesID")
        data = entry.get("data") or []
        if isinstance(sid, str):
            out[sid] = data if isinstance(data, list) else []
    return out


def build_categories(series_data: dict[str, Any]) -> list[dict[str, Any]]:
    cats: list[dict[str, Any]] = []
    for series_id in CATEGORY_SERIES:
        name = CATEGORY_NAMES[series_id]
        rows = series_data.get(series_id) or []
        if not isinstance(rows, list):
            continue
        latest, _, yo = get_latest_three(rows)
        if not latest or not yo:
            continue
        try:
            lv = float(latest["value"])
            ypv = float(yo["value"])
        except (TypeError, ValueError, KeyError):
            continue
        yoy = round(((lv - ypv) / ypv * 100) if ypv else 0.0, 2)
        cats.append(
            {
                "name": name,
                "yoy_change_pct": yoy,
                "contribution": compute_contribution(name, yoy),
            }
        )
    return cats



def _mock_cpi() -> dict[str, Any]:
    """
    Realistic 2026 CPI mock.
    BLS CPI-U: ~317.8 (Mar 2026); YoY ~2.4%; Core YoY ~2.8% (shelter sticky).
    """
    categories = [
        {"name": "Food", "yoy_change_pct": 2.1, "contribution": 0.029},
        {"name": "Energy", "yoy_change_pct": -1.8, "contribution": -0.013},
        {"name": "Shelter", "yoy_change_pct": 4.2, "contribution": 0.153},
        {"name": "Medical Care", "yoy_change_pct": 3.1, "contribution": 0.029},
    ]
    return {
        "generated_at": iso_now_z(),
        "period": "2026-03",
        "cpi_index": 317.8,
        "mom_change_pct": 0.2,
        "yoy_change_pct": 2.4,
        "core_cpi_yoy_pct": 2.8,
        "inflation_signal": classify_signal(2.4),
        "record_count": len(categories),
        "categories": categories,
        "source": "mock_cpi_2026_targets",
        "_meta": {"live": False, "note": "BLS API unavailable"},
    }

def scrape() -> dict[str, Any]:
    now_y = datetime.now(timezone.utc).year
    start_year = str(now_y - 2)
    end_year = str(now_y)
    all_series = ["CUUR0000SA0", "CUUR0000SA0L1E"] + CATEGORY_SERIES
    try:
        series_blob = fetch_cpi_series(all_series, start_year=start_year, end_year=end_year)
    except Exception:
        return _mock_cpi()

    headline_rows = series_blob.get("CUUR0000SA0") or []
    core_rows = series_blob.get("CUUR0000SA0L1E") or []

    h_latest, h_prior, h_yago = get_latest_three(
        headline_rows if isinstance(headline_rows, list) else []
    )
    c_latest, _, c_yago = get_latest_three(
        core_rows if isinstance(core_rows, list) else []
    )

    if not h_latest:
        return _mock_cpi()

    cpi_index = float(h_latest["value"])
    mom_pct = (
        round(
            (float(h_latest["value"]) - float(h_prior["value"]))
            / float(h_prior["value"])
            * 100,
            3,
        )
        if h_prior
        else 0.0
    )
    yoy_pct = (
        round(
            (float(h_latest["value"]) - float(h_yago["value"]))
            / float(h_yago["value"])
            * 100,
            2,
        )
        if h_yago
        else 0.0
    )
    core_yoy = (
        round(
            (float(c_latest["value"]) - float(c_yago["value"]))
            / float(c_yago["value"])
            * 100,
            2,
        )
        if (c_latest and c_yago)
        else 0.0
    )

    period = f'{h_latest["year"]}-{str(h_latest["period"]).replace("M", "").zfill(2)}'

    cats = build_categories(series_blob)

    return {
        "generated_at": iso_now_z(),
        "period": period[:7] if len(period) >= 7 else period,
        "cpi_index": cpi_index,
        "mom_change_pct": mom_pct,
        "yoy_change_pct": yoy_pct,
        "core_cpi_yoy_pct": core_yoy,
        "inflation_signal": classify_signal(yoy_pct),
        "record_count": len(cats),
        "categories": cats,
        "source": "bls_cpi_public_api",
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="cpi_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="BLS CPI -> data_cache JSON")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape()
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"CPI index={out.get('cpi_index')} signal={out.get('inflation_signal')}")
        return 0
    except Exception as e:
        print(f"inflation_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
