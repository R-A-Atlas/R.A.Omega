"""
multi_ranker.py — ATLAS Multi-Ticker Ranker

Run full ATLAS research on up to 20 tickers and rank them by conviction score.
Answers: "Out of these 10 stocks, which one should I trade RIGHT NOW?"

Scoring formula (0-100):
  ATLAS confidence score     (40 pts) — the AI's own conviction
  IV rank signal             (15 pts) — options cheap = more room to run
  Short float                (10 pts) — squeeze potential
  Options flow sentiment     (10 pts) — institutional money direction
  Earnings catalyst timing   (10 pts) — event-driven momentum
  Analyst consensus          ( 8 pts) — Wall St agreement
  News sentiment             ( 7 pts) — recent catalyst quality

Output:
  - Ranked table printed to console
  - HTML report: reports/ATLAS_RANKER_{timestamp}.html
  - Returns list of ranked results for programmatic use

Usage:
  python multi_ranker.py SOUN RZLV MARA ASTS IONQ
  python multi_ranker.py --file tickers.txt
  python multi_ranker.py --discover "AI penny stocks" --top 10
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent / "reports"
_REPORTS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Composite scoring
# ─────────────────────────────────────────────────────────────────────────────
def _score_result(research: dict) -> dict:
    """
    Score a single deep_research result on 0-100 scale.
    Returns score + breakdown dict.
    """
    syn = research.get("synthesis") or {}
    mkt = research.get("mktdata") or {}
    scr = research.get("scrape") or {}
    js  = (scr.get("js_data") or {}) if scr else {}
    fv  = (scr.get("finviz") or {}) if scr else {}
    bc  = js.get("barchart") or {}
    uw  = js.get("unusual_whales_js") or {}

    breakdown: dict = {}
    total = 0.0

    # ── 1. ATLAS confidence (40 pts) ─────────────────────────────────────────
    conf = syn.get("confidence") or syn.get("confidence_score") or 0
    try:
        conf_pts = min(40, float(conf) / 10 * 40)
    except Exception:
        conf_pts = 0
    breakdown["atlas_confidence"] = round(conf_pts, 1)
    total += conf_pts

    # ── 2. IV Rank (15 pts) — low IV = cheap options, more upside room ───────
    iv_str = bc.get("iv_rank") or (scr.get("unusual_whales") or {}).get("iv_rank","")
    try:
        ivr = float(str(iv_str).replace("%",""))
        # Best score when IV is low (20-35): options cheap, room to squeeze
        if ivr < 20:   iv_pts = 15.0
        elif ivr < 35: iv_pts = 12.0
        elif ivr < 55: iv_pts = 8.0
        elif ivr < 75: iv_pts = 4.0
        else:          iv_pts = 1.0   # IV extreme = crush risk
    except Exception:
        iv_pts = 0
    breakdown["iv_rank"] = round(iv_pts, 1)
    total += iv_pts

    # ── 3. Short float (10 pts) — squeeze fuel ───────────────────────────────
    sf_str = fv.get("short_float") or mkt.get("short_float","")
    try:
        sf = float(str(sf_str).replace("%",""))
        if sf > 30:   sf_pts = 10.0
        elif sf > 20: sf_pts = 7.0
        elif sf > 10: sf_pts = 4.0
        else:         sf_pts = 1.0
    except Exception:
        sf_pts = 0
    breakdown["short_float"] = round(sf_pts, 1)
    total += sf_pts

    # ── 4. Options flow (10 pts) ─────────────────────────────────────────────
    flow = (uw.get("bullish_bearish") or "").lower()
    pcr_str = bc.get("put_call_vol_ratio") or uw.get("put_call_ratio","")
    flow_pts = 0
    try:
        pcr = float(str(pcr_str))
        if pcr < 0.4:   flow_pts = 10.0   # very bullish
        elif pcr < 0.7: flow_pts = 7.0
        elif pcr < 1.0: flow_pts = 4.0
        elif pcr < 1.5: flow_pts = 2.0
        else:           flow_pts = 0
    except Exception:
        if "bullish" in flow:  flow_pts = 7.0
        elif "bearish" in flow: flow_pts = 0
        else:                   flow_pts = 3.0  # neutral
    breakdown["options_flow"] = round(flow_pts, 1)
    total += flow_pts

    # ── 5. Earnings catalyst (10 pts) ────────────────────────────────────────
    from datetime import date as _date
    import re as _re
    next_e = mkt.get("next_earnings") or (scr.get("finviz") or {}).get("earnings_date","")
    cat_pts = 0
    try:
        if next_e and next_e not in ("?","unknown",""):
            dm = _re.search(r"(\d{4}-\d{2}-\d{2})", str(next_e))
            if dm:
                ed = _date.fromisoformat(dm.group(1))
                days = (ed - _date.today()).days
                if 0 <= days <= 2:    cat_pts = 10.0  # imminent
                elif days <= 7:       cat_pts = 8.0
                elif days <= 14:      cat_pts = 5.0
                elif days <= 30:      cat_pts = 3.0
    except Exception:
        pass
    breakdown["earnings_catalyst"] = round(cat_pts, 1)
    total += cat_pts

    # ── 6. Analyst consensus (8 pts) ─────────────────────────────────────────
    rating_str = (mkt.get("analyst_rating") or "").lower()
    an_pts = 0
    if "strong buy" in rating_str: an_pts = 8.0
    elif "buy" in rating_str:      an_pts = 5.0
    elif "hold" in rating_str:     an_pts = 2.0
    elif "sell" in rating_str:     an_pts = 0
    breakdown["analyst_rating"] = round(an_pts, 1)
    total += an_pts

    # ── 7. News sentiment (7 pts) ────────────────────────────────────────────
    xref = (scr.get("cross_reference") or {}) if scr else {}
    xconf = (xref.get("confidence_data") or {}) if xref else {}
    news_sent = (xconf.get("news_sentiment") or "").upper()
    ns_pts = 0
    if news_sent == "BULLISH":  ns_pts = 7.0
    elif news_sent == "NEUTRAL": ns_pts = 3.5
    elif news_sent == "BEARISH": ns_pts = 0
    else:                        ns_pts = 3.0  # unknown = neutral
    breakdown["news_sentiment"] = round(ns_pts, 1)
    total += ns_pts

    # Overall letter grade
    score = round(total, 1)
    if score >= 80:    grade = "A+"
    elif score >= 70:  grade = "A"
    elif score >= 60:  grade = "B+"
    elif score >= 50:  grade = "B"
    elif score >= 40:  grade = "C"
    else:              grade = "D"

    return {
        "score":     score,
        "grade":     grade,
        "breakdown": breakdown,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Batch ranker
# ─────────────────────────────────────────────────────────────────────────────
def rank_tickers(tickers: list[str], budget: float = 100.0,
                 delay_between: float = 5.0) -> list[dict]:
    """
    Run ATLAS deep research on each ticker and rank by composite score.

    Returns list of results sorted by score (best first).
    Each result contains: ticker, score, grade, breakdown, full research.
    """
    try:
        import deep_research as dr
    except ImportError:
        log.error("deep_research.py not found")
        return []

    results = []
    total   = len(tickers)

    for i, ticker in enumerate(tickers):
        ticker = ticker.upper().strip()
        log.info("[ranker] (%d/%d) Researching %s...", i + 1, total, ticker)
        print(f"  [{i+1}/{total}] Researching {ticker}...", flush=True)

        try:
            research = dr.research_ticker(ticker, budget=budget)
            scoring  = _score_result(research)
            syn      = research.get("synthesis") or {}
            tp       = syn.get("trade_plan") or {}

            results.append({
                "ticker":         ticker,
                "rank":           0,  # set after sort
                "score":          scoring["score"],
                "grade":          scoring["grade"],
                "breakdown":      scoring["breakdown"],
                "atlas_rating":   syn.get("overall_rating","?"),
                "confidence":     syn.get("confidence","?"),
                "action":         tp.get("action","?"),
                "entry":          tp.get("entry_price","?"),
                "target_1":       tp.get("target_1","?"),
                "stop":           tp.get("stop_loss","?"),
                "summary":        (syn.get("executive_summary") or "")[:120],
                "position_sizing": research.get("position_sizing"),
                "research":       research,
            })
        except Exception:
            log.warning("[ranker] Research failed for %s", ticker, exc_info=True)
            results.append({
                "ticker": ticker, "score": 0, "grade": "F",
                "breakdown": {}, "atlas_rating": "ERROR",
                "confidence": 0, "action": "SKIP",
                "summary": "Research failed",
            })

        if i < total - 1:
            time.sleep(delay_between)

    # Sort and assign ranks
    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


# ─────────────────────────────────────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────────────────────────────────────
def render_ranker_html(results: list[dict], budget: float = 100.0) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n   = len(results)

    def grade_color(g: str) -> str:
        return {"A+":"#00d4ff","A":"#4caf50","B+":"#8bc34a","B":"#ffca28",
                "C":"#ff9800","D":"#f44336","F":"#666"}.get(g, "#aaa")

    def score_bar(score: float) -> str:
        w = min(100, score)
        color = "#4caf50" if score >= 70 else ("#ffca28" if score >= 50 else "#f44336")
        return (f'<div style="height:6px;background:#1a1a1a;border-radius:3px;width:100px;display:inline-block">'
                f'<div style="height:6px;width:{w}px;background:{color};border-radius:3px"></div></div>')

    rows = ""
    for r in results:
        rank_color = "#00d4ff" if r["rank"] == 1 else ("#4caf50" if r["rank"] <= 3 else "#aaa")
        action_c   = "#4caf50" if "buy" in str(r.get("action","")).lower() else "#f44336"
        sizing_str = ""
        if r.get("position_sizing"):
            sz = r["position_sizing"].get("recommendation") or {}
            total_cost = sz.get("total_cost",0)
            max_loss   = sz.get("max_loss",0)
            if total_cost:
                sizing_str = f'${total_cost:.0f} / risk ${max_loss:.0f}'

        bd = r.get("breakdown") or {}
        bd_str = " ".join(
            f'<span style="font-size:9px;background:#111;padding:1px 4px;border-radius:2px;color:#666">'
            f'{k[:4]}:{v:.0f}</span>'
            for k, v in bd.items()
        )

        rows += f"""
        <tr style="border-bottom:1px solid #1a1a1a">
          <td style="padding:12px 10px;color:{rank_color};font-size:18px;font-weight:700">{r['rank']}</td>
          <td style="padding:12px 10px;color:#00d4ff;font-weight:700;font-size:16px">{r['ticker']}</td>
          <td style="padding:12px 10px">
            <span style="font-size:20px;font-weight:700;color:{grade_color(r['grade'])}">{r['grade']}</span>
            <div style="margin-top:4px">{score_bar(r['score'])}</div>
            <div style="font-size:11px;color:#666;margin-top:2px">{r['score']:.0f}/100</div>
          </td>
          <td style="padding:12px 10px;color:{action_c};font-weight:600">{r['action']}</td>
          <td style="padding:12px 10px;color:#aaa;font-size:12px">{r.get('summary','')}</td>
          <td style="padding:12px 10px;color:#888;font-size:11px">{sizing_str}</td>
          <td style="padding:12px 10px">{bd_str}</td>
        </tr>"""

    top = results[0] if results else {}
    top_summary = top.get("summary","")
    top_sizing  = ""
    if top.get("position_sizing"):
        sl = top["position_sizing"].get("summary_lines") or []
        top_sizing = "<br>".join(sl[:3])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ATLAS Ranker — {now}</title>
<style>
  body {{background:#0d1117;color:#e0e0e0;font-family:system-ui,sans-serif;margin:0;padding:20px}}
  h1 {{color:#00d4ff;font-size:22px;margin:0 0 4px}}
  table {{width:100%;border-collapse:collapse}}
  tr:hover {{background:#0e1117}}
  th {{padding:8px 10px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;border-bottom:2px solid #1a1a1a}}
</style>
</head>
<body>
<h1>ATLAS Multi-Ticker Ranker</h1>
<div style="color:#666;font-size:13px;margin-bottom:20px">{n} tickers ranked by composite score · {now} · Budget: ${budget}</div>

{'<div style="background:#0e1020;border:1px solid #00d4ff44;border-radius:10px;padding:16px;margin-bottom:24px"><div style="color:#00d4ff;font-weight:700;font-size:16px">TOP PICK: ' + top.get("ticker","") + '  <span style="color:#4caf50">' + top.get("grade","") + '  ' + str(top.get("score","")) + '/100</span></div><div style="color:#ccc;font-size:13px;margin-top:8px">' + top_summary + '</div>' + (f'<div style="color:#aaa;font-size:12px;margin-top:8px">{top_sizing}</div>' if top_sizing else "") + '</div>' if top else ""}

<table>
  <thead>
    <tr>
      <th>#</th><th>Ticker</th><th>Score</th><th>Action</th>
      <th>Summary</th><th>Position Size</th><th>Score Breakdown</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div style="margin-top:20px;font-size:11px;color:#333;text-align:center">
  Score formula: Confidence(40) + IV_Rank(15) + Short_Float(10) + Options_Flow(10) + Earnings_Catalyst(10) + Analyst(8) + News(7)
</div>
</body>
</html>"""


def run_and_save(tickers: list[str], budget: float = 100.0) -> Path:
    """Run ranker and save HTML report. Returns report path."""
    results = rank_tickers(tickers, budget)
    html    = render_ranker_html(results, budget)
    ts      = datetime.now().strftime("%Y%m%d_%H%M")
    path    = _REPORTS_DIR / f"ATLAS_RANKER_{ts}.html"
    path.write_text(html, encoding="utf-8")
    log.info("[ranker] Report saved: %s", path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="ATLAS Multi-Ticker Ranker")
    parser.add_argument("tickers", nargs="*", help="Tickers to rank")
    parser.add_argument("--file",    metavar="FILE", help="Text file with one ticker per line")
    parser.add_argument("--budget",  type=float, default=100.0)
    parser.add_argument("--delay",   type=float, default=5.0, help="Seconds between tickers")
    args = parser.parse_args()

    tickers: list[str] = list(args.tickers)
    if args.file:
        fp = Path(args.file)
        if fp.exists():
            tickers += [l.strip().upper() for l in fp.read_text().splitlines() if l.strip()]

    if not tickers:
        print("Usage: python multi_ranker.py SOUN RZLV MARA ASTS")
        print("       python multi_ranker.py --file tickers.txt")
        sys.exit(1)

    print(f"\nRanking {len(tickers)} tickers: {', '.join(tickers)}\n")
    results = rank_tickers(tickers, args.budget, args.delay)

    print(f"\n{'='*70}")
    print(f"{'#':<3} {'Ticker':<8} {'Grade':<6} {'Score':<6} {'Action':<14} Summary")
    print(f"{'='*70}")
    for r in results:
        print(f"{r['rank']:<3} {r['ticker']:<8} {r['grade']:<6} {r['score']:<6.0f} "
              f"{str(r.get('action','?')):<14} {r.get('summary','')[:50]}")

    report_path = run_and_save(results if False else tickers, args.budget)
    # Actually re-use results
    html = render_ranker_html(results, args.budget)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path = _REPORTS_DIR / f"ATLAS_RANKER_{ts}.html"
    path.write_text(html, encoding="utf-8")
    print(f"\nReport: {path}")
