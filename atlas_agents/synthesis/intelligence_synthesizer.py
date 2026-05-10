"""
Combine ``data_cache`` agent JSON snapshots into synthesis artifacts.

Reads ingest snapshots plus bundled ``sp500_symbol_sector.json`` for sector tagging;
writes only ``data_cache/synthesis_*_latest.json`` plus optional stamped siblings.
Signals are descriptive only—not investment recommendations.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHESIS_DIR = Path(__file__).resolve().parent
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
VAULT_NOTES_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Notes"

STALE_SECONDS = 24 * 3600

DISCLAIMER = (
    "Signal reporting only. Not investment advice and not a solicitation. "
    "Past patterns do not predict future outcomes."
)

PATTERN_REGIME_FILES = frozenset(
    {"bond_yields_latest.json", "equities_latest.json", "cpi_latest.json"}
)
PATTERN_SENTIMENT_FILES = frozenset(
    {"sentiment_latest.json", "dark_pool_latest.json", "options_flow_latest.json"}
)
PATTERN_SECTOR_FILES = frozenset({"equities_latest.json", "insider_trades_latest.json"})
PATTERN_STRESS_FILES = frozenset(
    {"forex_latest.json", "commodities_latest.json", "bond_yields_latest.json"}
)

SECTOR_MAP_PATH = SYNTHESIS_DIR / "sp500_symbol_sector.json"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_generated_at(iso_z: str | None) -> datetime | None:
    if not iso_z or not isinstance(iso_z, str):
        return None
    s = iso_z.strip()
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.replace("Z", "").split("+")[0], fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def freshness_for_ts(parsed: datetime | None, now_utc: datetime) -> tuple[str, str | None]:
    if parsed is None:
        return "UNKNOWN", None
    parsed_utc = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    secs = max(0.0, (now_utc - parsed_utc).total_seconds())
    if secs > STALE_SECONDS:
        hours = round(secs / 3600.0, 2)
        return (
            "STALE",
            f"Data older than {STALE_SECONDS // 3600}h (approx_age={hours}h).",
        )
    return "FRESH", None


def generated_at_from_obj(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    for k in ("generated_at", "fetched_at", "as_of", "snapshot_time"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def data_cache_json_files() -> list[Path]:
    if not DATA_CACHE_DIR.is_dir():
        return []
    return sorted(DATA_CACHE_DIR.glob("*.json"), key=lambda x: x.name.lower())


def load_agent_snapshots(exclude_prefix: str = "synthesis_") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in data_cache_json_files():
        if p.name.startswith(exclude_prefix):
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            out[p.name] = obj
    return out


def snapshot_catalog(now_utc: datetime) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for p in data_cache_json_files():
        cat = "synthesis_output" if p.name.startswith("synthesis_") else "agent_ingest"
        obj: Any = None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            obj = raw if isinstance(raw, dict) else None
        except Exception:
            raw = None
        g = generated_at_from_obj(obj) if obj is not None else None
        fam, fh = freshness_for_ts(_parse_generated_at(g), now_utc)
        rows.append(
            {
                "file": p.name,
                "category": cat,
                "generated_at": g,
                "freshness": fam,
                "freshness_note": fh,
            }
        )
    return {"generated_at_catalog_utc": iso_now_z(), "files": rows}


def build_inputs_status(
    required: frozenset[str],
    snaps: dict[str, Any],
    now_utc: datetime,
) -> dict[str, dict[str, Any]]:
    inp: dict[str, dict[str, Any]] = {}
    for fname in sorted(required):
        obj = snaps.get(fname)
        if obj is None:
            inp[fname] = {"status": "missing", "freshness": "N/A", "generated_at": None}
            continue
        g = generated_at_from_obj(obj)
        fam, fnote = freshness_for_ts(_parse_generated_at(g), now_utc)
        row: dict[str, Any] = {
            "status": "present",
            "freshness": fam,
            "generated_at": g,
        }
        if fnote:
            row["freshness_detail"] = fnote
        inp[fname] = row
    return inp


def overall_conf_from_inputs(inp: dict[str, dict[str, Any]]) -> float:
    scores: list[float] = []
    for meta in inp.values():
        if meta.get("status") != "present":
            scores.append(0.35)
            continue
        fres = meta.get("freshness")
        if fres == "STALE":
            scores.append(0.55)
        elif fres == "UNKNOWN":
            scores.append(0.65)
        else:
            scores.append(0.95)
    if not scores:
        return 0.0
    geo = math.exp(sum(math.log(max(s, 0.05)) for s in scores) / len(scores))
    return round(min(1.0, geo), 3)


def _equity_buckets(
    equities: dict[str, Any],
) -> tuple[list[tuple[str, float]], list[tuple[str, float]], list[tuple[str, float]]]:
    gain: list[tuple[str, float]] = []
    lose: list[tuple[str, float]] = []
    actv: list[tuple[str, float]] = []

    def walk(bucket: Any, collector: list[tuple[str, float]]) -> None:
        if not isinstance(bucket, list):
            return
        for row in bucket:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or row.get("ticker") or "").strip().upper()
            if not sym:
                continue
            try:
                ch = float(row.get("regular_market_change_percent") or row.get("change_pct") or 0)
            except (TypeError, ValueError):
                ch = 0.0
            collector.append((sym, ch))

    walk(equities.get("gainers"), gain)
    walk(equities.get("losers"), lose)
    walk(equities.get("most_active"), actv)
    return gain, lose, actv


def load_sector_map() -> dict[str, str]:
    if not SECTOR_MAP_PATH.is_file():
        return {}
    try:
        data = json.loads(SECTOR_MAP_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    m = data.get("map") if isinstance(data, dict) else None
    if not isinstance(m, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in m.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip():
            out[k.strip().upper()] = v.strip()
    return out


def pattern_regime(snaps: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    inp = build_inputs_status(PATTERN_REGIME_FILES, snaps, now_utc)
    base_conf = overall_conf_from_inputs(inp)
    bond = snaps.get("bond_yields_latest.json")
    eq = snaps.get("equities_latest.json")
    cpi = snaps.get("cpi_latest.json")

    supporting: list[dict[str, Any]] = []
    contradicting: list[dict[str, Any]] = []
    rationale: list[str] = []

    if isinstance(bond, dict):
        sig = bond.get("curve_signal")
        spread = bond.get("spread_2y_10y")
        if sig == "INVERTED":
            contradicting.append(
                {
                    "signal": "inverted_yield_curve",
                    "detail": "Curve snapshot flagged INVERTED (2y/10y spread negative).",
                    "confidence": 0.72,
                }
            )
            rationale.append("Bonds flag INVERTED curve.")
        elif sig == "NORMAL":
            supporting.append(
                {
                    "signal": "normal_yield_curve",
                    "detail": "Curve snapshot flagged NORMAL.",
                    "confidence": 0.68,
                }
            )
            rationale.append("Bonds flag NORMAL curve.")
        elif sig == "FLAT":
            contradicting.append(
                {
                    "signal": "flat_yield_curve_uncertainty_proxy",
                    "detail": "Curve snapshot flagged FLAT.",
                    "confidence": 0.55,
                }
            )
        try:
            if isinstance(spread, (int, float)):
                rationale.append(f"spread_2y_10y={spread}")
        except Exception:
            pass
    else:
        rationale.append("Missing bond yields snapshot.")

    if isinstance(cpi, dict):
        infl = str(cpi.get("inflation_signal") or "")
        if infl in ("HOT", "ELEVATED"):
            contradicting.append(
                {
                    "signal": "elevated_headline_inflation_snapshot",
                    "detail": infl,
                    "confidence": 0.65,
                }
            )
        elif infl == "DEFLATIONARY":
            contradicting.append(
                {
                    "signal": "weak_inflation_pulse_signal",
                    "detail": infl,
                    "confidence": 0.5,
                }
            )
        elif infl:
            supporting.append(
                {
                    "signal": "moderate_inflation_signal",
                    "detail": infl,
                    "confidence": 0.6,
                }
            )
        rationale.append(f"CPI inflation_signal={infl or 'UNKNOWN'}.")
    else:
        rationale.append("Missing CPI snapshot.")

    if isinstance(eq, dict):
        gain, lose, _ = _equity_buckets(eq)
        gm = sum(p for _, p in gain) / max(len(gain), 1)
        lm = sum(p for _, p in lose) / max(len(lose), 1)
        rationale.append(
            f"Equity lists sampled: avg gainer_chg={gm:.2f}% avg loser_chg={lm:.2f}%."
        )
        if gm >= 8 and gm > abs(lm) * 0.9:
            supporting.append(
                {
                    "signal": "risk_on_leaderboard_snapshot",
                    "detail": "Large average mover strength on scorer gainers slice.",
                    "confidence": 0.62,
                }
            )
        if lm <= -8 or abs(lm) > gm + 6:
            contradicting.append(
                {
                    "signal": "risk_off_leaderboard_snapshot",
                    "detail": "Weak average performance on losers slice.",
                    "confidence": 0.58,
                }
            )
    else:
        rationale.append("Missing equities snapshot.")

    if all(snaps.get(f) for f in PATTERN_REGIME_FILES):
        s_count = sum(1 for x in supporting)
        c_count = sum(1 for x in contradicting)
        if c_count >= s_count + 1:
            regime = "BEAR"
        elif s_count >= c_count + 1:
            regime = "BULL"
        else:
            regime = "NEUTRAL"
    else:
        regime = "INSUFFICIENT_DATA"

    vc = supporting + contradicting
    conf_agg = round(
        base_conf * (sum(float(x["confidence"]) for x in vc) / max(len(vc), 1) / 1.05),
        3,
    )
    confidence = round(max(0.05, min(1.0, conf_agg if vc else base_conf * 0.5)), 3)

    return {
        "pattern": "regime_confirmation",
        "generated_at": iso_now_z(),
        "disclaimer": DISCLAIMER,
        "inputs": inp,
        "overall_confidence": confidence,
        "regime": regime,
        "supporting_signals": supporting,
        "contradicting_signals": contradicting,
        "rationale_hints": rationale,
    }


def _extract_sentiment_rows(obj: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("tickers", "mentions", "rows", "items", "sentiment"):
        v = obj.get(key)
        if isinstance(v, list):
            rows = [r for r in v if isinstance(r, dict)]
            if rows:
                return rows
    return []


def _retail_tone_from_row(row: dict[str, Any]) -> str | None:
    lbl = row.get("label") or row.get("sentiment") or row.get("tone")
    if isinstance(lbl, str):
        t = lbl.upper()
        if any(x in t for x in ("BULL", "POSITIVE", "GREED")):
            return "bullish_snapshot"
        if any(x in t for x in ("BEAR", "NEGATIVE", "FEAR")):
            return "bearish_snapshot"
    b = row.get("bullish_pct") or row.get("bull_pct")
    be = row.get("bearish_pct") or row.get("bear_pct")
    try:
        if b is not None and be is not None:
            bf, bef = float(b), float(be)
            if bf > bef * 1.2:
                return "bullish_snapshot"
            if bef > bf * 1.2:
                return "bearish_snapshot"
    except (TypeError, ValueError):
        pass
    s = row.get("score") or row.get("sentiment_score")
    try:
        if s is not None:
            v = float(s)
            if v > 0.2:
                return "bullish_snapshot"
            if v < -0.2:
                return "bearish_snapshot"
    except (TypeError, ValueError):
        pass
    return None


def _ticker_upper(row: dict[str, Any]) -> str | None:
    for k in ("ticker", "symbol", "underlying"):
        x = row.get(k)
        if isinstance(x, str) and x.strip():
            return x.strip().upper()
    return None


def _dark_pool_heavy(sym: str, dp_rows: dict[str, list[dict[str, Any]]]) -> tuple[bool, float]:
    import re

    for r in dp_rows.get(sym, []):
        for key in ("dark_pct", "pct_dark", "dark_volume_pct", "pct_block"):
            v = r.get(key)
            try:
                if v is None:
                    continue
                pct = float(re.sub(r"[^\d.\-]", "", str(v))) if isinstance(v, str) else float(v)
                return pct >= 15.0, pct
            except (TypeError, ValueError):
                continue
        for key in ("notional_mm",):
            try:
                n = float(r.get(key) or 0)
                if n >= 250:
                    return True, n
            except (TypeError, ValueError):
                pass
    return False, 0.0


def _collect_dark_pool(sym_map: dict[str, list[dict[str, Any]]], obj: dict[str, Any]) -> None:
    for key in ("blocks", "rows", "trades", "instruments"):
        lst = obj.get(key)
        if not isinstance(lst, list):
            continue
        for r in lst:
            if not isinstance(r, dict):
                continue
            t = _ticker_upper(r) or (
                str(r.get("underlying") or "").strip().upper() if r.get("underlying") else None
            )
            if t:
                sym_map[t].append(r)


def _options_flow_signals(opt_raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    if isinstance(opt_raw.get("unusual_activity"), list):
        rows.extend(r for r in opt_raw["unusual_activity"] if isinstance(r, dict))
    elif isinstance(opt_raw.get("rows"), list):
        rows.extend(r for r in opt_raw["rows"] if isinstance(r, dict))

    ticker_to_modes: dict[str, set[str]] = defaultdict(set)

    for r in rows:
        t = _ticker_upper(r)
        if not t:
            continue
        sig = str(r.get("signal") or "").upper()
        ot = str(r.get("type") or "").upper()
        if "BEAR" in sig or ot == "PUT":
            ticker_to_modes[t].add("bear_institutional_flow_proxy")
        elif "BULL" in sig or ot == "CALL":
            ticker_to_modes[t].add("bull_institutional_flow_proxy")

    for t, modes in ticker_to_modes.items():
        if modes == {"bear_institutional_flow_proxy"}:
            out[t] = "bear_institutional_flow_proxy"
        elif modes == {"bull_institutional_flow_proxy"}:
            out[t] = "bull_institutional_flow_proxy"
        else:
            out[t] = "mixed_institutional_flow_proxy"
    return out


def pattern_sentiment_divergence(snaps: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    inp = build_inputs_status(PATTERN_SENTIMENT_FILES, snaps, now_utc)
    base_conf = overall_conf_from_inputs(inp)

    if any(inp[f]["status"] != "present" for f in PATTERN_SENTIMENT_FILES):
        return {
            "pattern": "sentiment_vs_positioning_divergence",
            "generated_at": iso_now_z(),
            "disclaimer": DISCLAIMER,
            "inputs": inp,
            "overall_confidence": round(base_conf * 0.35, 3),
            "status": "INSUFFICIENT_DATA",
            "detail": "Requires sentiment_latest.json, dark_pool_latest.json, options_flow_latest.json.",
            "divergence_opportunities": [],
        }

    sent_raw = snaps["sentiment_latest.json"]
    dp_raw = snaps["dark_pool_latest.json"]
    opt_raw = snaps["options_flow_latest.json"]

    if not isinstance(sent_raw, dict) or not isinstance(dp_raw, dict) or not isinstance(
        opt_raw, dict
    ):
        return {
            "pattern": "sentiment_vs_positioning_divergence",
            "generated_at": iso_now_z(),
            "disclaimer": DISCLAIMER,
            "inputs": inp,
            "overall_confidence": round(base_conf * 0.3, 3),
            "status": "INSUFFICIENT_DATA",
            "detail": "Malformed JSON payloads for one or more required files.",
            "divergence_opportunities": [],
        }

    sent_rows = _extract_sentiment_rows(sent_raw)
    retail_by_ticker: dict[str, str | None] = {}
    for row in sent_rows:
        t = _ticker_upper(row)
        if not t:
            continue
        tone = _retail_tone_from_row(row)
        if tone:
            retail_by_ticker[t] = tone

    dp_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    _collect_dark_pool(dp_sym, dp_raw)

    opt_map = _options_flow_signals(opt_raw)

    symbols = set(retail_by_ticker) | set(opt_map) | set(dp_sym.keys())
    divergences: list[dict[str, Any]] = []

    for t in symbols:
        retail = retail_by_ticker.get(t)
        if not retail:
            continue
        inst = opt_map.get(t)
        if not inst:
            continue
        if inst.startswith("mixed"):
            continue

        divergence_type = ""

        heavy_dp, pct_val = _dark_pool_heavy(t, dp_sym)
        dp_note = (
            "heavy_dark_pool_pct_proxy"
            if heavy_dp
            else (
                "non_structured_dark_pool_row"
                if t in dp_sym
                else "no_dark_pool_row_for_ticker"
            )
        )

        if retail == "bullish_snapshot" and inst == "bear_institutional_flow_proxy":
            divergence_type = "retail_bullish_vs_institutional_flow_bear_proxy"
        elif retail == "bearish_snapshot" and inst == "bull_institutional_flow_proxy":
            divergence_type = "retail_bearish_vs_institutional_flow_bull_proxy"

        if divergence_type:

            ss = round(0.55 + base_conf * 0.08, 3)
            if heavy_dp:
                ss = round(min(0.93, ss + 0.12), 3)
            elif pct_val > 8:
                ss = round(min(0.9, ss + 0.06), 3)

            divergences.append(
                {
                    "ticker": t,
                    "retail_tone_proxy": retail,
                    "institutional_options_flow_proxy": inst,
                    "dark_pool_classification": dp_note,
                    "divergence_type": divergence_type,
                    "signal_strength_confidence": ss,
                    "confidence_note": (
                        "Strength scales with joint presence (sentiment ticker + directional flow)."
                        + (" Dark block percentage elevated vs threshold." if heavy_dp else "")
                    ),
                }
            )

    divergences.sort(key=lambda r: (-r["signal_strength_confidence"], r["ticker"]))

    overall = round(min(1.0, base_conf * (0.5 + min(10, len(divergences)) * 0.05)), 3)

    return {
        "pattern": "sentiment_vs_positioning_divergence",
        "generated_at": iso_now_z(),
        "disclaimer": DISCLAIMER,
        "inputs": inp,
        "overall_confidence": overall,
        "status": (
            "OK" if divergences else "NO_CROSS_SYMBOL_DIVERGENCE_IDENTIFIED_UNDER_SCHEMA"
        ),
        "detail": "",
        "divergence_opportunities": divergences[:40],
    }


def pattern_sector_rotation(snaps: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    sector_map = load_sector_map()
    inp = build_inputs_status(PATTERN_SECTOR_FILES, snaps, now_utc)
    ins_obj = snaps.get("insider_trades_latest.json")

    if inp["equities_latest.json"]["status"] != "present":
        inp_ext = dict(inp)
        inp_ext["sector_map_bundle"] = {
            "status": "reference_bundle_on_disk",
            "symbols_loaded": len(sector_map),
            "path": str(SECTOR_MAP_PATH),
        }
        return _sector_rotation_insufficient(
            snaps, now_utc, inp_ext, msg="MISSING EQUITIES CACHE"
        )

    if inp["insider_trades_latest.json"]["status"] != "present":
        combined = dict(inp)
        combined["sector_map_bundle"] = {
            "status": (
                "present" if sector_map else "missing"
            ),
            "freshness": "N/A",
            "generated_at": None,
        }
        return _sector_rotation_insufficient(
            snaps, now_utc, combined, msg="MISSING INSIDER CACHE"
        )

    if not sector_map:

        inp2 = dict(inp)
        inp2["sector_map_bundle"] = {
            "status": "missing",
            "freshness": "N/A",
            "generated_at": None,
            "detail": str(SECTOR_MAP_PATH),
        }
        base_conf = overall_conf_from_inputs(inp)
        return {
            "pattern": "sector_rotation",
            "generated_at": iso_now_z(),
            "disclaimer": DISCLAIMER,
            "inputs": inp2,
            "overall_confidence": round(base_conf * 0.35, 3),
            "status": "INSUFFICIENT_DATA",
            "detail": "Bundled sp500_symbol_sector.json missing.",
            "rotation_candidates": [],
        }

    filings = []
    if isinstance(ins_obj, dict) and isinstance(ins_obj.get("filings"), list):
        filings.extend(f for f in ins_obj["filings"] if isinstance(f, dict))

    insider_buy_by_sector: dict[str, list[str]] = defaultdict(list)

    for f in filings:
        ticker = str(f.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        sect = sector_map.get(ticker)
        if sect is None:
            continue
        tt = _tx_type_buy_sell_hint(f)

        if tt == "BUY_HINT":
            insider_buy_by_sector[sect].append(ticker)

    losers_syms = set()

    eq = snaps.get("equities_latest.json")
    if isinstance(eq, dict):
        _, lose, _ = _equity_buckets(eq)
        for sym, ch in lose:
            if ch < -1:
                losers_syms.add(sym)

    rotation_rows: list[dict[str, Any]] = []

    for sector, insider_syms_raw in insider_buy_by_sector.items():
        unique_insider_buys = sorted(set(insider_syms_raw))
        sell_overlap = losers_syms.intersection(unique_insider_buys)
        rotation_rows.append(
            {
                "sector": sector or "UNKNOWN",
                "tickers_insider_buy_proxy": unique_insider_buys[:15],
                "losers_overlap_with_insider_buy": sorted(sell_overlap)[:15],
                "evidence_notes": (
                    "Insiders show purchase-like heuristic while losers list overlaps same tickers "
                    "(retail liquidation proxy vs insiders)."
                ),
                "confidence": round(0.5 + min(15, len(unique_insider_buys)) * 0.02, 3),
                "confidence_note": "Heuristic linkage; causal claims not inferred.",
            }
        )

    rotation_rows.sort(
        key=lambda r: (-r["confidence"], -len(r["tickers_insider_buy_proxy"]), r["sector"])
    )

    inp2 = dict(inp)
    inp2["sector_map_bundle"] = {
        "status": "present",
        "freshness": "FRESH",
        "generated_at": None,
        "symbols_loaded": len(sector_map),
    }

    confidence = overall_conf_from_inputs(inp)
    confidence = round(
        confidence
        * (0.82 if rotation_rows else 0.52)
        * (1.03 if losers_syms else 0.9),
        3,
    )

    return {
        "pattern": "sector_rotation",
        "generated_at": iso_now_z(),
        "disclaimer": DISCLAIMER,
        "inputs": inp2,
        "overall_confidence": min(1.0, confidence),
        "rotation_thesis_preview": (
            "Sectors with insider-buy heuristics overlapping equity weak-list names "
            "describe a divergence between narrative retail pressure and insiders."
        ),
        "rotation_candidates": rotation_rows[:12],
        "counts": {
            "insider_buy_proxy_tickers_unique": sum(
                len(set(v)) for v in insider_buy_by_sector.values()
            ),
            "weak_equity_snapshots": len(losers_syms),
        },
    }


def _tx_type_buy_sell_hint(f: dict[str, Any]) -> str:
    tt = str(f.get("transaction_type") or "").upper()
    sg = str(f.get("signal") or "").upper()
    if (
        tt.startswith("B")
        or "BUY" in sg
        or "PURCH" in sg
        or sg == "ACCUMULATE"
    ):
        return "BUY_HINT"
    if "SELL" in sg or tt.startswith("S"):
        return "SELL_HINT"
    return ""


def _sector_rotation_insufficient(
    snaps: dict[str, Any],
    now_utc: datetime,
    inp_ext: dict[str, dict[str, Any]],
    *,
    msg: str,
) -> dict[str, Any]:
    base_conf = overall_conf_from_inputs(
        build_inputs_status(PATTERN_SECTOR_FILES, snaps, now_utc)
    )
    return {
        "pattern": "sector_rotation",
        "generated_at": iso_now_z(),
        "disclaimer": DISCLAIMER,
        "inputs": inp_ext,
        "overall_confidence": round(base_conf * 0.35, 3),
        "status": "INSUFFICIENT_DATA",
        "detail": msg,
        "rotation_candidates": [],
    }
def _stress_from_forex(fx: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    stresses: list[dict[str, Any]] = []
    score_accum = 0.0
    lst = fx.get("pairs") or fx.get("rows") or fx.get("rates")
    rows: list[dict[str, Any]] = lst if isinstance(lst, list) else []

    def pct_from(row: dict[str, Any]) -> tuple[str, float]:
        pct = row.get("change_pct")
        if pct is None:
            for k in ("day_change_pct", "move_pct", "pct_change", "pctChg"):
                pct = row.get(k)
                if pct is not None:
                    break
        lbl = str(
            row.get("pair")
            or row.get("symbol")
            or row.get("ccy_pair")
            or row.get("fx_pair")
            or row.get("ticker")
            or ""
        ).strip()
        try:
            pct_f = float(pct if pct is not None else 0.0)
        except (TypeError, ValueError):
            pct_f = 0.0
        return lbl, pct_f

    for row in rows:
        if not isinstance(row, dict):
            continue
        lbl, pct_f = pct_from(row)
        if abs(pct_f) < 1.5:
            continue
        lvl = min(abs(pct_f) / 8.0, 1.0)
        score_accum += lvl * 2.25
        stresses.append(
            {
                "domain": "forex",
                "label": lbl or "pair_unknown",
                "change_pct_estimate": pct_f,
                "confidence": 0.62,
                "confidence_note": "Pct move heuristic (>1.5 pct threshold).",
            }
        )

    quotes = fx.get("quotes")
    if isinstance(quotes, dict):
        for sym, qr in quotes.items():
            if not isinstance(qr, dict):
                continue
            try:
                ch = float(qr.get("change_pct") or qr.get("move_pct") or 0)
            except (TypeError, ValueError):
                ch = 0.0
            if abs(ch) < 1.5:
                continue
            score_accum += 1.1
            stresses.append(
                {
                    "domain": "forex",
                    "label": str(sym),
                    "change_pct_estimate": ch,
                    "confidence": 0.55,
                    "confidence_note": "quotes map pct.",
                }
            )

    return stresses, score_accum


def _stress_from_commodities(cm: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    stresses: list[dict[str, Any]] = []
    score_accum = 0.0
    baskets: list[list[Any]] = []
    for key in ("commodities", "instruments", "rows", "energy", "metals"):
        b = cm.get(key)
        if isinstance(b, list):
            baskets.append(b)

    for basket in baskets:
        for row in basket:
            if not isinstance(row, dict):
                continue
            pct = row.get("change_pct") or row.get("pct_change")
            lbl = str(row.get("name") or row.get("symbol") or row.get("ticker") or "").strip()
            try:
                ch = float(pct)
            except (TypeError, ValueError):
                continue
            if abs(ch) < 3.5:
                continue
            score_accum += min(abs(ch) / 14.0, 1.0) * 2.4
            stresses.append(
                {
                    "domain": "commodities",
                    "label": lbl or "instrument",
                    "change_pct_estimate": ch,
                    "confidence": 0.56,
                    "confidence_note": ">3.5 pct threshold heuristic.",
                }
            )

    return stresses, score_accum


def pattern_cross_asset_stress(snaps: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    inp = build_inputs_status(PATTERN_STRESS_FILES, snaps, now_utc)
    base_conf = overall_conf_from_inputs(inp)
    stresses: list[dict[str, Any]] = []
    agg_pts = 0.0

    fx = snaps.get("forex_latest.json")
    cm = snaps.get("commodities_latest.json")
    bn = snaps.get("bond_yields_latest.json")

    if inp["forex_latest.json"]["status"] == "present" and isinstance(fx, dict):
        lst, pts = _stress_from_forex(fx)
        stresses.extend(lst)
        agg_pts += pts

    if inp["commodities_latest.json"]["status"] == "present" and isinstance(cm, dict):
        lst, pts = _stress_from_commodities(cm)
        stresses.extend(lst)
        agg_pts += pts

    if inp["bond_yields_latest.json"]["status"] == "present" and isinstance(bn, dict):
        sig = str(bn.get("curve_signal") or "").upper()
        if sig == "INVERTED":
            try:
                sp = float(bn.get("spread_2y_10y") or 0)
            except (TypeError, ValueError):
                sp = 0.0
            stresses.append(
                {
                    "domain": "rates",
                    "label": "treasury_curve_snapshot",
                    "change_pct_estimate": sp,
                    "confidence": 0.7,
                    "confidence_note": "INVERTED snapshot flag.",
                }
            )
            agg_pts += 2.2
        elif sig == "FLAT":
            agg_pts += 0.85

    missing_all = (
        inp["forex_latest.json"]["status"] != "present"
        and inp["commodities_latest.json"]["status"] != "present"
        and inp["bond_yields_latest.json"]["status"] != "present"
    )

    if missing_all:
        macro = round(10 * base_conf * 0.38, 1)
        return {
            "pattern": "cross_asset_stress",
            "generated_at": iso_now_z(),
            "disclaimer": DISCLAIMER,
            "inputs": inp,
            "overall_confidence": round(max(0.12, base_conf * 0.45), 3),
            "macro_risk_score": min(10.0, macro),
            "stress_highlights": [],
            "notes": (
                "All inputs missing. Populate forex_latest.json, commodities_latest.json, bond_yields_latest.json."
            ),
        }

    macro = round(min(10.0, (agg_pts / 6.2) * (0.76 + base_conf * 0.22)), 1)
    stresses.sort(key=lambda r: (-float(r["confidence"]), r["domain"], r["label"]))

    return {
        "pattern": "cross_asset_stress",
        "generated_at": iso_now_z(),
        "disclaimer": DISCLAIMER,
        "inputs": inp,
        "overall_confidence": round(min(1.0, 0.52 + macro / 25.5 + base_conf * 0.18), 3),
        "macro_risk_score": macro,
        "stress_highlights": stresses[:20],
        "stress_point_total_raw": round(agg_pts, 4),
        "confidence_note": "Combines pct shocks across assets plus curve heuristic.",
    }


def build_markdown_brief(now_utc: datetime, payloads: dict[str, dict[str, Any]]) -> str:
    order = {"regime": 0, "sentiment": 1, "sector": 2, "stress": 3}
    hdr = sorted(payloads.keys(), key=lambda k: order.get(k, 99))

    lines: list[str] = [
        "# Intelligence synthesizer briefing",
        "",
        f"Synthesis UTC: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        DISCLAIMER,
        "",
    ]
    for key in hdr:
        body = payloads[key]
        pname = body.get("pattern") or key
        lines.append(f"## {key} ({pname})")
        lines.append(f"- overall_confidence: {body.get('overall_confidence')}")
        reg = body.get("regime")
        if reg is not None:
            lines.append(f"- regime: `{reg}`")
        st = body.get("status")
        if st is not None:
            lines.append(f"- status: `{st}`")
        dt = body.get("detail")
        if dt:
            lines.append(f"- detail: {dt}")
        mrs = body.get("macro_risk_score")
        if mrs is not None:
            lines.append(f"- macro_risk_score (0–10): {mrs}")
        dives = body.get("divergence_opportunities")
        if dives is not None:
            lines.append(f"- divergence tickers: {len(dives)}")
        rots = body.get("rotation_candidates")
        if rots is not None:
            lines.append(f"- sector rotation clusters: {len(rots)}")
        lines.append("")
        inp = body.get("inputs") or {}
        lines.append("| file | status | freshness | generated_at |")
        lines.append("| --- | --- | --- | --- |")
        for fn in sorted(inp.keys()):
            meta = inp[fn]
            if not isinstance(meta, dict):
                lines.append(f"| {fn} | ? | — | — |")
                continue
            gd = meta.get("generated_at")
            lines.append(
                f"| {fn} | {meta.get('status')} | {meta.get('freshness')} | {gd or '—'} |"
            )
            fd = meta.get("freshness_detail")
            if fd:
                lines.append(f"  - {fd}")
        lines.append("")

    lines.append("## data_cache catalog")
    cat = snapshot_catalog(now_utc)
    for row in cat.get("files") or []:
        parts = [str(row.get("file")), str(row.get("category")), str(row.get("freshness"))]
        if row.get("generated_at"):
            parts.append(f"gen_at={row.get('generated_at')}")
        if row.get("freshness_note"):
            parts.append(row["freshness_note"])
        lines.append("- " + ", ".join(p for p in parts if p and p != "None"))

    return "\n".join(lines) + "\n"


RUN_SPECS: list[tuple[str, Any, str, str]] = [
    ("regime", pattern_regime, "synthesis_regime_latest.json", "synthesis_regime_"),
    (
        "sentiment",
        pattern_sentiment_divergence,
        "synthesis_sentiment_divergence_latest.json",
        "synthesis_sentiment_divergence_",
    ),
    ("sector", pattern_sector_rotation, "synthesis_sector_rotation_latest.json", "synthesis_sector_rotation_"),
    (
        "stress",
        pattern_cross_asset_stress,
        "synthesis_cross_asset_stress_latest.json",
        "synthesis_cross_asset_stress_",
    ),
]


def persist_synthesis(
    payload: dict[str, Any],
    stable_filename: str,
    stamped_prefix: str,
    *,
    write_stamped: bool,
) -> tuple[Path, Path | None]:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if write_stamped:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from atlas_core.utils.agent_utils import write_cache_json_pair

        sp, tsp = write_cache_json_pair(
            DATA_CACHE_DIR,
            payload,
            stable_filename=stable_filename,
            stamped_prefix=stamped_prefix,
        )

        return sp, tsp

    stable_path = DATA_CACHE_DIR / stable_filename
    text = json.dumps(payload, indent=2, default=str) + "\n"
    stable_path.write_text(text, encoding="utf-8")
    return stable_path, None

def run_synthesis(
    pattern: str = "all",
    *,
    write_stamped: bool = True,
    write_vault: bool = True,
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    snaps = load_agent_snapshots()

    sel = pattern.strip().lower()
    choice_index = {"regime": 0, "sentiment": 1, "sector": 2, "stress": 3}

    if sel == "catalog":
        return {"catalog": snapshot_catalog(now_utc)}
    if sel == "all":
        specs = RUN_SPECS
    elif sel in choice_index:
        specs = [RUN_SPECS[choice_index[sel]]]
    else:
        raise ValueError(f"unknown pattern `{pattern}`")

    payloads: dict[str, dict[str, Any]] = {}
    written_records: list[dict[str, Any]] = []

    for key, runner, stable, prefixed in specs:
        payloads[key] = runner(snaps, now_utc)
        spath, tstamped = persist_synthesis(
            payloads[key], stable, prefixed, write_stamped=write_stamped
        )
        written_records.append(
            {
                "key": key,
                "stable_path": str(spath),
                "timestamped_path": str(tstamped) if tstamped else None,
            }
        )

    if write_vault:
        VAULT_NOTES_DIR.mkdir(parents=True, exist_ok=True)
        note_path = VAULT_NOTES_DIR / f"synthesis_{now_utc.date().isoformat()}.md"
        blob = build_markdown_brief(now_utc, payloads)
        sep = f"\n\n---\n\nRe-run {iso_now_z()} batch `{pattern}`.\n\n"
        if note_path.is_file():
            prev = note_path.read_text(encoding="utf-8")
            note_path.write_text(prev.rstrip() + sep + blob, encoding="utf-8")
        else:
            note_path.write_text(blob, encoding="utf-8")

    return {
        "generated_at_run": iso_now_z(),
        "pattern_request": sel,
        "payloads": payloads,
        "json_written": written_records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="ATLAS Intelligence Synthesizer.")
    ap.add_argument(
        "--pattern",
        default="all",
        choices=["all", "regime", "sentiment", "sector", "stress", "catalog"],
    )
    ap.add_argument("--no-stamped-copy", action="store_true")
    ap.add_argument("--no-vault", action="store_true")
    ns = ap.parse_args()
    try:
        if ns.pattern == "catalog":
            print(json.dumps(snapshot_catalog(datetime.now(timezone.utc)), indent=2, default=str))
            return
        summary = run_synthesis(
            pattern=ns.pattern,
            write_stamped=not ns.no_stamped_copy,
            write_vault=not ns.no_vault,
        )

        msg = {"ok": True, "pattern": summary["pattern_request"], "keys": list(summary["payloads"])}
        print(json.dumps(msg, indent=2))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
