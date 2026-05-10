"""
paper_trader.py - ATLAS Autonomous Paper Trading State Machine

ATLAS autonomously places and manages paper trades on Alpaca based on deep research
output. Entry via confidence-scaled sizing. Exit via bracket order (take-profit +
stop-loss in one API call). Auto-grades outcomes in tracker.py to close the
self-learning loop.

State flow per trade:
  PENDING  → deep research flagged, not yet placed (rare, usually skips directly to OPEN)
  OPEN     → bracket order live on Alpaca, monitoring
  CLOSED_WIN  → take-profit hit, graded WIN in tracker
  CLOSED_LOSS → stop-loss hit, graded LOSS in tracker
  SKIPPED  → conviction too low, logged but not traded

Usage:
    python paper_trader.py status           # show all trades
    python paper_trader.py monitor          # start 60s monitor loop (Ctrl+C to stop)
    python paper_trader.py close AAPL       # manually close a position
    python paper_trader.py clear-closed     # remove closed trades from state file
    python paper_trader.py propose TICKER   # run research + propose a trade

Integration (called from deep_research.py automatically):
    import paper_trader
    paper_trader.propose_trade(research_dict)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from gemini_limiter import wait_for_slot

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
STATE_FILE         = Path(__file__).parent / "paper_trades.json"
_MIN_CONVICTION_DEFAULT = 7.0   # fallback if adaptive threshold file not found
MIN_CONVICTION     = _MIN_CONVICTION_DEFAULT  # overridden at runtime by auto_tuner
MAX_OPEN_POSITIONS = 5          # max concurrent paper positions
MAX_POSITION_PCT   = 0.10       # max 10% of account equity per trade
MIN_POSITION_PCT   = 0.01       # min 1% of account equity per trade
MONITOR_INTERVAL_S = 60         # seconds between monitor checks
DEFAULT_TP_PCT     = 0.15       # fallback take-profit: +15% from entry
DEFAULT_SL_PCT     = 0.07       # fallback stop-loss: -7% from entry

# Actions from deep research that result in a BUY order
TRADEABLE_ACTIONS = {"buy_stock", "buy", "strong_buy"}
BULLISH_RATINGS   = {"strong_buy", "buy"}


# ─────────────────────────────────────────────────────────────────────────────
# State persistence
# ─────────────────────────────────────────────────────────────────────────────

def _load_state() -> list[dict]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_state(trades: list[dict]) -> None:
    STATE_FILE.write_text(json.dumps(trades, indent=2, default=str), encoding="utf-8")


def _update_trade(trade_id: str, updates: dict) -> None:
    trades = _load_state()
    for t in trades:
        if t.get("id") == trade_id:
            t.update(updates)
            break
    _save_state(trades)


# ─────────────────────────────────────────────────────────────────────────────
# Alpaca helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_alpaca():
    """Get the Alpaca TradingClient (reuses broker_alpaca's lazy client)."""
    try:
        import broker_alpaca as alp
        return alp._get_client(), alp
    except Exception as e:
        log.error("[paper] Alpaca unavailable: %s", e)
        return None, None


def _current_positions() -> dict[str, dict]:
    """Return {ticker: position_dict} for all open Alpaca positions."""
    try:
        import broker_alpaca as alp
        positions = alp.get_positions()
        return {p["symbol"]: p for p in positions}
    except Exception:
        return {}


def _get_account_equity() -> float:
    """Return current paper account equity."""
    try:
        import broker_alpaca as alp
        acct = alp.get_account()
        return float(acct.get("equity", 100_000)) if acct else 100_000.0
    except Exception:
        return 100_000.0


def _determine_close_outcome(ticker: str, order_id: str,
                              entry_price: float, stop_loss: float,
                              target_price: float) -> tuple[str, float]:
    """
    Determine if a closed position was a WIN or LOSS.
    Tries Alpaca order legs first, falls back to yfinance price.
    Returns (outcome, close_price).
    """
    client, alp = _get_alpaca()
    if client and order_id:
        try:
            order = client.get_order_by_id(order_id)
            legs  = getattr(order, "legs", None) or []
            for leg in legs:
                status     = str(getattr(leg, "status", "")).lower()
                fill_price = getattr(leg, "filled_avg_price", None)
                if status in ("filled", "partially_filled") and fill_price:
                    fp = float(fill_price)
                    outcome = "WIN" if fp > entry_price else "LOSS"
                    log.info("[paper] %s closed via bracket leg @ $%.2f → %s", ticker, fp, outcome)
                    return outcome, fp
        except Exception as e:
            log.debug("[paper] Bracket leg check failed for %s: %s", ticker, e)

    # Fallback: use yfinance price
    try:
        import yfinance as yf
        price = yf.Ticker(ticker).fast_info.get("lastPrice") or entry_price
        price = float(price)
        # Use midpoint between entry and stop as WIN/LOSS divider
        midpoint = (entry_price + stop_loss) / 2
        outcome  = "WIN" if price >= entry_price else "LOSS"
        log.info("[paper] %s outcome via yfinance price $%.2f → %s", ticker, price, outcome)
        return outcome, price
    except Exception:
        return "UNKNOWN", entry_price


# ─────────────────────────────────────────────────────────────────────────────
# Market hours check
# ─────────────────────────────────────────────────────────────────────────────

def _is_market_hours() -> bool:
    """Return True if US market is currently open (simple check, no holiday logic)."""
    from datetime import timezone as tz
    try:
        import pytz
        et = pytz.timezone("America/New_York")
        now = datetime.now(et)
    except ImportError:
        # Fallback: UTC-5 approximate
        from datetime import timedelta
        now_utc = datetime.now(tz.utc)
        now     = now_utc.replace(tzinfo=None) - __import__("datetime").timedelta(hours=5)

    weekday = now.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:          # weekend
        return False
    hour, minute = now.hour, now.minute
    open_mins  = 9 * 60 + 30   # 9:30 AM
    close_mins = 16 * 60        # 4:00 PM
    current    = hour * 60 + minute
    return open_mins <= current < close_mins


# ─────────────────────────────────────────────────────────────────────────────
# Position sizing
# ─────────────────────────────────────────────────────────────────────────────

def _compute_shares(equity: float, entry_price: float,
                    stop_loss: float, confidence: int) -> int:
    """
    Size a stock position using risk-based sizing.
    Risk at most MAX_POSITION_PCT * equity, scaled by confidence.
    Returns integer share count (minimum 1).
    """
    # Confidence scale: 10 = 100%, 7 = 60%, below 7 = skip
    conf_scale = {10: 1.0, 9: 0.9, 8: 0.75, 7: 0.6}.get(min(confidence, 10), 0.5)
    max_dollar = equity * MAX_POSITION_PCT * conf_scale
    min_dollar = equity * MIN_POSITION_PCT

    # Risk per share = distance to stop
    risk_per_share = abs(entry_price - stop_loss)
    if risk_per_share < 0.01:
        risk_per_share = entry_price * DEFAULT_SL_PCT  # fallback

    # 2% account risk rule
    risk_budget  = equity * 0.02 * conf_scale
    shares_by_risk = risk_budget / risk_per_share

    # Cap by max dollar amount
    shares_by_dollar = max_dollar / entry_price

    shares = int(min(shares_by_risk, shares_by_dollar))
    shares = max(1, shares)

    # Final sanity: total cost must be at least min_dollar
    if shares * entry_price < min_dollar:
        shares = max(1, int(min_dollar / entry_price))

    return shares


# ─────────────────────────────────────────────────────────────────────────────
# Core: propose a trade from deep research output
# ─────────────────────────────────────────────────────────────────────────────

def propose_trade(research: dict) -> Optional[dict]:
    """
    Evaluate a deep research result and place a paper trade if conviction is high.
    Called automatically from deep_research.py after research completes.

    Returns the trade dict if placed, None if skipped.
    """
    # Load adaptive conviction threshold (auto_tuner adjusts this over time)
    global MIN_CONVICTION
    try:
        import auto_tuner as _at
        MIN_CONVICTION = _at.load_paper_conviction()
    except Exception:
        MIN_CONVICTION = _MIN_CONVICTION_DEFAULT

    syn    = research.get("synthesis") or {}
    tp     = syn.get("trade_plan") or {}
    ticker = (research.get("ticker") or syn.get("ticker") or "").upper()

    if not ticker:
        log.debug("[paper] No ticker in research dict — skipping")
        return None

    confidence   = int(syn.get("confidence") or 0)
    rating       = str(syn.get("overall_rating") or "").lower()
    action       = str(tp.get("action") or "").lower().replace(" ", "_")
    entry_price  = tp.get("entry_price")
    stop_loss    = tp.get("stop_loss")
    target_1     = tp.get("target_1")

    log.info("[paper] Evaluating %s: confidence=%d rating=%s action=%s",
             ticker, confidence, rating, action)

    # ── Conviction gate ─────────────────────────────────────────────────────
    if confidence < MIN_CONVICTION:
        log.info("[paper] %s skipped — conviction %d < %d threshold",
                 ticker, confidence, MIN_CONVICTION)
        _append_skipped(ticker, confidence, f"conviction {confidence} < {MIN_CONVICTION}")
        return None

    if action not in TRADEABLE_ACTIONS and rating not in BULLISH_RATINGS:
        log.info("[paper] %s skipped — action=%s rating=%s not tradeable",
                 ticker, action, rating)
        _append_skipped(ticker, confidence, f"action={action} not tradeable")
        return None

    # ── Open positions cap ───────────────────────────────────────────────────
    trades = _load_state()
    open_count = sum(1 for t in trades if t.get("state") == "OPEN")
    if open_count >= MAX_OPEN_POSITIONS:
        log.info("[paper] %s skipped — already at max %d open positions", ticker, MAX_OPEN_POSITIONS)
        return None

    # ── Already have an open trade for this ticker? ──────────────────────────
    if any(t.get("ticker") == ticker and t.get("state") == "OPEN" for t in trades):
        log.info("[paper] %s skipped — already have an open position", ticker)
        return None

    # ── Market hours check ───────────────────────────────────────────────────
    if not _is_market_hours():
        log.info("[paper] %s skipped — market is closed", ticker)
        return None

    # ── Get current price if entry_price missing ─────────────────────────────
    if not entry_price:
        try:
            import yfinance as yf
            entry_price = float(yf.Ticker(ticker).fast_info.get("lastPrice", 0))
        except Exception:
            pass
    if not entry_price or entry_price <= 0:
        log.warning("[paper] %s skipped — no entry price available", ticker)
        return None
    entry_price = float(entry_price)

    # ── Fill in missing stop / target with defaults ───────────────────────────
    if not stop_loss or float(stop_loss) <= 0:
        stop_loss = round(entry_price * (1 - DEFAULT_SL_PCT), 2)
    stop_loss = float(stop_loss)

    if not target_1 or float(target_1) <= entry_price:
        target_1 = round(entry_price * (1 + DEFAULT_TP_PCT), 2)
    target_1 = float(target_1)

    # ── Position sizing ──────────────────────────────────────────────────────
    equity = _get_account_equity()
    shares = _compute_shares(equity, entry_price, stop_loss, confidence)
    total_cost = shares * entry_price

    log.info("[paper] Sizing %s: %d shares @ $%.2f = $%.0f | TP=$%.2f | SL=$%.2f",
             ticker, shares, entry_price, total_cost, target_1, stop_loss)

    # ── Place bracket order on Alpaca ────────────────────────────────────────
    _, alp = _get_alpaca()
    if not alp:
        log.error("[paper] Alpaca unavailable — cannot place trade for %s", ticker)
        return None

    order = alp.place_bracket_order(
        ticker      = ticker,
        qty         = shares,
        side        = "buy",
        take_profit = target_1,
        stop_loss   = stop_loss,
        reason      = f"ATLAS auto-paper: confidence={confidence}/10 {rating}",
    )

    if not order:
        log.error("[paper] Bracket order failed for %s", ticker)
        return None

    # ── Record in tracker.py ─────────────────────────────────────────────────
    rec_id = 0
    try:
        import tracker
        rec_id = tracker.record_recommendation(research)
    except Exception as e:
        log.debug("[paper] tracker.record_recommendation failed: %s", e)

    # ── Save state ───────────────────────────────────────────────────────────
    trade = {
        "id":            str(uuid.uuid4())[:8],
        "ticker":        ticker,
        "state":         "OPEN",
        "side":          "buy",
        "qty":           shares,
        "entry_price":   entry_price,
        "target_price":  target_1,
        "stop_loss":     stop_loss,
        "alpaca_order_id": order.get("order_id", ""),
        "rec_id":        rec_id,
        "confidence":    confidence,
        "rating":        rating,
        "placed_at":     datetime.now(timezone.utc).isoformat(),
        "closed_at":     None,
        "closed_price":  None,
        "pnl":           None,
        "pnl_pct":       None,
        "outcome":       None,
        "notes":         f"ATLAS confidence={confidence}/10 | TP=${target_1:.2f} | SL=${stop_loss:.2f}",
    }

    trades.append(trade)
    _save_state(trades)

    log.info("[paper] PLACED: %s %d shares @ $%.2f | TP=$%.2f | SL=$%.2f | order=%s",
             ticker, shares, entry_price, target_1, stop_loss, order.get("order_id", "?")[:8])

    return trade


def _append_skipped(ticker: str, confidence: int, reason: str) -> None:
    """Log a skipped trade to state for audit trail."""
    trades = _load_state()
    trades.append({
        "id":         str(uuid.uuid4())[:8],
        "ticker":     ticker,
        "state":      "SKIPPED",
        "confidence": confidence,
        "reason":     reason,
        "placed_at":  datetime.now(timezone.utc).isoformat(),
    })
    _save_state(trades)


# ─────────────────────────────────────────────────────────────────────────────
# Core: monitor open trades and auto-grade closed ones
# ─────────────────────────────────────────────────────────────────────────────

def monitor_trades() -> dict:
    """
    Check all OPEN trades against current Alpaca positions.
    Close and auto-grade any that are no longer in Alpaca.
    Returns summary dict.
    """
    trades  = _load_state()
    open_trades = [t for t in trades if t.get("state") == "OPEN"]

    if not open_trades:
        log.debug("[paper] No open trades to monitor")
        return {"open": 0, "just_closed": 0}

    current_positions = _current_positions()
    just_closed = 0

    for trade in open_trades:
        ticker   = trade["ticker"]
        trade_id = trade["id"]

        if ticker in current_positions:
            # Still open — update unrealized P&L
            pos    = current_positions[ticker]
            upl    = pos.get("unrealized_pl")
            uplpct = pos.get("unrealized_plpc")
            _update_trade(trade_id, {
                "unrealized_pl":  round(upl, 2) if upl else None,
                "unrealized_plpc": round(float(uplpct) * 100, 2) if uplpct else None,
            })
            log.debug("[paper] %s still OPEN | UPL=$%s", ticker, upl)
        else:
            # Position is gone — it closed (TP or SL hit)
            log.info("[paper] %s no longer in Alpaca positions — determining outcome...", ticker)

            outcome, close_price = _determine_close_outcome(
                ticker      = ticker,
                order_id    = trade.get("alpaca_order_id", ""),
                entry_price = trade.get("entry_price", 0),
                stop_loss   = trade.get("stop_loss", 0),
                target_price= trade.get("target_price", 0),
            )

            entry  = float(trade.get("entry_price", close_price) or close_price)
            qty    = int(trade.get("qty", 1))
            pnl    = round((close_price - entry) * qty, 2)
            pnl_pct= round((close_price - entry) / entry * 100, 2) if entry else 0

            state  = "CLOSED_WIN" if outcome == "WIN" else "CLOSED_LOSS"
            if outcome == "UNKNOWN":
                state = "CLOSED_WIN" if pnl >= 0 else "CLOSED_LOSS"

            _update_trade(trade_id, {
                "state":        state,
                "outcome":      "WIN" if "WIN" in state else "LOSS",
                "closed_at":    datetime.now(timezone.utc).isoformat(),
                "closed_price": round(close_price, 2),
                "pnl":          pnl,
                "pnl_pct":      pnl_pct,
            })

            # Auto-grade in tracker.py
            rec_id = trade.get("rec_id", 0)
            if rec_id:
                try:
                    import tracker
                    tracker.record_outcome(
                        recommendation_id = rec_id,
                        price_at_event    = close_price,
                        outcome           = "WIN" if "WIN" in state else "LOSS",
                        event_type        = "paper_trade_close",
                        notes             = f"Paper trade auto-graded | PnL=${pnl:+.2f} ({pnl_pct:+.2f}%)",
                    )
                    log.info("[paper] Auto-graded rec_id=%d -> %s ($%+.2f)", rec_id, state, pnl)
                except Exception as e:
                    log.debug("[paper] Auto-grade failed: %s", e)

            # Trade post-mortem: Gemini extracts a lesson, stored in memory
            _run_trade_postmortem(trade, state, pnl_pct, close_price)

            icon = "[WIN]" if "WIN" in state else "[LOSS]"
            log.info("[paper] %s %s closed %s @ $%.2f | PnL: $%+.2f (%+.2f%%)",
                     icon, ticker, state, close_price, pnl, pnl_pct)
            just_closed += 1

    remaining_open = sum(1 for t in _load_state() if t.get("state") == "OPEN")
    return {"open": remaining_open, "just_closed": just_closed}


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Trade post-mortem — Gemini extracts a lesson from each closed trade
# ─────────────────────────────────────────────────────────────────────────────

def _run_trade_postmortem(trade: dict, state: str, pnl_pct: float, close_price: float) -> None:
    """
    After a paper trade closes, ask Gemini to write a 2-sentence lesson
    about what worked or what went wrong. Store it in memory as a trade_lesson
    so future research on the same ticker or same setup can reference it.
    Runs in a try/except — never blocks monitor loop.
    """
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
        load_dotenv()

        api_key = (os.environ.get("GEMINI_API_KEY", "")
                   or os.environ.get("GOOGLE_API_KEY", "")).strip()
        if not api_key:
            return

        from google import genai
        client = genai.Client(api_key=api_key)

        outcome   = "WIN" if "WIN" in state else "LOSS"
        ticker    = trade.get("ticker", "?")
        setup     = ", ".join(trade.get("setup_tags", [])) or "general bullish"
        entry     = trade.get("entry_price", "?")
        target    = trade.get("target_price", "?")
        stop      = trade.get("stop_loss", "?")
        rationale = trade.get("rationale", "")[:200]
        placed_at = trade.get("placed_at", "?")[:10]

        prompt = f"""A paper trade just closed on {ticker}. Extract ONE concrete lesson.

Trade details:
- Ticker: {ticker}
- Setup tags: {setup}
- Entry: ${entry}  |  Target: ${target}  |  Stop: ${stop}
- Outcome: {outcome}  |  PnL: {pnl_pct:+.1f}%
- Close price: ${close_price:.2f}
- Original rationale: {rationale}
- Trade placed: {placed_at}

Write exactly 2 sentences:
1. What specifically caused this {outcome} (be concrete, not generic)
2. What to do differently or repeat next time for this setup type

Do NOT use bullet points. Just 2 plain sentences. Max 60 words total."""

        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        try:
            wait_for_slot("paper_trader")
            resp   = client.models.generate_content(model=model, contents=prompt)
            lesson = (resp.text or "").strip()
        except Exception:
            try:
                wait_for_slot("paper_trader_fallback")
                resp   = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                lesson = (resp.text or "").strip()
            except Exception:
                return

        if not lesson or len(lesson) < 20:
            return

        import memory as _mem
        _mem.remember(
            ticker     = ticker,
            fact_type  = "trade_lesson",
            key        = f"paper_{outcome.lower()}_{placed_at}",
            value      = lesson,
            confidence = 0.9 if outcome == "WIN" else 0.8,
            sources    = ["paper_trade_postmortem"],
        )
        log.info("[paper] Post-mortem lesson stored for %s: %s", ticker, lesson[:80])

    except Exception as e:
        log.debug("[paper] Post-mortem failed (non-critical): %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Monitor daemon loop
# ─────────────────────────────────────────────────────────────────────────────

def run_monitor_loop(interval_s: int = MONITOR_INTERVAL_S) -> None:
    """
    Run the monitor loop indefinitely. Press Ctrl+C to stop.
    Auto-triggers auto_tuner.run_cycle() after grading closed trades.
    """
    log.info("[paper] Monitor started — checking every %ds. Ctrl+C to stop.", interval_s)
    while True:
        try:
            result = monitor_trades()
            if result.get("just_closed", 0) > 0:
                # Trigger auto-tuner after any new grades
                try:
                    import auto_tuner
                    auto_tuner.run_cycle()
                    log.info("[paper] Auto-tuner cycle triggered after trade close")
                except Exception:
                    pass
            log.info("[paper] Monitor tick | open=%d | just_closed=%d",
                     result.get("open", 0), result.get("just_closed", 0))
        except Exception as e:
            log.error("[paper] Monitor error: %s", e)
        time.sleep(interval_s)


# ─────────────────────────────────────────────────────────────────────────────
# Summary for dashboard / CLI
# ─────────────────────────────────────────────────────────────────────────────

def get_summary() -> dict:
    """Return a summary dict suitable for dashboard display."""
    trades = _load_state()
    open_   = [t for t in trades if t.get("state") == "OPEN"]
    wins    = [t for t in trades if t.get("outcome") == "WIN"]
    losses  = [t for t in trades if t.get("outcome") == "LOSS"]
    skipped = [t for t in trades if t.get("state") == "SKIPPED"]
    closed  = wins + losses

    total_pnl = sum(float(t.get("pnl") or 0) for t in closed)
    win_rate  = (len(wins) / len(closed) * 100) if closed else 0

    return {
        "open_trades":    open_,
        "closed_trades":  sorted(closed, key=lambda x: x.get("closed_at", ""), reverse=True)[:10],
        "skipped_count":  len(skipped),
        "total_trades":   len(closed),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       round(win_rate, 1),
        "total_pnl":      round(total_pnl, 2),
        "max_open":       MAX_OPEN_POSITIONS,
    }


def close_position_manual(ticker: str) -> bool:
    """Manually close an open paper trade and mark it closed."""
    tk = ticker.upper()
    _, alp = _get_alpaca()
    if alp:
        result = alp.close_position(tk)
        if result:
            log.info("[paper] Manually closed position %s on Alpaca", tk)
        else:
            # Position may not be filled yet — cancel any pending orders for this ticker
            try:
                orders = alp.get_open_orders()
                for o in orders:
                    if o.get("symbol") == tk:
                        alp.cancel_order(o["id"])
                        log.info("[paper] Cancelled pending order %s for %s", o["id"][:8], tk)
            except Exception as e:
                log.debug("[paper] Cancel pending orders failed for %s: %s", tk, e)

    trades = _load_state()
    closed_any = False
    for t in trades:
        if t.get("ticker") == tk and t.get("state") == "OPEN":
            try:
                import yfinance as yf
                close_price = float(yf.Ticker(tk).fast_info.get("lastPrice", t.get("entry_price", 0)))
            except Exception:
                close_price = float(t.get("entry_price", 0))

            entry   = float(t.get("entry_price", close_price) or close_price)
            qty     = int(t.get("qty", 1))
            pnl     = round((close_price - entry) * qty, 2)
            pnl_pct = round((close_price - entry) / entry * 100, 2) if entry else 0
            outcome = "WIN" if pnl >= 0 else "LOSS"

            t.update({
                "state":        "CLOSED_WIN" if outcome == "WIN" else "CLOSED_LOSS",
                "outcome":      outcome,
                "closed_at":    datetime.now(timezone.utc).isoformat(),
                "closed_price": round(close_price, 2),
                "pnl":          pnl,
                "pnl_pct":      pnl_pct,
                "notes":        (t.get("notes", "") or "") + " | Manually closed",
            })

            rec_id = t.get("rec_id", 0)
            if rec_id:
                try:
                    import tracker
                    tracker.record_outcome(rec_id, close_price, outcome,
                                           event_type="manual_close",
                                           notes=f"Manual close | PnL=${pnl:+.2f}")
                except Exception:
                    pass

            closed_any = True
            log.info("[paper] Manual close %s @ $%.2f | PnL: $%+.2f (%+.2f%%)",
                     tk, close_price, pnl, pnl_pct)

    _save_state(trades)
    return closed_any


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _print_summary():
    summary = get_summary()
    open_trades   = summary["open_trades"]
    closed_trades = summary["closed_trades"]

    print(f"\n{'='*60}")
    print(f"  ATLAS PAPER TRADING — STATE MACHINE")
    print(f"{'='*60}")
    print(f"  Open positions:  {len(open_trades)} / {summary['max_open']}")
    print(f"  Total trades:    {summary['total_trades']}")
    print(f"  Win rate:        {summary['win_rate']:.1f}%  ({summary['wins']}W / {summary['losses']}L)")
    print(f"  Total P&L:       ${summary['total_pnl']:+,.2f}")
    print(f"  Skipped:         {summary['skipped_count']} (conviction too low)")

    if open_trades:
        print(f"\n  Open Trades:")
        print(f"  {'Ticker':<8} {'Qty':>5} {'Entry':>8} {'TP':>8} {'SL':>8} {'UPL':>8} {'Since'}")
        print(f"  {'-'*65}")
        for t in open_trades:
            upl   = t.get("unrealized_pl")
            upl_s = f"${upl:+.2f}" if upl is not None else "—"
            since = (t.get("placed_at", "")[:10])
            print(f"  {t['ticker']:<8} {t.get('qty',0):>5} "
                  f"${t.get('entry_price',0):>7.2f} "
                  f"${t.get('target_price',0):>7.2f} "
                  f"${t.get('stop_loss',0):>7.2f} "
                  f"{upl_s:>8} {since}")

    if closed_trades:
        print(f"\n  Recent Closed Trades:")
        print(f"  {'Ticker':<8} {'Out':>6} {'Entry':>8} {'Close':>8} {'PnL':>9} {'Closed'}")
        print(f"  {'-'*60}")
        for t in closed_trades[:8]:
            out   = t.get("outcome", "?")
            pnl   = t.get("pnl")
            pnl_s = f"${pnl:+.2f}" if pnl is not None else "-"
            close = (t.get("closed_at", "")[:10])
            icon  = "[W]" if out == "WIN" else "[L]"
            print(f"  {t['ticker']:<8} {icon} {out:<4} "
                  f"${t.get('entry_price',0):>7.2f} "
                  f"${t.get('closed_price',0):>7.2f} "
                  f"{pnl_s:>9} {close}")

    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd  = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg2 = sys.argv[2].upper() if len(sys.argv) > 2 else ""

    if cmd == "status":
        _print_summary()

    elif cmd == "monitor":
        print(f"\nStarting monitor loop (every {MONITOR_INTERVAL_S}s). Ctrl+C to stop.")
        run_monitor_loop()

    elif cmd == "close" and arg2:
        ok = close_position_manual(arg2)
        print(f"Close {'succeeded' if ok else 'failed'} for {arg2}")

    elif cmd == "clear-closed":
        trades = _load_state()
        before = len(trades)
        trades = [t for t in trades if t.get("state") in ("OPEN", "PENDING")]
        _save_state(trades)
        print(f"Cleared {before - len(trades)} closed/skipped trades. {len(trades)} remain.")

    elif cmd == "propose" and arg2:
        print(f"\nRunning deep research + paper trade proposal for {arg2}...")
        try:
            import deep_research as dr
            research = dr.research_ticker(arg2, budget=1000)
            trade    = propose_trade(research)
            if trade:
                print(f"\n  Trade placed: {trade['qty']} shares of {trade['ticker']}")
                print(f"  Entry: ${trade['entry_price']:.2f} | TP: ${trade['target_price']:.2f} | SL: ${trade['stop_loss']:.2f}")
            else:
                print(f"\n  No trade placed (check logs for reason)")
        except Exception as e:
            print(f"  Error: {e}")

    else:
        print(__doc__)
