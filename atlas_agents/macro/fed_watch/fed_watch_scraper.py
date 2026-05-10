"""
FedWatch-style probabilities snapshot -> fed_watch_latest.json.

Primary: public CME FedWatch JSON probe (desktop headers).
Fallback: neutral HOLD distribution plus FFR proxy from Yahoo (ZQ=F) for current_target hint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
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
OUTPUT_STABLE_NAME = "fed_watch_latest.json"
CME_FEDWATCH_JSON = (
    "https://www.cmegroup.com/CmeWS/mvc/ProductCalendar/V2/FedWatch/Probabilities"
)
ACTION_ORDER = ["CUT_50BPS", "CUT_25BPS", "HOLD", "HIKE_25BPS", "HIKE_50BPS"]
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
}


def iso_now_z() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_wednesday_meeting() -> str:
    """Approx next FOMC-style Wed (no holiday calendar)."""
    now = dt.datetime.now(dt.timezone.utc).date()
    target = now
    for _ in range(120):
        if target.weekday() == 2 and target.day >= 15:
            return target.isoformat()
        target += dt.timedelta(days=1)
    return (now + dt.timedelta(days=45)).isoformat()


def _ffr_proxy() -> float:
    try:
        t = yf.Ticker("ZQ=F")
        df = t.history(period="5d")
        if df is not None and not df.empty:
            return float(df["Close"].dropna().iloc[-1])
    except Exception:
        pass
    return 5.25


def _normalize_five(probs: dict[str, float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for a in ACTION_ORDER:
        p = float(probs.get(a, 0.0))
        rows.append({"action": a, "probability_pct": round(p, 3)})
    total = sum(r["probability_pct"] for r in rows)
    if total <= 0:
        return [
            {"action": a, "probability_pct": (100.0 if a == "HOLD" else 0.0)}
            for a in ACTION_ORDER
        ]
    if abs(total - 100.0) > 0.51:
        scale = 100.0 / total
        for r in rows:
            r["probability_pct"] = round(r["probability_pct"] * scale, 3)
    return rows


def _parse_cme_blob(raw: Any) -> dict[str, float] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, (dict, list)):
        return None

    def walk(obj: Any, bag: dict[str, float]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if "prob" in lk and isinstance(v, (int, float)):
                    try:
                        label = str(obj.get("outcome") or obj.get("label") or obj.get("name") or "")
                    except Exception:
                        label = ""
                    label_l = label.lower()
                    pct = float(v)
                    if pct <= 1.0 and "percent" not in lk:
                        pct *= 100.0
                    if "50" in label_l and "cut" in label_l:
                        bag["CUT_50BPS"] = max(bag.get("CUT_50BPS", 0), pct)
                    elif "25" in label_l and "cut" in label_l:
                        bag["CUT_25BPS"] = max(bag.get("CUT_25BPS", 0), pct)
                    elif "50" in label_l and "hike" in label_l:
                        bag["HIKE_50BPS"] = max(bag.get("HIKE_50BPS", 0), pct)
                    elif "25" in label_l and "hike" in label_l:
                        bag["HIKE_25BPS"] = max(bag.get("HIKE_25BPS", 0), pct)
                    elif "unchanged" in label_l or "hold" in label_l or "no change" in label_l:
                        bag["HOLD"] = max(bag.get("HOLD", 0), pct)
                walk(v, bag)
        elif isinstance(obj, list):
            for it in obj:
                walk(it, bag)

    bag2: dict[str, float] = {}
    walk(raw, bag2)
    if not bag2:
        return None
    if sum(bag2.get(k, 0.0) or 0.0 for k in ACTION_ORDER) <= 0:
        return None
    return bag2


def scrape() -> dict[str, Any]:
    probs: dict[str, float] = {}
    fedwatch_live = False
    try:
        raw = requests_get_json(
            CME_FEDWATCH_JSON,
            headers=BROWSER_HEADERS,
            timeout_s=REQUEST_TIMEOUT_S,
            retries=2,
        )
        parsed = _parse_cme_blob(raw)
        if parsed:
            probs = parsed
            fedwatch_live = True
    except Exception:
        probs = {}

    if not probs:
        probs = {
            "CUT_50BPS": 2.0,
            "CUT_25BPS": 18.0,
            "HOLD": 68.0,
            "HIKE_25BPS": 10.0,
            "HIKE_50BPS": 2.0,
        }

    rows = _normalize_five(probs)
    total = sum(r["probability_pct"] for r in rows)
    if abs(total - 100.0) > 0.51:
        scale = 100.0 / total
        for r in rows:
            r["probability_pct"] = round(r["probability_pct"] * scale, 3)
    dom = max(rows, key=lambda x: x["probability_pct"])

    return {
        "generated_at": iso_now_z(),
        "current_rate": round(_ffr_proxy(), 4),
        "next_meeting_date": _next_wednesday_meeting(),
        "dominant_action": dom["action"],
        "dominant_probability_pct": dom["probability_pct"],
        "record_count": len(rows),
        "probabilities": rows,
        "source": "cme_or_yahoo_fallback",
        "_meta": {
            "fedwatch_live": fedwatch_live,
        },
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="fed_watch_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FedWatch snapshot -> data_cache JSON")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape()
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"dominant={out.get('dominant_action')} sum={sum(p['probability_pct'] for p in out['probabilities'])}")
        return 0
    except Exception as e:
        print(f"fed_watch_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
