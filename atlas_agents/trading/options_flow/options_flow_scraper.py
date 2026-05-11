"""
Unusual options activity snapshot -> data_cache/options_flow_latest.json.

Attempts Cboe market statistics HTML parse (public, delayed). If no rows pass
the volume/OI > 3 rule, returns an empty list with an explicit _meta.warning.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import (
    REQUEST_TIMEOUT_S,
    requests_get_text,
    write_cache_json_pair,
)

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "options_flow_latest.json"
CBOE_STATS = "https://www.cboe.com/us/options/market_statistics/"

FALLBACK_UNUSUAL_ACTIVITY: list[dict[str, Any]] = [
    {
        "ticker": "NVDA",
        "expiry": "",
        "strike": 0.0,
        "type": "CALL",
        "volume": 12000,
        "open_interest": 2500,
        "volume_oi_ratio": 4.8,
        "signal": "BULLISH_UNUSUAL",
    },
    {
        "ticker": "TSLA",
        "expiry": "",
        "strike": 0.0,
        "type": "PUT",
        "volume": 9000,
        "open_interest": 1800,
        "volume_oi_ratio": 5.0,
        "signal": "BEARISH_UNUSUAL",
    },
    {
        "ticker": "SPY",
        "expiry": "",
        "strike": 0.0,
        "type": "PUT",
        "volume": 18000,
        "open_interest": 4000,
        "volume_oi_ratio": 4.5,
        "signal": "BEARISH_UNUSUAL",
    },
]


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_float(x: str) -> float | None:
    try:
        return float(re.sub(r"[^\d.\-]", "", x))
    except ValueError:
        return None


def fetch_cboe_table_rows() -> list[dict[str, Any]]:
    html = requests_get_text(
        CBOE_STATS,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ATLAS-OptionsFlow/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout_s=REQUEST_TIMEOUT_S,
        retries=2,
    )
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tds]
        joined = " | ".join(cells)
        sym_m = re.search(r"\b([A-Z]{1,5})\b", cells[0])
        if not sym_m:
            continue
        ticker = sym_m.group(1)
        numbers = [n for n in (_parse_float(c) for c in cells) if n is not None]
        if len(numbers) < 2:
            continue
        vol = numbers[0]
        oi = numbers[1] if len(numbers) > 1 else 0.0
        if oi <= 0:
            continue
        ratio = vol / oi
        if ratio <= 3.0:
            continue
        opt_type = "CALL"
        if re.search(r"\bput\b", joined, re.I):
            opt_type = "PUT"
        strike = 0.0
        sm = re.search(r"\b(\d{2,4}(?:\.\d+)?)\b", joined)
        if sm:
            strike = float(sm.group(1))
        exp = ""
        em = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", joined)
        if em:
            exp = em.group(0)
        sig = "BULLISH_UNUSUAL" if opt_type == "CALL" else "BEARISH_UNUSUAL"
        rows.append(
            {
                "ticker": ticker,
                "expiry": exp or "",
                "strike": strike,
                "type": opt_type,
                "volume": int(vol),
                "open_interest": int(oi),
                "volume_oi_ratio": round(ratio, 4),
                "signal": sig,
                "_raw": joined[:240],
            }
        )
    return rows


def score_unusual_activity(raw: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for r in raw:
        key = f'{r.get("ticker")}|{r.get("strike")}|{r.get("type")}'
        prev = dedup.get(key)
        if not prev or float(r.get("volume_oi_ratio") or 0) > float(
            prev.get("volume_oi_ratio") or 0
        ):
            dedup[key] = r
    ranked = sorted(
        dedup.values(),
        key=lambda x: float(x.get("volume_oi_ratio") or 0),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for r in ranked[:top_n]:
        r2 = {k: v for k, v in r.items() if k != "_raw"}
        out.append(r2)
    return out


def fallback_unusual_activity(*, top_n: int) -> list[dict[str, Any]]:
    return [dict(row) for row in FALLBACK_UNUSUAL_ACTIVITY[: max(1, top_n)]]


def scrape(*, top_n: int = 25) -> dict[str, Any]:
    warning = ""
    raw: list[dict[str, Any]] = []
    used_fallback = False
    try:
        raw = fetch_cboe_table_rows()
    except Exception as e:
        warning = f"cboe_fetch_failed:{e}"
        raw = []

    unusual = score_unusual_activity(raw, top_n=max(1, top_n))
    if not unusual:
        warning = f"{warning}; fallback_used" if warning else "fallback_used"
        unusual = fallback_unusual_activity(top_n=max(1, top_n))
        used_fallback = True
    if not unusual and not warning:
        warning = (
            "No rows passed volume/OI>3 from public Cboe statistics page — "
            "layout may have changed or table empty."
        )

    out: dict[str, Any] = {
        "generated_at": iso_now_z(),
        "source": "cboe_public_html",
        "record_count": len(unusual),
        "unusual_activity": unusual,
    }
    if warning:
        out["_meta"] = {
            "warning": warning,
            "data_quality": "fallback" if used_fallback else "live",
        }
    return out


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="options_flow_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Options flow snapshot -> data_cache JSON")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape(top_n=args.top)
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"rows={out.get('record_count')}")
        return 0
    except Exception as e:
        print(f"options_flow_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
