"""Generate compact summary files for R.A. Omega data caches.

Raw `*_latest.json` cache files are useful for deep inspection, but they are too
large to inject into every model call. This module creates a `*_summary.json`
companion for each cache with the smallest useful set of signals.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_CACHE_DIR = ROOT / "data_cache"
SUMMARY_DIR = DATA_CACHE_DIR / "summaries"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pick_symbol(row: dict[str, Any]) -> str:
    for key in ("symbol", "ticker", "asset", "name", "id"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


def list_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    preferred = [
        "items",
        "records",
        "signals",
        "trades",
        "rates",
        "commodities",
        "pairs",
        "alerts",
        "upcoming",
        "clusters",
        "ads",
        "cards",
        "cities",
        "segments",
        "sales",
        "loans",
        "companies",
        "tickers",
    ]
    out: list[dict[str, Any]] = []
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list):
            out.extend(x for x in value if isinstance(x, dict))
    if out:
        return out
    for value in payload.values():
        if isinstance(value, list):
            out.extend(x for x in value if isinstance(x, dict))
    return out


def top_by(rows: list[dict[str, Any]], keys: tuple[str, ...], reverse: bool = True) -> dict[str, Any]:
    if not rows:
        return {}
    def score(row: dict[str, Any]) -> float:
        return max(number(row.get(key)) for key in keys)
    return dict(sorted(rows, key=score, reverse=reverse)[0])


def row_delta(row: dict[str, Any]) -> float:
    return max(number(row.get(key)) for key in ("change_pct", "pct_change", "change_percent", "change", "return_pct"))


def classify_signal(values: list[float]) -> str:
    if not values:
        return "NEUTRAL"
    avg = sum(values) / len(values)
    if avg > 0.75:
        return "BULLISH"
    if avg < -0.75:
        return "BEARISH"
    return "MIXED"


def generic_summary(name: str, payload: Any) -> dict[str, Any]:
    rows = list_items(payload)
    generated = payload.get("generated_at") if isinstance(payload, dict) else ""
    record_count = payload.get("record_count") if isinstance(payload, dict) else len(rows)
    deltas = [row_delta(row) for row in rows if row_delta(row) != 0]
    top = top_by(rows, ("change_pct", "pct_change", "change", "return_pct"))
    if top is None or row_delta(top) == 0:
        top = top_by(rows, ("score", "signal_score", "volume"))
    low = top_by(rows, ("change_pct", "pct_change", "change"), reverse=False)
    sectors = Counter(str(row.get("sector") or row.get("category") or row.get("segment") or "") for row in rows)
    sectors.pop("", None)
    payload_keys = sorted(payload.keys())[:16] if isinstance(payload, dict) else []
    return {
        "generated_at": utc_now(),
        "source_generated_at": generated,
        "source_cache": name,
        "record_count": int(number(record_count, len(rows))),
        "signal": classify_signal(deltas),
        "top_signal": {
            "id": pick_symbol(top),
            "change_pct": row_delta(top),
            "label": str(top.get("signal") or top.get("rating") or top.get("trend") or ""),
        } if top else {},
        "weakest_signal": {
            "id": pick_symbol(low),
            "change_pct": row_delta(low),
            "label": str(low.get("signal") or low.get("rating") or low.get("trend") or ""),
        } if low else {},
        "dominant_category": sectors.most_common(1)[0][0] if sectors else "",
        "important_keys": payload_keys,
    }


def summarize_crypto_top50(payload: dict[str, Any], name: str) -> dict[str, Any]:
    rows = list_items(payload)
    top = top_by(rows, ("change_pct", "pct_change", "change"))
    low = top_by(rows, ("change_pct", "pct_change", "change"), reverse=False)
    vol = top_by(rows, ("volume_usd", "volume", "quote_volume"))
    meme_count = sum(1 for row in rows if "meme" in str(row.get("category", "")).lower())
    utility_count = sum(1 for row in rows if "utility" in str(row.get("category", "")).lower())
    deltas = [row_delta(row) for row in rows if row_delta(row) != 0]
    signal = classify_signal(deltas)
    regime = "RISK_ON" if signal == "BULLISH" else "RISK_OFF" if signal == "BEARISH" else "NEUTRAL"
    return {
        "generated_at": utc_now(),
        "top_gainer": {"symbol": pick_symbol(top), "change_pct": row_delta(top)} if top else {"symbol": "", "change_pct": 0},
        "top_loser": {"symbol": pick_symbol(low), "change_pct": row_delta(low)} if low else {"symbol": "", "change_pct": 0},
        "highest_volume": {"symbol": pick_symbol(vol), "volume_usd": number(vol.get("volume_usd") or vol.get("volume"))} if vol else {"symbol": "", "volume_usd": 0},
        "meme_count": meme_count,
        "utility_count": utility_count,
        "market_regime": regime,
        "signal": signal,
    }


def summarize_equities(payload: dict[str, Any], name: str) -> dict[str, Any]:
    gainers = [x for x in payload.get("gainers", []) if isinstance(x, dict)] if isinstance(payload, dict) else []
    losers = [x for x in payload.get("losers", []) if isinstance(x, dict)] if isinstance(payload, dict) else []
    rows = gainers + losers or list_items(payload)
    top = top_by(gainers or rows, ("change_pct", "pct_change", "change"))
    low = top_by(losers or rows, ("change_pct", "pct_change", "change"), reverse=False)
    active = top_by(rows, ("volume", "avg_volume_3m"))
    sectors = Counter(str(row.get("sector") or row.get("bucket") or "") for row in rows)
    hot = Counter(str(row.get("sector") or row.get("bucket") or "") for row in gainers)
    cold = Counter(str(row.get("sector") or row.get("bucket") or "") for row in losers)
    sectors.pop("", None); hot.pop("", None); cold.pop("", None)
    breadth = "EXPANDING" if len(gainers) > len(losers) else "CONTRACTING" if len(losers) > len(gainers) else "NEUTRAL"
    return {
        "generated_at": utc_now(),
        "top_gainer": {"ticker": pick_symbol(top), "change_pct": row_delta(top), "sector": str(top.get("sector") or top.get("bucket") or "")} if top else {"ticker": "", "change_pct": 0, "sector": ""},
        "top_loser": {"ticker": pick_symbol(low), "change_pct": row_delta(low), "sector": str(low.get("sector") or low.get("bucket") or "")} if low else {"ticker": "", "change_pct": 0, "sector": ""},
        "most_active": {"ticker": pick_symbol(active), "volume": number(active.get("volume"))} if active else {"ticker": "", "volume": 0},
        "hot_sector": hot.most_common(1)[0][0] if hot else sectors.most_common(1)[0][0] if sectors else "",
        "cold_sector": cold.most_common(1)[0][0] if cold else "",
        "breadth_signal": breadth,
    }


def summarize_options_flow(payload: dict[str, Any], name: str) -> dict[str, Any]:
    rows = payload.get("unusual_activity", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    calls = [row for row in rows if str(row.get("type", "")).upper() == "CALL"]
    puts = [row for row in rows if str(row.get("type", "")).upper() == "PUT"]
    def pack(row: dict[str, Any]) -> dict[str, Any]:
        return {"ticker": pick_symbol(row), "signal_strength": str(row.get("signal") or row.get("volume_oi_ratio") or "")}
    call_vol = sum(number(row.get("volume")) for row in calls)
    put_vol = sum(number(row.get("volume")) for row in puts)
    ratio_signal = "BULLISH" if call_vol > put_vol * 1.2 else "BEARISH" if put_vol > call_vol * 1.2 else "NEUTRAL"
    conviction = top_by(rows, ("volume_oi_ratio", "volume"))
    return {
        "generated_at": utc_now(),
        "unusual_calls": [pack(row) for row in sorted(calls, key=lambda x: number(x.get("volume_oi_ratio")), reverse=True)[:5]],
        "unusual_puts": [pack(row) for row in sorted(puts, key=lambda x: number(x.get("volume_oi_ratio")), reverse=True)[:5]],
        "put_call_ratio_signal": ratio_signal,
        "top_conviction_ticker": pick_symbol(conviction),
    }


def summarize_bond_yields(payload: dict[str, Any], name: str) -> dict[str, Any]:
    rows = list_items(payload)
    flat = payload if isinstance(payload, dict) else {}
    two = number(flat.get("2y_rate") or flat.get("two_year") or flat.get("us2y"))
    ten = number(flat.get("10y_rate") or flat.get("ten_year") or flat.get("us10y"))
    for row in rows:
        label = str(row.get("maturity") or row.get("tenor") or row.get("name") or "").lower()
        if "2" in label and "y" in label:
            two = number(row.get("rate") or row.get("yield"), two)
        if "10" in label and "y" in label:
            ten = number(row.get("rate") or row.get("yield"), ten)
    spread = round(ten - two, 4)
    curve = "INVERTED" if spread < -0.1 else "FLAT" if abs(spread) <= 0.1 else "NORMAL"
    recession = "HIGH" if curve == "INVERTED" else "MEDIUM" if curve == "FLAT" else "LOW"
    return {
        "generated_at": utc_now(),
        "curve_signal": curve,
        "recession_signal": recession,
        "2y_rate": two,
        "10y_rate": ten,
        "spread_2y_10y": spread,
    }


def summarize_cpi(payload: dict[str, Any], name: str) -> dict[str, Any]:
    flat = payload if isinstance(payload, dict) else {}
    yoy = number(flat.get("yoy_change_pct") or flat.get("cpi_yoy") or flat.get("headline_yoy") or flat.get("yoy"))
    trend = str(flat.get("trend") or "").upper()
    if trend not in {"ACCELERATING", "DECELERATING", "STABLE"}:
        trend = "STABLE"
    hot = flat.get("hot_categories") if isinstance(flat.get("hot_categories"), list) else []
    fed = "HAWKISH" if yoy >= 3.0 or trend == "ACCELERATING" else "DOVISH" if yoy <= 2.2 and trend == "DECELERATING" else "NEUTRAL"
    return {
        "generated_at": utc_now(),
        "yoy_change_pct": yoy,
        "trend": trend,
        "hot_categories": hot[:6],
        "fed_implication": fed,
    }


def summarize_congress_trades(payload: dict[str, Any], name: str) -> dict[str, Any]:
    rows = payload.get("trades", []) if isinstance(payload, dict) else []
    rows = [row for row in rows if isinstance(row, dict)]
    buys = [row for row in rows if "buy" in str(row.get("action") or row.get("transaction") or "").lower()]
    sells = [row for row in rows if "sell" in str(row.get("action") or row.get("transaction") or "").lower()]
    buy_counts = Counter(pick_symbol(row) for row in buys if pick_symbol(row))
    sell_counts = Counter(pick_symbol(row) for row in sells if pick_symbol(row))
    sentiment = "BULLISH" if len(buys) > len(sells) else "BEARISH" if len(sells) > len(buys) else "MIXED"
    notable = rows[0] if rows else {}
    return {
        "generated_at": utc_now(),
        "most_bought_tickers": [x for x, _ in buy_counts.most_common(5)],
        "most_sold_tickers": [x for x, _ in sell_counts.most_common(5)],
        "net_sentiment": sentiment,
        "notable_trade": {
            "member": str(notable.get("member") or notable.get("representative") or notable.get("name") or ""),
            "ticker": pick_symbol(notable),
            "action": str(notable.get("action") or notable.get("transaction") or ""),
        },
    }


SPECIAL_SUMMARIZERS = {
    "crypto_top50": summarize_crypto_top50,
    "equities": summarize_equities,
    "options_flow": summarize_options_flow,
    "bond_yields": summarize_bond_yields,
    "cpi": summarize_cpi,
    "inflation": summarize_cpi,
    "congress_trades": summarize_congress_trades,
}


def summary_name_for_cache(path: Path) -> str:
    stem = path.stem
    if stem.endswith("_latest"):
        stem = stem[: -len("_latest")]
    return f"{stem}_summary.json"


def summarize_cache(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    stem = path.stem[: -len("_latest")] if path.stem.endswith("_latest") else path.stem
    summarizer = SPECIAL_SUMMARIZERS.get(stem)
    if summarizer and isinstance(payload, dict):
        return summarizer(payload, path.name)
    return generic_summary(path.name, payload)


def generate_all(data_cache_dir: Path = DATA_CACHE_DIR, summary_dir: Path = SUMMARY_DIR) -> dict[str, Any]:
    latest_files = sorted(data_cache_dir.glob("*_latest.json"))
    outputs: list[str] = []
    errors: list[dict[str, str]] = []
    for path in latest_files:
        try:
            summary = summarize_cache(path)
            out = summary_dir / summary_name_for_cache(path)
            write_json(out, summary)
            try:
                outputs.append(out.relative_to(ROOT).as_posix())
            except ValueError:
                outputs.append(out.as_posix())
        except Exception as exc:  # keep one bad cache from blocking the whole pantry
            errors.append({"cache": path.name, "error": str(exc)})
    return {
        "ok": not errors,
        "generated_at": utc_now(),
        "cache_files": len(latest_files),
        "summary_files": len(outputs),
        "outputs": outputs,
        "errors": errors,
    }


def main() -> int:
    result = generate_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
