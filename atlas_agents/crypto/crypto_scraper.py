"""
ATLAS autonomous crypto snapshot (no LLM).

Merge policy:
  1) CoinGecko /search/trending — prioritized ordering (few items on free tier).
  2) CoinGecko /coins/markets (volume_desc) — fills remaining slots up to TOP_N unique ids.
  3) CoinGecko /coins/{id} — categories for meme vs utility classification (+ retries on 429), parallelized lightly.
  Optional: Binance /api/v3/ticker/24hr — supplemental USDT quote volume keyed by base symbol.

Output: data_cache/crypto_top50_latest.json (+ dated copy) relative to repo root.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import (
    REQUEST_TIMEOUT_S,
    requests_get_json,
    write_cache_json_pair,
)


DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "crypto_top50_latest.json"

COINGECKO_ROOT = "https://api.coingecko.com/api/v3"
BINANCE_TICKER_24H = "https://api.binance.com/api/v3/ticker/24hr"

MAX_MARKETS_ROWS = 250
TOP_DEFAULT = 50
DEFAULT_CATEGORY_WORKERS = 1
MEME_HINTS = ("meme",)
CATEGORY_REQUEST_GAP_S = 0.55  # sequential /coins/{id} pacing when --category-workers 1


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_sector(categories: list[str]) -> str:
    if not categories:
        return "unknown"
    lowered = [c.lower() for c in categories]
    for c in lowered:
        for hint in MEME_HINTS:
            if hint in c:
                return "meme"
    return "utility"


def fetch_coingecko_trending() -> tuple[list[tuple[str, dict[str, Any]]], dict[str, int]]:
    """
    Returns list of (coin_id, item_payload) preserving API order,
    plus coin_id -> 1-based trending rank for coins on the trending list (not nft/exchange buckets).
    """
    data = requests_get_json(f"{COINGECKO_ROOT}/search/trending")
    trending_ids: dict[str, int] = {}
    rows: list[tuple[str, dict[str, Any]]] = []
    rank = 0
    for entry in data.get("coins") or []:
        item = (entry.get("item") or {}) if isinstance(entry, dict) else {}
        cid = (item.get("id") or "").strip()
        if not cid:
            continue
        rank += 1
        trending_ids[cid] = rank
        rows.append((cid, item))
    return rows, trending_ids


def fetch_coingecko_markets(
    *,
    per_page: int = MAX_MARKETS_ROWS,
    coin_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "vs_currency": "usd",
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    if coin_ids:
        chunk = ",".join(coin_ids[:250])
        params["ids"] = chunk
        params["per_page"] = min(len(coin_ids), 250)
        params["page"] = 1
    else:
        params["order"] = "volume_desc"
        params["per_page"] = per_page
        params["page"] = 1
    return requests_get_json(f"{COINGECKO_ROOT}/coins/markets", params=params)


def fetch_binance_usdt_volumes() -> dict[str, float]:
    """
    Map base asset (uppercase) -> quote volume in USDT (float) for USDT pairs.
    """
    try:
        raw = requests_get_json(BINANCE_TICKER_24H, retries=3)
    except Exception:
        return {}
    if not isinstance(raw, list):
        return {}
    out: dict[str, float] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "")
        if not sym.endswith("USDT"):
            continue
        base = sym[: -len("USDT")]
        try:
            qv = float(row.get("quoteVolume") or 0)
        except (TypeError, ValueError):
            continue
        if base:
            out[base.upper()] = qv
    return out


def fetch_coin_categories(coin_id: str) -> tuple[list[str], str | None]:
    """
    Returns (categories_list, warning_or_none).
    Uses shared requests_get_json (429 + retries + JSON decode recovery).
    """
    try:
        d = requests_get_json(
            f"{COINGECKO_ROOT}/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
            retries=3,
            timeout_s=REQUEST_TIMEOUT_S,
        )
    except Exception as e:
        return [], f"category_fetch_failed: {e}"
    if not isinstance(d, dict):
        return [], "category_fetch_failed: invalid_json_shape"
    cats = list(d.get("categories") or [])
    cleaned = [c for c in cats if isinstance(c, str) and c.strip()]
    return cleaned, None


def fetch_categories_bulk(
    coin_ids: list[str],
    *,
    max_workers: int,
) -> dict[str, tuple[list[str], str | None]]:
    """Sequential + gap when workers==1 (free-tier friendly). Optional parallel pool if workers>1."""
    if not coin_ids:
        return {}
    if max_workers <= 1:
        out_sq: dict[str, tuple[list[str], str | None]] = {}
        for i, cid in enumerate(coin_ids):
            out_sq[cid] = fetch_coin_categories(cid)
            if i + 1 < len(coin_ids):
                time.sleep(CATEGORY_REQUEST_GAP_S)
        return out_sq
    workers = max(2, min(max_workers, len(coin_ids), 8))
    out: dict[str, tuple[list[str], str | None]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(fetch_coin_categories, cid): cid for cid in coin_ids}
        for fut in as_completed(fut_map):
            cid = fut_map[fut]
            try:
                out[cid] = fut.result()
            except Exception as e:
                out[cid] = ([], f"category_fetch_failed: {e}")
    for cid in coin_ids:
        out.setdefault(cid, ([], "category_fetch_failed: missing"))
    return out


def build_merged_ids(
    top_n: int,
    trending_ordered: list[tuple[str, dict[str, Any]]],
    markets: list[dict[str, Any]],
) -> list[str]:
    """
    Ordered ids: trending-first (preserve order), then volume markets fill.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for cid, _ in trending_ordered:
        if cid not in seen:
            ordered.append(cid)
            seen.add(cid)
    # fill from markets
    for row in markets:
        cid = row.get("id")
        if not isinstance(cid, str) or not cid:
            continue
        if cid in seen:
            continue
        ordered.append(cid)
        seen.add(cid)
        if len(ordered) >= top_n:
            break
    return ordered[:top_n]


def scrape(
    *,
    top_n: int,
    binance_crosscheck: bool,
    category_workers: int,
) -> dict[str, Any]:
    trending_rows, trending_ranks = fetch_coingecko_trending()
    markets_raw = fetch_coingecko_markets()
    markets_by_id = {row["id"]: row for row in markets_raw if isinstance(row, dict) and row.get("id")}

    merged_ids = build_merged_ids(top_n, trending_rows, markets_raw)
    missing_mkt = [cid for cid in merged_ids if cid not in markets_by_id]
    if missing_mkt:
        extra = fetch_coingecko_markets(coin_ids=missing_mkt)
        for row in extra:
            if isinstance(row, dict) and row.get("id"):
                markets_by_id[row["id"]] = row

    trending_coin_ids = {t[0] for t in trending_rows}
    trending_item_by_id = {cid: item for cid, item in trending_rows}

    binance_map: dict[str, float] = fetch_binance_usdt_volumes() if binance_crosscheck else {}

    cat_by_id = fetch_categories_bulk(merged_ids, max_workers=category_workers)

    coins_out: list[dict[str, Any]] = []
    for cid in merged_ids:
        row = markets_by_id.get(cid, {})
        trend_item = trending_item_by_id.get(cid) or {}
        sym = ((row.get("symbol") if row else None) or trend_item.get("symbol") or "")
        sym = str(sym).lower()
        name = (row.get("name") if row else None) or trend_item.get("name") or cid

        mcap = row.get("market_cap")
        vol = row.get("total_volume")
        price = row.get("current_price")
        chg = row.get("price_change_percentage_24h")

        if not row:
            # minimal row for trending coin not in first markets page — still fetch categories
            row = {"id": cid, "symbol": sym, "name": name}

        categories, cat_warn = cat_by_id.get(cid, ([], None))

        is_trending = cid in trending_coin_ids
        trending_rank_val = trending_ranks.get(cid) if is_trending else None

        base_upper = sym.upper()
        bv = binance_map.get(base_upper)

        coin_obj: dict[str, Any] = {
            "id": cid,
            "symbol": sym,
            "name": name or cid,
            "market_cap_usd": mcap,
            "volume_24h_usd": vol,
            "price_usd": price,
            "price_change_24h_pct": chg,
            "sector_category": classify_sector(categories),
            "categories": categories,
            "trending": is_trending,
            "trending_rank": trending_rank_val,
        }
        if cat_warn:
            coin_obj["category_warnings"] = [cat_warn]
        if bv is not None:
            coin_obj["binance_quote_volume_24h_usdt"] = bv
        coins_out.append(coin_obj)

    payload: dict[str, Any] = {
        "generated_at": iso_now(),
        "category_fetch_workers": category_workers,
        "category_request_gap_s": CATEGORY_REQUEST_GAP_S if category_workers <= 1 else None,
        "merge_policy": (
            "Union: CoinGecko /search/trending order first, "
            "then CoinGecko /coins/markets (volume_desc) until "
            f"{top_n} unique coin ids."
        ),
        "sources": {
            "coingecko": [
                "/search/trending",
                "/coins/markets",
                "/coins/{id} (categories only)",
            ],
            "binance": [BINANCE_TICKER_24H] if binance_crosscheck else [],
        },
        "coin_count": len(coins_out),
        "coins": coins_out,
    }
    return payload


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    stable, stamped = write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="crypto_top50_",
    )
    return stable, stamped


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="ATLAS crypto top snapshot -> data_cache JSON")
    p.add_argument("--top", type=int, default=TOP_DEFAULT, help="number of coins (default 50)")
    p.add_argument("--no-binance", action="store_true", help="skip Binance quoteVolume cross-check")
    p.add_argument(
        "--category-workers",
        type=int,
        default=DEFAULT_CATEGORY_WORKERS,
        help="parallelism for CoinGecko /coins/{id} category fetches (default 1 = sequential + gap; 2–8 = thread pool)",
    )
    args = p.parse_args(argv)

    if args.top < 1 or args.top > MAX_MARKETS_ROWS:
        print(f"--top must be 1..{MAX_MARKETS_ROWS}", file=sys.stderr)
        return 2

    try:
        payload = scrape(
            top_n=args.top,
            binance_crosscheck=not args.no_binance,
            category_workers=max(1, min(args.category_workers, 8)),
        )
        stable, stamped = write_outputs(payload)
        print(f"Wrote {stable}")
        print(f"Wrote {stamped}")
        print(f"coins={payload['coin_count']} generated_at={payload['generated_at']}")
        return 0
    except Exception as e:
        print(f"crypto_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
