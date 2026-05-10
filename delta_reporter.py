"""
delta_reporter.py — ATLAS Auto Delta Reports

Re-scrapes a ticker every N minutes and shows ONLY what changed.
No more re-reading 40-page reports. Just the signal.

What it detects:
  PRICE        — price moved > X% since last check
  IV RANK      — IV rank jumped or dropped significantly  
  NEWS         — new headlines since last scan
  INSIDER      — new insider transaction filed
  OPTIONS FLOW — sentiment flipped (bullish → bearish or vice versa)
  VOLUME       — unusual volume (> 2x average)
  ANALYST      — new rating change or price target update
  EARNINGS     — earnings date is now within 24 hours
  ALERT FIRED  — one of your price alerts triggered

Each delta is classified by severity:
  CRITICAL — stop loss hit, earnings today, major insider sale
  HIGH     — IV jumped 20+ points, price > 5% move, sentiment flip
  MEDIUM   — new news, analyst change, IV up 10 pts
  LOW      — minor price movement, normal vol activity

Outputs:
  - Console: colored summary (only changed items)
  - HTML file: reports/ATLAS_DELTA_{TICKER}.html (refreshes in browser)
  - Returns dict for programmatic use

Usage:
  python delta_reporter.py SOUN         -- single scan + diff vs last save
  python delta_reporter.py SOUN --watch -- continuous mode (every 30 min)
  python delta_reporter.py SOUN --interval 15  -- every 15 minutes

Wired automatically into auto_bot.py --watch mode for all positions.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_REPORTS_DIR  = Path(__file__).parent / "reports"
_SNAPSHOTS_DIR = Path(__file__).parent / "delta_snapshots"
_POSITIONS_CACHE = Path(__file__).parent / "positions_cache.json"
_SNAPSHOTS_DIR.mkdir(exist_ok=True)
_REPORTS_DIR.mkdir(exist_ok=True)

_DEFAULT_INTERVAL_MIN = 30


def tickers_from_positions_cache() -> list[str]:
    """Load unique tickers from positions_cache.json stocks + options and watchlist.json."""
    out: list[str] = []
    if _POSITIONS_CACHE.exists():
        try:
            data = json.loads(_POSITIONS_CACHE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        for s in (data.get("stocks") or []):
            t = (s.get("ticker") or "").upper().strip()
            if t:
                out.append(t)
        for o in (data.get("options") or []):
            t = (o.get("ticker") or "").upper().strip()
            if t:
                out.append(t)
    wl_path = Path(__file__).parent / "watchlist.json"
    if wl_path.exists():
        try:
            wl = json.loads(wl_path.read_text(encoding="utf-8"))
            for t in (wl.get("tickers") or []):
                u = (str(t) if t is not None else "").upper().strip()
                if u:
                    out.append(u)
        except Exception:
            pass
    return list(dict.fromkeys(out))


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot — a lightweight fingerprint of key metrics at a point in time
# ─────────────────────────────────────────────────────────────────────────────
def _extract_snapshot(scrape: dict, js_data: dict = None) -> dict:
    """Extract the key numeric and text facts we want to diff next time."""
    fv  = scrape.get("finviz") or {}
    uw  = scrape.get("unusual_whales") or {}
    ew  = scrape.get("earnings_whispers") or {}
    mb  = scrape.get("marketbeat") or {}
    js  = js_data or scrape.get("js_data") or {}
    bc  = js.get("barchart") or {}
    bhi = js.get("barchart_hist_iv") or {}
    st  = js.get("stocktwits") or {}
    uw_js = js.get("unusual_whales_js") or {}
    ew_js = js.get("earnings_whispers_js") or {}
    inst = scrape.get("institutional_13f") or {}

    news = scrape.get("news") or []
    sa   = scrape.get("seeking_alpha") or []
    insiders = scrape.get("insider_data") or []

    # Collect all headline titles as a frozen set for diff
    all_titles = set()
    for item in news:
        t = item.get("title","").strip()
        if t: all_titles.add(t[:80])
    for art in sa:
        t = art.get("title","").strip()
        if t: all_titles.add(t[:80])

    # Latest insider trade
    latest_insider = None
    if insiders:
        latest_insider = (
            f"{insiders[0].get('trade_date','')} "
            f"{insiders[0].get('insider','')} "
            f"{insiders[0].get('trade_type','')} "
            f"{insiders[0].get('value','')}"
        )

    return {
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "price":           fv.get("price"),
        "volume":          fv.get("volume"),
        "avg_volume":      fv.get("avg_volume"),
        "rel_volume":      fv.get("rel_volume"),
        "short_float":     fv.get("short_float"),
        "rsi":             fv.get("rsi"),
        "iv_rank":         bc.get("iv_rank") or bhi.get("iv_rank_current") or uw.get("iv_rank"),
        "iv_percentile":   bc.get("iv_percentile"),
        "pcr":             bc.get("put_call_vol_ratio") or uw_js.get("put_call_ratio"),
        "flow_sentiment":  uw_js.get("bullish_bearish") or uw.get("flow_sentiment"),
        "whisper_eps":     ew_js.get("whisper_eps") or ew.get("whisper_eps"),
        "earnings_date":   ew_js.get("earnings_date") or ew.get("earnings_date") or fv.get("earnings_date"),
        "analyst_rating":  mb.get("consensus_rating"),
        "analyst_target":  mb.get("avg_price_target"),
        "bull_pct":        st.get("bullish_pct"),
        "bear_pct":        st.get("bearish_pct"),
        "inst_pct":        inst.get("institutional_pct_str"),
        "news_titles":     sorted(list(all_titles)),
        "latest_insider":  latest_insider,
        "headline_count":  len(all_titles),
    }


def _load_snapshot(ticker: str) -> Optional[dict]:
    path = _SNAPSHOTS_DIR / f"{ticker.upper()}_snapshot.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_snapshot(ticker: str, snapshot: dict) -> None:
    path = _SNAPSHOTS_DIR / f"{ticker.upper()}_snapshot.json"
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Delta detector — compare two snapshots, classify changes
# ─────────────────────────────────────────────────────────────────────────────
def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace("%","").replace("$","").replace(",","").strip())
    except Exception:
        return None


def detect_deltas(old: dict, new: dict) -> list[dict]:
    """
    Compare two snapshots. Return list of detected changes, each with:
      severity: CRITICAL | HIGH | MEDIUM | LOW
      category: PRICE | IV | NEWS | INSIDER | FLOW | VOLUME | ANALYST | EARNINGS
      message:  plain English description of what changed
      old_val / new_val: the raw values for display
    """
    deltas: list[dict] = []

    def add(severity, category, message, old_val=None, new_val=None):
        deltas.append({
            "severity": severity,
            "category": category,
            "message":  message,
            "old_val":  old_val,
            "new_val":  new_val,
        })

    # ── Price change ────────────────────────────────────────────────────────
    old_price = _safe_float(old.get("price"))
    new_price = _safe_float(new.get("price"))
    if old_price and new_price and old_price > 0:
        pct = (new_price - old_price) / old_price * 100
        if abs(pct) >= 5:
            direction = "UP" if pct > 0 else "DOWN"
            sev = "CRITICAL" if abs(pct) >= 10 else "HIGH"
            add(sev, "PRICE", f"Price moved {direction} {abs(pct):.1f}%: ${old_price:.2f} → ${new_price:.2f}",
                f"${old_price:.2f}", f"${new_price:.2f}")
        elif abs(pct) >= 2:
            add("MEDIUM", "PRICE", f"Price moved {abs(pct):.1f}%: ${old_price:.2f} → ${new_price:.2f}",
                f"${old_price:.2f}", f"${new_price:.2f}")

    # ── Relative volume spike ────────────────────────────────────────────────
    new_rvol = _safe_float(new.get("rel_volume"))
    old_rvol = _safe_float(old.get("rel_volume"))
    if new_rvol and new_rvol >= 2.5:
        sev = "HIGH" if new_rvol >= 5 else "MEDIUM"
        add(sev, "VOLUME", f"Unusual volume: {new_rvol:.1f}x average",
            f"{old_rvol:.1f}x" if old_rvol else "?", f"{new_rvol:.1f}x")
    elif new_rvol and old_rvol and (new_rvol / old_rvol) >= 2.0:
        add("MEDIUM", "VOLUME", f"Volume accelerating: {old_rvol:.1f}x → {new_rvol:.1f}x",
            f"{old_rvol:.1f}x", f"{new_rvol:.1f}x")

    # ── IV rank change ───────────────────────────────────────────────────────
    old_iv = _safe_float(old.get("iv_rank"))
    new_iv = _safe_float(new.get("iv_rank"))
    if old_iv is not None and new_iv is not None:
        iv_delta = new_iv - old_iv
        if abs(iv_delta) >= 20:
            direction = "SPIKED" if iv_delta > 0 else "COLLAPSED"
            sev = "HIGH"
            interp = ""
            if new_iv > 70:
                interp = " — options NOW expensive, crush risk high"
            elif new_iv < 20:
                interp = " — options NOW cheap, good time to buy"
            add(sev, "IV", f"IV Rank {direction} {abs(iv_delta):.0f} pts: {old_iv:.0f} → {new_iv:.0f}{interp}",
                f"{old_iv:.0f}", f"{new_iv:.0f}")
        elif abs(iv_delta) >= 10:
            add("MEDIUM", "IV", f"IV Rank shifted {iv_delta:+.0f}: {old_iv:.0f} → {new_iv:.0f}",
                f"{old_iv:.0f}", f"{new_iv:.0f}")

    # ── Options flow sentiment flip ──────────────────────────────────────────
    old_flow = (old.get("flow_sentiment") or "").lower()
    new_flow = (new.get("flow_sentiment") or "").lower()
    if old_flow and new_flow and old_flow != new_flow:
        direction = new_flow.upper()
        sev = "HIGH" if direction in ("BULLISH","BEARISH") else "MEDIUM"
        add(sev, "FLOW", f"Options flow FLIPPED: {old_flow.upper()} → {new_flow.upper()}",
            old_flow.upper(), new_flow.upper())

    # ── Put/call ratio change ────────────────────────────────────────────────
    old_pcr = _safe_float(old.get("pcr"))
    new_pcr = _safe_float(new.get("pcr"))
    if old_pcr and new_pcr:
        pcr_delta = abs(new_pcr - old_pcr)
        if pcr_delta >= 0.3:
            direction = "higher (more puts = bearish)" if new_pcr > old_pcr else "lower (more calls = bullish)"
            add("MEDIUM", "FLOW", f"Put/Call ratio shifted {direction}: {old_pcr:.2f} → {new_pcr:.2f}",
                f"{old_pcr:.2f}", f"{new_pcr:.2f}")

    # ── Earnings date approaching ────────────────────────────────────────────
    ed_str = new.get("earnings_date") or ""
    if ed_str and ed_str not in ("?", "unknown", ""):
        try:
            import re
            from datetime import date as _date
            date_m = re.search(r"(\d{4}-\d{2}-\d{2})", str(ed_str))
            if not date_m:
                # Try "May 7, 2026" format
                from datetime import datetime as _dt
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%b %d %Y"):
                    try:
                        ed = _dt.strptime(ed_str[:15], fmt).date()
                        break
                    except Exception:
                        ed = None
            else:
                ed = _date.fromisoformat(date_m.group(1))

            if ed:
                days_away = (ed - _date.today()).days
                if days_away == 0:
                    add("CRITICAL", "EARNINGS", f"EARNINGS TODAY ({ed_str}) — position sizing critical now!", ed_str, "TODAY")
                elif days_away == 1:
                    add("HIGH", "EARNINGS", f"Earnings TOMORROW ({ed_str}) — consider position size", ed_str, "TOMORROW")
                elif days_away <= 3:
                    add("MEDIUM", "EARNINGS", f"Earnings in {days_away} days ({ed_str})", ed_str, f"{days_away}d")
        except Exception:
            pass

    # ── New news headlines ───────────────────────────────────────────────────
    old_titles = set(old.get("news_titles") or [])
    new_titles = set(new.get("news_titles") or [])
    new_headlines = new_titles - old_titles
    if new_headlines:
        count = len(new_headlines)
        sev   = "HIGH" if count >= 3 else "MEDIUM"
        titles_preview = " | ".join(list(new_headlines)[:2])
        add(sev, "NEWS", f"{count} new headline{'s' if count>1 else ''}: {titles_preview}",
            str(len(old_titles)), str(len(new_titles)))

    # ── New insider transaction ──────────────────────────────────────────────
    old_ins = old.get("latest_insider") or ""
    new_ins = new.get("latest_insider") or ""
    if new_ins and new_ins != old_ins:
        sev = "HIGH" if any(k in new_ins.lower() for k in ("purchase","buy","acquisition")) else "MEDIUM"
        add(sev, "INSIDER", f"New insider transaction: {new_ins}", old_ins or "none", new_ins)

    # ── Analyst rating / target change ──────────────────────────────────────
    old_rating = old.get("analyst_rating") or ""
    new_rating = new.get("analyst_rating") or ""
    old_target = _safe_float(old.get("analyst_target"))
    new_target = _safe_float(new.get("analyst_target"))

    if new_rating and new_rating != old_rating:
        add("MEDIUM", "ANALYST", f"Analyst consensus changed: {old_rating} → {new_rating}",
            old_rating, new_rating)
    if old_target and new_target and abs(new_target - old_target) >= 0.50:
        direction = "raised" if new_target > old_target else "cut"
        add("MEDIUM", "ANALYST", f"Price target {direction}: ${old_target:.2f} → ${new_target:.2f}",
            f"${old_target:.2f}", f"${new_target:.2f}")

    # ── Stocktwits sentiment shift ──────────────────────────────────────────
    old_bull = _safe_float(old.get("bull_pct"))
    new_bull = _safe_float(new.get("bull_pct"))
    if old_bull and new_bull:
        shift = new_bull - old_bull
        if abs(shift) >= 15:
            direction = "MORE bullish" if shift > 0 else "MORE bearish"
            add("MEDIUM", "SENTIMENT", f"Retail sentiment shifted {direction}: {old_bull:.0f}% → {new_bull:.0f}% bulls",
                f"{old_bull:.0f}%", f"{new_bull:.0f}%")

    # Sort by severity
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    deltas.sort(key=lambda d: sev_order.get(d["severity"], 4))
    return deltas


# ─────────────────────────────────────────────────────────────────────────────
# HTML report generator
# ─────────────────────────────────────────────────────────────────────────────
_SEV_COLORS = {
    "CRITICAL": ("#ff1744", "#2a0a0a"),
    "HIGH":     ("#ff6d00", "#1e1000"),
    "MEDIUM":   ("#ffca28", "#1e1800"),
    "LOW":      ("#78909c", "#0d1117"),
}
_CAT_ICONS = {
    "PRICE":    "PRICE",
    "IV":       "IV",
    "NEWS":     "NEWS",
    "INSIDER":  "INSIDER",
    "FLOW":     "FLOW",
    "VOLUME":   "VOL",
    "ANALYST":  "ANALYST",
    "EARNINGS": "EARNINGS",
    "SENTIMENT":"SENTIMENT",
}


def _render_delta_html(ticker: str, deltas: list[dict],
                       old_snap: dict, new_snap: dict,
                       interval_min: int = 30) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    old_ts = (old_snap.get("timestamp") or "")[:16].replace("T"," ")

    if not deltas:
        content = """
        <div style="text-align:center;padding:40px;color:#4caf50;font-size:18px">
          No significant changes detected since last scan.<br>
          <span style="font-size:13px;color:#666">All metrics stable.</span>
        </div>"""
    else:
        rows = ""
        for d in deltas:
            color, bg = _SEV_COLORS.get(d["severity"], ("#ccc","#111"))
            cat_label = _CAT_ICONS.get(d["category"], d["category"])
            old_v = d.get("old_val","") or ""
            new_v = d.get("new_val","") or ""
            change_str = f'<span style="color:#666">{old_v}</span> → <span style="color:{color};font-weight:bold">{new_v}</span>' if old_v and new_v else ""
            rows += f"""
            <tr style="background:{bg}">
              <td style="padding:10px 12px;color:{color};font-weight:bold;white-space:nowrap">
                <span style="font-size:11px;background:{color};color:#000;padding:2px 6px;border-radius:3px">{d['severity']}</span>
              </td>
              <td style="padding:10px 12px;color:#aaa;white-space:nowrap">{cat_label}</td>
              <td style="padding:10px 12px;color:#e0e0e0">{d['message']}</td>
              <td style="padding:10px 12px;font-size:12px">{change_str}</td>
            </tr>"""

        content = f"""
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#0d1117;color:#666;font-size:12px;text-transform:uppercase">
              <th style="padding:8px 12px;text-align:left">Severity</th>
              <th style="padding:8px 12px;text-align:left">Category</th>
              <th style="padding:8px 12px;text-align:left">What Changed</th>
              <th style="padding:8px 12px;text-align:left">Values</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    critical_count = sum(1 for d in deltas if d["severity"] == "CRITICAL")
    high_count     = sum(1 for d in deltas if d["severity"] == "HIGH")
    total_changes  = len(deltas)
    status_color   = "#ff1744" if critical_count else ("#ff6d00" if high_count else ("#ffca28" if total_changes else "#4caf50"))
    status_label   = "CRITICAL ALERT" if critical_count else ("ACTION NEEDED" if high_count else ("WATCH" if total_changes else "STABLE"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="{interval_min * 60}">
<title>ATLAS Delta: {ticker}</title>
<style>
  body {{background:#0d1117;color:#e0e0e0;font-family:system-ui,sans-serif;margin:0;padding:20px}}
  .header {{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}}
  .ticker {{font-size:28px;font-weight:700;color:#00d4ff}}
  .status {{font-size:14px;font-weight:700;color:{status_color};background:#1a1a2e;padding:6px 14px;border-radius:6px;border:1px solid {status_color}}}
  .meta {{font-size:12px;color:#666;margin-top:4px}}
  .stats {{display:flex;gap:12px;margin-bottom:20px}}
  .stat {{background:#1a1a2e;border-radius:6px;padding:10px 16px;min-width:100px;text-align:center}}
  .stat-val {{font-size:20px;font-weight:700}}
  .stat-lbl {{font-size:11px;color:#666;margin-top:2px}}
  .snapshot {{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:20px}}
  .snap-item {{background:#1a1a2e;border-radius:4px;padding:8px 12px}}
  .snap-key {{font-size:10px;color:#666;text-transform:uppercase}}
  .snap-val {{font-size:14px;font-weight:600;color:#ccc;margin-top:2px}}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="ticker">ATLAS DELTA: {ticker}</div>
    <div class="meta">Now: {now} &nbsp;|&nbsp; Prev scan: {old_ts} &nbsp;|&nbsp; {total_changes} changes</div>
  </div>
  <div class="status">{status_label}</div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-val" style="color:#ff1744">{critical_count}</div><div class="stat-lbl">Critical</div></div>
  <div class="stat"><div class="stat-val" style="color:#ff6d00">{high_count}</div><div class="stat-lbl">High</div></div>
  <div class="stat"><div class="stat-val" style="color:#ffca28">{sum(1 for d in deltas if d['severity']=='MEDIUM')}</div><div class="stat-lbl">Medium</div></div>
  <div class="stat"><div class="stat-val" style="color:#00d4ff">{new_snap.get('headline_count',0)}</div><div class="stat-lbl">Headlines</div></div>
  <div class="stat"><div class="stat-val" style="color:#4caf50">${new_snap.get('price','?')}</div><div class="stat-lbl">Price Now</div></div>
  <div class="stat"><div class="stat-val" style="color:#9c27b0">{new_snap.get('iv_rank','?')}</div><div class="stat-lbl">IV Rank</div></div>
</div>

<div style="margin-bottom:20px">
  <h3 style="color:#666;font-size:13px;margin:0 0 8px">CURRENT SNAPSHOT</h3>
  <div class="snapshot">
    <div class="snap-item"><div class="snap-key">Price</div><div class="snap-val">${new_snap.get('price','?')}</div></div>
    <div class="snap-item"><div class="snap-key">RSI</div><div class="snap-val">{new_snap.get('rsi','?')}</div></div>
    <div class="snap-item"><div class="snap-key">Rel Volume</div><div class="snap-val">{new_snap.get('rel_volume','?')}</div></div>
    <div class="snap-item"><div class="snap-key">IV Rank</div><div class="snap-val">{new_snap.get('iv_rank','?')}</div></div>
    <div class="snap-item"><div class="snap-key">Put/Call Ratio</div><div class="snap-val">{new_snap.get('pcr','?')}</div></div>
    <div class="snap-item"><div class="snap-key">Flow</div><div class="snap-val">{(new_snap.get('flow_sentiment') or '?').upper()}</div></div>
    <div class="snap-item"><div class="snap-key">Whisper EPS</div><div class="snap-val">{new_snap.get('whisper_eps','?')}</div></div>
    <div class="snap-item"><div class="snap-key">Earnings Date</div><div class="snap-val">{new_snap.get('earnings_date','?')}</div></div>
    <div class="snap-item"><div class="snap-key">Analyst Rating</div><div class="snap-val">{new_snap.get('analyst_rating','?')}</div></div>
    <div class="snap-item"><div class="snap-key">ST Bulls%</div><div class="snap-val">{new_snap.get('bull_pct','?')}{'%' if new_snap.get('bull_pct') else ''}</div></div>
  </div>
</div>

<h3 style="color:#666;font-size:13px;margin:0 0 8px">CHANGES DETECTED</h3>
{content}

<div style="margin-top:20px;font-size:11px;color:#333;text-align:center">
  Auto-refresh every {interval_min} minutes &nbsp;|&nbsp; ATLAS Delta Reporter
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Core scan function
# ─────────────────────────────────────────────────────────────────────────────
def scan_ticker(ticker: str, interval_min: int | dict = _DEFAULT_INTERVAL_MIN,
                notify_on_high: bool = True) -> dict:
    """
    Run a full scrape of ticker, diff against last snapshot, write delta report.
    If interval_min is a dict, it is treated as a precomputed web_scraper result
    (see dashboard /research). Otherwise interval_min is the HTML auto-refresh minutes.
    Returns: {"deltas": [...], "snapshot": {...}, "report_path": "..."}
    """
    ticker = ticker.upper().strip()
    log.info("[delta] Scanning %s...", ticker)

    if isinstance(interval_min, dict):
        scrape = interval_min
        interval_min = _DEFAULT_INTERVAL_MIN
    else:
        scrape = None

    # Run full scrape (unless caller passed precomputed scrape)
    if scrape is None:
        try:
            import web_scraper
            scrape = web_scraper.gather_all(ticker)
        except Exception:
            log.error("[delta] web_scraper failed for %s", ticker, exc_info=True)
            return {"error": "scrape failed", "ticker": ticker}

    new_snap = _extract_snapshot(scrape)
    old_snap = _load_snapshot(ticker) or new_snap  # first run: no diff

    deltas   = detect_deltas(old_snap, new_snap)
    _save_snapshot(ticker, new_snap)

    # Write HTML report
    html = _render_delta_html(ticker, deltas, old_snap, new_snap, interval_min)
    report_path = _REPORTS_DIR / f"ATLAS_DELTA_{ticker}.html"
    report_path.write_text(html, encoding="utf-8")

    # Fire desktop alerts for CRITICAL/HIGH changes
    if notify_on_high and deltas:
        critical = [d for d in deltas if d["severity"] in ("CRITICAL","HIGH")]
        if critical:
            try:
                import alerts as _alerts
                for d in critical[:3]:  # max 3 notifications per scan
                    _alerts._notify(
                        f"{ticker} {d['category']}",
                        d["message"],
                        urgent=(d["severity"] == "CRITICAL")
                    )
            except Exception:
                pass

    log.info("[delta] %s — %d changes (%d critical). Report: %s",
             ticker, len(deltas),
             sum(1 for d in deltas if d["severity"]=="CRITICAL"),
             report_path.name)

    return {
        "ticker":      ticker,
        "deltas":      deltas,
        "snapshot":    new_snap,
        "report_path": str(report_path),
        "scanned_at":  new_snap["timestamp"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Background watcher — runs scan_ticker in a loop
# ─────────────────────────────────────────────────────────────────────────────
class DeltaWatcher:
    """Continuously watches one or more tickers for changes."""

    def __init__(self, tickers: list[str], interval_min: int = _DEFAULT_INTERVAL_MIN):
        self.tickers      = [t.upper() for t in tickers]
        self.interval_min = interval_min
        self._thread: Optional[threading.Thread] = None
        self._running     = False

    def _loop(self) -> None:
        log.info("[delta watcher] Started — watching %s every %d min",
                 ", ".join(self.tickers), self.interval_min)
        time.sleep(45)  # wait 45s on first run so news/vision get quota first
        while self._running:
            for ticker in self.tickers:
                if not self._running:
                    break
                try:
                    result = scan_ticker(ticker, self.interval_min)
                    n_changes = len(result.get("deltas") or [])
                    if n_changes:
                        log.info("[delta watcher] %s — %d changes", ticker, n_changes)
                    else:
                        log.info("[delta watcher] %s — stable", ticker)
                except Exception:
                    log.error("[delta watcher] Error scanning %s", ticker, exc_info=True)

            # Sleep until next interval
            for _ in range(self.interval_min * 60 // 10):
                if not self._running:
                    break
                time.sleep(10)

        log.info("[delta watcher] Stopped.")

    def start(self) -> threading.Thread:
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, name="atlas-delta", daemon=True
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._running = False


def start_watcher(tickers: list[str],
                  interval_min: int = _DEFAULT_INTERVAL_MIN) -> DeltaWatcher:
    """Start the delta watcher and return it."""
    w = DeltaWatcher(tickers, interval_min)
    w.start()
    return w


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="ATLAS Delta Reporter")
    parser.add_argument("tickers", nargs="*", help="Tickers to watch (optional; defaults to positions_cache.json)")
    parser.add_argument("--watch",    action="store_true", help="Continuous mode")
    parser.add_argument("--interval", type=int, default=30, help="Minutes between scans (default 30)")
    args = parser.parse_args()

    cli_tickers = [t.upper() for t in (args.tickers or []) if t]
    tickers = cli_tickers or tickers_from_positions_cache()
    if not tickers:
        print("No tickers found in positions_cache.json and none provided.")
        sys.exit(1)

    if args.watch:
        print(f"Starting delta watcher: {', '.join(tickers)} every {args.interval} min")
        print("Reports will appear in reports/ATLAS_DELTA_{TICKER}.html")
        print("Ctrl+C to stop.\n")
        watcher = start_watcher(tickers, args.interval)
        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            watcher.stop()
            print("\nWatcher stopped.")
    else:
        for ticker in tickers:
            result = scan_ticker(ticker, args.interval)
            deltas = result.get("deltas") or []
            print(f"\n{'='*60}")
            print(f"DELTA REPORT: {ticker}  ({len(deltas)} changes)")
            print(f"{'='*60}")
            if not deltas:
                print("  No significant changes since last scan.")
            for d in deltas:
                ov = d.get("old_val","")
                nv = d.get("new_val","")
                change = f" ({ov} -> {nv})" if ov and nv else ""
                print(f"  [{d['severity']:<8}] {d['category']:<10} {d['message']}{change}")
            print(f"\n  Report: {result.get('report_path','')}")
