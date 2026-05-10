"""
options_simulator.py — Options Profit/Loss Calculator

Pure Python math — no API keys, no scraping, no rate limits.

What it does:
  Given a real options contract (strike, expiry, ask price, budget):
  1. Calculates exact P/L at every possible stock price at expiry
  2. Finds breakeven price, max loss, profit at multiple targets
  3. Shows theta decay — how much value you lose per day just from time
  4. Models IV crush — what happens to option value after earnings event
  5. Generates an HTML P/L curve visualization embedded in the report
  6. Produces a text summary for the AI synthesis context

This answers the question: "If I put $100 into this contract, what exactly
happens to my money at each possible outcome?"
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Black-Scholes helpers — used for IV crush and theta estimates
# ─────────────────────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Standard normal CDF — approximation accurate to 7 decimal places."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_price(S: float, K: float, T: float, r: float,
              sigma: float, option_type: str = "call") -> float:
    """
    Black-Scholes option price.
    S = stock price, K = strike, T = time in years, r = risk-free rate,
    sigma = implied volatility (as decimal, e.g. 0.80 = 80%), type = call/put
    """
    if T <= 0 or sigma <= 0:
        # At expiry: intrinsic value only
        if option_type == "call":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bs_theta(S: float, K: float, T: float, r: float,
              sigma: float, option_type: str = "call") -> float:
    """
    Black-Scholes theta — daily dollar loss per share from time decay.
    Returns negative number (theta is always negative for long options).
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    norm_pdf_d1 = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)

    if option_type == "call":
        theta_annual = (
            -(S * norm_pdf_d1 * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        )
    else:
        theta_annual = (
            -(S * norm_pdf_d1 * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        )
    return theta_annual / 365  # daily theta per share


def _implied_vol_from_price(S: float, K: float, T: float, r: float,
                             market_price: float, option_type: str = "call",
                             iterations: int = 50) -> float:
    """
    Newton-Raphson IV solver — back-solves for IV given market option price.
    Returns implied volatility as a decimal (0.80 = 80% IV).
    """
    if T <= 0 or market_price <= 0:
        return 0.5  # fallback

    sigma = 0.5  # initial guess
    for _ in range(iterations):
        price = _bs_price(S, K, T, r, sigma, option_type)
        diff  = price - market_price
        if abs(diff) < 0.0001:
            break
        # Vega
        d1   = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        vega = S * math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi) * math.sqrt(T)
        if vega < 1e-10:
            break
        sigma -= diff / vega
        sigma  = max(0.01, min(sigma, 5.0))  # clamp to reasonable range

    return sigma


# ─────────────────────────────────────────────────────────────────────────────
# Core simulator
# ─────────────────────────────────────────────────────────────────────────────

def simulate(
    ticker:       str,
    strike:       float,
    expiry:       str,         # "YYYY-MM-DD"
    ask:          float,       # cost per share (multiply by 100 for 1 contract)
    current_price: float,
    option_type:  str  = "call",
    budget:       float = 100.0,
    r:            float = 0.045,   # risk-free rate ~4.5%
    iv_override:  Optional[float] = None,  # if known, pass IV as decimal
    iv_crush_pct: Optional[float] = None,  # e.g. 0.30 = IV drops 30% post-earnings
) -> dict:
    """
    Full options scenario analysis.

    Returns a dict with:
      - scenarios: list of {stock_price, pnl_dollars, pnl_pct, contracts}
      - greeks: {iv, theta_daily, delta_approx}
      - summary: text block ready for AI context
      - html_chart: embedded HTML P/L visualization
    """
    ticker       = ticker.upper()
    option_type  = option_type.lower()
    cost_contract = round(ask * 100, 2)
    contracts     = max(1, int(budget // cost_contract))
    total_cost    = contracts * cost_contract

    # Days to expiry
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        today    = date.today()
        dte      = max(1, (exp_date - today).days)
    except Exception:
        dte = 14   # fallback

    T = dte / 365.0  # time in years

    # Implied volatility — back-solve from market price if not given
    iv = iv_override or _implied_vol_from_price(current_price, strike, T, r, ask, option_type)

    # Greeks
    theta_per_share = _bs_theta(current_price, strike, T, r, iv, option_type)
    theta_per_contract = theta_per_share * 100  # 1 contract = 100 shares

    # Delta approximation
    if T > 0 and iv > 0:
        d1    = (math.log(current_price / strike) + (r + 0.5 * iv**2) * T) / (iv * math.sqrt(T))
        delta = _norm_cdf(d1) if option_type == "call" else _norm_cdf(d1) - 1.0
    else:
        delta = 0.5

    # ── Scenario analysis: P/L at expiry ─────────────────────────────────────
    # Price range: from 40% below to 100% above current price
    lo = current_price * 0.40
    hi = current_price * 2.00
    steps = 30
    step  = (hi - lo) / steps

    scenarios = []
    for i in range(steps + 1):
        sp = round(lo + i * step, 2)
        if option_type == "call":
            intrinsic = max(0.0, sp - strike)
        else:
            intrinsic = max(0.0, strike - sp)

        pnl_per_share   = intrinsic - ask
        pnl_per_contract = pnl_per_share * 100
        total_pnl        = pnl_per_contract * contracts
        pnl_pct          = (total_pnl / total_cost) * 100 if total_cost > 0 else 0

        scenarios.append({
            "stock_price":  sp,
            "pnl_dollars":  round(total_pnl, 2),
            "pnl_pct":      round(pnl_pct, 1),
            "pnl_per_contract": round(pnl_per_contract, 2),
        })

    # ── IV crush scenario ─────────────────────────────────────────────────────
    iv_crush_scenario = None
    if iv_crush_pct and iv > 0:
        iv_post_crush = iv * (1 - iv_crush_pct)
        # Value right after earnings if stock barely moves (±2%)
        flat_price    = current_price * 1.02
        pre_val       = _bs_price(current_price, strike, T, r, iv, option_type)
        post_val      = _bs_price(flat_price, strike, max(T - 1/365, 0.001),
                                  r, iv_post_crush, option_type)
        iv_crush_pnl  = (post_val - ask) * 100 * contracts
        iv_crush_scenario = {
            "description": f"Stock flat (+2%), IV drops {iv_crush_pct*100:.0f}% post-earnings",
            "iv_before":   f"{iv*100:.1f}%",
            "iv_after":    f"{iv_post_crush*100:.1f}%",
            "pnl":         round(iv_crush_pnl, 2),
            "pnl_pct":     round((iv_crush_pnl / total_cost) * 100, 1) if total_cost else 0,
        }

    # ── Key price levels ──────────────────────────────────────────────────────
    breakeven        = round(strike + ask, 2) if option_type == "call" else round(strike - ask, 2)
    profit_at_10pct  = _profit_at(current_price * 1.10, strike, ask, contracts, option_type)
    profit_at_20pct  = _profit_at(current_price * 1.20, strike, ask, contracts, option_type)
    profit_at_50pct  = _profit_at(current_price * 1.50, strike, ask, contracts, option_type)
    loss_at_5pct_dn  = _profit_at(current_price * 0.95, strike, ask, contracts, option_type)

    # ── Text summary for AI ───────────────────────────────────────────────────
    crush_text = ""
    if iv_crush_scenario:
        crush_text = (
            f"\nIV CRUSH WARNING: If stock barely moves after earnings and IV drops "
            f"{iv_crush_pct*100:.0f}%, option loses "
            f"${abs(iv_crush_scenario['pnl']):.0f} "
            f"({abs(iv_crush_scenario['pnl_pct']):.0f}% of premium) immediately."
        )

    summary = f"""
=== OPTIONS PROFIT/LOSS ANALYSIS: {ticker} ${strike}{option_type[0].upper()} exp {expiry} ===
Contract ask: ${ask:.2f}/share  →  ${cost_contract:.2f} per contract
Budget: ${budget:.0f}  →  {contracts} contract(s)  →  Total at risk: ${total_cost:.2f}
Days to expiry: {dte}

KEY LEVELS:
  Breakeven at expiry:  ${breakeven:.2f} (stock must reach this for you to profit)
  Current price:        ${current_price:.2f}
  {'Must gain' if option_type=='call' else 'Must drop'}: ${abs(breakeven - current_price):.2f} ({abs(breakeven/current_price - 1)*100:.1f}%)

GREEKS:
  Implied Volatility:  {iv*100:.1f}%
  Delta:               {delta:.2f}  (option moves ~${delta:.2f} per $1 stock move)
  Theta (daily decay): ${theta_per_contract:.2f}/day per contract (time working against you)
  Theta over {dte} days: ${abs(theta_per_contract*dte):.2f} total time decay if held to expiry

P/L SCENARIOS (total for {contracts} contract(s), ${total_cost:.0f} invested):
  Stock up +10% → ${current_price*1.10:.2f}:  ${profit_at_10pct:+.0f}  ({profit_at_10pct/total_cost*100:+.0f}%)
  Stock up +20% → ${current_price*1.20:.2f}:  ${profit_at_20pct:+.0f}  ({profit_at_20pct/total_cost*100:+.0f}%)
  Stock up +50% → ${current_price*1.50:.2f}:  ${profit_at_50pct:+.0f}  ({profit_at_50pct/total_cost*100:+.0f}%)
  Stock down -5% → ${current_price*0.95:.2f}: ${loss_at_5pct_dn:+.0f}  ({loss_at_5pct_dn/total_cost*100:+.0f}%)
  Stock flat / below ${strike:.2f} at expiry:  -${total_cost:.0f}  (-100% — full loss){crush_text}

MAX LOSS: ${total_cost:.2f} (100% of premium paid — only if stock stays below ${strike} at expiry)
MAX GAIN: Unlimited (theoretically — stock can keep rising)
"""

    return {
        "ticker":       ticker,
        "strike":       strike,
        "expiry":       expiry,
        "dte":          dte,
        "ask":          ask,
        "option_type":  option_type,
        "cost_contract": cost_contract,
        "contracts":    contracts,
        "total_cost":   total_cost,
        "breakeven":    breakeven,
        "iv":           round(iv, 4),
        "delta":        round(delta, 3),
        "theta_daily":  round(theta_per_contract, 3),
        "scenarios":    scenarios,
        "iv_crush":     iv_crush_scenario,
        "profit_at_10pct": profit_at_10pct,
        "profit_at_20pct": profit_at_20pct,
        "profit_at_50pct": profit_at_50pct,
        "summary":      summary.strip(),
        "html_chart":   _render_chart(
            ticker, strike, expiry, ask, contracts, total_cost,
            breakeven, current_price, option_type, dte, iv, delta,
            theta_per_contract, scenarios, iv_crush_scenario,
            profit_at_10pct, profit_at_20pct, profit_at_50pct,
        ),
    }


def _profit_at(stock_price: float, strike: float, ask: float,
               contracts: int, option_type: str) -> float:
    if option_type == "call":
        intrinsic = max(0.0, stock_price - strike)
    else:
        intrinsic = max(0.0, strike - stock_price)
    return round((intrinsic - ask) * 100 * contracts, 2)


# ─────────────────────────────────────────────────────────────────────────────
# HTML chart renderer — inline SVG P/L curve
# ─────────────────────────────────────────────────────────────────────────────

def _render_chart(
    ticker: str, strike: float, expiry: str, ask: float,
    contracts: int, total_cost: float, breakeven: float,
    current_price: float, option_type: str, dte: int,
    iv: float, delta: float, theta: float,
    scenarios: list[dict], iv_crush: Optional[dict],
    p10: float, p20: float, p50: float,
) -> str:
    """Generate a self-contained HTML block with P/L chart (SVG) and scenario table."""

    # SVG chart dimensions
    W, H   = 600, 220
    PAD    = 50
    chart_w = W - PAD * 2
    chart_h = H - PAD * 2

    prices = [s["stock_price"] for s in scenarios]
    pnls   = [s["pnl_dollars"] for s in scenarios]
    min_pnl = min(pnls)
    max_pnl = max(pnls)
    pnl_range = max_pnl - min_pnl or 1
    price_range = prices[-1] - prices[0] or 1

    def px(price: float) -> float:
        return PAD + (price - prices[0]) / price_range * chart_w

    def py(pnl: float) -> float:
        return H - PAD - (pnl - min_pnl) / pnl_range * chart_h

    zero_y = py(0)

    # Build polyline points
    points = " ".join(f"{px(s['stock_price']):.1f},{py(s['pnl_dollars']):.1f}" for s in scenarios)

    # Profit zone (above zero) polygon
    profit_pts = []
    loss_pts   = []
    for s in scenarios:
        pnl = s["pnl_dollars"]
        x   = px(s["stock_price"])
        y   = py(pnl)
        if pnl >= 0:
            profit_pts.append((x, y))
        else:
            loss_pts.append((x, y))

    # Build profit fill path (polygon along the line + zero baseline)
    def zone_polygon(pts: list, baseline_y: float) -> str:
        if not pts:
            return ""
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        # Close with baseline
        path += f" {pts[-1][0]:.1f},{baseline_y:.1f} {pts[0][0]:.1f},{baseline_y:.1f}"
        return f'<polygon points="{path}" fill="rgba(74,222,128,0.15)" />'

    def loss_polygon(pts: list, baseline_y: float) -> str:
        if not pts:
            return ""
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        path += f" {pts[-1][0]:.1f},{baseline_y:.1f} {pts[0][0]:.1f},{baseline_y:.1f}"
        return f'<polygon points="{path}" fill="rgba(248,113,113,0.15)" />'

    # Labels for x-axis
    x_labels = []
    for i in [0, 5, 10, 15, 20, 25, 30]:
        if i < len(scenarios):
            s = scenarios[i]
            x_labels.append(
                f'<text x="{px(s["stock_price"]):.1f}" y="{H - 8}" '
                f'text-anchor="middle" font-size="9" fill="#888">'
                f'${s["stock_price"]:.2f}</text>'
            )

    # Current price line
    cp_x = px(current_price)
    be_x = px(breakeven)

    # P/L at key levels table rows
    scenario_rows = ""
    key_prices = [
        (current_price * 0.85, "Stock -15%",   "loss"),
        (current_price * 0.95, "Stock -5%",    "loss"),
        (current_price,        "Stock flat",   "neutral"),
        (breakeven,            "Breakeven",     "neutral"),
        (current_price * 1.10, "Stock +10%",   "profit"),
        (current_price * 1.20, "Stock +20%",   "profit"),
        (current_price * 1.50, "Stock +50%",   "profit"),
        (current_price * 2.00, "Stock +100%",  "profit"),
    ]
    for sp, label, tone in key_prices:
        pnl  = _profit_at(sp, strike, ask, contracts, option_type)
        pct  = (pnl / total_cost * 100) if total_cost else 0
        color = "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#facc15")
        scenario_rows += (
            f"<tr>"
            f"<td style='padding:4px 10px;color:#ccc'>{label}</td>"
            f"<td style='padding:4px 10px;color:#ccc'>${sp:.2f}</td>"
            f"<td style='padding:4px 10px;color:{color};font-weight:600'>"
            f"{'+'if pnl>=0 else ''}${pnl:.0f}</td>"
            f"<td style='padding:4px 10px;color:{color}'>"
            f"{'+'if pct>=0 else ''}{pct:.0f}%</td>"
            f"</tr>"
        )

    iv_crush_html = ""
    if iv_crush:
        crush_color = "#f87171" if iv_crush["pnl"] < 0 else "#4ade80"
        iv_crush_html = f"""
        <div style="margin-top:12px;padding:10px 14px;background:#1a0a0a;
                    border:1px solid #5a1a1a;border-radius:8px;font-size:.82rem">
          <span style="color:#f87171;font-weight:700">IV CRUSH WARNING</span>
          &nbsp;—&nbsp; {iv_crush['description']}<br>
          IV before: <b style="color:#fff">{iv_crush['iv_before']}</b>
          &nbsp;→&nbsp; IV after: <b style="color:#fff">{iv_crush['iv_after']}</b>
          &nbsp;|&nbsp; Immediate P/L:
          <b style="color:{crush_color}">{'+'if iv_crush['pnl']>=0 else ''}${iv_crush['pnl']:.0f}
          ({'+' if iv_crush['pnl_pct']>=0 else ''}{iv_crush['pnl_pct']:.0f}%)</b>
        </div>"""

    html = f"""
<div style="background:#0d0d0d;border:1px solid #2a2a2a;border-radius:12px;
            padding:18px 20px;margin:16px 0;font-family:monospace">
  <div style="color:#4da6ff;font-size:.95rem;font-weight:700;margin-bottom:4px">
    OPTIONS P/L SIMULATOR
  </div>
  <div style="color:#888;font-size:.8rem;margin-bottom:14px">
    {ticker} ${strike}{option_type[0].upper()} &nbsp;|&nbsp; Exp: {expiry} ({dte}d)
    &nbsp;|&nbsp; Ask: ${ask:.2f}/share = ${ask*100:.2f}/contract
    &nbsp;|&nbsp; {contracts} contract(s) &nbsp;|&nbsp; Total at risk: ${total_cost:.2f}
  </div>

  <!-- P/L Curve SVG -->
  <svg width="{W}" height="{H}" style="display:block;margin-bottom:14px">
    <!-- zero line fill zones -->
    {zone_polygon(profit_pts, zero_y)}
    {loss_polygon(loss_pts, zero_y)}

    <!-- zero baseline -->
    <line x1="{PAD}" y1="{zero_y:.1f}" x2="{W-PAD}" y2="{zero_y:.1f}"
          stroke="#444" stroke-width="1" stroke-dasharray="4,3"/>

    <!-- current price vertical -->
    <line x1="{cp_x:.1f}" y1="{PAD}" x2="{cp_x:.1f}" y2="{H-PAD}"
          stroke="#4da6ff" stroke-width="1" stroke-dasharray="3,3" opacity=".6"/>
    <text x="{cp_x:.1f}" y="{PAD-4}" text-anchor="middle"
          font-size="9" fill="#4da6ff">Current ${current_price:.2f}</text>

    <!-- breakeven vertical -->
    <line x1="{be_x:.1f}" y1="{PAD}" x2="{be_x:.1f}" y2="{H-PAD}"
          stroke="#facc15" stroke-width="1" stroke-dasharray="3,3" opacity=".7"/>
    <text x="{be_x:.1f}" y="{H-PAD+16}" text-anchor="middle"
          font-size="9" fill="#facc15">BE ${breakeven:.2f}</text>

    <!-- P/L polyline -->
    <polyline points="{points}" fill="none" stroke="#4ade80" stroke-width="2"/>

    <!-- x-axis labels -->
    {''.join(x_labels)}

    <!-- axis labels -->
    <text x="{W//2}" y="{H-1}" text-anchor="middle" font-size="9" fill="#666">
      Stock Price at Expiry
    </text>
    <text x="10" y="{H//2}" text-anchor="middle" font-size="9" fill="#666"
          transform="rotate(-90,10,{H//2})">P/L $</text>
  </svg>

  <!-- Greeks row -->
  <div style="display:flex;gap:20px;margin-bottom:14px;font-size:.82rem">
    <div><span style="color:#888">IV: </span>
         <span style="color:#fff;font-weight:600">{iv*100:.1f}%</span></div>
    <div><span style="color:#888">Delta: </span>
         <span style="color:#fff;font-weight:600">{delta:.2f}</span>
         <span style="color:#888"> ($1 move → option {'+'if delta>0 else ''}{delta*100:.0f}¢)</span></div>
    <div><span style="color:#888">Theta: </span>
         <span style="color:#f87171;font-weight:600">${theta:.2f}/day</span>
         <span style="color:#888"> per contract</span></div>
    <div><span style="color:#888">DTE: </span>
         <span style="color:#facc15;font-weight:600">{dte} days</span></div>
  </div>

  <!-- Breakeven callout -->
  <div style="background:#0a1a2a;border:1px solid #1a3a5a;border-radius:8px;
              padding:8px 14px;margin-bottom:12px;font-size:.85rem">
    Breakeven at expiry: <b style="color:#facc15">${breakeven:.2f}</b>
    &nbsp;—&nbsp; stock must move
    <b style="color:#fff">{'up' if option_type=='call' else 'down'}
    ${abs(breakeven-current_price):.2f} ({abs(breakeven/current_price-1)*100:.1f}%)</b>
    from current price
  </div>

  <!-- Scenario table -->
  <table style="width:100%;border-collapse:collapse;font-size:.82rem">
    <thead>
      <tr style="border-bottom:1px solid #333">
        <th style="padding:4px 10px;color:#666;text-align:left;font-weight:400">Scenario</th>
        <th style="padding:4px 10px;color:#666;text-align:left;font-weight:400">Stock Price</th>
        <th style="padding:4px 10px;color:#666;text-align:left;font-weight:400">P/L ({contracts}x)</th>
        <th style="padding:4px 10px;color:#666;text-align:left;font-weight:400">Return %</th>
      </tr>
    </thead>
    <tbody>
      {scenario_rows}
    </tbody>
  </table>
  {iv_crush_html}
</div>"""

    return html


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: simulate the best contract from a research dict
# ─────────────────────────────────────────────────────────────────────────────

def simulate_from_research(research: dict) -> Optional[dict]:
    """
    Extract the recommended options contract from a deep_research result dict
    and run the full simulation on it. Returns simulation dict or None.
    """
    syn = research.get("synthesis") or {}
    op  = syn.get("options_play") or {}
    bc  = op.get("best_contract") or {}

    if not bc:
        return None

    mkt    = research.get("mktdata") or {}
    price  = mkt.get("price") or syn.get("price_now") or 0
    budget = research.get("budget", 100.0)

    try:
        return simulate(
            ticker        = research.get("ticker","?"),
            strike        = float(bc.get("strike", 0)),
            expiry        = str(bc.get("expiry","2026-12-31")),
            ask           = float(bc.get("ask_estimate") or bc.get("cost_1_contract",50)/100),
            current_price = float(price),
            option_type   = str(bc.get("type","call")),
            budget        = float(budget),
            iv_crush_pct  = 0.35 if syn.get("earnings_analysis",{}).get("play_earnings") else None,
        )
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Quick test / standalone run
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    # Example: SOUN $10 Call expiring May 9 at $0.80 ask, current price $9.14, $100 budget
    ticker  = sys.argv[1] if len(sys.argv) > 1 else "SOUN"
    strike  = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    expiry  = sys.argv[3] if len(sys.argv) > 3 else "2026-05-09"
    ask     = float(sys.argv[4]) if len(sys.argv) > 4 else 0.80
    price   = float(sys.argv[5]) if len(sys.argv) > 5 else 9.14
    budget  = float(sys.argv[6]) if len(sys.argv) > 6 else 100.0

    result = simulate(
        ticker        = ticker,
        strike        = strike,
        expiry        = expiry,
        ask           = ask,
        current_price = price,
        option_type   = "call",
        budget        = budget,
        iv_crush_pct  = 0.35,  # 35% IV crush after earnings
    )

    print(result["summary"].encode("ascii", "replace").decode())
    print(f"\nIV: {result['iv']*100:.1f}%  Delta: {result['delta']:.2f}  "
          f"Theta: ${result['theta_daily']:.2f}/day")
    print(f"HTML chart: {len(result['html_chart'])} chars")

    # Save the HTML chart to a test file
    with open("test_options_chart.html", "w", encoding="utf-8") as f:
        f.write(f"<html><body style='background:#000'>{result['html_chart']}</body></html>")
    print("Chart saved to test_options_chart.html")
