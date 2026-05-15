#!/usr/bin/env python3
"""
atlas_omega.py — ATLAS Omega Universal Financial Intelligence Agent
======================================================================
Code fetches structured data in parallel; one Gemini call synthesizes JSON.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Module-level executor (reused across requests, not re-created per call) ──
_IO_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=8, thread_name_prefix="atlas_cache_io"
)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from gemini_limiter import GEMINI_HTTP_TIMEOUT_MS, wait_for_slot

from atlas_options_parse import extract_options_values_from_text

load_dotenv()
log = logging.getLogger(__name__)


def _omega_json_loads(raw: str) -> Any:
    """Gemini JSON mode may include illegal control chars — strip before json.loads."""
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
        if cleaned != s:
            return json.loads(cleaned)
        raise


KNOWN_LARGE_COMPANIES: frozenset[str] = frozenset({
    "blackrock", "apple", "microsoft", "google", "amazon",
    "tesla", "jpmorgan", "goldman sachs", "morgan stanley",
    "berkshire", "warren buffett", "vanguard", "fidelity",
    "citadel", "bridgewater", "sequoia", "softbank",
})

# ETFs / index proxies: market + news only; SEC filings omitted to save latency
_OMEGA_ETF_SYMBOLS: frozenset[str] = frozenset(
    {
        "SPY", "QQQ", "IWM", "VTI", "VOO", "IJH", "VB", "SMH", "SOXX", "BOTZ",
        "XLK", "XLE", "XLF", "GLD", "TLT", "HYG", "ARKK", "DIA", "IBB", "XBI",
    }
)

# Broad / thematic research: user wants ideas, allocation, or “where to put $X” —
# fetch a *pack* of symbols so the model can compare names using real numbers.
_DISCOVERY_RE = re.compile(
    r"\b("
    r"best\s+stock|best\s+stocks|stock\s+pick|stock\s+idea|stocks\s+to|stocks?\s+for|"
    r"where\s+to\s+invest|invest\s+my|invest\s+\$|put\s+\$|allocate|portfolio|thematic|screen|discover|"
    r"what\s+should\s+i\s+buy|recommend.*stock|growth\s+stock|dividend|"
    r"how\s+to\s+invest|small\s+account|retail\s+invest"
    r")\b",
    re.I,
)


def _is_discovery_or_allocation_query(q: str) -> bool:
    ql = q.strip().lower()
    if _DISCOVERY_RE.search(ql):
        return True
    if re.search(r"\$[\d,]+", ql) and re.search(
        r"\b(invest|investing|buy|allocate|put|deploy|grow)\b", ql
    ):
        return True
    if re.search(r"\$[\d,]+", ql) and "stock" in ql:
        return True
    return False


def _parse_budget_from_query(q: str) -> float:
    m = re.search(r"\$[\d,]+(?:\.\d{2})?", q)
    if m:
        try:
            return float(m.group(0).replace("$", "").replace(",", ""))
        except ValueError:
            pass
    return 1000.0


def _thematic_symbols_for_query(query: str) -> list[str]:
    """
    Ordered watchlist: benchmarks + theme names (yfinance).
    For discovery/allocation: try stock_universe progressive scan (Finviz + filters);
    on failure, use curated fallbacks.
    """
    ql = query.lower()
    out: list[str] = []

    def add(sym: str) -> None:
        s = sym.upper().strip()
        if s and s not in out:
            out.append(s)

    if _is_discovery_or_allocation_query(query):
        try:
            import stock_universe as su

            budget = _parse_budget_from_query(query)
            params = su.omega_discovery_to_scan_params(query, dollar_amount=budget)
            scan = su.run_progressive_scan(
                theme=params["theme"],
                budget=params.get("budget", budget),
                price_min=params["price_min"],
                price_max=params["price_max"],
                universe_size=params["universe_size"],
                pass3_candidates=params["pass3_candidates"],
                top_n=params["top_n"],
                skip_deep_rank=True,
                verbose=False,
            )
            if scan.get("error"):
                raise RuntimeError(scan["error"])
            candidates = (
                scan.get("pass3_candidates")
                or scan.get("pass3_top")
                or scan.get("final_recommendations")
                or []
            )
            for c in candidates[:12]:
                if isinstance(c, dict) and c.get("ticker"):
                    add(str(c["ticker"]))
            if out:
                for s in ("SPY", "QQQ", "IWM"):
                    add(s)
                log.info(
                    "[omega] stock_universe → %d symbols (theme=%s)",
                    len(out),
                    params.get("theme"),
                )
                return out[:15]
        except Exception as e:
            log.warning("[omega] stock_universe scan failed, using fallback: %s", e)

    for s in ("SPY", "QQQ", "IWM"):
        add(s)

    if any(k in ql for k in ("ai", "artificial intelligence", "machine learning", "llm")):
        for s in ("SMH", "BOTZ", "NVDA", "AMD", "PLTR", "MSFT", "GOOGL", "SOUN", "IONQ"):
            add(s)
    if "semi" in ql or "chip" in ql:
        for s in ("SMH", "SOXX", "NVDA", "AMD", "AVGO"):
            add(s)
    if "energy" in ql or "oil" in ql:
        for s in ("XLE", "XOM", "CVX"):
            add(s)
    if "small" in ql or "mid cap" in ql or "mid-cap" in ql:
        for s in ("IWM", "VB", "IJH"):
            add(s)
    if "bio" in ql or "biotech" in ql:
        for s in ("IBB", "XBI", "MRNA", "BNTX"):
            add(s)
    if "bank" in ql or "financial" in ql:
        for s in ("XLF", "JPM"):
            add(s)
    if "squeeze" in ql or "short" in ql:
        for s in ("GME", "AMC", "MARA", "RIOT", "SOUN"):
            add(s)
    if "penny" in ql or "cheap" in ql:
        for s in ("SOUN", "GFAI", "BBAI", "MULN", "NKLA"):
            add(s)
    if len(out) <= 3:
        for s in ("VTI", "XLK"):
            add(s)

    return out[:12]


def _fetch_market_regime_light() -> dict:
    try:
        import market_scanner as ms

        return ms.get_market_regime()
    except Exception as e:
        return {"error": str(e), "regime": "UNKNOWN"}


DC_INTENT_CRYPTO = "CRYPTO_MARKET_SCAN"
DC_INTENT_EQUITIES = "EQUITIES_MARKET_SCAN"
DC_INTENT_OPTIONS_FLOW = "OPTIONS_FLOW_MARKET_SCAN"
DC_INTENT_INSIDER = "INSIDER_TRADES_MARKET_SCAN"
DC_INTENT_BOND_YIELDS = "TREASURY_YIELD_MARKET_SCAN"
DC_INTENT_CPI = "CPI_INFLATION_MARKET_SCAN"
DC_INTENT_FED_WATCH = "FED_WATCH_MARKET_SCAN"
DC_INTENT_WATCHES = "WATCH_MARKET_SCAN"
DC_INTENT_DARK_POOL = "DARK_POOL_MARKET_SCAN"
DC_INTENT_SECTOR_ROTATION = "SECTOR_ROTATION_MARKET_SCAN"
DC_INTENT_GLOBAL_LIQUIDITY = "GLOBAL_LIQUIDITY_MARKET_SCAN"
DC_INTENT_EARNINGS = "EARNINGS_MARKET_SCAN"
DC_INTENT_FOREX = "FOREX_MARKET_SCAN"
DC_INTENT_COMMODITIES = "COMMODITIES_MARKET_SCAN"
DC_INTENT_SUPPLY_CHAIN = "SUPPLY_CHAIN_MARKET_SCAN"
DC_INTENT_ENERGY = "ENERGY_MARKET_SCAN"
DC_INTENT_CLIMATE_RISK = "CLIMATE_RISK_MARKET_SCAN"
DC_INTENT_TARIFFS = "TARIFFS_MARKET_SCAN"
DC_INTENT_JOBS = "JOBS_MARKET_SCAN"
DC_INTENT_CONGRESS_TRADES = "CONGRESS_TRADES_MARKET_SCAN"

# Phase-2 extended intents (Tasks 4-12)
DC_INTENT_DARK_POOL_SCAN = "DARK_POOL_SCAN"
DC_INTENT_PENNY_STOCK_SCAN = "PENNY_STOCK_SCAN"
DC_INTENT_REAL_ESTATE_SCAN = "REAL_ESTATE_SCAN"
DC_INTENT_PERSONAL_WEALTH_SCAN = "PERSONAL_WEALTH_SCAN"
DC_INTENT_TAX_LEGAL_SCAN = "TAX_LEGAL_SCAN"
DC_INTENT_BUSINESS_SCAN = "BUSINESS_SCAN"
DC_INTENT_ALTERNATIVE_ASSET_SCAN = "ALTERNATIVE_ASSET_SCAN"
DC_INTENT_GLOBAL_LIQUIDITY_SCAN = "GLOBAL_LIQUIDITY_SCAN"
DC_INTENT_GROWTH_MARKETING_SCAN = "GROWTH_MARKETING_SCAN"
DC_INTENT_INTELLIGENCE_SYNTHESIS = "INTELLIGENCE_SYNTHESIS"
DC_INTENT_SECTOR_ROTATION_SCAN = "SECTOR_ROTATION_SCAN"
DC_INTENT_SENTIMENT_DIVERGENCE_SCAN = "SENTIMENT_DIVERGENCE_SCAN"
DC_INTENT_MACRO_RISK_SCAN = "MACRO_RISK_SCAN"

DATA_CACHE_MACRO_ONLY_INTENTS: frozenset[str] = frozenset(
    {
        DC_INTENT_CRYPTO,
        DC_INTENT_EQUITIES,
        DC_INTENT_OPTIONS_FLOW,
        DC_INTENT_INSIDER,
        DC_INTENT_BOND_YIELDS,
        DC_INTENT_CPI,
        DC_INTENT_FED_WATCH,
        DC_INTENT_WATCHES,
        DC_INTENT_DARK_POOL,
        DC_INTENT_SECTOR_ROTATION,
        DC_INTENT_GLOBAL_LIQUIDITY,
        DC_INTENT_EARNINGS,
        DC_INTENT_FOREX,
        DC_INTENT_COMMODITIES,
        DC_INTENT_SUPPLY_CHAIN,
        DC_INTENT_ENERGY,
        DC_INTENT_CLIMATE_RISK,
        DC_INTENT_TARIFFS,
        DC_INTENT_JOBS,
        DC_INTENT_CONGRESS_TRADES,
        # Phase-2 extended
        DC_INTENT_DARK_POOL_SCAN,
        DC_INTENT_PENNY_STOCK_SCAN,
        DC_INTENT_REAL_ESTATE_SCAN,
        DC_INTENT_PERSONAL_WEALTH_SCAN,
        DC_INTENT_TAX_LEGAL_SCAN,
        DC_INTENT_BUSINESS_SCAN,
        DC_INTENT_ALTERNATIVE_ASSET_SCAN,
        DC_INTENT_GLOBAL_LIQUIDITY_SCAN,
        DC_INTENT_GROWTH_MARKETING_SCAN,
        DC_INTENT_INTELLIGENCE_SYNTHESIS,
        DC_INTENT_SECTOR_ROTATION_SCAN,
        DC_INTENT_SENTIMENT_DIVERGENCE_SCAN,
        DC_INTENT_MACRO_RISK_SCAN,
    }
)


def _data_cache_root() -> Path:
    env = (os.environ.get("ATLAS_DATA_CACHE_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data_cache"


def _compact_crypto_cache(obj: dict, n: int = 25) -> dict:
    coins = obj.get("coins") if isinstance(obj.get("coins"), list) else []
    keys = (
        "symbol",
        "name",
        "price_usd",
        "price_change_24h_pct",
        "volume_24h_usd",
        "market_cap_usd",
        "sector_category",
        "trending",
        "trending_rank",
    )
    top: list[dict[str, Any]] = []
    for c in coins[:n]:
        if not isinstance(c, dict):
            continue
        top.append({k: c.get(k) for k in keys})
    return {
        "snapshot": "crypto_top50",
        "generated_at": obj.get("generated_at"),
        "merge_policy": obj.get("merge_policy"),
        "coin_count": obj.get("coin_count"),
        "top_coins": top,
    }


def _compact_equities_cache(obj: dict, per: int = 10) -> dict:
    keys = (
        "rank",
        "ticker",
        "name",
        "exchange",
        "price",
        "change",
        "change_pct",
        "volume",
        "avg_volume_3m",
        "market_cap",
        "signal",
    )

    def slice_list(key: str) -> list[dict[str, Any]]:
        block = obj.get(key)
        if not isinstance(block, list):
            return []
        out: list[dict[str, Any]] = []
        for row in block[:per]:
            if not isinstance(row, dict):
                continue
            out.append({k: row.get(k) for k in keys})
        return out

    ma_src = obj.get("most_active")
    if not isinstance(ma_src, list):
        ma_src = obj.get("most_actives")
    most_active: list[dict[str, Any]] = []
    if isinstance(ma_src, list):
        for row in ma_src[:per]:
            if not isinstance(row, dict):
                continue
            most_active.append({k: row.get(k) for k in keys})

    return {
        "snapshot": "equities_screener",
        "generated_at": obj.get("generated_at"),
        "source": obj.get("source"),
        "record_count": obj.get("record_count"),
        "gainers": slice_list("gainers"),
        "losers": slice_list("losers"),
        "active": most_active,
    }


def _compact_watches_cache(obj: dict, n: int = 12) -> dict[str, Any]:
    models_in = obj.get("models") if isinstance(obj.get("models"), list) else []
    keys = (
        "brand",
        "model",
        "reference",
        "avg_price",
        "retail_price",
        "premium_over_retail_pct",
        "trend",
        "listings_count",
    )
    models: list[dict[str, Any]] = []
    for row in models_in[:n]:
        if isinstance(row, dict):
            models.append({k: row.get(k) for k in keys})
    return {
        "snapshot": "luxury_watch_market",
        "generated_at": obj.get("generated_at"),
        "record_count": obj.get("record_count"),
        "models": models,
    }


def _compact_options_flow(obj: dict, n: int = 20) -> dict[str, Any]:
    rows_in = obj.get("unusual_activity") if isinstance(obj.get("unusual_activity"), list) else []
    keys = ("ticker", "expiry", "strike", "type", "volume", "open_interest", "volume_oi_ratio", "signal")
    clipped: list[dict[str, Any]] = []
    for r in rows_in[:n]:
        if isinstance(r, dict):
            clipped.append({k: r.get(k) for k in keys})
    snap: dict[str, Any] = {
        "snapshot": "options_flow",
        "generated_at": obj.get("generated_at"),
        "source": obj.get("source"),
        "record_count": obj.get("record_count"),
        "unusual_activity": clipped,
    }
    wm = obj.get("_meta") if isinstance(obj.get("_meta"), dict) else None
    if wm:
        snap["_meta"] = wm
    return snap


def _compact_insider_trades(obj: dict, n: int = 25) -> dict[str, Any]:
    rows_in = obj.get("filings") if isinstance(obj.get("filings"), list) else []
    keys = (
        "ticker",
        "company_name",
        "insider_name",
        "role",
        "transaction_type",
        "shares",
        "price",
        "date",
        "signal",
    )
    clipped: list[dict[str, Any]] = []
    for r in rows_in[:n]:
        if isinstance(r, dict):
            clipped.append({k: r.get(k) for k in keys})
    out: dict[str, Any] = {
        "snapshot": "sec_form4_filings",
        "generated_at": obj.get("generated_at"),
        "source": obj.get("source"),
        "record_count": len(clipped),
        "filings": clipped,
    }
    wm = obj.get("_meta") if isinstance(obj.get("_meta"), dict) else None
    if wm:
        out["_meta"] = wm
    return out


def _compact_bond_yields(obj: dict, n: int = 14) -> dict[str, Any]:
    ys = obj.get("yields") if isinstance(obj.get("yields"), list) else []
    rows: list[dict[str, Any]] = []
    for r in ys[:n]:
        if isinstance(r, dict):
            rows.append({"maturity": r.get("maturity"), "rate": r.get("rate"), "date": r.get("date")})
    snap: dict[str, Any] = {
        "snapshot": "treasury_yield_curve",
        "generated_at": obj.get("generated_at"),
        "record_date": obj.get("record_date"),
        "curve_signal": obj.get("curve_signal"),
        "spread_2y_10y": obj.get("spread_2y_10y"),
        "record_count": obj.get("record_count"),
        "yields": rows,
        "source": obj.get("source"),
    }
    wm = obj.get("_meta") if isinstance(obj.get("_meta"), dict) else None
    if wm:
        snap["_meta"] = wm
    return snap


def _compact_cpi(obj: dict) -> dict[str, Any]:
    cats = obj.get("categories") if isinstance(obj.get("categories"), list) else []
    clipped: list[dict[str, Any]] = []
    for c in cats[:8]:
        if isinstance(c, dict):
            clipped.append(
                {
                    "name": c.get("name"),
                    "yoy_change_pct": c.get("yoy_change_pct"),
                    "contribution": c.get("contribution"),
                }
            )
    return {
        "snapshot": "bls_cpi",
        "generated_at": obj.get("generated_at"),
        "period": obj.get("period"),
        "cpi_index": obj.get("cpi_index"),
        "mom_change_pct": obj.get("mom_change_pct"),
        "yoy_change_pct": obj.get("yoy_change_pct"),
        "core_cpi_yoy_pct": obj.get("core_cpi_yoy_pct"),
        "inflation_signal": obj.get("inflation_signal"),
        "record_count": obj.get("record_count"),
        "categories": clipped,
        "source": obj.get("source"),
    }


def _compact_fed_watch(obj: dict) -> dict[str, Any]:
    probs = obj.get("probabilities") if isinstance(obj.get("probabilities"), list) else []
    rows: list[dict[str, Any]] = []
    for p in probs[:8]:
        if isinstance(p, dict):
            rows.append({"action": p.get("action"), "probability_pct": p.get("probability_pct")})
    snap: dict[str, Any] = {
        "snapshot": "fed_watch_probabilities",
        "generated_at": obj.get("generated_at"),
        "current_rate": obj.get("current_rate"),
        "next_meeting_date": obj.get("next_meeting_date"),
        "dominant_action": obj.get("dominant_action"),
        "dominant_probability_pct": obj.get("dominant_probability_pct"),
        "probabilities": rows,
        "source": obj.get("source"),
    }
    wm = obj.get("_meta") if isinstance(obj.get("_meta"), dict) else None
    if wm:
        snap["_meta"] = wm
    return snap


def _read_data_cache_json(filename: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """
    Read a single JSON cache file with bulletproof error handling.

    Never raises — always returns (None, meta_with_error) on any failure so the
    caller receives a graceful warning string instead of a server crash.

    Failure modes handled:
      * File missing            -> error="missing_file:<path>"
      * File unreadable (perms) -> error="read_error:<OSError>"
      * Invalid UTF-8           -> error="encoding_error:<details>"
      * Truncated / bad JSON    -> error="json_parse_error:<details>"
      * JSON is not a dict      -> error="invalid_json_shape"
      * Any other exception     -> error="unexpected_error:<details>"
    """
    meta: dict[str, Any] = {"file": filename, "loaded": False, "error": None}
    path = _data_cache_root() / filename
    if not path.is_file():
        meta["error"] = f"missing_file:{path}"
        return None, meta
    try:
        raw_text: str = path.read_text(encoding="utf-8")
    except OSError as e:
        meta["error"] = f"read_error:{e}"
        return None, meta
    except UnicodeDecodeError as e:
        meta["error"] = f"encoding_error:{e}"
        return None, meta
    try:
        raw_obj: Any = json.loads(raw_text)
    except json.JSONDecodeError as e:
        meta["error"] = f"json_parse_error:{e}"
        return None, meta
    except Exception as e:
        meta["error"] = f"unexpected_parse_error:{e}"
        return None, meta
    if not isinstance(raw_obj, dict):
        meta["error"] = "invalid_json_shape"
        return None, meta
    meta["loaded"] = True
    return raw_obj, meta


def _graceful_cache_warning(filename: str, error: str) -> str:
    """
    Return a human-readable warning string to inject into the LLM context when
    a cache file is unavailable. The LLM sees this instead of the server crashing.
    """
    return (
        f"[DATA_CACHE_WARNING] {filename} could not be loaded ({error}). "
        "This data is temporarily unavailable — proceed with analysis using other available data."
    )


def _summary_filename_for_cache(filename: str) -> str:
    if filename.endswith("_latest.json"):
        return filename.replace("_latest.json", "_summary.json")
    return filename.replace(".json", "_summary.json")


def _summary_snapshot_for_intent(intent: str) -> str:
    return {
        DC_INTENT_CRYPTO: "crypto_top50",
        DC_INTENT_EQUITIES: "equities_screener",
        DC_INTENT_OPTIONS_FLOW: "options_flow",
        DC_INTENT_INSIDER: "sec_form4_filings",
        DC_INTENT_BOND_YIELDS: "bond_yields",
        DC_INTENT_CPI: "bls_cpi",
        DC_INTENT_FED_WATCH: "fed_watch_probabilities",
        DC_INTENT_WATCHES: "luxury_watch_market",
        DC_INTENT_DARK_POOL: "dark_pool_prints",
        DC_INTENT_SECTOR_ROTATION: "sector_rotation",
        DC_INTENT_GLOBAL_LIQUIDITY: "global_liquidity",
        DC_INTENT_EARNINGS: "earnings_calendar",
        DC_INTENT_FOREX: "forex_rates",
        DC_INTENT_COMMODITIES: "commodities",
        DC_INTENT_SUPPLY_CHAIN: "supply_chain",
        DC_INTENT_ENERGY: "energy_grid",
        DC_INTENT_CLIMATE_RISK: "climate_risk",
        DC_INTENT_TARIFFS: "tariffs",
        DC_INTENT_JOBS: "jobs",
        DC_INTENT_CONGRESS_TRADES: "congress_trades",
    }.get(intent, intent)


def _load_cache_files_parallel(
    filenames: list[str],
) -> dict[str, tuple[Optional[dict[str, Any]], dict[str, Any]]]:
    """
    Load multiple cache JSON files in parallel using the module-level thread pool.
    Returns {filename: (raw_obj_or_None, meta_dict)}.

    Uses the shared _IO_EXECUTOR (not a per-call ThreadPoolExecutor) to avoid
    thread-spawn overhead on every request. Timeout of 5s prevents indefinite hangs.
    """
    results: dict[str, tuple[Optional[dict[str, Any]], dict[str, Any]]] = {}
    futures = {
        _IO_EXECUTOR.submit(_read_data_cache_json, fname): fname
        for fname in filenames
    }
    for future in as_completed(futures, timeout=5):
        fname = futures[future]
        try:
            results[fname] = future.result()
        except Exception as exc:
            results[fname] = (None, {"file": fname, "loaded": False, "error": str(exc)})
    return results


def load_equities_payload() -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Read and compact data_cache/equities_latest.json for Omega prompt context."""
    raw, meta = _read_data_cache_json("equities_latest.json")
    if raw is None:
        return None, meta
    compact = _compact_equities_cache(raw)
    meta["asset_rows"] = _ik_row_count(compact)
    return compact, meta


def load_options_flow_payload() -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Read and compact data_cache/options_flow_latest.json for Omega prompt context."""
    raw, meta = _read_data_cache_json("options_flow_latest.json")
    if raw is None:
        return None, meta
    compact = _compact_options_flow(raw)
    meta["asset_rows"] = _ik_row_count(compact)
    return compact, meta


def load_insider_payload() -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    """Read and compact data_cache/insider_trades_latest.json for Omega prompt context."""
    raw, meta = _read_data_cache_json("insider_trades_latest.json")
    if raw is None:
        return None, meta
    compact = _compact_insider_trades(raw)
    meta["asset_rows"] = _ik_row_count(compact)
    return compact, meta


def _rows_matching_tickers(rows: Any, tickers: set[str]) -> list[dict[str, Any]]:
    if not tickers or not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper().strip()
        if ticker in tickers:
            out.append(row)
    return out


def _extract_ticker_set(ctx: "UserContext", query: str) -> set[str]:
    tickers: set[str] = {str(t).upper().strip() for t in (getattr(ctx, "tickers", []) or []) if str(t).strip()}
    for m in re.finditer(r"\b[A-Z]{1,5}\b", query or ""):
        sym = m.group(0).upper()
        if sym not in _OMEGA_ETF_SYMBOLS and sym not in {"CEO", "CFO", "SEC", "IRS", "USA", "USD"}:
            tickers.add(sym)
    return tickers


def build_market_intelligence_context(
    query: str,
    ctx: "UserContext",
    *,
    include_full: bool = False,
) -> dict[str, Any]:
    """
    Load D2/D3/D4 snapshots for Omega.

    For market-wide cache routes, include compact full snapshots. For specific ticker
    prompts, include only matching options/insider/equities rows so the prompt stays small.
    """
    tickers = _extract_ticker_set(ctx, query)
    payload: dict[str, Any] = {
        "snapshot": "d2_d3_d4_market_intelligence",
        "tickers_checked": sorted(tickers),
        "sources": {},
        "ticker_slices": {},
    }

    equities, eq_meta = load_equities_payload()
    options, opt_meta = load_options_flow_payload()
    insiders, ins_meta = load_insider_payload()
    payload["sources"] = {
        "equities": eq_meta,
        "options_flow": opt_meta,
        "insider_trades": ins_meta,
    }

    if include_full:
        payload["equities"] = equities or {"status": "No equities cache data available."}
        payload["options_flow"] = options or {"status": "No options flow cache data available."}
        payload["insider_trades"] = insiders or {"status": "No insider trades cache data available."}

    if tickers:
        eq_rows: list[dict[str, Any]] = []
        if isinstance(equities, dict):
            for key in ("gainers", "losers", "active", "most_active"):
                eq_rows.extend(_rows_matching_tickers(equities.get(key), tickers))
        opt_rows = _rows_matching_tickers(options.get("unusual_activity") if isinstance(options, dict) else [], tickers)
        ins_rows = _rows_matching_tickers(insiders.get("filings") if isinstance(insiders, dict) else [], tickers)
        payload["ticker_slices"] = {
            "equities": eq_rows,
            "options_flow": opt_rows,
            "insider_trades": ins_rows,
        }

    return payload


def _ik_row_count(compact: dict[str, Any]) -> int:
    for k in (
        "top_coins",
        "gainers",
        "active",
        "most_active",
        "models",
        "unusual_activity",
        "filings",
        "yields",
        "categories",
        "probabilities",
        "upcoming",
        "pairs",
        "commodities",
        "indices",
        "breakdown",
        "flood_zone_changes",
        "active_tariffs",
        "sector_breakdown",
        "trades",
    ):
        block = compact.get(k)
        if isinstance(block, list):
            return len(block)
    return int(compact.get("record_count") or 0)


def _compact_dark_pool(obj: dict) -> dict:
    """Compact dark_pool_latest.json for Omega context."""
    signals = obj.get("signals") or []
    return {
        "snapshot": "dark_pool_activity",
        "week_of": obj.get("week_of"),
        "source": obj.get("source"),
        "record_count": obj.get("record_count", 0),
        "signals": signals[:20],  # top 20 for context window
    }


def _compact_sector_rotation(obj: dict) -> dict:
    """Compact sector_rotation_latest.json for Omega context."""
    return {
        "snapshot": "sector_rotation",
        "source": obj.get("source"),
        "leading_sectors": obj.get("leading_sectors", []),
        "lagging_sectors": obj.get("lagging_sectors", []),
        "record_count": obj.get("record_count", 0),
        "sectors": obj.get("sectors", []),
    }


def _compact_global_liquidity(obj: dict) -> dict:
    """Compact global_liquidity_latest.json for Omega context."""
    return {
        "snapshot": "global_m2_liquidity",
        "period": obj.get("period"),
        "m2_trillions_usd": obj.get("m2_trillions_usd"),
        "yoy_change_pct": obj.get("yoy_change_pct"),
        "liquidity_regime": obj.get("liquidity_regime"),
        "source": obj.get("source"),
    }


def _compact_generic_cache(obj: dict, *, snapshot: str, list_key: str | None = None, limit: int = 20) -> dict:
    out = {
        "snapshot": snapshot,
        "generated_at": obj.get("generated_at"),
        "source": obj.get("source") or obj.get("data_source"),
        "record_count": obj.get("record_count", 0),
    }
    for key in (
        "global_trend",
        "grid_trend",
        "national_flood_risk_trend",
        "active_count",
        "escalating_count",
        "labor_market_signal",
        "unemployment_rate",
        "jobs_added_thousands",
        "dxy_proxy",
        "renewables_pct_grid",
        "electricity_avg_kwh_cents",
        "gas_national_avg_gallon",
        "most_traded_ticker",
        "late_disclosure_count",
    ):
        if key in obj:
            out[key] = obj.get(key)
    if list_key and isinstance(obj.get(list_key), list):
        out[list_key] = obj[list_key][:limit]
    return out


def _compact_dark_pool_scan(obj: dict) -> dict:
    """D8: dark_pool_latest.json → top_tickers, ratio_signals, date."""
    top = obj.get("top_tickers") or obj.get("tickers") or []
    if isinstance(top, list):
        top = top[:20]
    return {
        "snapshot": "dark_pool_scan",
        "date": obj.get("date") or obj.get("generated_at"),
        "top_tickers": top,
        "ratio_signals": obj.get("ratio_signals") or obj.get("signals"),
        "total_volume": obj.get("total_volume"),
        "notable_prints": (obj.get("notable_prints") or [])[:10],
    }


def _compact_penny_stock_scan(obj: dict) -> dict:
    """D9: penny_stocks_latest.json → top_movers, volume_leaders, date."""
    movers = obj.get("top_movers") or obj.get("movers") or []
    if isinstance(movers, list):
        movers = movers[:20]
    leaders = obj.get("volume_leaders") or obj.get("leaders") or []
    if isinstance(leaders, list):
        leaders = leaders[:15]
    return {
        "snapshot": "penny_stock_scan",
        "date": obj.get("date") or obj.get("generated_at"),
        "top_movers": movers,
        "volume_leaders": leaders,
        "total_screened": obj.get("total_screened"),
    }


def _compact_real_estate_cache(files: dict) -> dict:
    """R1-R7: aggregate 7 real estate cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "real_estate_scan",
        "median_price": _get("residential", "median_price"),
        "yoy_change": _get("residential", "yoy_change"),
        "days_on_market": _get("residential", "days_on_market"),
        "avg_rent": _get("rental_yield", "avg_rent"),
        "gross_yield": _get("rental_yield", "gross_yield"),
        "str_avg_daily_rate": _get("str", "avg_daily_rate"),
        "str_occupancy_rate": _get("str", "occupancy_rate"),
        "commercial_lease_rate": _get("commercial", "avg_lease_rate"),
        "commercial_vacancy": _get("commercial", "vacancy_rate"),
        "permit_trends": _get("zoning", "permit_trends"),
        "top_reit_yields": (_get("reits", "top_yields") or _get("reits", "reits") or [])[:5],
        "mortgage_30yr": _get("mortgage_rates", "current_30yr"),
        "mortgage_15yr": _get("mortgage_rates", "current_15yr"),
        "mortgage_trend": _get("mortgage_rates", "trend"),
    }


def _compact_wealth_cache(files: dict) -> dict:
    """W1-W8: aggregate 8 wealth/debt cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "personal_wealth_scan",
        "best_hysa_apy": _get("hysa", "best_apy"),
        "best_hysa_bank": _get("hysa", "bank_name"),
        "best_cashback_card": _get("credit_cards", "best_cashback"),
        "best_travel_card": _get("credit_cards", "best_travel"),
        "auto_loan_avg_rate": _get("auto_loans", "avg_rate"),
        "auto_loan_credit_union": _get("auto_loans", "credit_union_rate"),
        "student_debt_federal_rate": _get("student_debt", "federal_rate"),
        "student_forgiveness_programs": _get("student_debt", "forgiveness_programs"),
        "ira_limit": _get("retirement_limits", "ira_limit"),
        "401k_limit": _get("retirement_limits", "401k_limit"),
        "retirement_year": _get("retirement_limits", "year"),
        "personal_loan_rate_range": _get("personal_loans", "avg_rate_range"),
        "top_affordable_cities": (_get("col", "top_affordable_cities") or [])[:5],
        "avg_grocery_index": _get("col", "avg_grocery_index"),
        "avg_auto_premium": _get("insurance", "avg_auto_premium"),
        "avg_home_premium": _get("insurance", "avg_home_premium"),
    }


def _compact_tax_legal_cache(files: dict) -> dict:
    """L1-L6: aggregate 6 tax/legal cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "tax_legal_scan",
        "tax_brackets": _get("federal_tax", "brackets"),
        "standard_deduction": _get("federal_tax", "standard_deduction"),
        "tax_year": _get("federal_tax", "year"),
        "top_low_tax_states": (_get("state_tax", "top_low_tax_states") or [])[:5],
        "special_tax_programs": _get("state_tax", "special_programs"),
        "bankruptcy_ch7_count": _get("bankruptcy", "ch7_count"),
        "bankruptcy_ch11_count": _get("bankruptcy", "ch11_count"),
        "bankruptcy_trend": _get("bankruptcy", "filing_trend"),
        "recent_sec_risk_filings": (_get("sec_filings", "recent_risk_filings") or [])[:5],
        "consumer_alerts": (_get("consumer_alerts", "top_alerts") or [])[:5],
        "consumer_alert_severity": _get("consumer_alerts", "severity_counts"),
        "federal_min_wage": _get("labor_law", "federal_min_wage"),
        "recent_labor_changes": _get("labor_law", "recent_changes"),
    }


def _compact_business_cache(files: dict) -> dict:
    """B1-B6: aggregate 6 business cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "business_scan",
        "sba_top_programs": (_get("sba", "top_programs") or [])[:5],
        "sba_max_amounts": _get("sba", "max_amounts"),
        "sba_deadlines": _get("sba", "deadlines"),
        "median_cac": _get("saas_metrics", "median_cac"),
        "median_ltv": _get("saas_metrics", "median_ltv"),
        "avg_churn": _get("saas_metrics", "avg_churn"),
        "top_ecommerce_niches": (_get("ecommerce", "top_niches") or [])[:5],
        "ecommerce_trend_scores": _get("ecommerce", "trend_scores"),
        "top_freelance_roles": (_get("freelance_rates", "top_roles") or [])[:5],
        "freelance_rate_ranges": _get("freelance_rates", "rate_ranges"),
        "top_franchises": (_get("franchise", "top_franchises") or [])[:5],
        "franchise_cost_ranges": _get("franchise", "cost_ranges"),
        "vc_hot_sectors": (_get("vc_deals", "hot_sectors") or [])[:5],
        "vc_recent_deals": (_get("vc_deals", "recent_deals") or [])[:5],
    }


def _compact_alternative_asset_cache(files: dict) -> dict:
    """A1-A5: aggregate 5 alternative asset cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "alternative_asset_scan",
        "top_watch_models": (_get("watches", "top_models") or _get("watches", "models") or [])[:5],
        "watch_avg_prices": _get("watches", "avg_prices"),
        "watch_premiums": _get("watches", "premiums"),
        "recent_art_sales": (_get("art", "recent_sales") or [])[:5],
        "top_artists": (_get("art", "top_artists") or [])[:5],
        "trending_collectibles": (_get("collectibles", "trending_items") or [])[:5],
        "collectibles_price_trends": _get("collectibles", "price_trends"),
        "p2p_avg_returns": _get("p2p", "avg_returns"),
        "p2p_default_rates": _get("p2p", "default_rates"),
        "gold_spot": _get("metals", "gold_spot"),
        "silver_spot": _get("metals", "silver_spot"),
        "metals_premiums": _get("metals", "premiums"),
    }


def _compact_global_liquidity_scan(obj: dict) -> dict:
    """M9: global_liquidity_latest.json → liquidity_trend, signal, key_drivers."""
    return {
        "snapshot": "global_liquidity_scan",
        "period": obj.get("period"),
        "m2_trillions_usd": obj.get("m2_trillions_usd"),
        "yoy_change_pct": obj.get("yoy_change_pct"),
        "liquidity_regime": obj.get("liquidity_regime"),
        "liquidity_trend": obj.get("liquidity_trend") or obj.get("trend"),
        "signal": obj.get("signal"),
        "key_drivers": obj.get("key_drivers"),
        "source": obj.get("source"),
    }


def _compact_macro_risk_scan(files: dict) -> dict:
    """Macro Risk: combines fed_watch, cpi_inflation, jobs, treasury_yield, regime_change."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "macro_risk_scan",
        "fed_rate_probability": _get("fed_watch", "next_meeting_probability") or _get("fed_watch", "rate_probability"),
        "fed_stance": _get("fed_watch", "stance") or _get("fed_watch", "policy"),
        "cpi_latest": _get("cpi_inflation", "latest_cpi") or _get("cpi_inflation", "value"),
        "cpi_trend": _get("cpi_inflation", "trend"),
        "jobs_added": _get("jobs", "nonfarm_payrolls") or _get("jobs", "jobs_added"),
        "unemployment_rate": _get("jobs", "unemployment_rate"),
        "yield_10yr": _get("treasury_yield", "ten_year") or _get("treasury_yield", "yield_10yr"),
        "yield_2yr": _get("treasury_yield", "two_year") or _get("treasury_yield", "yield_2yr"),
        "yield_curve_signal": _get("treasury_yield", "curve_signal") or _get("treasury_yield", "inversion"),
        "current_regime": _get("regime_change", "current_regime"),
        "regime_confidence": _get("regime_change", "confidence"),
        "risk_signal": _get("regime_change", "signal"),
    }


def _compact_growth_marketing_cache(files: dict) -> dict:
    """G1-G10: aggregate 10 growth/marketing cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "growth_marketing_scan",
        "top_advertisers": (_get("competitor_ads", "top_advertisers") or [])[:5],
        "ad_spend_ranges": _get("competitor_ads", "spend_ranges"),
        "trending_keywords": (_get("seo_keywords", "trending_keywords") or [])[:10],
        "keyword_volumes": _get("seo_keywords", "volumes"),
        "brand_sentiment": _get("sentiment", "brand_sentiment"),
        "trending_topics": (_get("sentiment", "trending_topics") or [])[:5],
        "email_domain_score": _get("email_health", "domain_score"),
        "email_deliverability": _get("email_health", "deliverability"),
        "avg_engagement_benchmarks": _get("engagement", "avg_engagement_benchmarks"),
        "common_complaints": (_get("reviews", "common_complaints") or [])[:5],
        "top_praise": (_get("reviews", "top_praise") or [])[:3],
        "avg_roas_by_platform": _get("roas", "avg_roas_by_platform"),
        "lead_count": _get("leads", "lead_count"),
        "lead_categories": _get("leads", "categories"),
        "crm_sync_status": _get("crm_sync", "sync_status"),
    }


def _compact_intelligence_cache(files: dict) -> dict:
    """IQ1-IQ8: aggregate 8 intelligence synthesis cache files."""
    def _get(name: str, key: str, fallback=None):
        d = files.get(name) or {}
        return d.get(key, fallback)

    return {
        "snapshot": "intelligence_synthesis",
        "top_correlations": (_get("correlation", "top_correlations") or [])[:5],
        "notable_divergences": (_get("correlation", "notable_divergences") or [])[:3],
        "current_regime": _get("regime_change", "current_regime"),
        "regime_confidence": _get("regime_change", "confidence"),
        "regime_signal": _get("regime_change", "signal"),
        "high_impact_earnings": (_get("earnings_season_brief", "high_impact_reports") or [])[:5],
        "weekly_earnings_risk": _get("earnings_season_brief", "weekly_risk"),
        "sector_rotation_thesis": _get("sector_rotation", "rotation_thesis"),
        "inflow_sectors": (_get("sector_rotation", "inflow_sectors") or [])[:5],
        "top_news_catalysts": (_get("news_catalysts", "top_impact_headlines") or [])[:5],
        "catalyst_tickers": (_get("news_catalysts", "affected_tickers") or [])[:10],
        "sentiment_divergences": (_get("sentiment_divergence", "top_divergences") or [])[:5],
        "divergence_trade_implications": _get("sentiment_divergence", "trade_implications"),
        "portfolio_risk_score": _get("risk_budget", "portfolio_risk_score"),
        "risk_alerts": (_get("risk_budget", "alerts") or [])[:5],
    }


def _compact_sector_rotation_scan(obj: dict) -> dict:
    """IQ4-specific: sector_rotation_latest.json → detailed rotation view."""
    return {
        "snapshot": "sector_rotation_scan",
        "rotation_thesis": obj.get("rotation_thesis"),
        "inflow_sectors": (obj.get("inflow_sectors") or [])[:5],
        "outflow_sectors": (obj.get("outflow_sectors") or [])[:5],
        "institutional_flows": obj.get("institutional_flows"),
        "signal_strength": obj.get("signal_strength"),
        "generated_at": obj.get("generated_at"),
    }


def _compact_sentiment_divergence_scan(obj: dict) -> dict:
    """IQ6-specific: sentiment_divergence_latest.json → divergence signals."""
    return {
        "snapshot": "sentiment_divergence_scan",
        "top_divergences": (obj.get("top_divergences") or [])[:10],
        "trade_implications": obj.get("trade_implications"),
        "retail_sentiment": obj.get("retail_sentiment"),
        "institutional_sentiment": obj.get("institutional_sentiment"),
        "generated_at": obj.get("generated_at"),
    }


def _load_internal_knowledge_payload(
    intent: str,
    *,
    prefer_raw: bool = False,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {
        "intent": intent,
        "file": "",
        "loaded": False,
        "error": None,
        "cache_layer": "raw" if prefer_raw else "summary",
        "load_path": "",
    }
    root = _data_cache_root()
    intent_files: dict[str, str] = {
        DC_INTENT_CRYPTO: "crypto_top50_latest.json",
        DC_INTENT_EQUITIES: "equities_latest.json",
        DC_INTENT_OPTIONS_FLOW: "options_flow_latest.json",
        DC_INTENT_INSIDER: "insider_trades_latest.json",
        DC_INTENT_BOND_YIELDS: "bond_yields_latest.json",
        DC_INTENT_CPI: "cpi_latest.json",
        DC_INTENT_FED_WATCH: "fed_watch_latest.json",
        DC_INTENT_WATCHES: "watches_latest.json",
        DC_INTENT_DARK_POOL: "dark_pool_latest.json",
        DC_INTENT_SECTOR_ROTATION: "sector_rotation_latest.json",
        DC_INTENT_GLOBAL_LIQUIDITY: "global_liquidity_latest.json",
        DC_INTENT_EARNINGS: "earnings_latest.json",
        DC_INTENT_FOREX: "forex_latest.json",
        DC_INTENT_COMMODITIES: "commodities_latest.json",
        DC_INTENT_SUPPLY_CHAIN: "supply_chain_latest.json",
        DC_INTENT_ENERGY: "energy_latest.json",
        DC_INTENT_CLIMATE_RISK: "climate_risk_latest.json",
        DC_INTENT_TARIFFS: "tariffs_latest.json",
        DC_INTENT_JOBS: "jobs_latest.json",
        DC_INTENT_CONGRESS_TRADES: "congress_trades_latest.json",
        # Phase-2 single-file intents
        DC_INTENT_DARK_POOL_SCAN: "dark_pool_latest.json",
        DC_INTENT_PENNY_STOCK_SCAN: "penny_stocks_latest.json",
        DC_INTENT_GLOBAL_LIQUIDITY_SCAN: "global_liquidity_latest.json",
        DC_INTENT_SECTOR_ROTATION_SCAN: "sector_rotation_latest.json",
        DC_INTENT_SENTIMENT_DIVERGENCE_SCAN: "sentiment_divergence_latest.json",
    }

    # Phase-2 multi-file intents: load multiple cache files in parallel
    _MULTI_FILE_INTENTS = {
        DC_INTENT_REAL_ESTATE_SCAN: {
            "residential": "residential_latest.json",
            "rental_yield": "rental_yield_latest.json",
            "str": "str_latest.json",
            "commercial": "commercial_latest.json",
            "zoning": "zoning_latest.json",
            "reits": "reits_latest.json",
            "mortgage_rates": "mortgage_rates_latest.json",
        },
        DC_INTENT_PERSONAL_WEALTH_SCAN: {
            "hysa": "hysa_latest.json",
            "credit_cards": "credit_cards_latest.json",
            "auto_loans": "auto_loans_latest.json",
            "student_debt": "student_debt_latest.json",
            "retirement_limits": "retirement_limits_latest.json",
            "personal_loans": "personal_loans_latest.json",
            "col": "col_latest.json",
            "insurance": "insurance_latest.json",
        },
        DC_INTENT_TAX_LEGAL_SCAN: {
            "federal_tax": "federal_tax_latest.json",
            "state_tax": "state_tax_latest.json",
            "bankruptcy": "bankruptcy_latest.json",
            "sec_filings": "sec_filings_latest.json",
            "consumer_alerts": "consumer_alerts_latest.json",
            "labor_law": "labor_law_latest.json",
        },
        DC_INTENT_BUSINESS_SCAN: {
            "sba": "sba_latest.json",
            "saas_metrics": "saas_metrics_latest.json",
            "ecommerce": "ecommerce_latest.json",
            "freelance_rates": "freelance_rates_latest.json",
            "franchise": "franchise_latest.json",
            "vc_deals": "vc_deals_latest.json",
        },
        DC_INTENT_ALTERNATIVE_ASSET_SCAN: {
            "watches": "watches_latest.json",
            "art": "art_latest.json",
            "collectibles": "collectibles_latest.json",
            "p2p": "p2p_latest.json",
            "metals": "metals_latest.json",
        },
        DC_INTENT_GROWTH_MARKETING_SCAN: {
            "competitor_ads": "competitor_ads_latest.json",
            "seo_keywords": "seo_keywords_latest.json",
            "sentiment": "sentiment_latest.json",
            "email_health": "email_health_latest.json",
            "engagement": "engagement_latest.json",
            "reviews": "reviews_latest.json",
            "roas": "roas_latest.json",
            "leads": "leads_latest.json",
            "crm_sync": "crm_sync_latest.json",
        },
        DC_INTENT_INTELLIGENCE_SYNTHESIS: {
            "correlation": "correlation_latest.json",
            "regime_change": "regime_change_latest.json",
            "earnings_season_brief": "earnings_season_brief_latest.json",
            "sector_rotation": "sector_rotation_latest.json",
            "news_catalysts": "news_catalysts_latest.json",
            "sentiment_divergence": "sentiment_divergence_latest.json",
            "risk_budget": "risk_budget_latest.json",
        },
        DC_INTENT_MACRO_RISK_SCAN: {
            "fed_watch": "fed_watch_latest.json",
            "cpi_inflation": "cpi_inflation_latest.json",
            "jobs": "jobs_latest.json",
            "treasury_yield": "treasury_yield_latest.json",
            "regime_change": "regime_change_latest.json",
        },
    }

    if intent in _MULTI_FILE_INTENTS:
        file_map = _MULTI_FILE_INTENTS[intent]
        parallel_results = _load_cache_files_parallel(list(file_map.values()))
        files_data: dict[str, Any] = {}
        any_loaded = False
        for key, fname_multi in file_map.items():
            raw_obj_multi, _ = parallel_results.get(fname_multi, (None, {}))
            if isinstance(raw_obj_multi, dict):
                files_data[key] = raw_obj_multi
                any_loaded = True
            else:
                files_data[key] = {}
        if not any_loaded:
            meta["error"] = "no_multi_file_data_loaded"
            return None, meta
        if intent == DC_INTENT_REAL_ESTATE_SCAN:
            compact = _compact_real_estate_cache(files_data)
        elif intent == DC_INTENT_PERSONAL_WEALTH_SCAN:
            compact = _compact_wealth_cache(files_data)
        elif intent == DC_INTENT_TAX_LEGAL_SCAN:
            compact = _compact_tax_legal_cache(files_data)
        elif intent == DC_INTENT_BUSINESS_SCAN:
            compact = _compact_business_cache(files_data)
        elif intent == DC_INTENT_ALTERNATIVE_ASSET_SCAN:
            compact = _compact_alternative_asset_cache(files_data)
        elif intent == DC_INTENT_GROWTH_MARKETING_SCAN:
            compact = _compact_growth_marketing_cache(files_data)
        elif intent == DC_INTENT_INTELLIGENCE_SYNTHESIS:
            compact = _compact_intelligence_cache(files_data)
        elif intent == DC_INTENT_MACRO_RISK_SCAN:
            compact = _compact_macro_risk_scan(files_data)
        else:
            compact = {"snapshot": intent, "data": files_data}
        meta["loaded"] = True
        meta["asset_rows"] = _ik_row_count(compact)
        meta["file"] = ",".join(file_map.values())
        return compact, meta

    fname = intent_files.get(intent)
    if not fname:
        meta["error"] = "unknown_data_cache_intent"
        return None, meta
    meta["file"] = fname
    summary_name = _summary_filename_for_cache(fname)
    summary_path = root / "summaries" / summary_name
    if not prefer_raw and summary_path.is_file():
        payload, summary_meta = _read_data_cache_json(f"summaries/{summary_name}")
        meta.update(
            {
                "file": f"summaries/{summary_name}",
                "loaded": bool(summary_meta.get("loaded")),
                "error": summary_meta.get("error"),
                "cache_layer": "summary",
                "load_path": str(summary_path),
            }
        )
        if payload is not None:
            payload.setdefault("snapshot", _summary_snapshot_for_intent(intent))
            if intent == DC_INTENT_WATCHES:
                payload.setdefault("models", [])
            payload.setdefault("_cache_layer", "summary")
            payload.setdefault("_source_cache", fname)
            meta["asset_rows"] = _ik_row_count(payload)
            return payload, meta
    elif not prefer_raw:
        meta["summary_fallback"] = f"missing_file:{summary_path}"

    meta["file"] = fname
    meta["cache_layer"] = "raw"
    path = root / fname
    meta["load_path"] = str(path)
    if not path.is_file():
        meta["error"] = f"missing_file:{path}"
        return None, meta
    try:
        raw_obj: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        meta["error"] = str(e)
        return None, meta
    if not isinstance(raw_obj, dict):
        meta["error"] = "invalid_json_shape"
        return None, meta
    if intent == DC_INTENT_EQUITIES:
        compact, loader_meta = load_equities_payload()
        meta.update({k: v for k, v in loader_meta.items() if k in ("loaded", "error", "asset_rows")})
        return compact, meta
    if intent == DC_INTENT_OPTIONS_FLOW:
        compact, loader_meta = load_options_flow_payload()
        meta.update({k: v for k, v in loader_meta.items() if k in ("loaded", "error", "asset_rows")})
        return compact, meta
    if intent == DC_INTENT_INSIDER:
        compact, loader_meta = load_insider_payload()
        meta.update({k: v for k, v in loader_meta.items() if k in ("loaded", "error", "asset_rows")})
        return compact, meta

    if intent == DC_INTENT_CRYPTO:
        compact = _compact_crypto_cache(raw_obj)
    elif intent == DC_INTENT_BOND_YIELDS:
        compact = _compact_bond_yields(raw_obj)
    elif intent == DC_INTENT_CPI:
        compact = _compact_cpi(raw_obj)
    elif intent == DC_INTENT_FED_WATCH:
        compact = _compact_fed_watch(raw_obj)
    elif intent == DC_INTENT_WATCHES:
        compact = _compact_watches_cache(raw_obj)
    elif intent == DC_INTENT_DARK_POOL:
        compact = _compact_dark_pool(raw_obj)
    elif intent == DC_INTENT_SECTOR_ROTATION:
        compact = _compact_sector_rotation(raw_obj)
    elif intent == DC_INTENT_GLOBAL_LIQUIDITY:
        compact = _compact_global_liquidity(raw_obj)
    elif intent == DC_INTENT_EARNINGS:
        compact = _compact_generic_cache(raw_obj, snapshot="earnings_calendar", list_key="upcoming")
    elif intent == DC_INTENT_FOREX:
        compact = _compact_generic_cache(raw_obj, snapshot="forex_rates", list_key="pairs")
    elif intent == DC_INTENT_COMMODITIES:
        compact = _compact_generic_cache(raw_obj, snapshot="commodities", list_key="commodities")
    elif intent == DC_INTENT_SUPPLY_CHAIN:
        compact = _compact_generic_cache(raw_obj, snapshot="supply_chain", list_key="indices")
    elif intent == DC_INTENT_ENERGY:
        compact = _compact_generic_cache(raw_obj, snapshot="energy_grid", list_key="breakdown")
    elif intent == DC_INTENT_CLIMATE_RISK:
        compact = _compact_generic_cache(raw_obj, snapshot="climate_risk", list_key="flood_zone_changes")
    elif intent == DC_INTENT_TARIFFS:
        compact = _compact_generic_cache(raw_obj, snapshot="tariffs", list_key="active_tariffs")
    elif intent == DC_INTENT_JOBS:
        compact = _compact_generic_cache(raw_obj, snapshot="jobs", list_key="sector_breakdown")
    elif intent == DC_INTENT_CONGRESS_TRADES:
        compact = _compact_generic_cache(raw_obj, snapshot="congress_trades", list_key="trades")
    # Phase-2 single-file intents
    elif intent == DC_INTENT_DARK_POOL_SCAN:
        compact = _compact_dark_pool_scan(raw_obj)
    elif intent == DC_INTENT_PENNY_STOCK_SCAN:
        compact = _compact_penny_stock_scan(raw_obj)
    elif intent == DC_INTENT_GLOBAL_LIQUIDITY_SCAN:
        compact = _compact_global_liquidity_scan(raw_obj)
    elif intent == DC_INTENT_SECTOR_ROTATION_SCAN:
        compact = _compact_sector_rotation_scan(raw_obj)
    elif intent == DC_INTENT_SENTIMENT_DIVERGENCE_SCAN:
        compact = _compact_sentiment_divergence_scan(raw_obj)
    else:
        meta["error"] = "unknown_data_cache_intent"
        return None, meta
    meta["loaded"] = True
    meta["asset_rows"] = _ik_row_count(compact)
    return compact, meta


DOMAINS = {
    "STOCK_RESEARCH":  "Stock analysis, options, earnings",
    "CRYPTO_ANALYSIS": "Cryptocurrency, DeFi",
    "MACRO_RESEARCH":  "Macro, Fed, sector rotation",
    "HOME_BUYING":     "Mortgage, home purchase",
    "CAR_BUYING":      "Auto loans, dealers",
    "DEBT_PAYOFF":     "Debt strategies",
    "SAVINGS_PLAN":    "Savings, HYSA",
    "FUTURES_TRADING": "Futures, commodities",
    "TAX_PLANNING":    "Tax planning",
    "RETIREMENT":      "401k, IRA, retirement",
    "CREDIT_REPAIR":   "Credit score",
    "GENERAL_FINANCE": "General finance",
}


@dataclass
class UserContext:
    credit_score: Optional[int] = None
    annual_income: Optional[float] = None
    monthly_income: Optional[float] = None
    down_payment: Optional[float] = None
    monthly_budget: Optional[float] = None
    location: Optional[str] = None
    existing_debt: Optional[float] = None
    savings: Optional[float] = None
    timeline: Optional[str] = None
    risk_tolerance: Optional[str] = None
    tickers: list = field(default_factory=list)
    options_position: dict = field(default_factory=dict)


class IntentClassifier:
    _TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
    _CREDIT_RE = re.compile(
        r"credit\s*(?:score|rating)?\s*(?:of|is|around|~)?\s*(\d{3})", re.I
    )
    _INCOME_RE = re.compile(
        r"\$?([\d,]+)k?\s*(?:a year|per year|annually|salary|income)", re.I
    )
    _DOWN_RE = re.compile(
        r"\$?([\d,]+)k?\s*(?:down|down payment|upfront|to put)", re.I
    )
    _BUDGET_RE = re.compile(
        r"\$?([\d,]+)k?\s*(?:per month|monthly|/mo|a month)", re.I
    )
    _DEBT_RE = re.compile(
        r"\$?([\d,]+)k?\s*(?:in debt|owed|balance|credit card)", re.I
    )
    _ZIP_RE = re.compile(r"\b(\d{5})\b")
    _STRIKE_RE = re.compile(
        r"\$?(\d{1,4}(?:\.\d{1,2})?)\s*(?:call|put|strike)\b", re.I
    )
    _EXPIRY_RE = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?"
        r"|\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2}",
        re.I,
    )
    _STOP = {
        "A", "I", "MY", "ME", "IN", "ON", "AT", "TO", "OR", "AND", "FOR", "THE", "THIS",
        "WITH", "FROM", "INTO", "WILL", "HAVE", "HAS", "ARE", "WAS", "IS", "IT", "DO", "HOW",
        "WHO", "WHY", "WHAT", "WHEN", "WHERE", "ANY", "ALL", "BY", "AN", "BE", "AS", "IF",
        "NO", "SO", "US", "CAN", "GET", "NOW", "OWN", "AI", "ML", "GDP", "CPI", "FED", "SEC",
        "FDA", "RSI", "IV", "DTE", "ATM", "OTM", "ITM", "Q1", "Q2", "Q3", "Q4", "EPS", "PE",
    }
    _KW = {
        "HOME_BUYING": [
            ("house", 3), ("mortgage", 3.5), ("buy a house", 4), ("refinanc", 3),
        ],
        "CAR_BUYING": [
            ("car", 2.5), ("auto loan", 3.5), ("buy a car", 4), ("dealer", 2.5),
        ],
        "DEBT_PAYOFF": [
            ("debt", 3), ("pay off", 3), ("credit card", 3), ("snowball", 3),
        ],
        "SAVINGS_PLAN": [("savings", 3), ("emergency fund", 3.5), ("hysa", 3.5)],
        "CRYPTO_ANALYSIS": [("bitcoin", 3), ("crypto", 3.5), ("ethereum", 3)],
        "MACRO_RESEARCH": [("macro", 3.5), ("inflation", 3), ("fed", 1.5)],
        "FUTURES_TRADING": [("futures", 3.5), ("commodity", 3), ("cme", 3)],
        "TAX_PLANNING": [("tax", 3), ("irs", 3), ("capital gains", 3.5)],
        "RETIREMENT": [("401k", 3.5), ("roth", 3), ("retirement", 3.5)],
        "CREDIT_REPAIR": [("credit repair", 4), ("fico", 3)],
        "STOCK_RESEARCH": [
            ("stock", 2), ("earnings", 2.5), ("options", 2.5), ("strike", 2.5),
            ("invest", 2.5), ("investing", 2.5), ("portfolio", 3), ("allocate", 2.5),
            ("etf", 2.5), ("thematic", 3), ("discover", 2), ("screen", 2),
            ("dividend", 2), ("how to invest", 3),
        ],
    }

    def classify(self, query: str) -> tuple[str, UserContext]:
        q, ql = query.strip(), query.strip().lower()
        ctx = UserContext()
        m = self._CREDIT_RE.search(ql)
        if m:
            ctx.credit_score = int(m.group(1))
        m = self._INCOME_RE.search(ql)
        if m:
            v = float(m.group(1).replace(",", ""))
            ctx.annual_income = (
                v * 1000 if "k" in ql[max(0, m.start() - 2) : m.end() + 2] else v
            )
        m = self._DOWN_RE.search(ql)
        if m:
            v = float(m.group(1).replace(",", ""))
            ctx.down_payment = (
                v * 1000 if "k" in ql[max(0, m.start() - 2) : m.end() + 2] else v
            )
        m = self._BUDGET_RE.search(ql)
        if m:
            v = float(m.group(1).replace(",", ""))
            ctx.monthly_budget = (
                v * 1000 if "k" in ql[max(0, m.start() - 2) : m.end() + 2] else v
            )
        m = self._DEBT_RE.search(ql)
        if m:
            v = float(m.group(1).replace(",", ""))
            ctx.existing_debt = (
                v * 1000 if "k" in ql[max(0, m.start() - 2) : m.end() + 2] else v
            )
        m = self._ZIP_RE.search(q)
        if m:
            ctx.location = m.group(1)
        else:
            lm = re.search(
                r"in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:,\s*[A-Z]{2})?)", q
            )
            if lm:
                ctx.location = lm.group(1)
        ctx.tickers = list(
            dict.fromkeys(
                t
                for t in self._TICKER_RE.findall(q)
                if t not in self._STOP and len(t) >= 2
            )
        )
        sm = self._STRIKE_RE.search(q)
        em = self._EXPIRY_RE.search(q)
        if sm or em:
            ctx.options_position = {
                "strike": float(sm.group(1)) if sm else None,
                "expiry_raw": em.group(0) if em else None,
                "option_type": (
                    "call"
                    if re.search(r"\bcall\b", ql)
                    else ("put" if re.search(r"\bput\b", ql) else None)
                ),
            }
            ext = extract_options_values_from_text(q)
            if ext.get("avg_premium") is not None:
                ctx.options_position["avg_premium"] = ext["avg_premium"]
            if ext.get("current_mark") is not None:
                ctx.options_position["current_mark"] = ext["current_mark"]
            if ext.get("iv_pct") is not None:
                ctx.options_position["iv_pct"] = ext["iv_pct"]
        scores = {d: 0.0 for d in DOMAINS}
        for domain, kws in self._KW.items():
            for kw, w in kws:
                if kw in ql:
                    scores[domain] += w
        if ctx.options_position.get("strike") or ctx.options_position.get("expiry_raw"):
            scores["STOCK_RESEARCH"] += 3.0
        if ctx.tickers and max(scores.values()) < 4:
            scores["STOCK_RESEARCH"] += 2.5
        best = max(scores, key=lambda k: scores[k])
        if scores[best] < 1.0:
            best = "GENERAL_FINANCE"
        if best == "GENERAL_FINANCE" and re.search(r"\$[\d,]+", ql) and any(
            w in ql for w in ("invest", "investing", "portfolio", "allocate", "stock", "etf")
        ):
            scores["STOCK_RESEARCH"] = scores.get("STOCK_RESEARCH", 0) + 4.0
            best = max(scores, key=lambda k: scores[k])
        return best, ctx


class MarketWorker:
    def fetch(self, ticker: str) -> dict:
        try:
            import yfinance as yf

            tk = yf.Ticker(ticker)
            info = tk.info or {}
            hist = tk.history(period="60d")
            return {
                "ticker": ticker,
                "price": info.get("regularMarketPrice") or info.get("currentPrice"),
                "market_cap": info.get("marketCap"),
                "short_float": info.get("shortPercentOfFloat"),
                "sector": info.get("sector"),
                "company": info.get("longName"),
                "description": (info.get("longBusinessSummary") or "")[:600],
                "rsi_14": self._rsi(hist["Close"].tolist()) if not hist.empty else None,
            }
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    def _rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return None
        d = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        g = [max(x, 0) for x in d[-period:]]
        l = [abs(min(x, 0)) for x in d[-period:]]
        ag, al = sum(g) / period, sum(l) / period
        if al == 0:
            return 100.0
        return round(100 - (100 / (1 + ag / al)), 2)

    def sec_filings(self, ticker: str) -> dict:
        try:
            resp = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": "ATLAS research@atlas.local"},
                timeout=10,
            )
            cik = None
            for e in resp.json().values():
                if e.get("ticker", "").upper() == ticker.upper():
                    cik = str(e["cik_str"]).zfill(10)
                    break
            if not cik:
                return {}
            resp2 = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers={"User-Agent": "ATLAS research@atlas.local"},
                timeout=10,
            )
            subs = resp2.json()
            recent = subs.get("filings", {}).get("recent", {})
            forms, dates, acc = recent.get("form", []), recent.get("filingDate", []), recent.get(
                "accessionNumber", []
            )
            out: dict = {}
            for form in ("10-K", "8-K"):
                m = [(dates[i], acc[i]) for i, f in enumerate(forms) if f == form][:3]
                out[form] = [{"date": d, "accession": a} for d, a in m]
            return out
        except Exception as e:
            return {"error": str(e)}


class MacroWorker:
    def fetch(self) -> dict:
        result: dict = {}
        try:
            import yfinance as yf

            for sym, key in (
                ("^TNX", "10y_treasury"),
                ("^VIX", "vix"),
                ("^GSPC", "sp500"),
            ):
                try:
                    hist = yf.Ticker(sym).history(period="5d")
                    if not hist.empty:
                        result[key] = {
                            "value": round(float(hist["Close"].iloc[-1]), 3),
                        }
                except Exception:
                    pass
        except Exception:
            pass
        return result


class ConsumerWorker:
    AUTO_RATES = {
        (720, 999): {"tier": "Super prime", "new": 5.61, "used": 7.43},
        (660, 719): {"tier": "Prime", "new": 7.01, "used": 9.73},
        (620, 659): {"tier": "Near prime", "new": 9.62, "used": 13.72},
        (300, 619): {"tier": "Subprime+", "new": 12.0, "used": 15.0},
    }

    def auto_loan_rate(self, credit_score: int = 680) -> dict:
        for (lo, hi), data in self.AUTO_RATES.items():
            if lo <= credit_score <= hi:
                return {**data, "credit_score": credit_score}
        return {"tier": "Unknown", "new": None, "used": None}

    def calc_payment(self, principal: float, annual_rate: float, months: int) -> dict:
        if annual_rate == 0:
            pmt = principal / months
        else:
            r = annual_rate / 100 / 12
            pmt = principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)
        return {
            "monthly": round(pmt, 2),
            "total": round(pmt * months, 2),
            "total_interest": round(pmt * months - principal, 2),
        }


class LocationWorker:
    def geocode(self, location: str):
        try:
            url = (
                f"https://nominatim.openstreetmap.org/search?"
                f"q={quote(location)}&format=json&limit=1"
            )
            data = requests.get(
                url, headers={"User-Agent": "ATLAS-Omega/1.0"}, timeout=8
            ).json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None

    def find_near(
        self,
        location: str,
        kind: str,
        label: str,
        radius_m: int = 20000,
        limit: int = 8,
    ):
        coords = self.geocode(location)
        if not coords:
            return []
        lat, lon = coords
        if kind in ("dealer", "shop=car", "car"):
            q = f"""[out:json][timeout:20];
            (node["shop"="car"](around:{radius_m},{lat},{lon});
             node["shop"="car_dealer"](around:{radius_m},{lat},{lon}););
            out {limit};"""
        else:
            tag = kind.replace("amenity=", "", 1) if "amenity=" in kind else kind
            q = (
                f'[out:json][timeout:15];node["amenity"="{tag}"](around:{radius_m},'
                f"{lat},{lon});out body {limit};"
            )
        try:
            data = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": q},
                timeout=22,
            ).json()
            rows = []
            for el in data.get("elements", [])[:limit]:
                tg = el.get("tags", {})
                if tg.get("name"):
                    rows.append(
                        {
                            "name": tg.get("name"),
                            "address": f"{tg.get('addr:housenumber','')} {tg.get('addr:street','')}".strip(),
                            "type": label,
                        }
                    )
            return rows
        except Exception:
            return []


class CryptoWorker:
    _MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    }

    def fetch(self, ticker: str) -> dict:
        coin = self._MAP.get(ticker.upper(), ticker.lower())
        try:
            r = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin}",
                params={"localization": "false", "market_data": "true"},
                timeout=12,
            )
            d = r.json()
            md = d.get("market_data", {})
            return {
                "name": d.get("name"),
                "price_usd": md.get("current_price", {}).get("usd"),
                "change_24h": md.get("price_change_percentage_24h"),
            }
        except Exception as e:
            return {"coin": coin, "error": str(e)}


class NewsWorker:
    _FEEDS = (
        ("reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("marketwatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    )

    def for_ticker(self, ticker: str, max_per=5):
        try:
            import feedparser
        except ImportError:
            return []
        out = []
        for name, url in self._FEEDS:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:15]:
                    t, s = e.get("title", ""), e.get("summary", "")
                    if ticker.upper() in (t + s).upper():
                        out.append(
                            {
                                "source": name,
                                "title": t,
                                "summary": (s or "")[:280],
                            }
                        )
                    if len(out) >= max_per:
                        return out
            except Exception:
                continue
        return out


class CommandDispatcher:
    def __init__(self):
        self.market = MarketWorker()
        self.macro = MacroWorker()
        self.consumer = ConsumerWorker()
        self.location = LocationWorker()
        self.crypto = CryptoWorker()
        self.news = NewsWorker()

    def _resolve_stock_bundle(self, ctx: UserContext, query: str) -> tuple[list[str], bool]:
        """
        (symbols, multi_name_pack)
        multi_name_pack=True → broader parallel fetch (thematic / allocation questions).
        """
        disc = _is_discovery_or_allocation_query(query)
        if ctx.tickers and not disc:
            return ctx.tickers[:4], False
        if ctx.tickers and disc:
            merged: list[str] = []
            for t in ctx.tickers + _thematic_symbols_for_query(query):
                u = t.upper().strip()
                if u not in merged:
                    merged.append(u)
            return merged[:12], True
        thematic = _thematic_symbols_for_query(query)
        if not thematic:
            thematic = ["SPY", "QQQ", "IWM"]
        return thematic[:12], bool(disc or len(thematic) > 1)

    def execute(
        self,
        domain: str,
        ctx: UserContext,
        query: str,
        data_cache_intent: str | None = None,
    ) -> dict:
        bundle = {
            "domain": domain,
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
        }
        tasks: dict[str, Any] = {}

        if data_cache_intent in DATA_CACHE_MACRO_ONLY_INTENTS:
            tasks["macro"] = self.macro.fetch
            with ThreadPoolExecutor(max_workers=min(len(tasks), 20)) as ex:
                fmap = {ex.submit(fn): k for k, fn in tasks.items()}
                for fut in as_completed(fmap):
                    k = fmap[fut]
                    try:
                        bundle["data"][k] = fut.result(timeout=60)
                    except Exception as e:
                        bundle["data"][k] = {"error": str(e)}
            return bundle

        if domain == "STOCK_RESEARCH":
            symbols, multi = self._resolve_stock_bundle(ctx, query)
            news_cap = 3 if multi else 5
            sec_cap = 4 if multi else 3
            sec_added = 0
            for t in symbols:
                tasks[f"market_{t}"] = lambda tk=t: self.market.fetch(tk)
                tasks[f"news_{t}"] = lambda tk=t: self.news.for_ticker(
                    tk, max_per=news_cap
                )
                if (
                    t.upper() not in _OMEGA_ETF_SYMBOLS
                    and sec_added < sec_cap
                    and len(t) <= 5
                ):
                    tasks[f"sec_{t}"] = lambda tk=t: self.market.sec_filings(tk)
                    sec_added += 1
            tasks["macro"] = self.macro.fetch
            if multi:
                tasks["market_regime"] = _fetch_market_regime_light
        elif domain == "CRYPTO_ANALYSIS":
            for t in (ctx.tickers or ["BTC"])[:3]:
                tasks[f"crypto_{t}"] = lambda tk=t: self.crypto.fetch(tk)
            tasks["macro"] = self.macro.fetch
        elif domain == "MACRO_RESEARCH":
            tasks["macro"] = self.macro.fetch
            tasks["news"] = lambda: self.news.for_ticker("SPY", max_per=3)
            if _is_discovery_or_allocation_query(query):
                for t in _thematic_symbols_for_query(query)[:8]:
                    tasks[f"market_{t}"] = lambda tk=t: self.market.fetch(tk)
                tasks["market_regime"] = _fetch_market_regime_light
        elif domain == "HOME_BUYING":
            tasks["macro"] = self.macro.fetch
            if ctx.location:
                tasks["banks"] = lambda: self.location.find_near(
                    ctx.location, "bank", "bank"
                )
        elif domain == "CAR_BUYING":
            cr = ctx.credit_score or 680
            tasks["rates"] = lambda: self.consumer.auto_loan_rate(cr)
            tasks["macro"] = self.macro.fetch
            if ctx.location:
                tasks["dealers"] = lambda: self.location.find_near(
                    ctx.location, "shop=car", "dealer", 25000
                )
        elif domain == "FUTURES_TRADING":
            ft = ctx.tickers or ["GC=F", "CL=F", "ES=F"]
            for t in ft[:4]:
                tasks[f"fut_{t}"] = lambda tk=t: self.market.fetch(tk)
            tasks["macro"] = self.macro.fetch
        else:
            tasks["macro"] = self.macro.fetch
            tasks["news"] = lambda: self.news.for_ticker("SPY", max_per=4)
            if ctx.tickers:
                tasks["m0"] = lambda: self.market.fetch(ctx.tickers[0])
            if _is_discovery_or_allocation_query(query):
                for t in _thematic_symbols_for_query(query)[:8]:
                    tasks[f"market_{t}"] = lambda tk=t: self.market.fetch(tk)
                tasks["market_regime"] = _fetch_market_regime_light

        with ThreadPoolExecutor(max_workers=min(len(tasks), 20)) as ex:
            fmap = {ex.submit(fn): k for k, fn in tasks.items()}
            for fut in as_completed(fmap):
                k = fmap[fut]
                try:
                    bundle["data"][k] = fut.result(timeout=60)
                except Exception as e:
                    bundle["data"][k] = {"error": str(e)}
        return bundle


class OmegaAgent:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.dispatcher = CommandDispatcher()
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            import google.genai as genai
            from google.genai.types import HttpOptions

            key = os.environ.get("GOOGLE_API_KEY", "")
            if key:
                self._client = genai.Client(
                    api_key=key,
                    http_options=HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS),
                )
        except ImportError:
            pass
        return self._client

    def ask_clarifying(self, query: str) -> list[str]:
        domain, ctx = self.classifier.classify(query)
        qs: list[str] = []
        if domain == "CAR_BUYING":
            if not ctx.credit_score:
                qs.append("Approximate credit score?")
            if not ctx.location:
                qs.append("City or zip for local dealers?")
        elif domain == "HOME_BUYING" and not ctx.credit_score:
            qs.append("Approximate credit score?")
        elif domain == "STOCK_RESEARCH" and ctx.options_position:
            if not ctx.options_position.get("expiry_raw"):
                qs.append("Exact option expiration date?")
            if not ctx.options_position.get("avg_premium"):
                qs.append("Premium paid per share?")
        return qs[:3]

    def _respond_casual(self, query: str) -> dict:
        """Return a plain conversational response for casual/off-topic queries."""
        _fallback = (
            "Hey there! I'm ATLAS, your financial intelligence assistant. "
            "Ask me about stocks, real estate, debt, crypto, or anything money-related!"
        )
        client = self._get_client()
        if client:
            try:
                import google.genai.types as gtypes
                system = (
                    "You are ATLAS, a friendly AI financial intelligence assistant. "
                    "The user is making casual conversation. Respond warmly and briefly in plain text. "
                    "If their message relates to finance, offer to help with analysis. "
                    "Keep your response to 1-2 sentences."
                )
                resp = client.models.generate_content(
                    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=system + "\n\nUser: " + query,
                    config=gtypes.GenerateContentConfig(temperature=0.7, max_output_tokens=256),
                )
                text = (resp.text or "").strip() or _fallback
            except Exception:
                text = _fallback
        else:
            text = _fallback
        return {
            "domain": "CASUAL",
            "domain_label": "Casual",
            "headline": "ATLAS",
            "urgency": "informational",
            "executive_brief": text,
            "query": query,
        }

    def query(
        self,
        user_query: str,
        follow_up_context: dict | None = None,
        session_id: str | None = None,
        data_cache_intent: str | None = None,
        prefer_raw_cache: bool = False,
        intent_route: str | None = None,
    ) -> dict:
        if intent_route in ("CASUAL", "GENERAL_CHAT"):
            return self._respond_casual(user_query)
        start = time.time()
        domain, ctx = self.classifier.classify(user_query)

        # Company web enrichment — only during synthesis, not routing
        # Uses detect_company_name() for proper alias + disambiguation matching
        _enriched_company: str | None = None
        if intent_route in ("COMPANY_RESEARCH", "GENERAL_FINANCE") or domain == "GENERAL_FINANCE":
            try:
                from query_router import detect_company_name as _detect_company
                _enriched_company = _detect_company(user_query)
            except Exception:
                pass
            if _enriched_company is None:
                # Fallback: check KNOWN_LARGE_COMPANIES for queries that got here via GENERAL_FINANCE
                for company in KNOWN_LARGE_COMPANIES:
                    if company in user_query.lower():
                        _enriched_company = company
                        break
            if _enriched_company:
                search_prompt = (
                    f"Search the web for current information about {_enriched_company}. "
                    "Include: what they do, AUM/revenue/market cap, recent news, "
                    "key executives, business model, competitive position, risks, sources. "
                )
                user_query = search_prompt + user_query
        if follow_up_context:
            for k, v in follow_up_context.items():
                if hasattr(ctx, k):
                    setattr(ctx, k, v)
        t1 = time.time()
        bundle = self.dispatcher.execute(
            domain, ctx, user_query, data_cache_intent=data_cache_intent
        )
        dc_meta: dict[str, Any] = {}
        if data_cache_intent:
            ik, dc_meta = _load_internal_knowledge_payload(
                data_cache_intent,
                prefer_raw=prefer_raw_cache,
            )
            if ik is not None:
                bundle["data"]["internal_knowledge_snapshot"] = ik
            else:
                bundle["data"]["internal_knowledge_snapshot"] = {
                    "_load_error": dc_meta.get("error"),
                    "intent": data_cache_intent,
                }
        include_market_intel = data_cache_intent in {
            DC_INTENT_EQUITIES,
            DC_INTENT_OPTIONS_FLOW,
            DC_INTENT_INSIDER,
        }
        ticker_market_intel = bool(_extract_ticker_set(ctx, user_query)) and domain == "STOCK_RESEARCH"
        if include_market_intel or ticker_market_intel:
            bundle["data"]["d2_d3_d4_market_intelligence"] = build_market_intelligence_context(
                user_query,
                ctx,
                include_full=include_market_intel,
            )
        # SEC EDGAR enrichment — synthesis-time only; never before routing
        # Runs when a company was identified and intent qualifies for company research.
        # Blocked for CASUAL, GENERAL_CHAT, pure trade_plan, and queries without a company.
        _sec_meta: dict = {}
        _wants_sec = bool(_enriched_company) and intent_route not in ("CASUAL", "GENERAL_CHAT")
        if _wants_sec:
            try:
                from omega_sec_edgar import get_filing_summary as _sec_summary, is_available as _sec_avail
                if _sec_avail():
                    _sec_raw = _sec_summary(_enriched_company)
                    if _sec_raw.get("sec_filings_used"):
                        bundle["data"]["sec_edgar_filings"] = {
                            "company":      _sec_raw.get("company"),
                            "cik":          _sec_raw.get("cik"),
                            "latest_10k":   _sec_raw.get("latest_10k"),
                            "latest_10q":   _sec_raw.get("latest_10q"),
                            "latest_8k":    _sec_raw.get("latest_8k"),
                            "filing_context": _sec_raw.get("filing_context", ""),
                        }
                        _sec_meta = {
                            "sec_filings_used": True,
                            "sec_status":       "found",
                            "cik":              _sec_raw.get("cik"),
                            "latest_10k":       _sec_raw.get("latest_10k"),
                            "latest_10q":       _sec_raw.get("latest_10q"),
                            "latest_8k":        _sec_raw.get("latest_8k"),
                        }
                        log.info("[Omega] SEC EDGAR: filings found for %s (CIK %s)", _enriched_company, _sec_raw.get("cik"))
                    else:
                        _sec_meta = {"sec_filings_used": False, "sec_status": "not_found"}
                else:
                    _sec_meta = {"sec_filings_used": False, "sec_status": "unavailable"}
            except Exception as _sec_exc:
                log.debug("[Omega] SEC EDGAR fetch failed: %s", _sec_exc)
                _sec_meta = {"sec_filings_used": False, "sec_status": "unavailable"}

        fetch_t = round(time.time() - t1, 2)
        report = self._synthesize(user_query, domain, ctx, bundle, data_cache_intent=data_cache_intent)
        ai_t = round(time.time() - t1 - fetch_t, 2)
        report.setdefault("_meta", {})
        if _sec_meta:
            report["_meta"].update(_sec_meta)
        report["_meta"].update(
            {
                "domain": domain,
                "fetch_time_s": fetch_t,
                "ai_time_s": max(ai_t, 0.01),
                "total_time_s": round(time.time() - start, 2),
                "sources_fetched": list(bundle["data"].keys()),
                "user_context": {
                    k: v for k, v in ctx.__dict__.items() if v not in (None, [], {})
                },
                "session_id": session_id,
            }
        )
        if data_cache_intent:
            report["_meta"]["data_cache"] = dc_meta
        return report

    def _synthesize(self, query: str, domain: str, ctx: UserContext, bundle: dict, *, data_cache_intent: str | None = None) -> dict:
        client = self._get_client()
        if not client:
            return {"error": "No GOOGLE_API_KEY in .env", "query": query}
        today = datetime.now(timezone.utc).strftime("%B %d, %Y")
        ik = bundle.get("data", {}).get("internal_knowledge_snapshot")
        worker_data = {
            k: v for k, v in bundle.get("data", {}).items() if k != "internal_knowledge_snapshot"
        }
        data_str = json.dumps(worker_data, indent=2, default=str)
        if len(data_str) > 24000:
            data_str = data_str[:24000] + "\n...[truncated]"
        ik_block = ""
        if ik is not None:
            ik_json = json.dumps(ik, indent=2, default=str)
            if len(ik_json) > 12000:
                ik_json = ik_json[:12000] + "\n...[truncated]"
            ik_block = f"""
=== INTERNAL KNOWLEDGE (AUTHORITATIVE SNAPSHOT DATA) ===
{ik_json}

INTERNAL KNOWLEDGE RULES (mandatory):
- Base which symbols/assets you cite for this scan ONLY on INTERNAL KNOWLEDGE above. Do not hallucinate tickers or coin symbols not listed there.
- Use only numeric facts (prices, % changes, volumes, market caps) that appear in INTERNAL KNOWLEDGE for those assets. If a field is missing, say unknown.
- DATA (from code workers) below is supplementary (e.g. macro). If it conflicts with INTERNAL KNOWLEDGE on membership, ranking, or snapshot figures, INTERNAL KNOWLEDGE wins for the scan universe.
"""

        lens = DOMAINS.get(domain, "Thorough actionable financial analysis.")
        multi_hint = ""
        if sum(1 for k in worker_data if str(k).startswith("market_")) >= 3:
            multi_hint = """
MULTI-NAME PACK: DATA has several market_<TICKER> snapshots. You must:
- Summarize current macro/regime using macro + market_regime + index levels.
- Compare 3–6 liquid ideas using ONLY tickers present in DATA (stocks/ETFs). Rank them for the user’s stated goal (growth, AI theme, $ amount, horizon).
- If the user gave a dollar amount, propose an example split across 2–4 NAMES from DATA (percentages or dollar stripes), plus a conservative ETF-only alternative.
- Options: you may describe 1–2 *example* retail options structures (directional or covered) using underlying symbols from DATA — cite approximate premium only if you have price in DATA; otherwise say “check chain”.
- Do NOT invent tickers, prices, or fundamentals not in DATA. If something is missing, say unknown and suggest what to verify next."""

        num_rule = (
            "Use only numbers present in INTERNAL KNOWLEDGE and/or DATA; otherwise say unknown."
            if ik is not None
            else "Use only numbers present in DATA; otherwise say unknown."
        )
        market_intel_rule = ""
        if "d2_d3_d4_market_intelligence" in worker_data:
            market_intel_rule = """
D2/D3/D4 MARKET INTELLIGENCE RULES:
- DATA.d2_d3_d4_market_intelligence contains equities movers, unusual options flow, and SEC Form 4 insider-trade snapshots.
- For market-wide questions, summarize only rows present in those snapshots; if record_count is 0 or a slice is empty, say no cached rows are available.
- For specific ticker questions, use ticker_slices first. If the ticker is absent from options_flow or insider_trades, explicitly say the cache has no matching row instead of inventing flow or filings.
"""
        # Domain framing — prepended for SCAN intents to set the analyst persona
        _DOMAIN_FRAMING: dict[str, str] = {
            "REAL_ESTATE_SCAN": "You are a senior real estate analyst with expertise in residential, commercial, rental, and REIT markets.",
            "PERSONAL_WEALTH_SCAN": "You are a certified financial planner (CFP) helping users optimize savings, debt, and personal finances. Always append: 'Consult a CFP for personalized advice.'",
            "TAX_LEGAL_SCAN": "You are a senior tax and legal analyst. This is informational only — always append: 'Consult a licensed tax professional or attorney for your specific situation.'",
            "BUSINESS_SCAN": "You are a venture analyst and business strategist with deep expertise in SMBs, SaaS metrics, franchise, and startup funding.",
            "ALTERNATIVE_ASSET_SCAN": "You are an alternative asset specialist covering luxury watches, fine art, collectibles, precious metals, and P2P lending.",
            "GROWTH_MARKETING_SCAN": "You are a growth and marketing analyst specializing in digital ads, SEO, brand sentiment, and ROI optimization.",
            "INTELLIGENCE_SYNTHESIS": "You are a senior quant analyst and portfolio strategist. Synthesize signals across regimes, rotations, and catalysts to surface the highest-conviction insights.",
            "DARK_POOL_SCAN": "You are a market microstructure analyst specializing in dark pool activity, off-exchange block trades, and institutional flow detection.",
            "PENNY_STOCK_SCAN": "You are a small-cap specialist focused on penny stocks and micro-cap movers. Note the high-risk nature of this asset class.",
            "GLOBAL_LIQUIDITY_SCAN": "You are a global macro and liquidity specialist tracking M2 money supply, central bank policy, and liquidity cycles.",
            "SECTOR_ROTATION_SCAN": "You are a sector rotation specialist who tracks institutional money flows across market sectors.",
            "SENTIMENT_DIVERGENCE_SCAN": "You are a contrarian analyst who identifies divergences between retail and institutional sentiment.",
        }
        domain_frame_prefix = ""
        if data_cache_intent and data_cache_intent in _DOMAIN_FRAMING:
            domain_frame_prefix = _DOMAIN_FRAMING[data_cache_intent] + "\n\n"

        try:
            from atlas_prompts.prompt_loader import get_domain_prompt as _get_domain_prompt
            agent_system_prompt = _get_domain_prompt(domain)
        except Exception:
            agent_system_prompt = ""

        prompt = f"""{domain_frame_prefix}You are ATLAS Omega. Today: {today}.
Query: "{query}"
Domain: {domain} ({lens})
User context:
{json.dumps({k:v for k,v in ctx.__dict__.items() if v not in (None,[],{})}, default=str)}
{multi_hint}
{ik_block}
{market_intel_rule}
DATA (from code workers):
{data_str}

Return ONE JSON object, no markdown. Keys:
domain, domain_label (friendly), headline, urgency (critical|urgent|normal|informational),
executive_brief, situation_analysis, key_insight, primary_recommendation,
scenarios: [{{label, probability, trigger, outcome, your_action}}],
numbers_that_matter: {{}},
action_plan: [{{step, timeframe, action, how, financial_impact}}],
named_resources: [{{name, type, why, contact}}],
hidden_angles: [],
risks_and_tripwires: [{{risk, severity, tripwire, response}}],
follow_up_questions: [],
last_updated
{num_rule}"""

        if agent_system_prompt:
            prompt = agent_system_prompt + "\n\n" + prompt

        # output_mode-based prompt constraints — use OUTPUT_CONTRACTS for required/forbidden
        try:
            from output_modes import resolve_output_mode as _resolve_output_mode_new
            _output_mode = _resolve_output_mode_new(query, domain)
        except Exception:
            try:
                from query_router import resolve_output_mode as _resolve_output_mode
                _output_mode = _resolve_output_mode(query, domain)
            except Exception:
                _output_mode = "finance_answer"

        try:
            from output_contracts import OUTPUT_CONTRACTS as _CONTRACTS
            _contract = _CONTRACTS.get(_output_mode)
        except Exception:
            _contract = None

        if _output_mode != "trade_plan":
            if _contract and _contract.forbidden_phrases:
                _forbidden_list = ", ".join(_contract.forbidden_phrases[:6])
                prompt += f"\n\nFORBIDDEN: Do not include {_forbidden_list}. This is not a trading query."
            else:
                prompt += "\n\nFORBIDDEN: Do not include entry_price, stop_loss, take_profit, execution_rules, trade_plan, risk_reward. This is not a trading query."

        if _output_mode == "company_report":
            _req_sections = ""
            if _contract and _contract.required_sections:
                _req_sections = ", ".join(_contract.required_sections)
            else:
                _req_sections = "Overview, Business Model, Financial Snapshot, Leadership, Recent News, Risks, Competitive Position, Sources"
            prompt += f"\n\nOUTPUT CONTRACT: Provide a company intelligence report. Required sections: {_req_sections}. No trade plan."
            if "sec_edgar_filings" in worker_data:
                prompt += "\n\nSEC EDGAR: DATA contains sec_edgar_filings with official filing dates. Cite 10-K and 10-Q dates in the Financial Snapshot section."

        if _output_mode == "chat":
            prompt += "\n\nOUTPUT: Short casual conversational answer. No finance jargon unless asked."

        if _output_mode == "document":
            prompt += "\n\nOUTPUT: Professional polished document structure. No trade plan unless user requested it."

        if _output_mode == "html_artifact":
            prompt += "\n\nOUTPUT: Return complete valid HTML with embedded CSS. No trade plan unless requested."

        try:
            import google.genai.types as gtypes

            model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            wait_for_slot("atlas_omega")
            # Enable Google Search tool if we added a "Search the web" prefix
            if query.lower().startswith("search the web"):
                cfg = gtypes.GenerateContentConfig(
                    tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
                    response_mime_type="application/json",
                    temperature=0.15,
                    max_output_tokens=16384,
                )
            else:
                cfg = gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.15,
                    max_output_tokens=16384,
                )
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=cfg,
            )
            raw = (resp.text or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\s*", "", raw)
                raw = re.sub(r"\s*```\s*$", "", raw).strip()
            return _omega_json_loads(raw)
        except Exception as e:
            log.error("[Omega] %s", e)
            try:
                wait_for_slot("atlas_omega_retry")
                resp = client.models.generate_content(
                    model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=prompt + "\nReturn ONLY raw JSON.",
                )
                return _omega_json_loads((resp.text or "").strip())
            except Exception as e2:
                return {"error": str(e2), "query": query, "domain": domain}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = OmegaAgent()
    r = agent.query("Should I worry about my SOUN position?")
    print(json.dumps(r, indent=2, default=str))