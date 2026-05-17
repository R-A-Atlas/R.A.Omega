"""
intelligence_hub.py — R.A. Omega Intelligence Hub

Aggregates signals from all 64 data_cache domains into a structured
hub snapshot. Powers GET /hub/snapshot and GET /hub/brief.

Reads from data_cache/*_latest.json files — no live API calls.
Sub-second, safe to call on every dashboard load.

Usage:
    from intelligence_hub import get_snapshot, get_brief
    snap = get_snapshot()
    brief = get_brief()
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "data_cache"

# ── Signal categories ─────────────────────────────────────────────────────────

CATEGORIES: dict[str, list[str]] = {
    "market": [
        "equities", "options_flow", "dark_pool", "earnings", "earnings_season_brief",
        "sector_rotation", "regime_change", "correlation", "penny_stocks",
    ],
    "macro": [
        "global_liquidity", "tariffs", "jobs", "energy", "supply_chain",
        "forex", "commodities", "congress_trades", "consumer_alerts",
    ],
    "intelligence": [
        "insider_trades", "sec_filings", "news_catalysts", "sentiment",
        "sentiment_divergence", "risk_budget", "climate_risk",
    ],
    "real_estate": [
        "mortgage_rates", "residential", "commercial", "rental_yield",
        "reits", "zoning", "str",
    ],
    "personal_finance": [
        "hysa", "credit_cards", "auto_loans", "student_debt",
        "personal_loans", "insurance", "retirement_limits", "col", "bankruptcy",
    ],
    "alternative": [
        "metals", "art", "watches", "collectibles", "p2p",
    ],
    "business": [
        "saas_metrics", "ecommerce", "franchise", "freelance_rates",
        "sba", "vc_deals", "labor_law", "federal_tax", "state_tax",
    ],
    "marketing": [
        "competitor_ads", "seo_keywords", "email_health", "engagement",
        "reviews", "roas", "leads", "crm_sync",
    ],
}

_DIRECTION_COLORS = {
    "bullish": "#10b981",
    "bearish": "#ef4444",
    "neutral": "#f59e0b",
    "mixed":   "#8b5cf6",
    "rising":  "#10b981",
    "falling": "#ef4444",
    "stable":  "#f59e0b",
    "unknown": "#64748b",
}

_CATEGORY_ICONS = {
    "market": "📈", "macro": "🌐", "intelligence": "🧠",
    "real_estate": "🏠", "personal_finance": "💰",
    "alternative": "💎", "business": "🏢", "marketing": "📣",
}


# ── Signal dataclass (plain dict for JSON serialisability) ────────────────────

def _signal(
    name: str,
    category: str,
    value: str,
    direction: str = "neutral",
    confidence: float = 0.8,
    detail: str = "",
    source: str = "data_cache",
    ts: str = "",
) -> dict:
    return {
        "name": name,
        "category": category,
        "value": value,
        "direction": direction,
        "color": _DIRECTION_COLORS.get(direction, "#64748b"),
        "confidence": confidence,
        "detail": detail,
        "source": source,
        "ts": ts,
    }


# ── Per-domain signal extractors ──────────────────────────────────────────────

def _ts(d: dict) -> str:
    return str(d.get("generated_at", ""))[:19]


def _load(name: str) -> Optional[dict]:
    p = CACHE_DIR / f"{name}_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_signal(domain: str, category: str) -> Optional[dict]:
    d = _load(domain)
    if not d:
        return None
    ts = _ts(d)

    # ── Market ──────────────────────────────────────────────────────────────
    if domain == "regime_change":
        regime = str(d.get("regime", "unknown")).upper()
        conf = float(d.get("confidence", 0.8))
        posture = str(d.get("recommended_posture", "")).lower()
        direction = "bullish" if "bull" in regime.lower() else "bearish" if "bear" in regime.lower() else "neutral"
        return _signal("Market Regime", category, regime, direction, conf, posture, ts=ts)

    if domain == "sector_rotation":
        leading = d.get("leading_sectors", [])
        lagging = d.get("lagging_sectors", [])
        lead_str = ", ".join(leading[:3]) if leading else "—"
        lag_str  = ", ".join(lagging[:2]) if lagging else "—"
        return _signal("Sector Rotation", category, f"Leading: {lead_str}", "mixed", 0.82,
                       f"Lagging: {lag_str}", ts=ts)

    if domain == "equities":
        gainers = d.get("gainers", [])
        losers  = d.get("losers", [])
        g = len(gainers); l = len(losers)
        direction = "bullish" if g > l else "bearish" if l > g else "neutral"
        top = gainers[0].get("ticker", "") if gainers else "—"
        return _signal("Equities", category, f"{g} gainers / {l} losers", direction, 0.85,
                       f"Top: {top}", ts=ts)

    if domain == "options_flow":
        signals = d.get("unusual_activity", [])
        bullish_ct = sum(1 for s in signals if "bull" in str(s.get("direction","")).lower() or "call" in str(s.get("type","")).lower())
        bear_ct    = sum(1 for s in signals if "bear" in str(s.get("direction","")).lower() or "put"  in str(s.get("type","")).lower())
        direction  = "bullish" if bullish_ct > bear_ct else "bearish" if bear_ct > bullish_ct else "neutral"
        return _signal("Options Flow", category, f"{len(signals)} unusual prints", direction, 0.88,
                       f"{bullish_ct} bullish / {bear_ct} bearish", ts=ts)

    if domain == "dark_pool":
        signals = d.get("signals", [])
        total = d.get("record_count", len(signals))
        return _signal("Dark Pool", category, f"{total} block prints", "neutral", 0.80,
                       "Institutional positioning data", ts=ts)

    if domain == "earnings":
        rec = d.get("record_count", 0)
        return _signal("Earnings", category, f"{rec} reports tracked", "neutral", 0.85, ts=ts)

    if domain == "earnings_season_brief":
        summary = str(d.get("summary", d.get("brief", "")))[:80]
        return _signal("Earnings Season", category, summary or "Active season", "mixed", 0.82, ts=ts)

    if domain == "correlation":
        return _signal("Correlation", category, "Cross-asset correlation matrix live", "neutral", 0.78, ts=ts)

    if domain == "penny_stocks":
        rec = d.get("record_count", 0)
        return _signal("Penny Stocks", category, f"{rec} scanned", "neutral", 0.70, ts=ts)

    # ── Macro ────────────────────────────────────────────────────────────────
    if domain == "global_liquidity":
        m2 = d.get("m2_trillions_usd", d.get("m2_billions_usd", 0))
        mom = d.get("mom_change_pct", 0)
        direction = "bullish" if float(mom or 0) > 0 else "bearish"
        return _signal("Global Liquidity (M2)", category, f"${m2}T", direction, 0.85,
                       f"MoM: {mom:+.2f}%" if mom else "", ts=ts)

    if domain == "tariffs":
        rec = d.get("record_count", 0)
        return _signal("Tariffs & Trade", category, f"{rec} active tariff signals", "bearish", 0.80, ts=ts)

    if domain == "jobs":
        rate = d.get("unemployment_rate", d.get("rate", ""))
        return _signal("Jobs Market", category, f"Unemployment: {rate}%" if rate else "Live data", "neutral", 0.85, ts=ts)

    if domain == "energy":
        return _signal("Energy Markets", category, "Oil, Gas & Grid live", "neutral", 0.80, ts=ts)

    if domain == "supply_chain":
        rec = d.get("record_count", 0)
        return _signal("Supply Chain", category, f"{rec} indicators tracked", "neutral", 0.78, ts=ts)

    if domain == "forex":
        rec = d.get("record_count", 0)
        return _signal("Forex", category, f"{rec} pairs tracked", "neutral", 0.80, ts=ts)

    if domain == "commodities":
        rec = d.get("record_count", 0)
        return _signal("Commodities", category, f"{rec} commodities live", "mixed", 0.82, ts=ts)

    if domain == "congress_trades":
        rec = d.get("record_count", 0)
        return _signal("Congress Trades", category, f"{rec} disclosures", "mixed", 0.90,
                       "Congressional trading activity", ts=ts)

    if domain == "consumer_alerts":
        rec = d.get("record_count", 0)
        return _signal("Consumer Alerts", category, f"{rec} active alerts", "bearish", 0.75, ts=ts)

    # ── Intelligence ─────────────────────────────────────────────────────────
    if domain == "insider_trades":
        rec = d.get("record_count", 0)
        buy_ct  = len([x for x in d.get("transactions", []) if "buy" in str(x.get("type","")).lower()])
        sell_ct = len([x for x in d.get("transactions", []) if "sell" in str(x.get("type","")).lower()])
        direction = "bullish" if buy_ct > sell_ct else "bearish" if sell_ct > buy_ct else "neutral"
        return _signal("Insider Trades", category, f"{rec} transactions", direction, 0.92,
                       f"{buy_ct} buys / {sell_ct} sells", ts=ts)

    if domain == "sec_filings":
        rec = d.get("record_count", 0)
        return _signal("SEC Filings", category, f"{rec} recent filings", "neutral", 0.88, ts=ts)

    if domain == "news_catalysts":
        events = d.get("events", d.get("catalysts", []))
        rec = d.get("record_count", len(events))
        return _signal("News Catalysts", category, f"{rec} active catalysts", "mixed", 0.85, ts=ts)

    if domain == "sentiment":
        topics = d.get("topics", [])
        bullish = sum(1 for t in topics if str(t.get("sentiment","")).lower() in ("positive","bullish"))
        bearish = sum(1 for t in topics if str(t.get("sentiment","")).lower() in ("negative","bearish"))
        direction = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"
        return _signal("Market Sentiment", category, f"{len(topics)} topics scanned", direction, 0.82,
                       f"{bullish} positive / {bearish} negative", ts=ts)

    if domain == "sentiment_divergence":
        return _signal("Sentiment Divergence", category, "Divergence scan live", "mixed", 0.80, ts=ts)

    if domain == "risk_budget":
        return _signal("Risk Budget", category, "Portfolio risk metrics live", "neutral", 0.88, ts=ts)

    if domain == "climate_risk":
        rec = d.get("record_count", 0)
        return _signal("Climate Risk", category, f"{rec} risk factors tracked", "bearish", 0.72, ts=ts)

    # ── Real Estate ──────────────────────────────────────────────────────────
    if domain == "mortgage_rates":
        trend = str(d.get("trend", "stable"))
        wow   = d.get("wow_change_30y", 0)
        direction = "bearish" if "rising" in trend.lower() or float(wow or 0) > 0 else "bullish" if "falling" in trend.lower() else "neutral"
        return _signal("Mortgage Rates (30yr)", category, f"Trend: {trend}", direction, 0.90,
                       f"WoW: {wow:+.3f}%" if wow else "", ts=ts)

    if domain == "residential":
        rec = d.get("record_count", 0)
        return _signal("Residential Market", category, f"{rec} listings tracked", "neutral", 0.80, ts=ts)

    if domain == "commercial":
        rec = d.get("record_count", 0)
        return _signal("Commercial RE", category, f"{rec} properties tracked", "neutral", 0.78, ts=ts)

    if domain == "rental_yield":
        rec = d.get("record_count", 0)
        return _signal("Rental Yields", category, f"{rec} markets tracked", "neutral", 0.82, ts=ts)

    if domain == "reits":
        rec = d.get("record_count", 0)
        return _signal("REITs", category, f"{rec} REITs tracked", "neutral", 0.82, ts=ts)

    if domain == "zoning":
        return _signal("Zoning & Permits", category, "Local zoning data live", "neutral", 0.70, ts=ts)

    if domain == "str":
        return _signal("Short-Term Rentals", category, "STR market data live", "neutral", 0.75, ts=ts)

    # ── Personal Finance ─────────────────────────────────────────────────────
    if domain == "hysa":
        accounts = d.get("accounts", [])
        best_rate = max((float(a.get("apy", 0)) for a in accounts), default=0)
        fed = d.get("fed_funds_rate", "")
        return _signal("HYSA Rates", category, f"Best APY: {best_rate:.2f}%" if best_rate else "Live rates", "bullish", 0.92,
                       f"Fed Funds: {fed}%" if fed else "", ts=ts)

    if domain == "credit_cards":
        return _signal("Credit Cards", category, "Best rewards & 0% APR offers", "neutral", 0.85, ts=ts)

    if domain == "auto_loans":
        return _signal("Auto Loans", category, "Current rate environment", "neutral", 0.82, ts=ts)

    if domain == "student_debt":
        return _signal("Student Debt", category, "Relief programs & rates", "neutral", 0.80, ts=ts)

    if domain == "personal_loans":
        return _signal("Personal Loans", category, "Best rate comparison live", "neutral", 0.80, ts=ts)

    if domain == "insurance":
        return _signal("Insurance", category, "Premium benchmarks live", "neutral", 0.75, ts=ts)

    if domain == "retirement_limits":
        return _signal("Retirement Limits", category, "IRA/401k contribution limits", "bullish", 0.95, ts=ts)

    if domain == "col":
        return _signal("Cost of Living", category, "City COL index live", "neutral", 0.82, ts=ts)

    if domain == "bankruptcy":
        return _signal("Bankruptcy", category, "Filing trends & legal alerts", "bearish", 0.78, ts=ts)

    # ── Alternative Assets ───────────────────────────────────────────────────
    if domain == "metals":
        return _signal("Precious Metals", category, "Gold, Silver, Platinum live", "bullish", 0.85, ts=ts)

    if domain == "art":
        return _signal("Art Market", category, "Auction results & trends", "neutral", 0.72, ts=ts)

    if domain == "watches":
        return _signal("Luxury Watches", category, "Pre-owned market data", "neutral", 0.70, ts=ts)

    if domain == "collectibles":
        return _signal("Collectibles", category, "Cards, memorabilia & more", "neutral", 0.70, ts=ts)

    if domain == "p2p":
        return _signal("P2P Lending", category, "Yield & default rate data", "neutral", 0.75, ts=ts)

    # ── Business ─────────────────────────────────────────────────────────────
    if domain == "saas_metrics":
        return _signal("SaaS Metrics", category, "Benchmarks: NRR, CAC, churn", "neutral", 0.82, ts=ts)

    if domain == "ecommerce":
        return _signal("eCommerce", category, "GMV trends & conversion benchmarks", "neutral", 0.80, ts=ts)

    if domain == "franchise":
        return _signal("Franchise", category, "ROI & fee benchmarks", "neutral", 0.75, ts=ts)

    if domain == "freelance_rates":
        return _signal("Freelance Rates", category, "Market rates by skill", "neutral", 0.78, ts=ts)

    if domain == "sba":
        return _signal("SBA Loans & Grants", category, "Active programs live", "bullish", 0.82, ts=ts)

    if domain == "vc_deals":
        rec = d.get("record_count", 0)
        return _signal("VC Deal Flow", category, f"{rec} recent deals", "mixed", 0.80, ts=ts)

    if domain == "labor_law":
        return _signal("Labor Law", category, "Compliance updates live", "neutral", 0.78, ts=ts)

    if domain == "federal_tax":
        return _signal("Federal Tax", category, "IRS rules & brackets", "neutral", 0.88, ts=ts)

    if domain == "state_tax":
        return _signal("State Tax", category, "State-level tax data", "neutral", 0.82, ts=ts)

    # ── Marketing ────────────────────────────────────────────────────────────
    if domain == "competitor_ads":
        return _signal("Competitor Ads", category, "Ad intelligence live", "mixed", 0.78, ts=ts)

    if domain == "seo_keywords":
        return _signal("SEO Keywords", category, "Keyword opportunity data", "bullish", 0.80, ts=ts)

    if domain == "email_health":
        return _signal("Email Health", category, "Deliverability & list metrics", "neutral", 0.75, ts=ts)

    if domain == "engagement":
        return _signal("Engagement", category, "Content performance data", "neutral", 0.75, ts=ts)

    if domain == "reviews":
        return _signal("Reviews", category, "Reputation & rating data", "neutral", 0.78, ts=ts)

    if domain == "roas":
        return _signal("ROAS", category, "Ad spend efficiency data", "neutral", 0.80, ts=ts)

    if domain == "leads":
        return _signal("Lead Generation", category, "Lead quality benchmarks", "neutral", 0.75, ts=ts)

    if domain == "crm_sync":
        return _signal("CRM Sync", category, "Pipeline & conversion data", "neutral", 0.75, ts=ts)

    return None


# ── Snapshot builder ──────────────────────────────────────────────────────────

def get_snapshot(categories: Optional[list[str]] = None) -> dict:
    """
    Build a hub snapshot from all data_cache domains.

    Args:
        categories: Optional filter (e.g. ["market", "macro"]). None = all.

    Returns:
        Dict with signals_by_category, top_signals, alert_count, summary, ts.
    """
    t0 = time.monotonic()
    target = categories or list(CATEGORIES.keys())
    signals_by_category: dict[str, list[dict]] = {}
    all_signals: list[dict] = []

    for cat in target:
        if cat not in CATEGORIES:
            continue
        cat_signals = []
        for domain in CATEGORIES[cat]:
            sig = _extract_signal(domain, cat)
            if sig:
                cat_signals.append(sig)
                all_signals.append(sig)
        if cat_signals:
            signals_by_category[cat] = cat_signals

    # Category-level summaries
    category_summary: dict[str, dict] = {}
    for cat, sigs in signals_by_category.items():
        bullish = sum(1 for s in sigs if s["direction"] in ("bullish", "rising"))
        bearish = sum(1 for s in sigs if s["direction"] in ("bearish", "falling"))
        overall = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"
        category_summary[cat] = {
            "direction": overall,
            "color": _DIRECTION_COLORS.get(overall, "#64748b"),
            "signal_count": len(sigs),
            "bullish": bullish,
            "bearish": bearish,
            "icon": _CATEGORY_ICONS.get(cat, "📊"),
        }

    # Top signals = highest confidence + non-neutral
    top_signals = sorted(
        [s for s in all_signals if s["direction"] not in ("neutral", "unknown")],
        key=lambda s: s["confidence"],
        reverse=True,
    )[:8]

    # Alert signals = bearish or strong divergences
    alerts = [s for s in all_signals if s["direction"] in ("bearish", "falling")]

    elapsed = int((time.monotonic() - t0) * 1000)

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": elapsed,
        "total_signals": len(all_signals),
        "alert_count": len(alerts),
        "categories_live": len(signals_by_category),
        "signals_by_category": signals_by_category,
        "category_summary": category_summary,
        "top_signals": top_signals,
        "alerts": alerts[:5],
    }


def get_brief() -> dict:
    """Return a condensed intelligence brief — top 3 signals per category."""
    snap = get_snapshot()
    brief: dict[str, Any] = {
        "ts": snap["ts"],
        "alert_count": snap["alert_count"],
        "total_signals": snap["total_signals"],
        "category_summary": snap["category_summary"],
        "top_signals": snap["top_signals"][:5],
        "alerts": snap["alerts"][:3],
        "categories": {},
    }
    for cat, sigs in snap["signals_by_category"].items():
        brief["categories"][cat] = sigs[:3]
    return brief
