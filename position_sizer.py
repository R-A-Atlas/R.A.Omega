"""
position_sizer.py — ATLAS Position Sizing Engine

Answers the question every trader skips: "How much should I actually buy?"

Three calculation methods:

1. KELLY CRITERION (optimal growth)
   Uses historical win rate + avg win/loss from the tracker database.
   Kelly % = (W * B - L) / B
   where W = win rate, B = avg_win / avg_loss, L = loss rate
   We use HALF-Kelly to reduce volatility (recommended for options).

2. FIXED FRACTIONAL (risk-based, default)
   Risk only X% of your account per trade.
   Default: 2% risk per trade (professional standard).
   Number of contracts = floor(account * risk_pct / max_loss_per_contract)

3. CONFIDENCE-SCALED (ATLAS-native)
   ATLAS confidence score (1-10) scales the position size.
   Score 8-10 → 100% of calculated size
   Score 5-7  → 60% of calculated size
   Score 1-4  → 25% of calculated size (small probe)

Output per call:
  - Exact number of shares OR contracts to buy
  - Total cost
  - Max loss in dollars (defined risk)
  - Expected value (EV) in dollars
  - Risk/reward ratio
  - Kelly optimal %
  - Plain English recommendation: "Buy 3 contracts at $0.45 each = $135 total.
    Max loss: $135. Target profit: $270 (2:1 R/R). Kelly optimal: 4.2%."
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Kelly criterion — uses tracker win rate if available
# ─────────────────────────────────────────────────────────────────────────────
def _kelly_fraction(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """
    Calculate full Kelly fraction.
    win_rate: 0.0 - 1.0  (e.g. 0.65 = 65% wins)
    avg_win_pct: average % gain on winners  (e.g. 1.20 = 120%)
    avg_loss_pct: average % loss on losers  (e.g. 0.85 = 85% loss)
    Returns fraction of capital to risk (0.0 - 1.0).
    """
    if avg_loss_pct <= 0 or win_rate <= 0:
        return 0.0
    loss_rate = 1.0 - win_rate
    b = avg_win_pct / avg_loss_pct  # reward-to-risk ratio
    kelly = (win_rate * b - loss_rate) / b
    return max(0.0, min(kelly, 0.25))  # cap at 25% even if Kelly says more


def _get_tracker_stats(setup_tags: list[str] = None) -> dict:
    """
    Pull historical win rate + avg P/L from tracker.py if available.
    Returns {"win_rate": 0.60, "avg_win_pct": 1.15, "avg_loss_pct": 0.82, "n": 14}
    """
    defaults = {"win_rate": 0.55, "avg_win_pct": 1.10, "avg_loss_pct": 0.85, "n": 0}
    try:
        import tracker
        with tracker._connect() as conn:
            rows = conn.execute("""
                SELECT o.outcome, o.pnl_pct
                FROM outcomes o
                WHERE o.outcome IN ('WIN','LOSS','PARTIAL_WIN')
            """).fetchall()

        if not rows:
            return defaults

        wins  = [r["pnl_pct"] for r in rows if r["outcome"] == "WIN" and r["pnl_pct"]]
        loses = [r["pnl_pct"] for r in rows if r["outcome"] == "LOSS" and r["pnl_pct"]]
        parts = [r["pnl_pct"] for r in rows if r["outcome"] == "PARTIAL_WIN" and r["pnl_pct"]]

        total = len(wins) + len(loses) + len(parts)
        if total < 3:
            return defaults

        win_rate  = (len(wins) + len(parts) * 0.5) / total
        avg_win   = (sum(wins) / len(wins) / 100) if wins else 1.10
        avg_loss  = abs(sum(loses) / len(loses) / 100) if loses else 0.85

        # If setup_tags provided, also get tag-specific stats for top tag
        tag_winrate = None
        if setup_tags:
            try:
                stats = tracker.setup_pattern_stats(min_samples=3)
                tag_stats = [s for s in stats if s["tag"] in setup_tags]
                if tag_stats:
                    best = max(tag_stats, key=lambda x: x["total"])
                    tag_winrate = best["win_rate"] / 100
            except Exception:
                pass

        final_winrate = tag_winrate if tag_winrate else win_rate
        return {
            "win_rate":     round(final_winrate, 3),
            "avg_win_pct":  round(avg_win, 3),
            "avg_loss_pct": round(avg_loss, 3),
            "n":            total,
        }
    except Exception:
        return defaults


# ─────────────────────────────────────────────────────────────────────────────
# Main position sizing function
# ─────────────────────────────────────────────────────────────────────────────
def size_position(
    budget:         float,                # total account / budget in USD
    confidence:     int,                  # ATLAS confidence score 1-10
    entry_price:    float,                # stock price or option premium
    stop_loss:      Optional[float] = None,  # stock stop price
    target_1:       Optional[float] = None,
    target_2:       Optional[float] = None,
    is_options:     bool = False,         # True if sizing options contracts
    options_cost:   Optional[float] = None,  # cost per contract (e.g. $85)
    options_strike: Optional[float] = None,
    options_expiry: Optional[str] = None,
    setup_tags:     Optional[list[str]] = None,
    risk_pct:       float = 0.02,        # default: risk 2% of account per trade
) -> dict:
    """
    Calculate exact position size.
    Returns a complete sizing recommendation with reasoning.
    """
    result: dict = {
        "budget":       budget,
        "confidence":   confidence,
        "entry_price":  entry_price,
        "is_options":   is_options,
    }

    # ── Step 1: Confidence multiplier ────────────────────────────────────────
    if confidence >= 8:
        conf_mult = 1.00   # full size
        conf_label = "HIGH conviction — full size"
    elif confidence >= 6:
        conf_mult = 0.60   # reduced size
        conf_label = "MEDIUM conviction — 60% of calculated size"
    else:
        conf_mult = 0.25   # probe position
        conf_label = "LOW conviction — 25% probe position only"

    result["confidence_multiplier"] = conf_mult
    result["confidence_label"]      = conf_label

    # ── Step 2: Kelly criterion ───────────────────────────────────────────────
    tracker_stats = _get_tracker_stats(setup_tags)
    kelly_frac    = _kelly_fraction(
        tracker_stats["win_rate"],
        tracker_stats["avg_win_pct"],
        tracker_stats["avg_loss_pct"],
    )
    half_kelly    = kelly_frac / 2  # use half-Kelly for safety
    kelly_dollars = budget * half_kelly

    result["kelly"] = {
        "full_kelly_pct":  round(kelly_frac * 100, 1),
        "half_kelly_pct":  round(half_kelly * 100, 1),
        "half_kelly_usd":  round(kelly_dollars, 2),
        "based_on_n":      tracker_stats["n"],
        "win_rate_used":   f"{tracker_stats['win_rate']*100:.0f}%",
        "avg_win_used":    f"+{tracker_stats['avg_win_pct']*100:.0f}%",
        "avg_loss_used":   f"-{tracker_stats['avg_loss_pct']*100:.0f}%",
    }

    if tracker_stats["n"] == 0:
        result["kelly"]["note"] = "No trade history yet — using default 55% win rate. Kelly will improve after 5+ graded trades."

    # ── Step 3: Fixed fractional sizing ──────────────────────────────────────
    max_risk_dollars = budget * risk_pct  # 2% of account by default

    if is_options and options_cost:
        # Options: max loss = full premium paid
        cost_per_contract = options_cost
        max_contracts_by_risk     = int(max_risk_dollars / cost_per_contract)
        max_contracts_by_kelly    = int(kelly_dollars / cost_per_contract)
        max_contracts_by_budget   = int(budget / cost_per_contract)

        # Use the most conservative of the three, then apply confidence multiplier
        raw_contracts = min(max_contracts_by_risk, max_contracts_by_kelly) if half_kelly > 0 else max_contracts_by_risk
        raw_contracts = max(1, raw_contracts)  # at least 1 if budget allows

        final_contracts = max(1, math.floor(raw_contracts * conf_mult))
        final_contracts = min(final_contracts, max_contracts_by_budget)  # can't exceed budget

        total_cost = final_contracts * cost_per_contract
        max_loss   = total_cost  # options: max loss = what you paid

        # Profit targets
        profit_t1  = None
        profit_t2  = None
        if target_1 and entry_price and options_strike:
            # Estimate option value at target: intrinsic value approximation
            if target_1 > options_strike:
                intrinsic_t1 = target_1 - options_strike
                # Contract value = 100 shares * intrinsic value (simplified)
                profit_t1 = final_contracts * (intrinsic_t1 * 100 - cost_per_contract)
        if target_2 and entry_price and options_strike:
            if target_2 > options_strike:
                intrinsic_t2 = target_2 - options_strike
                profit_t2 = final_contracts * (intrinsic_t2 * 100 - cost_per_contract)

        result["recommendation"] = {
            "action":           "BUY CALLS" if not is_options else "BUY OPTIONS",
            "contracts":        final_contracts,
            "cost_per_contract": cost_per_contract,
            "total_cost":       round(total_cost, 2),
            "max_loss":         round(max_loss, 2),
            "max_loss_pct":     round(max_loss / budget * 100, 1),
            "profit_at_t1":     round(profit_t1, 2) if profit_t1 else None,
            "profit_at_t2":     round(profit_t2, 2) if profit_t2 else None,
            "rr_ratio_t1":      round(profit_t1 / max_loss, 2) if profit_t1 and max_loss else None,
            "rr_ratio_t2":      round(profit_t2 / max_loss, 2) if profit_t2 and max_loss else None,
            "contracts_by_risk":  max_contracts_by_risk,
            "contracts_by_kelly": max_contracts_by_kelly,
        }

    else:
        # Stocks: max loss defined by stop loss
        if stop_loss and entry_price and stop_loss < entry_price:
            risk_per_share = entry_price - stop_loss
        else:
            risk_per_share = entry_price * 0.08  # default 8% stop

        shares_by_risk   = int(max_risk_dollars / risk_per_share) if risk_per_share > 0 else 0
        shares_by_kelly  = int(kelly_dollars / entry_price) if half_kelly > 0 else 0
        shares_by_budget = int(budget / entry_price)

        raw_shares    = min(shares_by_risk, shares_by_kelly) if half_kelly > 0 and shares_by_kelly > 0 else shares_by_risk
        raw_shares    = max(1, raw_shares)
        final_shares  = max(1, math.floor(raw_shares * conf_mult))
        final_shares  = min(final_shares, shares_by_budget)

        total_cost = final_shares * entry_price
        max_loss   = final_shares * risk_per_share

        profit_t1 = (target_1 - entry_price) * final_shares if target_1 else None
        profit_t2 = (target_2 - entry_price) * final_shares if target_2 else None

        result["recommendation"] = {
            "action":      "BUY SHARES",
            "shares":      final_shares,
            "entry_price": entry_price,
            "stop_loss":   stop_loss or round(entry_price * 0.92, 2),
            "total_cost":  round(total_cost, 2),
            "max_loss":    round(max_loss, 2),
            "max_loss_pct": round(max_loss / budget * 100, 1),
            "profit_at_t1": round(profit_t1, 2) if profit_t1 else None,
            "profit_at_t2": round(profit_t2, 2) if profit_t2 else None,
            "rr_ratio_t1":  round(profit_t1 / max_loss, 2) if profit_t1 and max_loss else None,
            "rr_ratio_t2":  round(profit_t2 / max_loss, 2) if profit_t2 and max_loss else None,
            "shares_by_risk":  shares_by_risk,
            "shares_by_kelly": shares_by_kelly,
        }

    # ── Step 4: Expected Value calculation ────────────────────────────────────
    wr  = tracker_stats["win_rate"]
    rec = result["recommendation"]
    if rec.get("profit_at_t1") and rec.get("max_loss"):
        ev = (wr * rec["profit_at_t1"]) - ((1 - wr) * rec["max_loss"])
        result["expected_value"] = round(ev, 2)
        result["ev_label"] = (
            f"EV = +${ev:.2f} (positive — take the trade)"
            if ev > 0 else f"EV = -${abs(ev):.2f} (negative — skip or reduce size)"
        )

    # ── Step 5: Plain English summary ─────────────────────────────────────────
    rec = result["recommendation"]
    if is_options and options_cost:
        n   = rec.get("contracts", 0)
        cost = rec.get("total_cost", 0)
        ml  = rec.get("max_loss", 0)
        t1  = rec.get("profit_at_t1")
        t2  = rec.get("profit_at_t2")
        rr  = rec.get("rr_ratio_t1")
        summary_lines = [
            f"BUY {n} CONTRACT{'S' if n != 1 else ''} @ ${options_cost:.2f} each = ${cost:.2f} total.",
            f"Max loss: ${ml:.2f} ({rec.get('max_loss_pct',0):.1f}% of ${budget:.0f} budget).",
        ]
        if t1:
            summary_lines.append(
                f"Target 1 (${target_1}): +${t1:.2f} profit"
                + (f" ({rr:.1f}:1 R/R)" if rr else "")
            )
        if t2:
            summary_lines.append(f"Target 2 (${target_2}): +${t2:.2f} profit")
        if result.get("ev_label"):
            summary_lines.append(result["ev_label"])
        summary_lines.append(f"Conviction: {conf_label}")
        if tracker_stats["n"] > 0:
            summary_lines.append(
                f"Track record: {tracker_stats['win_rate']*100:.0f}% win rate "
                f"over {tracker_stats['n']} trades (Half-Kelly: {half_kelly*100:.1f}%)"
            )
    else:
        sh  = rec.get("shares", 0)
        cost = rec.get("total_cost", 0)
        ml  = rec.get("max_loss", 0)
        sl  = rec.get("stop_loss", 0)
        t1  = rec.get("profit_at_t1")
        t2  = rec.get("profit_at_t2")
        rr  = rec.get("rr_ratio_t1")
        summary_lines = [
            f"BUY {sh} SHARE{'S' if sh != 1 else ''} @ ${entry_price:.2f} = ${cost:.2f} total.",
            f"Stop loss: ${sl:.2f}. Max loss: ${ml:.2f} ({rec.get('max_loss_pct',0):.1f}% of ${budget:.0f}).",
        ]
        if t1:
            summary_lines.append(
                f"Target 1 (${target_1}): +${t1:.2f}"
                + (f" ({rr:.1f}:1 R/R)" if rr else "")
            )
        if t2:
            summary_lines.append(f"Target 2 (${target_2}): +${t2:.2f}")
        if result.get("ev_label"):
            summary_lines.append(result["ev_label"])
        summary_lines.append(f"Conviction: {conf_label}")

    result["summary"] = " | ".join(summary_lines)
    result["summary_lines"] = summary_lines

    log.info("Position sized: %s  total=$%.2f  max_loss=$%.2f  conf=%d",
             rec.get("action","?"), rec.get("total_cost",0), rec.get("max_loss",0), confidence)
    return result


def size_from_research(research: dict) -> dict:
    """
    Auto-size a position directly from a deep_research result dict.
    Called automatically after every research run.
    """
    syn   = research.get("synthesis") or {}
    tp    = syn.get("trade_plan") or {}
    op    = syn.get("options_play") or {}
    bc    = op.get("best_contract") or {}
    mkt   = research.get("mktdata") or {}

    budget     = float(research.get("budget") or 100)
    confidence = int(syn.get("confidence") or 5)
    price      = float(syn.get("price_now") or mkt.get("price") or 0)

    # Try options first if recommended
    options_cost = None
    try:
        options_cost = float(bc.get("cost_1_contract") or 0) or None
    except Exception:
        pass

    is_options = bool(options_cost and op.get("recommended"))

    try:
        stop   = float(tp.get("stop_loss") or 0) or None
        t1     = float(tp.get("target_1")  or 0) or None
        t2     = float(tp.get("target_2")  or 0) or None
        strike = float(bc.get("strike")    or 0) or None
        expiry = bc.get("expiry")
    except Exception:
        stop = t1 = t2 = strike = expiry = None

    # Get setup tags from tracker if possible
    setup_tags = []
    try:
        import tracker
        setup_tags = tracker.detect_setup_tags(research)
    except Exception:
        pass

    if not price:
        return {"error": "No entry price available", "summary": "Cannot size — no price data."}

    return size_position(
        budget       = budget,
        confidence   = confidence,
        entry_price  = price,
        stop_loss    = stop,
        target_1     = t1,
        target_2     = t2,
        is_options   = is_options,
        options_cost = options_cost,
        options_strike = strike,
        options_expiry = expiry,
        setup_tags   = setup_tags,
    )


def to_html(sizing: dict) -> str:
    """Render position sizing result as an HTML block for reports."""
    rec   = sizing.get("recommendation") or {}
    kelly = sizing.get("kelly") or {}
    lines = sizing.get("summary_lines") or [sizing.get("summary","")]

    bullets = "".join(f"<li>{l}</li>" for l in lines)
    kelly_note = ""
    if kelly.get("based_on_n", 0) > 0:
        kelly_note = (
            f"<small style='color:#888'>Kelly based on {kelly['based_on_n']} graded trades · "
            f"Win rate: {kelly.get('win_rate_used','?')} · "
            f"Half-Kelly: {kelly.get('half_kelly_pct','?')}%</small>"
        )
    elif kelly.get("note"):
        kelly_note = f"<small style='color:#888'>{kelly['note']}</small>"

    rr = rec.get("rr_ratio_t1") or rec.get("rr_ratio_t2")
    rr_color = "#4caf50" if rr and rr >= 2.0 else ("#ff9800" if rr and rr >= 1.0 else "#f44336")

    return f"""
<div style="background:#1a1a2e;border:1px solid #2d2d4e;border-radius:8px;padding:16px;margin:12px 0">
  <h3 style="color:#00d4ff;margin:0 0 12px">Position Sizing</h3>
  <ul style="color:#e0e0e0;font-size:13px;line-height:1.8;margin:0;padding-left:20px">
    {bullets}
  </ul>
  {f'<div style="margin-top:10px;color:{rr_color};font-size:13px;font-weight:bold">R/R Ratio: {rr:.1f}:1</div>' if rr else ''}
  <div style="margin-top:8px">{kelly_note}</div>
</div>
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    # Quick demo: python position_sizer.py SOUN 9.50 8 100
    # args: price, confidence, budget
    price      = float(sys.argv[1]) if len(sys.argv) > 1 else 9.50
    confidence = int(sys.argv[2])   if len(sys.argv) > 2 else 7
    budget     = float(sys.argv[3]) if len(sys.argv) > 3 else 100.0

    print(f"\nPosition Sizing for ${price:.2f} stock (conf={confidence}/10, budget=${budget})\n")

    # Stock example
    stock = size_position(
        budget=budget, confidence=confidence,
        entry_price=price, stop_loss=price * 0.90,
        target_1=price * 1.20, target_2=price * 1.40,
        is_options=False
    )
    print("--- STOCK ---")
    for line in stock["summary_lines"]:
        print(f"  {line}")

    print()

    # Options example ($0.45 contract)
    opts = size_position(
        budget=budget, confidence=confidence,
        entry_price=price,
        target_1=price * 1.20, target_2=price * 1.40,
        is_options=True, options_cost=45.0,
        options_strike=price * 1.05,
    )
    print("--- OPTIONS ---")
    for line in opts["summary_lines"]:
        print(f"  {line}")
