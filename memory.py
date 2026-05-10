"""
memory.py — ATLAS Persistent Memory System

Two-tier memory modeled after how humans actually remember things:

TIER 1 — PERMANENT BRAIN (long-term memory)
  Stores facts that don't change or that matter forever:
  - Earnings history (every beat/miss, ever)
  - Trade history (what you bought, when, outcome)
  - Company profiles (what the company does, sector, competitors)
  - Analyst target history (how targets changed over time)
  - Options plays recommended (for later review)
  - Key dates and events (confirmed earnings dates, FDA dates, etc.)
  Never deleted. Grows over time. The more you use ATLAS, the smarter it gets.

TIER 2 — SHORT-TERM BRAIN (rolling 7-day window)
  Stores operational data that goes stale:
  - Current price, RSI, short float (changes daily)
  - Recent news headlines (stale after a week)
  - Current options chain data (expires or changes)
  - Recent analyst ratings (can be updated)
  Auto-expires after 168 hours (7 days). Keeps context clean.

ASSOCIATIVE RECALL (human-like)
  When you mention a ticker or topic → memory is searched and relevant
  facts are surfaced automatically. You don't ask for it explicitly —
  it happens like human memory, triggered by context.
  Mentioning "SOUN" pulls all SOUN memories.
  Mentioning "earnings" pulls all earnings memories.
  Mentioning "short squeeze" pulls stocks with high short float.

ANTI-HALLUCINATION
  All facts in memory include: value, confidence level, source, and age.
  Before every AI synthesis call, relevant memories are injected with
  explicit confidence labels. The AI is told: "you KNOW this" vs
  "this is unverified" vs "this data is X days old."
  The AI cannot fill gaps with made-up numbers — the prompt structure
  physically prevents it.

Storage: SQLite (built into Python, zero install needed)
File: atlas_memory.db (in project directory)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_DB_PATH    = Path(__file__).parent / "atlas_memory.db"
SHORT_TERM_HOURS = 168   # 7 days

# Fact types — organized for easy recall
FACT_TYPES = {
    # Permanent facts (don't change or change very slowly)
    "company_profile":   "permanent",   # what the company does
    "earnings_history":  "permanent",   # past quarter results
    "trade_history":     "permanent",   # your trades
    "event_confirmed":   "permanent",   # confirmed dates (earnings, FDA, etc.)
    "options_played":    "permanent",   # options contracts you bought/researched

    # Short-term facts (change weekly)
    "price":             "short_term",
    "technical":         "short_term",  # RSI, MA, support/resistance
    "fundamental":       "short_term",  # short float, analyst target, IV rank
    "news":              "short_term",  # recent headlines
    "sentiment":         "short_term",  # reddit/stocktwits sentiment
    "options_data":      "short_term",  # current chain data
    "earnings_upcoming": "short_term",  # unconfirmed upcoming dates
    "research_summary":  "short_term",  # full research snapshot
    "trade_lesson":      "permanent",   # post-mortem lesson extracted after a paper trade closes
}

# Keywords that trigger recall of specific fact types
RECALL_TRIGGERS = {
    "earnings":      ["earnings_history", "earnings_upcoming", "event_confirmed"],
    "price":         ["price", "technical", "fundamental"],
    "short":         ["fundamental"],
    "squeeze":       ["fundamental", "sentiment"],
    "options":       ["options_data", "options_played"],
    "news":          ["news", "sentiment"],
    "analyst":       ["fundamental"],
    "buy":           ["trade_history", "research_summary"],
    "sell":          ["trade_history"],
    "beat":          ["earnings_history"],
    "miss":          ["earnings_history"],
    "catalyst":      ["event_confirmed", "earnings_upcoming"],
    "reddit":        ["sentiment"],
    "insider":       ["fundamental"],
    "iv":            ["options_data", "fundamental"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker        TEXT,
            fact_type     TEXT NOT NULL,
            key           TEXT NOT NULL,
            value         TEXT NOT NULL,
            confidence    INTEGER DEFAULT 1,
            sources       TEXT,
            permanent     INTEGER DEFAULT 0,
            created_at    TEXT NOT NULL,
            expires_at    TEXT,
            last_accessed TEXT,
            access_count  INTEGER DEFAULT 0,
            tags          TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ticker    ON memories(ticker);
        CREATE INDEX IF NOT EXISTS idx_fact_type ON memories(fact_type);
        CREATE INDEX IF NOT EXISTS idx_key       ON memories(key);
        CREATE INDEX IF NOT EXISTS idx_expires   ON memories(expires_at);

        CREATE TABLE IF NOT EXISTS memory_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT NOT NULL,
            ticker     TEXT,
            detail     TEXT,
            created_at TEXT NOT NULL
        );
        """)


_init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Core memory operations
# ─────────────────────────────────────────────────────────────────────────────
def remember(
    key:         str,
    value:       Any,
    fact_type:   str     = "research_summary",
    ticker:      str     = "",
    confidence:  int     = 1,      # 1=single source, 2=corroborated, 3=confirmed
    sources:     list    = None,
    permanent:   bool    = False,
    tags:        list    = None,
) -> int:
    """
    Store a fact in memory.

    confidence levels:
      1 = single source (treat with caution)
      2 = corroborated (2 sources agree)
      3 = confirmed (3+ sources agree — treat as hard fact)

    permanent=True → never expires (earnings history, trade history, company facts)
    permanent=False → expires after 168 hours (price, news, options chain)
    """
    now        = datetime.now(timezone.utc).isoformat()
    expires_at = None if permanent else (
        datetime.now(timezone.utc) + timedelta(hours=SHORT_TERM_HOURS)
    ).isoformat()

    # Auto-detect permanent for certain fact types
    if FACT_TYPES.get(fact_type) == "permanent":
        permanent  = True
        expires_at = None

    value_str   = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    sources_str = json.dumps(sources or [])
    tags_str    = json.dumps(tags or [])

    with _connect() as conn:
        # Upsert: if same ticker+key exists, update it
        existing = conn.execute(
            "SELECT id, confidence, access_count FROM memories "
            "WHERE ticker=? AND key=? AND fact_type=?",
            (ticker.upper(), key, fact_type)
        ).fetchone()

        if existing:
            # Update existing — raise confidence if new data confirms it
            new_conf = max(existing["confidence"], confidence)
            conn.execute("""
                UPDATE memories
                SET value=?, confidence=?, sources=?, permanent=?,
                    expires_at=?, last_accessed=?, access_count=?, tags=?
                WHERE id=?
            """, (value_str, new_conf, sources_str, int(permanent),
                  expires_at, now, existing["access_count"], tags_str,
                  existing["id"]))
            mem_id = existing["id"]
            log.debug("Memory updated: [%s] %s=%s (conf=%d)", ticker, key, str(value)[:60], new_conf)
        else:
            cur = conn.execute("""
                INSERT INTO memories
                  (ticker, fact_type, key, value, confidence, sources,
                   permanent, created_at, expires_at, last_accessed, access_count, tags)
                VALUES (?,?,?,?,?,?,?,?,?,?,0,?)
            """, (ticker.upper(), fact_type, key, value_str, confidence,
                  sources_str, int(permanent), now, expires_at, now, tags_str))
            mem_id = cur.lastrowid
            log.debug("Memory stored: [%s] %s=%s (conf=%d, %s)",
                      ticker, key, str(value)[:60], confidence,
                      "permanent" if permanent else "7-day")

    return mem_id


def recall_ticker(ticker: str, include_expired: bool = False) -> list[dict]:
    """
    Retrieve all memories for a ticker.
    Returns list of memory dicts sorted by confidence desc, recency desc.
    """
    ticker = ticker.upper()
    now    = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        if include_expired:
            rows = conn.execute(
                "SELECT * FROM memories WHERE ticker=? ORDER BY confidence DESC, created_at DESC",
                (ticker,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE ticker=? "
                "AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY confidence DESC, created_at DESC",
                (ticker, now)
            ).fetchall()

        # Update access counts
        if rows:
            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE memories SET last_accessed=?, access_count=access_count+1 "
                f"WHERE id IN ({','.join('?'*len(ids))})",
                [now] + ids
            )

    return [dict(r) for r in rows]


def recall_query(query: str, ticker: str = "") -> list[dict]:
    """
    Associative recall — finds relevant memories from a natural language query.
    Triggered by keywords (like human memory being reminded of something).

    Example:
      recall_query("SOUN earnings tomorrow") →
        Returns all SOUN earnings memories + event_confirmed memories
    """
    query_lower = query.lower()
    now         = datetime.now(timezone.utc).isoformat()

    # Extract tickers from query (2-5 uppercase letters)
    tickers_in_query = re.findall(r'\b([A-Z]{1,5})\b', query)
    if ticker:
        tickers_in_query.append(ticker.upper())
    tickers_in_query = list(set(tickers_in_query))

    # Determine which fact types to retrieve based on keyword triggers
    triggered_types: set[str] = set()
    for keyword, fact_types in RECALL_TRIGGERS.items():
        if keyword in query_lower:
            triggered_types.update(fact_types)

    # Always retrieve permanent facts when a ticker is mentioned
    if tickers_in_query:
        triggered_types.update(["company_profile", "earnings_history",
                                 "event_confirmed", "trade_history"])

    # If no specific triggers, return recent research summaries
    if not triggered_types:
        triggered_types = {"research_summary", "fundamental"}

    results = []
    with _connect() as conn:
        for t in tickers_in_query:
            for ft in triggered_types:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE ticker=? AND fact_type=? "
                    "AND (expires_at IS NULL OR expires_at > ?) "
                    "ORDER BY confidence DESC, created_at DESC LIMIT 10",
                    (t, ft, now)
                ).fetchall()
                results.extend([dict(r) for r in rows])

        # Also do keyword search in values for non-ticker queries
        if not tickers_in_query:
            keywords = query_lower.split()[:5]
            for kw in keywords:
                if len(kw) > 3:
                    rows = conn.execute(
                        "SELECT * FROM memories "
                        "WHERE (key LIKE ? OR value LIKE ? OR tags LIKE ?) "
                        "AND (expires_at IS NULL OR expires_at > ?) "
                        "ORDER BY confidence DESC, created_at DESC LIMIT 5",
                        (f"%{kw}%", f"%{kw}%", f"%{kw}%", now)
                    ).fetchall()
                    results.extend([dict(r) for r in rows])

    # Deduplicate by id
    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)

    return unique


def recall_all_tickers() -> list[str]:
    """Return all tickers that have memories stored."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM memories WHERE ticker != '' ORDER BY ticker"
        ).fetchall()
    return [r["ticker"] for r in rows]


def forget_expired() -> int:
    """Delete all expired short-term memories. Call this periodically."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM memories WHERE permanent=0 AND expires_at IS NOT NULL AND expires_at < ?",
            (now,)
        )
        deleted = cur.rowcount
    if deleted:
        log.info("Memory cleanup: removed %d expired short-term memories", deleted)
    return deleted


def memory_stats() -> dict:
    """Return stats about the current memory state."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        permanent = conn.execute("SELECT COUNT(*) FROM memories WHERE permanent=1").fetchone()[0]
        active    = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE expires_at IS NULL OR expires_at > ?", (now,)
        ).fetchone()[0]
        expired   = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE permanent=0 AND expires_at < ?", (now,)
        ).fetchone()[0]
        tickers   = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM memories WHERE ticker != ''"
        ).fetchone()[0]
        by_type   = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT fact_type, COUNT(*) FROM memories GROUP BY fact_type"
            ).fetchall()
        }
    return {
        "total":     total,
        "permanent": permanent,
        "active":    active,
        "expired":   expired,
        "tickers":   tickers,
        "by_type":   by_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Context formatter — converts memories to text for AI prompt injection
# ─────────────────────────────────────────────────────────────────────────────
def to_context(memories: list[dict], header: str = "ATLAS MEMORY RECALL") -> str:
    """
    Format a list of memories into a text block suitable for AI prompt injection.
    Includes confidence labels so the AI knows what's verified vs. tentative.
    """
    if not memories:
        return ""

    CONF_LABELS = {
        3: "CONFIRMED (3+ sources)",
        2: "CORROBORATED (2 sources)",
        1: "SINGLE SOURCE",
    }
    TIER_LABELS = {
        1: "PERMANENT",
        0: "SHORT-TERM",
    }

    lines = [f"\n=== {header} ==="]
    lines.append("(Facts ATLAS already knows — treat CONFIRMED facts as hard truth,")
    lines.append(" SINGLE SOURCE facts as likely-correct, not guaranteed)")
    lines.append("")

    # Group by ticker
    by_ticker: dict[str, list[dict]] = {}
    no_ticker: list[dict] = []
    for m in memories:
        t = m.get("ticker","")
        if t:
            by_ticker.setdefault(t, []).append(m)
        else:
            no_ticker.append(m)

    def _format_value(v: str) -> str:
        try:
            parsed = json.loads(v)
            if isinstance(parsed, (dict, list)):
                return json.dumps(parsed, ensure_ascii=False)[:200]
            return str(parsed)
        except Exception:
            return v[:200]

    def _age(created_at: str) -> str:
        try:
            dt  = datetime.fromisoformat(created_at.replace("Z","+00:00"))
            now = datetime.now(timezone.utc)
            hrs = (now - dt).total_seconds() / 3600
            if hrs < 1:
                return f"{int(hrs*60)}m ago"
            elif hrs < 24:
                return f"{int(hrs)}h ago"
            else:
                return f"{int(hrs/24)}d ago"
        except Exception:
            return ""

    for ticker, mems in sorted(by_ticker.items()):
        lines.append(f"--- {ticker} ---")
        for m in sorted(mems, key=lambda x: (-x["confidence"], x["fact_type"])):
            conf  = CONF_LABELS.get(m["confidence"], f"conf={m['confidence']}")
            tier  = TIER_LABELS.get(m["permanent"], "SHORT-TERM")
            age   = _age(m["created_at"])
            val   = _format_value(m["value"])
            lines.append(
                f"  [{tier}] [{conf}] {m['key']}: {val}  ({age})"
            )
        lines.append("")

    if no_ticker:
        lines.append("--- General ---")
        for m in no_ticker[:10]:
            conf = CONF_LABELS.get(m["confidence"], f"conf={m['confidence']}")
            age  = _age(m["created_at"])
            val  = _format_value(m["value"])
            lines.append(f"  [{conf}] {m['fact_type']}/{m['key']}: {val}  ({age})")

    lines.append(f"=== END MEMORY ({len(memories)} facts recalled) ===\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Auto-extraction — learn from research results automatically
# ─────────────────────────────────────────────────────────────────────────────
def learn_from_research(research: dict) -> int:
    """
    Automatically extract and store key facts from a deep_research result.
    Called after every research run — the system learns without being told.
    Returns number of facts stored.
    """
    ticker = (research.get("ticker") or "").upper()
    if not ticker:
        return 0

    stored = 0
    syn    = research.get("synthesis") or {}
    mkt    = research.get("mktdata")   or {}
    budget = research.get("budget", 100)

    # ── Company profile (permanent) ──────────────────────────────────────────
    if syn.get("company_name"):
        remember(
            key="company_profile", ticker=ticker, fact_type="company_profile",
            value={
                "name":    syn.get("company_name"),
                "sector":  syn.get("sector") or mkt.get("sector"),
                "summary": syn.get("executive_summary","")[:300],
            },
            confidence=2, permanent=True,
            sources=["deep_research_synthesis"]
        )
        stored += 1

    # ── Confirmed earnings date (permanent if in the past, short-term if future) ─
    ea = syn.get("earnings_analysis") or {}
    next_e = ea.get("next_date") or mkt.get("next_earnings")
    if next_e and next_e != "unknown":
        try:
            from datetime import date
            ed = datetime.strptime(str(next_e)[:10], "%Y-%m-%d").date()
            is_future = ed >= date.today()
        except Exception:
            is_future = True
        remember(
            key="next_earnings_date", ticker=ticker,
            fact_type="event_confirmed" if not is_future else "earnings_upcoming",
            value=next_e, confidence=2, permanent=not is_future,
            sources=["yfinance", "deep_research"]
        )
        stored += 1

    # ── Analyst target (short-term) ──────────────────────────────────────────
    ac = syn.get("analyst_consensus") or {}
    if ac.get("avg_target"):
        remember(
            key="analyst_target", ticker=ticker, fact_type="fundamental",
            value={
                "target": ac.get("avg_target"),
                "rating": ac.get("rating"),
                "count":  ac.get("count"),
            },
            confidence=2, sources=["synthesis"]
        )
        stored += 1

    # ── Trade plan (short-term, high value) ──────────────────────────────────
    tp = syn.get("trade_plan") or {}
    if tp.get("action") and tp.get("entry_price"):
        remember(
            key="trade_plan", ticker=ticker, fact_type="research_summary",
            value={
                "action":      tp.get("action"),
                "entry":       tp.get("entry_price"),
                "stop":        tp.get("stop_loss"),
                "target1":     tp.get("target_1"),
                "target2":     tp.get("target_2"),
                "hold_period": tp.get("hold_period"),
                "rating":      syn.get("overall_rating"),
                "confidence":  syn.get("confidence"),
                "budget":      budget,
            },
            confidence=1, sources=["synthesis"]
        )
        stored += 1

    # ── Options play (short-term + permanent record) ─────────────────────────
    op = syn.get("options_play") or {}
    bc = op.get("best_contract") or {}
    if bc.get("expiry") and bc.get("strike"):
        remember(
            key=f"options_play_{bc['expiry']}_{bc['strike']}{bc.get('type','c')[0].upper()}",
            ticker=ticker, fact_type="options_played",
            value={
                "expiry":     bc.get("expiry"),
                "strike":     bc.get("strike"),
                "type":       bc.get("type"),
                "ask":        bc.get("ask_estimate"),
                "cost":       bc.get("cost_1_contract"),
                "breakeven":  bc.get("breakeven"),
                "rationale":  bc.get("rationale","")[:200],
                "budget":     budget,
                "recommended": op.get("recommended"),
            },
            confidence=1, permanent=True,  # permanent so we can review later
            sources=["synthesis"],
            tags=["options", "recommendation"]
        )
        stored += 1

    # ── Key price levels (short-term) ────────────────────────────────────────
    pl = syn.get("price_levels") or {}
    if pl.get("immediate_support") or pl.get("immediate_resistance"):
        remember(
            key="price_levels", ticker=ticker, fact_type="technical",
            value={
                "support1":    pl.get("immediate_support"),
                "support2":    pl.get("strong_support"),
                "resistance1": pl.get("immediate_resistance"),
                "resistance2": pl.get("strong_resistance"),
                "analyst_target": pl.get("analyst_target"),
                "price_at_research": mkt.get("price"),
            },
            confidence=1, sources=["synthesis"]
        )
        stored += 1

    # ── Risk factors (short-term) ────────────────────────────────────────────
    risks = syn.get("key_risks") or []
    if risks:
        remember(
            key="key_risks", ticker=ticker, fact_type="research_summary",
            value=risks[:3], confidence=1, sources=["synthesis"]
        )
        stored += 1

    # ── Overall rating + confidence (short-term) ─────────────────────────────
    if syn.get("overall_rating"):
        remember(
            key="atlas_rating", ticker=ticker, fact_type="research_summary",
            value={
                "rating":     syn.get("overall_rating"),
                "confidence": syn.get("confidence"),
                "summary":    syn.get("executive_summary","")[:200],
            },
            confidence=1, sources=["synthesis"]
        )
        stored += 1

    log.info("Learned %d facts from research on %s", stored, ticker)
    return stored


def learn_from_scrape(ticker: str, scraped: dict) -> int:
    """
    Extract and store key facts from a web_scraper.gather_all() result.
    Called after every scrape — updates short-term operational data.
    """
    ticker = ticker.upper()
    stored = 0
    fv     = scraped.get("finviz") or {}
    xref   = scraped.get("cross_reference") or {}
    xconf  = xref.get("confidence_data") or {}

    # Price (short-term, 1 day expiry)
    if fv.get("price"):
        remember(
            key="price", ticker=ticker, fact_type="price",
            value=fv["price"], confidence=3, sources=["finviz"],
        )
        stored += 1

    # Short float — squeeze potential (short-term)
    if fv.get("short_float"):
        remember(
            key="short_float", ticker=ticker, fact_type="fundamental",
            value=fv["short_float"], confidence=3, sources=["finviz"],
            tags=["short_interest"]
        )
        stored += 1

    # RSI + technical momentum
    if fv.get("rsi"):
        remember(
            key="rsi", ticker=ticker, fact_type="technical",
            value=fv["rsi"], confidence=3, sources=["finviz"]
        )
        stored += 1

    # Earnings date — confidence based on cross-reference
    ea_conf = xconf.get("earnings_date", {})
    if fv.get("earnings_date"):
        conf = 3 if ea_conf.get("confidence") == "CONFIRMED" else (
               2 if ea_conf.get("confidence") == "CORROBORATED" else 1)
        sources_list = ea_conf.get("sources", ["finviz"])
        remember(
            key="next_earnings_date", ticker=ticker, fact_type="earnings_upcoming",
            value=fv["earnings_date"], confidence=conf,
            sources=sources_list
        )
        stored += 1

    # Analyst target (cross-referenced)
    at_conf = xconf.get("analyst_target", {})
    if at_conf.get("value"):
        remember(
            key="analyst_target_price", ticker=ticker, fact_type="fundamental",
            value=f"${at_conf['value']}", confidence=2,
            sources=["finviz", "marketbeat"]
        )
        stored += 1

    # News sentiment score
    if xconf.get("news_sentiment"):
        remember(
            key="news_sentiment", ticker=ticker, fact_type="sentiment",
            value=xconf["news_sentiment"], confidence=2,
            sources=["cross_reference_engine"]
        )
        stored += 1

    # News headlines (store top 5)
    news = scraped.get("news") or []
    if news:
        remember(
            key="recent_headlines", ticker=ticker, fact_type="news",
            value=[{"date": n.get("date",""), "title": n.get("title","")}
                   for n in news[:5]],
            confidence=3, sources=["google_news", "benzinga"]
        )
        stored += 1

    # Insider activity
    insiders = scraped.get("insider_data") or []
    if insiders:
        buys  = [i for i in insiders if "buy" in i.get("trade_type","").lower()
                 or "P" in i.get("trade_type","")]
        sells = [i for i in insiders if "sale" in i.get("trade_type","").lower()]
        if buys or sells:
            remember(
                key="insider_activity", ticker=ticker, fact_type="fundamental",
                value={
                    "buys":  [{"date": b.get("trade_date"), "insider": b.get("insider"),
                               "value": b.get("value")} for b in buys[:3]],
                    "sells": [{"date": s.get("trade_date"), "insider": s.get("insider"),
                               "value": s.get("value")} for s in sells[:3]],
                },
                confidence=3, sources=["openinsider"],
                tags=["insider", "bullish" if buys else "bearish"]
            )
            stored += 1

    log.info("Learned %d facts from scrape on %s", stored, ticker)
    return stored


def learn_from_earnings(ticker: str, quarter: str, actual_eps: float,
                         estimate_eps: float, actual_rev: float,
                         estimate_rev: float, reaction_pct: float) -> None:
    """
    Store a completed earnings result permanently.
    This builds a historical record of how the stock behaved on earnings.
    """
    ticker = ticker.upper()
    beat_eps = actual_eps > estimate_eps
    beat_rev = actual_rev > estimate_rev

    remember(
        key=f"earnings_{quarter}",
        ticker=ticker,
        fact_type="earnings_history",
        value={
            "quarter":       quarter,
            "actual_eps":    actual_eps,
            "estimate_eps":  estimate_eps,
            "beat_eps":      beat_eps,
            "eps_surprise":  round(actual_eps - estimate_eps, 4),
            "actual_rev":    actual_rev,
            "estimate_rev":  estimate_rev,
            "beat_rev":      beat_rev,
            "stock_reaction_pct": reaction_pct,
        },
        confidence=3,
        permanent=True,
        sources=["earnings_report"],
        tags=["earnings", "beat" if (beat_eps and beat_rev) else "miss"]
    )
    log.info("Earnings recorded: %s %s — EPS %s (est %s) — stock reaction: %+.1f%%",
             ticker, quarter, actual_eps, estimate_eps, reaction_pct)


def log_trade(ticker: str, action: str, contracts_or_shares: int,
              price: float, total_cost: float, notes: str = "") -> None:
    """
    Record a trade permanently for future reference and learning.
    When you review performance, ATLAS can recall what it recommended vs. what happened.
    """
    ticker = ticker.upper()
    remember(
        key=f"trade_{datetime.now().strftime('%Y%m%d_%H%M')}",
        ticker=ticker,
        fact_type="trade_history",
        value={
            "action":   action,
            "quantity": contracts_or_shares,
            "price":    price,
            "cost":     total_cost,
            "notes":    notes,
            "date":     datetime.now(timezone.utc).isoformat(),
        },
        confidence=3, permanent=True,
        sources=["user_trade"],
        tags=["trade", action]
    )
    log.info("Trade logged: %s %s %d @ $%.2f (total: $%.2f)",
             action, ticker, contracts_or_shares, price, total_cost)


# ─────────────────────────────────────────────────────────────────────────────
# Memory-aware context builder for AI prompts
# ─────────────────────────────────────────────────────────────────────────────
def build_ai_context(ticker: str = "", query: str = "") -> str:
    """
    Build a memory context block to prepend to any AI synthesis prompt.
    This is the anti-hallucination layer — the AI reads what ATLAS already
    knows before generating any new analysis.

    Rules injected into the prompt:
    - CONFIRMED facts → state directly, no hedging
    - CORROBORATED facts → state as "per [source]"
    - SINGLE SOURCE facts → note caveat
    - Gaps → explicitly say "not in memory" — do NOT fill with training data
    """
    memories = []
    if ticker:
        memories.extend(recall_ticker(ticker))
    if query:
        memories.extend(recall_query(query, ticker=ticker))

    # Deduplicate
    seen = set()
    unique = []
    for m in memories:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    if not unique:
        return (
            f"\n=== ATLAS MEMORY: No prior knowledge of {ticker or query} ===\n"
            "This appears to be a new ticker or topic — no stored facts available.\n"
            "Base analysis entirely on freshly scraped data above.\n"
            "=== END MEMORY ===\n"
        )

    context = to_context(unique, header=f"ATLAS MEMORY — {ticker or 'RECALL'}")

    # Append anti-hallucination instruction
    context += (
        "\nANTI-HALLUCINATION RULES:\n"
        "- For CONFIRMED facts above: state them directly and confidently\n"
        "- For SINGLE SOURCE facts: note 'per [source]' but still use them\n"
        "- If a field is NOT in the memory above AND not in the scraped data: "
        "use null or say 'Not found' — never fill gaps with training-data guesses\n"
        "- If memory and new scraped data conflict: use new scraped data and note the discrepancy\n"
    )

    return context


# ─────────────────────────────────────────────────────────────────────────────
# CLI — inspect and manage the memory store
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"

    if cmd == "stats":
        s = memory_stats()
        print(f"\nATLAS Memory Database: {_DB_PATH}")
        print(f"  Total memories:     {s['total']}")
        print(f"  Permanent:          {s['permanent']}")
        print(f"  Active (not exp.):  {s['active']}")
        print(f"  Expired (cleanup):  {s['expired']}")
        print(f"  Tickers tracked:    {s['tickers']}")
        print(f"\nBy type:")
        for ft, count in sorted(s["by_type"].items()):
            print(f"  {ft:<22} {count}")

    elif cmd == "recall" and len(sys.argv) > 2:
        ticker = sys.argv[2].upper()
        mems   = recall_ticker(ticker)
        if not mems:
            print(f"No memories found for {ticker}")
        else:
            print(build_ai_context(ticker=ticker))

    elif cmd == "tickers":
        tickers = recall_all_tickers()
        print(f"Tickers in memory ({len(tickers)}): {', '.join(tickers)}")

    elif cmd == "clean":
        n = forget_expired()
        print(f"Cleaned {n} expired memories")

    elif cmd == "query" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        mems  = recall_query(query)
        print(build_ai_context(query=query))

    else:
        print("Usage:")
        print("  python memory.py stats              -- show memory stats")
        print("  python memory.py tickers            -- list all tracked tickers")
        print("  python memory.py recall SOUN        -- show all SOUN memories")
        print("  python memory.py query 'SOUN earnings' -- associative recall")
        print("  python memory.py clean              -- remove expired memories")
