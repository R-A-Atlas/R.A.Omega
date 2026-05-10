"""
volume_profile.py — ATLAS Volume Profile Engine
Level 2 Order Book Approximation (free, using yfinance hourly data)

What Level 2 tells you: WHERE institutional buyers and sellers are sitting.
What Volume Profile tells you: WHERE institutional buyers and sellers HAVE BEEN.

The logic: high volume at a price = lots of people agreed to trade there.
That price becomes a magnet. Price tends to return to high-volume areas,
and tends to stall at them. Low-volume areas get blown through fast.

Key concepts:
  POC  (Point of Control)   — price with most volume traded = strongest magnet/support
  VAH  (Value Area High)    — upper edge of the 70% volume zone
  VAL  (Value Area Low)     — lower edge of the 70% volume zone
  HVN  (High Volume Node)   — prices with concentrated volume = strong support/resistance
  LVN  (Low Volume Node)    — prices with thin volume = price moves through quickly
  VWAP (Volume Weighted Avg)— institutional benchmark; price below = bearish bias

Why it approximates Level 2:
  Real Level 2 shows you PENDING orders (bid/ask stack).
  Volume Profile shows you WHERE orders HAVE BEEN EXECUTED.
  Institutions tend to work the same price levels repeatedly.
  POC and Value Area High/Low are where their algorithms re-engage.
  This is not perfect — but it is genuinely useful and it's free.

What you get per report:
  - POC with dollar level  
  - Value Area (VAL → VAH)
  - Current price vs POC (above = bullish, below = bearish)
  - VWAP for intraday sessions
  - Top 3 HVN levels (support/resistance)
  - Top 2 LVN levels (price will accelerate through here)
  - SVG chart showing volume distribution by price
  - Plain English interpretation
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Core volume profile calculation
# ─────────────────────────────────────────────────────────────────────────────
def _tick_size(price: float) -> float:
    """Dynamic tick size based on price level."""
    if price < 1:     return 0.01
    elif price < 5:   return 0.05
    elif price < 20:  return 0.10
    elif price < 100: return 0.25
    else:             return 0.50


def calculate_volume_profile(ticker: str, lookback_days: int = 30) -> dict:
    """
    Build a volume profile from the last N days of hourly OHLCV data.

    Returns:
      poc:         float — price with most volume
      vah:         float — value area high (top of 70% zone)
      val:         float — value area low (bottom of 70% zone)
      vwap:        float — volume-weighted average price (full period)
      hvn:         list[float] — high volume nodes (top 5 by volume)
      lvn:         list[float] — low volume nodes (bottom 5, above val)
      profile:     dict[price_level → volume] — full distribution
      interpretation: str — plain English
      current_price: float
    """
    result: dict = {"ticker": ticker.upper(), "lookback_days": lookback_days}

    try:
        tk   = yf.Ticker(ticker.upper())
        # Use hourly data for lookback up to 60 days (yfinance limit for 1h)
        days = min(lookback_days, 59)
        hist = tk.history(period=f"{days}d", interval="1h")

        if hist is None or hist.empty:
            log.warning("[volume_profile] No hourly data for %s", ticker)
            return result

        # Current price
        current_price = float(hist["Close"].iloc[-1])
        result["current_price"] = current_price
        tick = _tick_size(current_price)

        # Build price→volume map
        # For each candle, distribute volume across the high-low range
        # (approximates where within the candle the volume actually traded)
        vol_map: dict[float, float] = defaultdict(float)

        for _, row in hist.iterrows():
            h     = float(row["High"])
            l     = float(row["Low"])
            c     = float(row["Close"])
            vol   = float(row["Volume"])
            if vol == 0 or math.isnan(vol):
                continue

            # Price levels this candle spans
            lo_level = math.floor(l / tick) * tick
            hi_level = math.ceil(h / tick) * tick
            levels   = []
            p = lo_level
            while p <= hi_level + 1e-9:
                levels.append(round(p, 6))
                p = round(p + tick, 6)

            if not levels:
                continue

            # Weight volume toward close (more trades happen near close)
            # Simple triangular weighting: levels near close get more
            close_level = round(round(c / tick) * tick, 6)
            weights = []
            for lvl in levels:
                dist = abs(lvl - close_level) / (tick * max(len(levels), 1))
                w    = max(0.1, 1.0 - dist)
                weights.append(w)
            total_w = sum(weights) or 1
            for lvl, w in zip(levels, weights):
                vol_map[round(lvl, 6)] += vol * (w / total_w)

        if not vol_map:
            return result

        # VWAP (volume weighted average price across all bars)
        vwap_num = sum(((row["High"] + row["Low"] + row["Close"]) / 3) * row["Volume"]
                       for _, row in hist.iterrows() if not math.isnan(row["Volume"]))
        vwap_den = hist["Volume"].sum()
        vwap = vwap_num / vwap_den if vwap_den else current_price
        result["vwap"] = round(vwap, 4)

        # Sort by price
        sorted_levels = sorted(vol_map.keys())
        total_volume  = sum(vol_map.values())

        # POC — highest volume level
        poc = max(vol_map, key=vol_map.get)
        result["poc"] = round(poc, 4)

        # Value Area — 70% of total volume centered on POC
        target_vol = total_volume * 0.70
        vah = poc
        val = poc
        accum_vol = vol_map[poc]

        poc_idx = sorted_levels.index(poc)
        up_idx   = poc_idx + 1
        dn_idx   = poc_idx - 1

        while accum_vol < target_vol:
            up_vol = vol_map.get(sorted_levels[up_idx], 0) if up_idx < len(sorted_levels) else 0
            dn_vol = vol_map.get(sorted_levels[dn_idx], 0) if dn_idx >= 0 else 0

            if up_vol >= dn_vol and up_idx < len(sorted_levels):
                accum_vol += up_vol
                vah = sorted_levels[up_idx]
                up_idx += 1
            elif dn_idx >= 0:
                accum_vol += dn_vol
                val = sorted_levels[dn_idx]
                dn_idx -= 1
            else:
                break

        result["vah"] = round(vah, 4)
        result["val"] = round(val, 4)

        # HVN — top 5 levels by volume (excluding POC itself)
        sorted_by_vol = sorted(vol_map.items(), key=lambda x: x[1], reverse=True)
        hvn = [round(p, 4) for p, _ in sorted_by_vol[1:8]
               if abs(p - poc) > tick * 2][:5]
        result["hvn"] = sorted(hvn)

        # LVN — lowest volume levels in the value area zone
        # (these are the gaps — price will accelerate through here)
        va_levels = {p: v for p, v in vol_map.items() if val <= p <= vah}
        if va_levels:
            sorted_va = sorted(va_levels.items(), key=lambda x: x[1])
            lvn = [round(p, 4) for p, _ in sorted_va[:4]
                   if abs(p - poc) > tick * 2][:3]
            result["lvn"] = sorted(lvn)

        # Profile dict for chart (normalized 0-100)
        max_vol = max(vol_map.values())
        result["profile"] = {
            str(round(p, 4)): round(v / max_vol * 100, 1)
            for p, v in sorted(vol_map.items())
            if v > max_vol * 0.05  # trim noise
        }

        # Interpretation
        price_vs_poc = ((current_price - poc) / poc * 100) if poc else 0
        price_vs_vwap = ((current_price - vwap) / vwap * 100) if vwap else 0
        in_value_area = val <= current_price <= vah

        interp_parts = []
        if price_vs_poc > 5:
            interp_parts.append(f"Price is {price_vs_poc:.1f}% ABOVE POC (${poc:.2f}) — extended, may revert to POC")
        elif price_vs_poc < -5:
            interp_parts.append(f"Price is {abs(price_vs_poc):.1f}% BELOW POC (${poc:.2f}) — POC acts as overhead resistance")
        else:
            interp_parts.append(f"Price is AT POC (${poc:.2f}) — high-volume equilibrium zone, expect chop or strong move")

        if price_vs_vwap > 2:
            interp_parts.append(f"Above VWAP (${vwap:.2f}) — bullish intraday bias")
        elif price_vs_vwap < -2:
            interp_parts.append(f"Below VWAP (${vwap:.2f}) — bearish intraday bias")

        if in_value_area:
            interp_parts.append(f"Inside Value Area (${val:.2f}–${vah:.2f}) — 70% of volume traded here, balanced market")
        elif current_price > vah:
            interp_parts.append(f"Above Value Area (${vah:.2f}) — breakout zone, watch for acceptance or rejection")
        else:
            interp_parts.append(f"Below Value Area (${val:.2f}) — breakdown zone, watch for reclaim or continuation")

        if hvn:
            nearest_hvn = min(hvn, key=lambda x: abs(x - current_price))
            interp_parts.append(f"Nearest HVN support/resistance: ${nearest_hvn:.2f}")

        result["interpretation"] = " | ".join(interp_parts)

        log.info("[volume_profile] %s — POC=$%.2f  VAL=$%.2f  VAH=$%.2f  VWAP=$%.2f  HVN=%s",
                 ticker, poc, val, vah, vwap,
                 ",".join(f"${x:.2f}" for x in hvn[:3]))

    except Exception:
        log.warning("[volume_profile] Failed for %s", ticker, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# SVG chart — horizontal volume profile bar chart
# ─────────────────────────────────────────────────────────────────────────────
def render_svg_chart(profile_data: dict, width: int = 400, height: int = 300) -> str:
    """
    Render an SVG horizontal volume profile chart.
    Each price level = a horizontal bar sized by volume.
    POC = highlighted in accent color.
    Value Area = shaded background.
    Current price = horizontal line.
    VWAP = dashed line.
    """
    profile   = profile_data.get("profile") or {}
    poc       = profile_data.get("poc")
    vah       = profile_data.get("vah")
    val       = profile_data.get("val")
    vwap      = profile_data.get("vwap")
    current   = profile_data.get("current_price")
    ticker    = profile_data.get("ticker","")

    if not profile or not poc:
        return ""

    levels    = [(float(p), v) for p, v in profile.items()]
    levels.sort(key=lambda x: x[0])
    prices    = [p for p, _ in levels]
    vols      = [v for _, v in levels]

    if not prices:
        return ""

    p_min, p_max = min(prices), max(prices)
    p_range = p_max - p_min or 1

    chart_w   = width - 80    # leave room for price labels
    chart_h   = height - 40
    margin_l  = 60
    margin_t  = 20

    bar_h = max(1, chart_h / len(levels))

    def price_to_y(p: float) -> float:
        # Invert: higher prices at top
        return margin_t + (1 - (p - p_min) / p_range) * chart_h

    def vol_to_w(v: float) -> float:
        return v / 100 * chart_w * 0.85

    bars = ""
    # Value Area background
    va_y1 = price_to_y(vah) if vah else margin_t
    va_y2 = price_to_y(val) if val else margin_t + chart_h
    bars += f'<rect x="{margin_l}" y="{va_y1:.1f}" width="{chart_w}" height="{(va_y2-va_y1):.1f}" fill="#1a2a1a" opacity="0.6"/>'

    for price, vol in levels:
        y   = price_to_y(price)
        bw  = vol_to_w(vol)
        bh  = max(1.5, bar_h * 0.85)
        is_poc = poc and abs(price - poc) < 0.001
        color = "#00d4ff" if is_poc else ("#4da6ff" if vah and val and val <= price <= vah else "#2a4a6a")
        bars += (
            f'<rect x="{margin_l}" y="{y - bh/2:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'fill="{color}" opacity="0.85"/>'
        )

    # Price labels on left
    tick = _tick_size(current or 10)
    label_step = max(1, len(levels) // 8)
    labels = ""
    for i, (price, _) in enumerate(levels):
        if i % label_step == 0:
            y = price_to_y(price)
            labels += f'<text x="{margin_l - 4}" y="{y + 4:.1f}" fill="#666" font-size="9" text-anchor="end">${price:.2f}</text>'

    # POC line
    poc_y    = price_to_y(poc)
    poc_line = f'<line x1="{margin_l}" y1="{poc_y:.1f}" x2="{margin_l + chart_w}" y2="{poc_y:.1f}" stroke="#00d4ff" stroke-width="1.5" stroke-dasharray="4,2"/>'
    poc_lbl  = f'<text x="{margin_l + chart_w + 4}" y="{poc_y + 4:.1f}" fill="#00d4ff" font-size="9">POC</text>'

    # Current price line
    cur_line = cur_lbl = ""
    if current:
        cur_y    = price_to_y(current)
        cur_line = f'<line x1="{margin_l}" y1="{cur_y:.1f}" x2="{margin_l + chart_w}" y2="{cur_y:.1f}" stroke="#4caf50" stroke-width="1.5"/>'
        cur_lbl  = f'<text x="{margin_l + chart_w + 4}" y="{cur_y + 4:.1f}" fill="#4caf50" font-size="9">${current:.2f}</text>'

    # VWAP line
    vwap_line = vwap_lbl = ""
    if vwap:
        vwap_y    = price_to_y(vwap)
        vwap_line = f'<line x1="{margin_l}" y1="{vwap_y:.1f}" x2="{margin_l + chart_w}" y2="{vwap_y:.1f}" stroke="#ff9800" stroke-width="1" stroke-dasharray="3,3"/>'
        vwap_lbl  = f'<text x="{margin_l + chart_w + 4}" y="{vwap_y + 4:.1f}" fill="#ff9800" font-size="9">VWAP</text>'

    # VAH / VAL labels
    va_labels = ""
    if vah:
        vy = price_to_y(vah)
        va_labels += f'<text x="{margin_l - 4}" y="{vy + 3:.1f}" fill="#4caf50" font-size="8" text-anchor="end">VAH</text>'
    if val:
        vy = price_to_y(val)
        va_labels += f'<text x="{margin_l - 4}" y="{vy + 3:.1f}" fill="#f44336" font-size="8" text-anchor="end">VAL</text>'

    return f"""
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" style="background:#0d1117;border-radius:8px">
  <text x="{width//2}" y="14" fill="#aaa" font-size="11" text-anchor="middle" font-family="sans-serif">{ticker} Volume Profile ({profile_data.get('lookback_days',30)}d)</text>
  {bars}
  {poc_line}{poc_lbl}
  {vwap_line}{vwap_lbl}
  {cur_line}{cur_lbl}
  {labels}
  {va_labels}
</svg>"""


def to_html(profile_data: dict) -> str:
    """Full HTML block for embedding in reports."""
    if not profile_data.get("poc"):
        return ""

    poc     = profile_data.get("poc","?")
    vah     = profile_data.get("vah","?")
    val     = profile_data.get("val","?")
    vwap    = profile_data.get("vwap","?")
    current = profile_data.get("current_price","?")
    hvn     = profile_data.get("hvn",[])
    lvn     = profile_data.get("lvn",[])
    interp  = profile_data.get("interpretation","")
    svg     = render_svg_chart(profile_data)

    price_vs_poc = ""
    try:
        diff = (float(current) - float(poc)) / float(poc) * 100
        color = "#4caf50" if diff >= 0 else "#f44336"
        price_vs_poc = f'<span style="color:{color};font-size:12px">{diff:+.1f}% vs POC</span>'
    except Exception:
        pass

    hvn_str = " | ".join(f"${x:.2f}" for x in hvn[:5]) if hvn else "—"
    lvn_str = " | ".join(f"${x:.2f}" for x in lvn[:3]) if lvn else "—"

    return f"""
<div style="background:#0e0e1a;border:1px solid #2a2a4a;border-radius:12px;padding:20px;margin-bottom:24px">
  <div style="font-size:14px;font-weight:700;color:#00d4ff;letter-spacing:1px;margin-bottom:14px">
    VOLUME PROFILE <span style="font-size:11px;color:#555;font-weight:normal">(Level 2 approximation via price-at-volume)</span>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:14px">
        <div style="background:#111;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:#666">POC (strongest magnet)</div>
          <div style="font-size:18px;font-weight:700;color:#00d4ff;margin-top:4px">${poc}</div>
          <div>{price_vs_poc}</div>
        </div>
        <div style="background:#111;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:#666">VWAP</div>
          <div style="font-size:18px;font-weight:700;color:#ff9800;margin-top:4px">${vwap}</div>
        </div>
        <div style="background:#111;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:#666">Value Area Low</div>
          <div style="font-size:16px;font-weight:700;color:#f44336;margin-top:4px">${val}</div>
        </div>
        <div style="background:#111;border-radius:8px;padding:10px;text-align:center">
          <div style="font-size:10px;color:#666">Value Area High</div>
          <div style="font-size:16px;font-weight:700;color:#4caf50;margin-top:4px">${vah}</div>
        </div>
      </div>
      <div style="margin-bottom:10px">
        <div style="font-size:11px;color:#666;margin-bottom:4px">HVN (support / resistance)</div>
        <div style="color:#4da6ff;font-size:13px">{hvn_str}</div>
      </div>
      <div style="margin-bottom:12px">
        <div style="font-size:11px;color:#666;margin-bottom:4px">LVN (price blows through here)</div>
        <div style="color:#ff9800;font-size:13px">{lvn_str}</div>
      </div>
      <div style="color:#aaa;font-size:12px;line-height:1.6">{interp}</div>
    </div>
    <div style="display:flex;align-items:flex-start">
      {svg}
    </div>
  </div>
</div>"""


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SOUN"
    days   = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    data   = calculate_volume_profile(ticker, days)
    print(f"\nVolume Profile: {ticker}")
    print(f"  POC:  ${data.get('poc','?')}")
    print(f"  VAL:  ${data.get('val','?')}")
    print(f"  VAH:  ${data.get('vah','?')}")
    print(f"  VWAP: ${data.get('vwap','?')}")
    print(f"  HVN:  {data.get('hvn','?')}")
    print(f"  LVN:  {data.get('lvn','?')}")
    print(f"  {data.get('interpretation','')}")
