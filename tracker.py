"""
tracker.py — ATLAS Win-Rate Tracker + Setup Pattern Library

This is what turns ATLAS from a research tool into something that gets
smarter with every trade. Three components:

1. RECOMMENDATION RECORDER
   Every time ATLAS deep-researches a stock, it auto-records:
   - What it said (buy/sell, entry, target, stop, options play)
   - What setup characteristics triggered the call
   - The confidence score at the time

2. OUTCOME RECORDER
   After the event (earnings, price target hit, stop hit):
   - Records what actually happened
   - Grades the recommendation: WIN / LOSS / PARTIAL
   - Calculates actual return vs. expected

3. SETUP PATTERN LIBRARY
   After 5+ outcomes for a setup type, ATLAS can say:
   "38% short float + earnings tomorrow + bullish options flow:
    I've made this call 14 times. 11 wins (79% win rate).
    Average win: +127%. Average loss: -85%."

   This gets injected into every new synthesis prompt — giving ATLAS
   a genuine track record that no other AI model has.

Storage: atlas_tracker.db (SQLite, same folder as atlas_memory.db)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yfinance as yf

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "atlas_tracker.db"

# ─────────────────────────────────────────────────────────────────────────────
# Setup tag definitions — what characteristics define a "setup"
# These are auto-detected from scrape/research data
# ─────────────────────────────────────────────────────────────────────────────
def detect_setup_tags(research: dict, scrape: dict = None) -> list[str]:
    """
    Auto-detect setup tags from research and scrape data.
    Tags become the fingerprint of a setup for pattern matching.
    """
    tags: list[str] = []
    syn = research.get("synthesis") or {}
    mkt = research.get("mktdata") or {}
    fv  = (scrape or {}).get("finviz") or {}
    xref = (scrape or {}).get("cross_reference") or {}
    xconf = xref.get("confidence_data") or {}
    js   = (scrape or {}).get("js_data") or {}
    bc_data = js.get("barchart") or {}

    # Short float squeeze potential
    short_str = fv.get("short_float") or mkt.get("short_pct", "")
    try:
        short_pct = float(str(short_str).replace("%","").strip())
        if short_pct > 35:  tags.append("extreme_short_float")
        elif short_pct > 20: tags.append("high_short_float")
        elif short_pct > 10: tags.append("elevated_short_float")
    except Exception:
        pass

    # Earnings timing
    next_e = mkt.get("next_earnings") or ""
    if next_e and next_e != "unknown":
        try:
            ed  = datetime.strptime(str(next_e)[:10], "%Y-%m-%d").date()
            days = (ed - date.today()).days
            if days <= 1:   tags.append("earnings_today")
            elif days <= 3: tags.append("earnings_imminent")
            elif days <= 7: tags.append("earnings_this_week")
            elif days <= 30: tags.append("earnings_this_month")
        except Exception:
            pass

    # IV rank from Barchart
    iv_rank_str = bc_data.get("iv_rank") or ""
    try:
        ivr = float(str(iv_rank_str).replace("%",""))
        if ivr < 20:   tags.append("iv_very_low")   # options cheap
        elif ivr < 40: tags.append("iv_low")
        elif ivr < 70: tags.append("iv_moderate")
        elif ivr < 85: tags.append("iv_high")        # crush risk
        else:          tags.append("iv_extreme")
    except Exception:
        pass

    # Options flow from Unusual Whales
    uw = js.get("unusual_whales_js") or {}
    flow = (uw.get("bullish_bearish") or uw.get("flow_sentiment") or "").lower()
    if "bullish" in flow: tags.append("bullish_options_flow")
    elif "bearish" in flow: tags.append("bearish_options_flow")

    pcr_str = uw.get("put_call_ratio") or ""
    try:
        pcr = float(pcr_str)
        if pcr < 0.4:   tags.append("very_bullish_pcr")   # mostly calls
        elif pcr < 0.7: tags.append("bullish_pcr")
        elif pcr > 1.5: tags.append("bearish_pcr")
    except Exception:
        pass

    # News sentiment
    news_sent = xconf.get("news_sentiment") or ""
    if news_sent == "BULLISH":  tags.append("bullish_news_sentiment")
    elif news_sent == "BEARISH": tags.append("bearish_news_sentiment")

    # RSI / momentum
    rsi_str = fv.get("rsi") or ""
    try:
        rsi = float(str(rsi_str))
        if rsi > 70:    tags.append("overbought_rsi")
        elif rsi > 55:  tags.append("bullish_momentum_rsi")
        elif rsi < 30:  tags.append("oversold_rsi")
        elif rsi < 45:  tags.append("bearish_momentum_rsi")
    except Exception:
        pass

    # Analyst consensus
    rating = (syn.get("analyst_consensus") or {}).get("rating") or \
             (mkt.get("analyst_rating") or "")
    if "strong buy" in rating.lower(): tags.append("analyst_strong_buy")
    elif "buy" in rating.lower():      tags.append("analyst_buy")
    elif "sell" in rating.lower():     tags.append("analyst_sell")

    # Overall ATLAS rating
    atlas_rating = (syn.get("overall_rating") or "").lower()
    if atlas_rating in ("strong_buy", "buy"): tags.append("atlas_bullish")
    elif atlas_rating in ("sell", "strong_sell"): tags.append("atlas_bearish")

    # Confidence
    conf = syn.get("confidence") or 0
    try:
        c = int(conf)
        if c >= 8:   tags.append("high_conviction")
        elif c >= 6: tags.append("medium_conviction")
        else:        tags.append("low_conviction")
    except Exception:
        pass

    # Revenue growth
    rev_g = mkt.get("revenue_growth")
    try:
        rg = float(str(rev_g or 0))
        if rg > 0.50:   tags.append("hypergrowth_revenue")
        elif rg > 0.20: tags.append("strong_revenue_growth")
        elif rg < 0:    tags.append("declining_revenue")
    except Exception:
        pass

    return list(set(tags))


# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker         TEXT NOT NULL,
            recorded_at    TEXT NOT NULL,
            event_date     TEXT,         -- earnings date or expected catalyst date
            action         TEXT,         -- buy_calls, buy_stock, buy_puts, avoid
            entry_price    REAL,
            stop_loss      REAL,
            target_1       REAL,
            target_2       REAL,
            options_strike REAL,
            options_expiry TEXT,
            options_type   TEXT,
            options_cost   REAL,
            atlas_rating   TEXT,
            atlas_conf     INTEGER,
            budget         REAL,
            setup_tags     TEXT,         -- JSON array of setup tags
            setup_hash     TEXT,         -- sorted tag fingerprint for grouping
            research_json  TEXT          -- full synthesis JSON (compressed)
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id   INTEGER NOT NULL,
            ticker              TEXT NOT NULL,
            graded_at           TEXT NOT NULL,
            event_type          TEXT,    -- earnings, price_target_hit, stop_hit, time_exit
            price_at_event      REAL,
            price_at_entry      REAL,
            pnl_pct             REAL,    -- actual % gain/loss on stock
            options_pnl_pct     REAL,    -- actual % on options if applicable
            outcome             TEXT,    -- WIN / LOSS / PARTIAL_WIN / OPEN
            beat_eps            INTEGER, -- 1=beat, 0=miss, NULL=unknown
            beat_rev            INTEGER,
            earnings_reaction   REAL,    -- % stock moved on earnings day
            notes               TEXT,
            FOREIGN KEY (recommendation_id) REFERENCES recommendations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_rec_ticker  ON recommendations(ticker);
        CREATE INDEX IF NOT EXISTS idx_rec_tags    ON recommendations(setup_hash);
        CREATE INDEX IF NOT EXISTS idx_out_ticker  ON outcomes(ticker);
        CREATE INDEX IF NOT EXISTS idx_out_rec     ON outcomes(recommendation_id);
        """)

_init_db()


def _get_recommendation_by_id(recommendation_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE id=?", (recommendation_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# Record a recommendation
# ─────────────────────────────────────────────────────────────────────────────
def record_recommendation(research: dict, scrape: dict = None) -> int:
    """
    Auto-record a recommendation from a deep_research result.
    Called automatically after every research run.
    Returns the recommendation ID.
    """
    ticker = (research.get("ticker") or "").upper()
    if not ticker:
        return 0

    syn  = research.get("synthesis") or {}
    mkt  = research.get("mktdata") or {}
    tp   = syn.get("trade_plan") or {}
    op   = syn.get("options_play") or {}
    bc   = op.get("best_contract") or {}
    ea   = syn.get("earnings_analysis") or {}

    tags      = detect_setup_tags(research, scrape)
    tag_hash  = ",".join(sorted(tags))
    now       = datetime.now(timezone.utc).isoformat()

    # Compress research to key fields only (not full text)
    research_summary = json.dumps({
        "overall_rating": syn.get("overall_rating"),
        "confidence":     syn.get("confidence"),
        "executive_summary": (syn.get("executive_summary") or "")[:200],
        "bull_thesis":    syn.get("bull_thesis"),
        "bear_thesis":    syn.get("bear_thesis"),
        "price_now":      syn.get("price_now"),
    }, ensure_ascii=False)

    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO recommendations
              (ticker, recorded_at, event_date, action, entry_price, stop_loss,
               target_1, target_2, options_strike, options_expiry, options_type,
               options_cost, atlas_rating, atlas_conf, budget, setup_tags,
               setup_hash, research_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ticker, now,
            ea.get("next_date") or mkt.get("next_earnings"),
            tp.get("action"),
            tp.get("entry_price"),   tp.get("stop_loss"),
            tp.get("target_1"),      tp.get("target_2"),
            bc.get("strike"),        bc.get("expiry"),
            bc.get("type"),          bc.get("cost_1_contract"),
            syn.get("overall_rating"), syn.get("confidence"),
            research.get("budget", 100),
            json.dumps(tags), tag_hash,
            research_summary,
        ))
        rec_id = cur.lastrowid

    log.info("Recommendation recorded: %s #%d — %s  tags=[%s]",
             ticker, rec_id, tp.get("action","?"), ", ".join(tags[:4]))
    return rec_id


def delete_recommendation(recommendation_id: int) -> bool:
    """Remove one recommendation and any linked outcomes (dashboard / manual cleanup)."""
    if recommendation_id <= 0:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM outcomes WHERE recommendation_id=?", (recommendation_id,))
        cur = conn.execute("DELETE FROM recommendations WHERE id=?", (recommendation_id,))
        ok = cur.rowcount > 0
    if ok:
        log.info("Recommendation #%d deleted", recommendation_id)
    return ok


def clear_all_recommendations() -> int:
    """Delete every outcome and recommendation row (fresh track record; keeps DB file)."""
    with _connect() as conn:
        conn.execute("DELETE FROM outcomes")
        cur = conn.execute("DELETE FROM recommendations")
        n = cur.rowcount
    log.info("Tracker cleared: %d recommendation rows removed", n)
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Record an outcome (manual or auto)
# ─────────────────────────────────────────────────────────────────────────────
def record_outcome(recommendation_id: int, price_at_event: float,
                   outcome: str, event_type: str = "manual",
                   beat_eps: int = None, beat_rev: int = None,
                   earnings_reaction: float = None, notes: str = "",
                   force_grade: bool = False) -> None:
    """
    Record what actually happened after a recommendation.
    outcome = "WIN" | "LOSS" | "PARTIAL_WIN"
    """
    with _connect() as conn:
        rec = conn.execute(
            "SELECT * FROM recommendations WHERE id=?", (recommendation_id,)
        ).fetchone()
        if not rec:
            log.warning("Recommendation #%d not found", recommendation_id)
            return

        entry  = rec["entry_price"] or 0
        pnl_pct = ((price_at_event - entry) / entry * 100) if entry else 0

        if pnl_pct is not None and abs(pnl_pct) < 0.001 and not force_grade:
            try:
                rec_ref = _get_recommendation_by_id(recommendation_id)
                if rec_ref and rec_ref.get('entry_price') and rec_ref.get('ticker'):
                    import yfinance as _yf
                    fi = getattr(_yf.Ticker(rec_ref['ticker']), 'fast_info', {}) or {}
                    cur = fi.get('last_price') or fi.get('regular_market_price')
                    if cur and float(rec_ref['entry_price']) > 0:
                        pnl_pct = ((float(cur) - float(rec_ref['entry_price']))
                                   / float(rec_ref['entry_price']) * 100)
            except Exception:
                pass

        conn.execute("""
            INSERT INTO outcomes
              (recommendation_id, ticker, graded_at, event_type, price_at_event,
               price_at_entry, pnl_pct, outcome, beat_eps, beat_rev,
               earnings_reaction, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            recommendation_id, rec["ticker"],
            datetime.now(timezone.utc).isoformat(),
            event_type, price_at_event, entry,
            round(pnl_pct, 2), outcome,
            beat_eps, beat_rev, earnings_reaction, notes
        ))

    log.info("Outcome recorded: #%d %s — %s  P/L=%.1f%%",
             recommendation_id, rec["ticker"], outcome, pnl_pct)


def auto_grade_pending(lookback_days: int = 30) -> int:
    """
    Automatically grade recommendations where the event date has passed.
    Fetches current price from yfinance, compares to entry price.
    Returns number of outcomes auto-recorded.
    """
    now     = datetime.now(timezone.utc)
    today_s = now.strftime("%Y-%m-%d")
    graded  = 0

    with _connect() as conn:
        # Find ungraded recommendations with past event dates
        pending = conn.execute("""
            SELECT r.* FROM recommendations r
            LEFT JOIN outcomes o ON o.recommendation_id = r.id
            WHERE o.id IS NULL
              AND r.event_date IS NOT NULL
              AND r.event_date <= ?
              AND r.recorded_at >= datetime(?, '-{} days')
        """.format(lookback_days), (today_s, today_s)).fetchall()

    for rec in pending:
        ticker = rec["ticker"]
        try:
            tk     = yf.Ticker(ticker)
            hist   = tk.history(period="5d")
            if hist.empty:
                continue
            current_price = float(hist["Close"].iloc[-1])
            entry         = rec["entry_price"] or current_price
            pnl_pct       = (current_price - entry) / entry * 100 if entry else 0

            # Simple auto-grade: win if price is above target_1, loss if below stop
            t1   = rec["target_1"] or (entry * 1.10 if entry else 0)
            stop = rec["stop_loss"] or (entry * 0.90 if entry else 0)

            if current_price >= t1:
                outcome = "WIN"
            elif stop and current_price <= stop:
                outcome = "LOSS"
            else:
                outcome = "PARTIAL_WIN" if pnl_pct > 0 else "LOSS"

            record_outcome(
                recommendation_id = rec["id"],
                price_at_event    = current_price,
                outcome           = outcome,
                event_type        = "auto_graded",
                notes             = f"Auto-graded: entry=${entry:.2f}, current=${current_price:.2f}, pnl={pnl_pct:+.1f}%"
            )
            graded += 1
            log.info("Auto-graded %s #%d: %s (%.1f%%)", ticker, rec["id"], outcome, pnl_pct)
        except Exception:
            log.debug("Auto-grade failed for %s #%d", ticker, rec["id"], exc_info=True)

    return graded


# ─────────────────────────────────────────────────────────────────────────────
# Pattern library — win rates by setup type
# ─────────────────────────────────────────────────────────────────────────────
def setup_pattern_stats(min_samples: int = 3) -> list[dict]:
    """
    Calculate win rates for each setup tag combination.
    Only includes setups with at least min_samples outcomes.
    Returns list sorted by win rate (best setups first).
    """
    with _connect() as conn:
        # Get all recommendations with outcomes
        rows = conn.execute("""
            SELECT r.setup_tags, r.ticker, r.atlas_rating, r.atlas_conf,
                   o.outcome, o.pnl_pct, o.earnings_reaction
            FROM recommendations r
            JOIN outcomes o ON o.recommendation_id = r.id
            WHERE o.outcome IN ('WIN','LOSS','PARTIAL_WIN')
        """).fetchall()

    if not rows:
        return []

    # Build per-tag statistics
    tag_stats: dict[str, dict] = {}
    for row in rows:
        try:
            tags = json.loads(row["setup_tags"] or "[]")
        except Exception:
            continue
        outcome = row["outcome"]
        pnl     = row["pnl_pct"] or 0

        for tag in tags:
            if tag not in tag_stats:
                tag_stats[tag] = {"wins": 0, "losses": 0, "partials": 0,
                                   "total": 0, "pnl_sum": 0.0, "tickers": set()}
            s = tag_stats[tag]
            s["total"] += 1
            s["pnl_sum"] += pnl
            s["tickers"].add(row["ticker"])
            if outcome == "WIN":          s["wins"] += 1
            elif outcome == "LOSS":       s["losses"] += 1
            elif outcome == "PARTIAL_WIN": s["partials"] += 1

    results = []
    for tag, s in tag_stats.items():
        if s["total"] < min_samples:
            continue
        win_rate = (s["wins"] + s["partials"] * 0.5) / s["total"] * 100
        avg_pnl  = s["pnl_sum"] / s["total"]
        results.append({
            "tag":        tag,
            "total":      s["total"],
            "wins":       s["wins"],
            "losses":     s["losses"],
            "partials":   s["partials"],
            "win_rate":   round(win_rate, 1),
            "avg_pnl":    round(avg_pnl, 1),
            "tickers":    list(s["tickers"])[:5],
        })

    return sorted(results, key=lambda x: (x["win_rate"], x["total"]), reverse=True)


def pattern_context_for_research(research: dict, scrape: dict = None) -> str:
    """
    Generate a pattern context block to inject into AI synthesis prompts.
    Tells the AI: "setups like this have historically performed as follows."
    """
    tags  = detect_setup_tags(research, scrape)
    stats = setup_pattern_stats(min_samples=3)

    if not stats:
        return ""

    # Find stats for tags present in this setup
    relevant = [s for s in stats if s["tag"] in tags]
    if not relevant:
        return ""

    lines = ["\n=== HISTORICAL PATTERN LIBRARY (ATLAS Track Record) ==="]
    lines.append("This setup contains the following tags and historical win rates:")
    lines.append("")

    for s in relevant[:8]:  # top 8 most relevant
        bar    = "#" * int(s["win_rate"] / 10)
        signal = "STRONG" if s["win_rate"] >= 70 else ("MIXED" if s["win_rate"] >= 50 else "WEAK")
        lines.append(
            f"  [{signal}] {s['tag']}: {s['win_rate']:.0f}% win rate "
            f"({s['wins']}W/{s['losses']}L over {s['total']} trades) "
            f"avg P/L: {s['avg_pnl']:+.1f}%"
        )

    lines.append("")
    lines.append("Use these historical win rates to calibrate your confidence score.")
    lines.append("If multiple tags show >70% win rate, increase confidence.")
    lines.append("If multiple tags show <40% win rate, decrease confidence.")
    lines.append("=== END PATTERN LIBRARY ===\n")

    return "\n".join(lines)


def winrate_summary() -> str:
    """Return a human-readable win rate summary for the CLI / reports."""
    with _connect() as conn:
        total_recs = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        total_out  = conn.execute(
            "SELECT COUNT(*) FROM outcomes WHERE outcome IN ('WIN','LOSS','PARTIAL_WIN')"
        ).fetchone()[0]
        wins  = conn.execute("SELECT COUNT(*) FROM outcomes WHERE outcome='WIN'").fetchone()[0]
        losses = conn.execute("SELECT COUNT(*) FROM outcomes WHERE outcome='LOSS'").fetchone()[0]
        avg   = conn.execute("SELECT AVG(pnl_pct) FROM outcomes WHERE outcome IN ('WIN','LOSS','PARTIAL_WIN')").fetchone()[0]

    if not total_out:
        return f"Track record: {total_recs} recommendations recorded, no outcomes graded yet."

    wr = wins / total_out * 100
    return (
        f"Track record: {total_out} graded outcomes — "
        f"{wins}W / {losses}L / {total_out-wins-losses} partial "
        f"({wr:.0f}% win rate, avg return {avg or 0:+.1f}%)"
    )


def recent_recommendations(limit: int = 10) -> list[dict]:
    """Return most recent recommendations with outcome status."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT r.id, r.ticker, r.recorded_at, r.action, r.entry_price,
                   r.target_1, r.stop_loss, r.atlas_rating, r.atlas_conf,
                   r.event_date, r.setup_tags,
                   o.outcome, o.pnl_pct, o.graded_at
            FROM recommendations r
            LEFT JOIN (
                SELECT recommendation_id, outcome, pnl_pct, graded_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY recommendation_id ORDER BY id DESC
                       ) AS rn
                FROM outcomes
            ) o ON o.recommendation_id = r.id AND o.rn = 1
            ORDER BY r.recorded_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if cmd == "summary":
        print(winrate_summary())
        recs = recent_recommendations(10)
        if recs:
            print(f"\nLast {len(recs)} recommendations:")
            for r in recs:
                tags = json.loads(r.get("setup_tags") or "[]")[:3]
                outcome_str = r.get("outcome") or "OPEN"
                pnl_str     = f" ({r['pnl_pct']:+.1f}%)" if r.get("pnl_pct") is not None else ""
                print(f"  #{r['id']} {r['ticker']:<6} {r.get('recorded_at','')[:10]}  "
                      f"{r.get('action','?'):<12} {r.get('atlas_rating','?'):<12} "
                      f"{outcome_str}{pnl_str}  [{','.join(tags)}]")

    elif cmd == "patterns":
        stats = setup_pattern_stats(min_samples=1)
        if not stats:
            print("No pattern data yet — need graded outcomes.")
        else:
            print(f"\nSetup Pattern Library ({len(stats)} patterns):")
            for s in stats[:20]:
                print(f"  {s['win_rate']:>5.0f}%  {s['tag']:<35} "
                      f"{s['wins']}W/{s['losses']}L  avg {s['avg_pnl']:+.1f}%")

    elif cmd == "grade":
        n = auto_grade_pending()
        print(f"Auto-graded {n} pending recommendations.")

    elif cmd == "outcome" and len(sys.argv) >= 4:
        # python tracker.py outcome <rec_id> <WIN|LOSS|PARTIAL_WIN> <price>
        rec_id  = int(sys.argv[2])
        outcome = sys.argv[3].upper()
        price   = float(sys.argv[4]) if len(sys.argv) > 4 else 0
        record_outcome(rec_id, price, outcome, event_type="manual")
        print(f"Outcome recorded for recommendation #{rec_id}: {outcome}")

    else:
        print("Usage:")
        print("  python tracker.py summary              -- recent recs + win rate")
        print("  python tracker.py patterns             -- setup pattern win rates")
        print("  python tracker.py grade                -- auto-grade pending outcomes")
        print("  python tracker.py outcome 3 WIN 11.50  -- manually record outcome")
