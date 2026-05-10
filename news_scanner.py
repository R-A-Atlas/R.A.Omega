#!/usr/bin/env python3
"""
ATLAS News Scanner
------------------
Reads positions_cache.json (written by screen_watcher.py or the manual
.env override) and continuously scans the web for news, catalysts, and
risk events for every ticker in your portfolio.

For each ticker it:
  1. Pulls live headlines from yfinance + Yahoo Finance RSS
  2. Sends everything to Gemini for a structured analysis:
       – Catalyst rating  (🟢 bullish / 🟡 neutral / 🔴 bearish)
       – Key headlines summary
       – How each item might affect YOUR open position
       – Suggested action  (hold / watch / consider exit)
  3. Writes  reports/TICKER_report.html  (one file per ticker)
  4. Writes  LIVE_REPORTS.html at project root (master tabbed view — open this in browser)
  5. Logs a one-line heartbeat every scan cycle, not every headline

Usage (standalone):
    python news_scanner.py               # runs forever, scans every 5 min
    python news_scanner.py --once        # one scan then exit
    python news_scanner.py --interval 3  # scan every 3 minutes

Designed to be imported and started as a thread by auto_bot.py --watch.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yfinance as yf
from dotenv import load_dotenv

from gemini_limiter import wait_for_slot

SCRIPT_DIR      = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")
load_dotenv()

POSITIONS_CACHE  = SCRIPT_DIR / "positions_cache.json"
REPORTS_DIR      = SCRIPT_DIR / "reports"
LIVE_REPORTS     = SCRIPT_DIR / "LIVE_REPORTS.html"
SCAN_INTERVAL    = int(os.environ.get("NEWS_SCAN_INTERVAL_MIN", "5")) * 60  # seconds

try:
    from google import genai as _genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False

_stop_event = threading.Event()


# ─────────────────────────────────────────────────────────────────────────────
# Gemini client
# ─────────────────────────────────────────────────────────────────────────────
def _gemini_client():
    if not _GENAI_OK:
        return None
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    return _genai.Client(api_key=api_key) if api_key else None


def _gemini_text(client, prompt: str, model: str | None = None) -> str:
    if client is None:
        return ""
    m = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    resp = None
    for _attempt in range(4):
        try:
            wait_for_slot("news_scanner")
            resp = client.models.generate_content(model=m, contents=prompt)
            break
        except Exception as _e:
            if ("429" in str(_e)
                    or "quota" in str(_e).lower()
                    or "RESOURCE_EXHAUSTED" in str(_e)):
                wait = 20 * (2 ** _attempt)  # 20s, 40s, 80s, 160s
                logging.warning("[gemini] 429 rate limit — waiting %ss before retry", wait)
                _time.sleep(wait)
            else:
                logging.debug("Gemini text call failed.", exc_info=True)
                return ""
    if resp is None:
        logging.error("[gemini] All retries exhausted — skipping this synthesis")
        return ""
    return (resp.text or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# News fetching — Gemini Grounded Search (primary) + yfinance (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _gemini_grounded_research(ticker: str, client) -> tuple[list[dict], str]:
    """
    Use Gemini with Google Search grounding to do real-time web research on
    a ticker.  Returns (structured_news_list, raw_research_text).

    This is the same mechanism as ChatGPT / Gemini Deep Research — Gemini
    searches the actual internet, reads pages, and returns cited facts with
    dates and sources.
    """
    if client is None:
        return [], ""

    model = "gemini-2.0-flash"   # grounding requires flash, not 2.5
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    search_prompt = f"""
Today is {today}.

Do a comprehensive news and financial research sweep on the stock ticker: {ticker}

Search for and report on ALL of the following — include exact dates, numbers, and sources for everything:

1. LATEST NEWS (past 7 days): Any company announcements, press releases, product launches, partnerships
2. ANALYST ACTIVITY: Recent upgrades/downgrades, price target changes, initiation of coverage — include the firm name, old target, new target, date
3. EARNINGS: Next scheduled earnings date and time (confirm from official sources). Previous earnings: reported EPS vs estimate, revenue vs estimate, guidance. Was it a beat or miss?
4. CATALYSTS: Specific upcoming events — earnings call date/time, product announcements, FDA dates, contract announcements, conference presentations
5. INSIDER & INSTITUTIONAL ACTIVITY: Any recent insider buys/sells, institutional filings (13F/13D)
6. OPTIONS ACTIVITY: Any unusual options volume or notable bets
7. SHORT INTEREST: Current short interest %, days to cover, recent changes
8. PRICE ACTION: 52-week high/low, key support and resistance levels, recent % move
9. SECTOR NEWS: Any broader sector or macro news that specifically affects {ticker}
10. SENTIMENT: Overall analyst consensus rating and average price target

Be specific. Use real numbers and real dates. Do not fabricate — if you cannot find something, say "Not found".
"""

    try:
        from google.genai import types as _gtypes
        # Retry with exponential backoff on rate limits
        for _attempt in range(4):
            try:
                wait_for_slot("news_scanner_grounded")
                resp = client.models.generate_content(
                    model=model,
                    contents=search_prompt,
                    config=_gtypes.GenerateContentConfig(
                        tools=[_gtypes.Tool(google_search=_gtypes.GoogleSearch())]
                    ),
                )
                break
            except Exception as _e:
                if ("429" in str(_e)
                        or "quota" in str(_e).lower()
                        or "RESOURCE_EXHAUSTED" in str(_e)):
                    wait = 20 * (2 ** _attempt)  # 20s, 40s, 80s, 160s
                    logging.warning("[gemini] 429 rate limit — waiting %ss before retry", wait)
                    _time.sleep(wait)
                else:
                    raise
        else:
            logging.error("[gemini] All retries exhausted — skipping this synthesis")
            return [], ""
        raw_text = (resp.text or "").strip()
        logging.debug("Grounded research for %s: %d chars", ticker, len(raw_text))

        # Parse grounding metadata for source URLs
        sources: list[dict] = []
        try:
            meta = resp.candidates[0].grounding_metadata
            for chunk in (meta.grounding_chunks or []):
                web = getattr(chunk, "web", None)
                if web and web.uri:
                    sources.append({"uri": web.uri, "title": getattr(web, "title", "")})
        except Exception:
            pass

        # Extract individual headline-like items from the research text
        news_items = _parse_grounded_research_to_news(raw_text, ticker, sources)
        return news_items, raw_text

    except Exception:
        logging.debug("Gemini grounded search failed for %s.", ticker, exc_info=True)
        return [], ""


def _parse_grounded_research_to_news(raw_text: str, ticker: str,
                                      sources: list[dict]) -> list[dict]:
    """
    Convert the freeform research text into structured news items by extracting
    bullet points / numbered items that look like news events.
    """
    import re
    lines = raw_text.split("\n")
    items: list[dict] = []
    source_idx = 0

    # Pull lines that look like actual news items (not section headers)
    date_pat = re.compile(
        r"\b(\d{4}-\d{2}-\d{2}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|"
        r"\d{1,2}/\d{1,2}/\d{4})\b",
        re.IGNORECASE,
    )

    for line in lines:
        line = line.strip()
        # Skip headers, empty lines, very short lines
        if not line or len(line) < 30:
            continue
        if line.startswith("#"):
            continue
        # Must start with bullet or number or contain ":" after a label
        if not (line.startswith(("-", "*", "•", "–")) or re.match(r"^\d+\.", line)):
            continue

        clean = re.sub(r"^[-*•–\d\.]+\s*", "", line).strip()
        if len(clean) < 20:
            continue

        # Try to extract a date from the line
        dm = date_pat.search(clean)
        ts = dm.group(0) if dm else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Assign a source URL if available
        url = ""
        if source_idx < len(sources):
            url = sources[source_idx].get("uri", "")
            source_idx += 1

        items.append({
            "title":  clean,
            "source": "Gemini Search",
            "time":   ts,
            "url":    url,
        })

    return items[:30]


def _yfinance_news_fallback(ticker: str, max_items: int = 20) -> list[dict]:
    """yfinance news — supports both old and new API shapes."""
    try:
        tk = yf.Ticker(ticker)
        raw = tk.news or []
        results = []
        for item in raw[:max_items]:
            # New yfinance wraps in content{}
            content = item.get("content") or item
            title    = (content.get("title") or item.get("title") or "").strip()
            pub_time = (content.get("pubDate") or
                        item.get("providerPublishTime") or
                        item.get("pubDate") or 0)
            url      = (content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict)
                        else content.get("url") or item.get("link") or "")
            source   = (content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict)
                        else item.get("publisher") or "Yahoo Finance")
            if not title:
                continue
            # pub_time might be a string ISO or an int timestamp
            if isinstance(pub_time, (int, float)) and pub_time > 0:
                ts = datetime.fromtimestamp(pub_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            elif isinstance(pub_time, str) and pub_time:
                ts = pub_time[:16]
            else:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            results.append({"title": title, "source": source, "time": ts, "url": url})
        return results
    except Exception:
        logging.debug("yfinance news fallback failed for %s.", ticker, exc_info=True)
        return []


def _yahoo_rss_fallback(ticker: str, max_items: int = 15) -> list[dict]:
    """Yahoo Finance RSS — handles both CDATA and plain title tags."""
    import re
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        items = re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)
        results = []
        for item in items[:max_items]:
            # Handle both CDATA and plain title
            tm = (re.search(r"<title><!\[CDATA\[(.*?)]]></title>", item) or
                  re.search(r"<title>(.*?)</title>", item))
            if not tm:
                continue
            title = tm.group(1).strip()
            link  = re.search(r"<link>(.*?)</link>", item)
            pubdt = re.search(r"<pubDate>(.*?)</pubDate>", item)
            ts    = (pubdt.group(1).strip()[:25] if pubdt else
                     datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            results.append({
                "title":  title,
                "source": "Yahoo Finance",
                "time":   ts,
                "url":    link.group(1).strip() if link else "",
            })
        return results
    except Exception:
        logging.debug("Yahoo RSS fallback failed for %s.", ticker, exc_info=True)
        return []


def _fetch_earnings_calendar(ticker: str) -> dict:
    """
    Pull real earnings dates and estimates from yfinance.
    Returns a dict with next_earnings, last_eps_actual, last_eps_est, etc.
    """
    result: dict = {}
    try:
        tk = yf.Ticker(ticker)
        cal = tk.calendar
        if cal is not None and not (hasattr(cal, "empty") and cal.empty):
            if hasattr(cal, "to_dict"):
                cd = cal.to_dict()
            elif isinstance(cal, dict):
                cd = cal
            else:
                cd = {}
            # Earnings date
            ed = cd.get("Earnings Date") or cd.get("earningsDate")
            if ed:
                if hasattr(ed, "__iter__") and not isinstance(ed, str):
                    dates = [str(d)[:10] for d in list(ed) if d]
                    result["next_earnings"] = dates[0] if dates else None
                    if len(dates) > 1:
                        result["earnings_date_range"] = f"{dates[0]} – {dates[-1]}"
                else:
                    result["next_earnings"] = str(ed)[:10]

        # EPS estimates from analyst data
        try:
            eps = tk.earnings_dates
            if eps is not None and not eps.empty:
                latest = eps.iloc[0]
                result["eps_estimate"]    = latest.get("EPS Estimate")
                result["eps_actual"]      = latest.get("Reported EPS")
                result["eps_surprise_pct"]= latest.get("Surprise(%)")
        except Exception:
            pass

        # Analyst targets
        try:
            info = tk.info or {}
            result["analyst_target"]   = info.get("targetMeanPrice")
            result["analyst_low"]      = info.get("targetLowPrice")
            result["analyst_high"]     = info.get("targetHighPrice")
            result["analyst_rating"]   = info.get("recommendationKey", "").replace("_", " ").title()
            result["analyst_count"]    = info.get("numberOfAnalystOpinions")
            result["52w_high"]         = info.get("fiftyTwoWeekHigh")
            result["52w_low"]          = info.get("fiftyTwoWeekLow")
            result["short_pct"]        = info.get("shortPercentOfFloat")
            result["forward_pe"]       = info.get("forwardPE")
            result["market_cap"]       = info.get("marketCap")
            result["sector"]           = info.get("sector")
            result["industry"]         = info.get("industry")
        except Exception:
            pass

    except Exception:
        logging.debug("Earnings calendar fetch failed for %s.", ticker, exc_info=True)
    return result


def _gather_news(ticker: str, client=None) -> tuple[list[dict], str, dict]:
    """
    Main news gather — tries Gemini grounded search first, falls back to
    yfinance + Yahoo RSS.  Also pulls earnings calendar.
    Returns (news_list, research_text, earnings_data).
    """
    grounded_news, research_text = _gemini_grounded_research(ticker, client)
    fallback_news = _yfinance_news_fallback(ticker) + _yahoo_rss_fallback(ticker)

    # Deduplicate
    seen: set[str] = set()
    combined: list[dict] = []
    for item in grounded_news + fallback_news:
        key = (item.get("title") or "").lower()[:80]
        if key and key not in seen:
            seen.add(key)
            combined.append(item)

    earnings = _fetch_earnings_calendar(ticker)
    logging.info("  %s: %d grounded + %d fallback = %d unique articles | "
                 "next earnings: %s",
                 ticker, len(grounded_news), len(fallback_news), len(combined),
                 earnings.get("next_earnings", "unknown"))
    return combined, research_text, earnings


# ─────────────────────────────────────────────────────────────────────────────
# Gemini analysis prompt
# ─────────────────────────────────────────────────────────────────────────────
def _build_analysis_prompt(ticker: str, position: dict, news: list[dict],
                            earnings: dict | None = None,
                            research_text: str = "") -> str:
    pos_kind = "stock"
    is_option = bool(position.get("option_type"))
    if is_option:
        pos_kind = (
            f"{position.get('option_type','?').upper()} CALL option "
            f"strike=${position.get('strike')}  exp={position.get('expiry')}"
            if position.get("option_type","").lower() == "call" else
            f"{position.get('option_type','?').upper()} PUT option "
            f"strike=${position.get('strike')}  exp={position.get('expiry')}"
        )

    qty_key = "shares" if not is_option else "contracts"
    qty     = position.get(qty_key) or position.get("quantity") or "?"
    avg     = position.get("avg_buy_price") or position.get("avg_premium") or "?"
    curr    = position.get("current_price") or "unknown"
    pnl     = position.get("total_return")
    pnl_pct = position.get("total_return_pct")
    pnl_str = f"${pnl:+,.2f} ({pnl_pct:+.2f}%)" if pnl is not None else "unknown"

    e = earnings or {}
    next_earnings  = e.get("next_earnings") or "Not confirmed"
    earnings_range = e.get("earnings_date_range") or next_earnings
    eps_est        = e.get("eps_estimate")
    eps_actual     = e.get("eps_actual")
    eps_surprise   = e.get("eps_surprise_pct")
    analyst_target = e.get("analyst_target")
    analyst_rating = e.get("analyst_rating") or "Unknown"
    analyst_count  = e.get("analyst_count") or "?"
    w52_high       = e.get("52w_high")
    w52_low        = e.get("52w_low")
    short_pct      = e.get("short_pct")
    market_cap     = e.get("market_cap")
    sector         = e.get("sector") or "Unknown"

    def _fmt(v, prefix="", suffix="", decimals=2):
        if v is None: return "N/A"
        try: return f"{prefix}{float(v):,.{decimals}f}{suffix}"
        except: return str(v)

    headlines_text = "\n".join(
        f"  [{i+1}] ({item['time']}) {item['title']}  [{item['source']}]"
        for i, item in enumerate(news[:30])
    ) or "  (no recent headlines found)"

    research_section = ""
    if research_text:
        research_section = f"""
=== DEEP RESEARCH REPORT (from live Google Search) ===
{research_text[:3000]}
"""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""
You are ATLAS, an elite trading analyst and risk manager.  Today is {today}.

=== MY OPEN POSITION ===
Ticker:          {ticker}
Type:            {pos_kind}
Quantity:        {qty} {qty_key}
Avg cost:        {avg}
Current price:   {curr}
Unrealised P&L:  {pnl_str}
Sector:          {sector}

=== MARKET DATA ===
52-week high:    {_fmt(w52_high, "$")}
52-week low:     {_fmt(w52_low, "$")}
Short interest:  {_fmt(short_pct, suffix="%", decimals=1) if short_pct else "N/A"}
Market cap:      {_fmt(market_cap, "$", decimals=0) if market_cap else "N/A"}
Analyst rating:  {analyst_rating}  ({analyst_count} analysts)
Analyst target:  {_fmt(analyst_target, "$")}

=== EARNINGS ===
Next earnings:   {earnings_range}
Last EPS actual: {_fmt(eps_actual)}  vs estimate: {_fmt(eps_est)}
Surprise:        {_fmt(eps_surprise, suffix="%")}

=== RECENT HEADLINES & RESEARCH ===
{headlines_text}
{research_section}

=== YOUR TASK ===
Analyze ALL the information above in the context of MY SPECIFIC POSITION.
Be precise — use real numbers, real dates, and real analysis.
If you see an upcoming earnings date, include it with exact date and your read on whether it's likely a beat or miss based on current data.
If this is an option position, specifically address: theta decay risk, probability of expiring in-the-money, whether to hold through earnings or exit before.

Return a single JSON object with EXACTLY this structure (all fields required, null if not available):
{{
  "ticker": "{ticker}",
  "overall_sentiment": "bullish | neutral | bearish",
  "catalyst_score": <integer 1-10>,
  "risk_score": <integer 1-10>,
  "summary": "<3-4 sentence current situation summary with specific numbers and dates>",
  "key_headlines": [
    {{
      "headline": "<exact headline or key fact with date>",
      "impact": "positive | negative | neutral",
      "why": "<one specific sentence explaining impact on this position>"
    }}
  ],
  "position_impact": "<detailed paragraph: how this news affects YOUR specific {pos_kind} — include price targets, expiry risk, theta, earnings play analysis>",
  "earnings_play": {{
    "next_date": "{next_earnings}",
    "expected_move": "<expected % move up or down based on options pricing or historical>",
    "beat_or_miss_probability": "<analyst consensus read — likely beat, miss, or in-line>",
    "options_strategy": "<if this is an option: hold through earnings Y/N and why; if stock: sell covered call, add, trim, etc.>"
  }},
  "suggested_action": "hold | watch | consider_exit | add | urgent_exit",
  "action_reason": "<one specific sentence with a price level or date mentioned>",
  "catalysts": [
    "<specific event with EXACT DATE if known — e.g. 'Q2 earnings: August 7 2026 pre-market'>",
    "<another catalyst with date>"
  ],
  "risks": [
    "<specific risk with numbers — e.g. 'Short interest 28% could cause squeeze or continued pressure'>",
    "<another risk>"
  ],
  "price_levels": {{
    "support": <number or null>,
    "resistance": <number or null>,
    "target": <number or null>,
    "stop_loss": <number or null>
  }},
  "analyst_consensus": {{
    "rating": "{analyst_rating}",
    "avg_target": {analyst_target or "null"},
    "count": {analyst_count if str(analyst_count).isdigit() else "null"}
  }},
  "last_analyzed": "{datetime.now(timezone.utc).isoformat()}"
}}

Return ONLY the JSON — no markdown fences, no explanation outside the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML report generation
# ─────────────────────────────────────────────────────────────────────────────
_SENTIMENT_ICON: dict[str, tuple[str, str, str]] = {
    "bullish":  ("🟢", "#00c851", "#0a2a18"),
    "neutral":  ("🟡", "#ffbb33", "#2a2000"),
    "bearish":  ("🔴", "#ff4444", "#2a0a0a"),
}

_ACTION_ICON: dict[str, tuple[str, str]] = {
    "hold":          ("⏸️",  "#aaaaaa"),
    "watch":         ("👁️",  "#ffbb33"),
    "consider_exit": ("⚠️",  "#ff8800"),
    "add":           ("➕",  "#00c851"),
    "urgent_exit":   ("🚨",  "#ff0000"),
}


def _score_bar(score: int | str, color: str) -> str:
    """Render a filled bar (0–10 scale) with CSS only."""
    try:
        pct = max(0, min(100, int(score) * 10))
    except (TypeError, ValueError):
        pct = 50
    return (
        f'<div style="background:#1e1e1e;border-radius:4px;height:8px;width:100%;margin-top:4px">'
        f'<div style="background:{color};width:{pct}%;height:8px;border-radius:4px;'
        f'transition:width .4s ease"></div></div>'
    )


def _ticker_section_html(ticker: str, analysis: dict, news: list[dict], position: dict) -> str:
    """Render the full detail section for one ticker (used inside the SPA tab)."""
    sentiment = (analysis.get("overall_sentiment") or "neutral").lower()
    s_icon, s_color, s_bg = _SENTIMENT_ICON.get(sentiment, ("⚪", "#888888", "#1a1a1a"))
    act_key  = (analysis.get("suggested_action") or "hold").lower()
    act_icon, act_color = _ACTION_ICON.get(act_key, ("❓", "#aaaaaa"))
    cat_score  = analysis.get("catalyst_score", "?")
    risk_score = analysis.get("risk_score", "?")
    ts = (analysis.get("last_analyzed") or "")[:19].replace("T", " ")

    qty_key = "shares" if not position.get("option_type") else "contracts"
    qty     = position.get(qty_key) or position.get("quantity") or "—"
    avg     = position.get("avg_buy_price") or position.get("avg_premium") or "—"
    curr    = position.get("current_price") or "—"
    pnl     = position.get("total_return")
    pnl_pct = position.get("total_return_pct")
    pnl_color = "#00c851" if (pnl or 0) >= 0 else "#ff4444"
    pnl_str     = f"${pnl:+,.2f}" if pnl is not None else "—"
    pnl_pct_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—"

    pl    = analysis.get("price_levels") or {}
    supp  = pl.get("support")    or "—"
    res   = pl.get("resistance") or "—"
    tgt   = pl.get("target")     or "—"
    stop  = pl.get("stop_loss")  or "—"

    ep  = analysis.get("earnings_play") or {}
    ep_date  = ep.get("next_date") or (analysis.get("_earnings") or {}).get("next_earnings") or "TBD"
    ep_move  = ep.get("expected_move") or "—"
    ep_beat  = ep.get("beat_or_miss_probability") or "—"
    ep_strat = ep.get("options_strategy") or "—"

    ea   = analysis.get("_earnings") or {}
    ac   = analysis.get("analyst_consensus") or {}
    at   = ac.get("avg_target") or ea.get("analyst_target")
    ar   = ac.get("rating")     or ea.get("analyst_rating") or "—"
    an   = ac.get("count")      or ea.get("analyst_count")  or "—"
    w52h = ea.get("52w_high")
    w52l = ea.get("52w_low")
    sht  = ea.get("short_pct")

    def _ef(v, prefix="$", suffix="", dec=2):
        if v is None or v == "N/A": return "—"
        try: return f"{prefix}{float(v):,.{dec}f}{suffix}"
        except: return str(v)

    # ── Key headlines ────────────────────────────────────────────
    kh_rows = ""
    for h in (analysis.get("key_headlines") or [])[:10]:
        imp = (h.get("impact") or "neutral").lower()
        ic  = {"positive": "#00c851", "negative": "#ff4444"}.get(imp, "#888")
        kh_rows += (
            f'<tr>'
            f'<td style="color:{ic};padding:8px 6px;width:14px">●</td>'
            f'<td style="padding:8px 6px;color:#ddd">{h.get("headline","")}</td>'
            f'<td style="padding:8px 6px;color:#888;font-size:.82rem">{h.get("why","")}</td>'
            f'</tr>'
        )

    # ── Catalysts / Risks ───────────────────────────────────────
    cats  = "".join(f"<li>{c}</li>" for c in (analysis.get("catalysts") or []))
    risks = "".join(f"<li>{r}</li>" for r in (analysis.get("risks") or []))

    # ── Raw feed ────────────────────────────────────────────────
    feed_rows = ""
    for item in news[:20]:
        url = item.get("url") or "#"
        feed_rows += (
            f'<tr>'
            f'<td style="padding:6px 8px;color:#555;font-size:.78rem;white-space:nowrap">{item.get("time","")[:16]}</td>'
            f'<td style="padding:6px 8px"><a href="{url}" target="_blank" '
            f'style="color:#4da6ff;text-decoration:none;font-size:.85rem">{item.get("title","")}</a></td>'
            f'<td style="padding:6px 8px;color:#555;font-size:.78rem">{item.get("source","")}</td>'
            f'</tr>'
        )

    opt_badge = ""
    if position.get("option_type"):
        opt_badge = (
            f'<span style="background:#1a1a3a;color:#88aaff;padding:2px 10px;'
            f'border-radius:20px;font-size:.8rem;margin-left:8px">'
            f'{position["option_type"].upper()} • Strike {position.get("strike","?")} • Exp {position.get("expiry","?")}'
            f'</span>'
        )

    return f"""
<div class="ticker-page" id="page-{ticker}" style="display:none">

  <!-- ── Header banner ── -->
  <div style="background:{s_bg};border:2px solid {s_color};border-radius:14px;
              padding:22px 24px;display:flex;align-items:center;gap:18px;margin-bottom:20px">
    <span style="font-size:3rem">{s_icon}</span>
    <div style="flex:1">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
        <span style="font-size:2.2rem;font-weight:800;color:{s_color}">{ticker}</span>
        {opt_badge}
        <span style="background:#111;border:1px solid {act_color};color:{act_color};
                     padding:4px 14px;border-radius:20px;font-size:.85rem;font-weight:600">
          {act_icon} {act_key.replace("_"," ").upper()}
        </span>
      </div>
      <div style="color:#aaa;font-size:.85rem;margin-top:6px">{analysis.get("action_reason","")}</div>
    </div>
    <div style="text-align:right;font-size:.75rem;color:#444">Last updated<br>{ts} UTC</div>
  </div>

  <!-- ── Summary box ── -->
  <div style="background:#141414;border-left:4px solid {s_color};border-radius:8px;
              padding:16px 20px;margin-bottom:20px;font-size:.95rem;line-height:1.7;color:#ccc">
    {analysis.get("summary","No summary available.")}
  </div>

  <!-- ── Stats row ── -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px;margin-bottom:20px">

    <div class="stat-card">
      <div class="stat-label">My Position</div>
      <div class="stat-val">{qty} {qty_key}</div>
      <div class="stat-sub">Avg cost: <b>{avg}</b></div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Current Price</div>
      <div class="stat-val">{curr}</div>
      <div class="stat-sub">52W: {_ef(w52l)} – {_ef(w52h)}</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Unrealised P&amp;L</div>
      <div class="stat-val" style="color:{pnl_color}">{pnl_str}</div>
      <div class="stat-sub" style="color:{pnl_color}">{pnl_pct_str}</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Analyst Consensus</div>
      <div class="stat-val" style="font-size:1.1rem">{ar}</div>
      <div class="stat-sub">Target: <b>{_ef(at)}</b> &nbsp;·&nbsp; {an} analysts</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Short Interest</div>
      <div class="stat-val" style="color:#ff8800">{_ef(sht,"","%",1) if sht else "—"}</div>
      <div class="stat-sub">of float</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Catalyst Score</div>
      <div class="stat-val" style="color:#00c851">{cat_score}<span style="font-size:.9rem;color:#555">/10</span></div>
      {_score_bar(cat_score, "#00c851")}
    </div>

    <div class="stat-card">
      <div class="stat-label">Risk Score</div>
      <div class="stat-val" style="color:#ff4444">{risk_score}<span style="font-size:.9rem;color:#555">/10</span></div>
      {_score_bar(risk_score, "#ff4444")}
    </div>

    <div class="stat-card">
      <div class="stat-label">Price Levels</div>
      <div class="stat-sub" style="line-height:2;margin-top:4px;font-size:.88rem">
        🛑 Stop loss: <b>{stop}</b><br>
        🟩 Support: <b>{supp}</b><br>
        🟥 Resistance: <b>{res}</b><br>
        🎯 Target: <b>{tgt}</b>
      </div>
    </div>
  </div>

  <!-- ── Earnings Play Card ── -->
  <div style="background:#0e1a0e;border:1px solid #1a3a1a;border-radius:12px;
              padding:18px 20px;margin-bottom:20px">
    <div style="font-size:.75rem;color:#00c851;text-transform:uppercase;letter-spacing:1px;
                font-weight:700;margin-bottom:12px">📅 Earnings Play</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px">
      <div>
        <div style="color:#666;font-size:.72rem;margin-bottom:3px">NEXT EARNINGS DATE</div>
        <div style="color:#fff;font-weight:700;font-size:1rem">{ep_date}</div>
      </div>
      <div>
        <div style="color:#666;font-size:.72rem;margin-bottom:3px">EXPECTED MOVE</div>
        <div style="color:#ffbb33;font-weight:700;font-size:1rem">{ep_move}</div>
      </div>
      <div>
        <div style="color:#666;font-size:.72rem;margin-bottom:3px">BEAT / MISS READ</div>
        <div style="color:#4da6ff;font-size:.88rem;line-height:1.4">{ep_beat}</div>
      </div>
      <div style="grid-column:1/-1">
        <div style="color:#666;font-size:.72rem;margin-bottom:3px">STRATEGY FOR THIS POSITION</div>
        <div style="color:#ccc;font-size:.9rem;line-height:1.5">{ep_strat}</div>
      </div>
    </div>
  </div>

  <!-- ── Position Impact ── -->
  <details open class="section-drop">
    <summary class="drop-title">📌 Position Impact Analysis</summary>
    <div class="drop-body">{analysis.get("position_impact","—")}</div>
  </details>

  <!-- ── Key Headlines (Analyzed) ── -->
  <details open class="section-drop">
    <summary class="drop-title">🧠 Key Headlines — Gemini Analysis</summary>
    <div class="drop-body" style="padding:0">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid #2a2a2a">
            <th style="padding:8px 6px;color:#555;font-size:.75rem;text-align:left;width:20px"></th>
            <th style="padding:8px 6px;color:#555;font-size:.75rem;text-align:left">Headline</th>
            <th style="padding:8px 6px;color:#555;font-size:.75rem;text-align:left;width:200px">Why it matters</th>
          </tr>
        </thead>
        <tbody>{kh_rows or '<tr><td colspan="3" style="padding:12px;color:#444">No headlines analyzed yet.</td></tr>'}</tbody>
      </table>
    </div>
  </details>

  <!-- ── Catalysts & Risks ── -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
    <details open class="section-drop">
      <summary class="drop-title">🚀 Upcoming Catalysts</summary>
      <div class="drop-body">
        <ul class="bullet-list">{cats or '<li style="color:#555">None identified</li>'}</ul>
      </div>
    </details>
    <details open class="section-drop">
      <summary class="drop-title">⚡ Key Risk Factors</summary>
      <div class="drop-body">
        <ul class="bullet-list">{risks or '<li style="color:#555">None identified</li>'}</ul>
      </div>
    </details>
  </div>

  <!-- ── Raw News Feed ── -->
  <details class="section-drop">
    <summary class="drop-title">📰 Raw News Feed ({len(news)} articles)</summary>
    <div class="drop-body" style="padding:0">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid #2a2a2a">
            <th style="padding:6px 8px;color:#555;font-size:.75rem;text-align:left;width:100px">Time</th>
            <th style="padding:6px 8px;color:#555;font-size:.75rem;text-align:left">Headline</th>
            <th style="padding:6px 8px;color:#555;font-size:.75rem;text-align:left;width:100px">Source</th>
          </tr>
        </thead>
        <tbody>{feed_rows or '<tr><td colspan="3" style="padding:12px;color:#444">No articles fetched.</td></tr>'}</tbody>
      </table>
    </div>
  </details>

</div>"""


def _render_ticker_report(ticker: str, analysis: dict, news: list[dict],
                           position: dict) -> str:
    sentiment = (analysis.get("overall_sentiment") or "neutral").lower()
    icon, color, bg = _SENTIMENT_ICON.get(sentiment, ("⚪", "#888888", "#1a1a1a"))
    act_key  = (analysis.get("suggested_action") or "hold").lower()
    act_icon, act_color = _ACTION_ICON.get(act_key, ("❓", "#aaaaaa"))
    cat_score = analysis.get("catalyst_score", "?")
    risk_score = analysis.get("risk_score", "?")
    ts = analysis.get("last_analyzed", datetime.now(timezone.utc).isoformat())

    headlines_html = ""
    for h in (analysis.get("key_headlines") or [])[:8]:
        imp = (h.get("impact") or "neutral").lower()
        imp_color = {"positive": "#00c851", "negative": "#ff4444"}.get(imp, "#aaaaaa")
        headlines_html += f"""
        <div class="headline-row">
          <span class="impact-dot" style="color:{imp_color}">●</span>
          <span class="headline-text">{h.get('headline','')}</span>
          <span class="headline-why">{h.get('why','')}</span>
        </div>"""

    catalysts_html = "".join(
        f"<li>{c}</li>" for c in (analysis.get("catalysts") or [])
    )
    risks_html = "".join(
        f"<li>{r}</li>" for r in (analysis.get("risks") or [])
    )

    raw_headlines_html = ""
    for item in news[:15]:
        url = item.get("url", "#")
        raw_headlines_html += (
            f'<div class="raw-headline">'
            f'<span class="raw-time">{item.get("time","")}</span> '
            f'<a href="{url}" target="_blank">{item.get("title","")}</a>'
            f' <span class="raw-source">[{item.get("source","")}]</span>'
            f'</div>'
        )

    qty_key = "shares" if not position.get("option_type") else "contracts"
    qty = position.get(qty_key) or position.get("quantity") or "—"
    avg = position.get("avg_buy_price") or position.get("avg_premium") or "—"
    curr = position.get("current_price") or "—"
    pnl  = position.get("total_return")
    pnl_pct = position.get("total_return_pct")
    pnl_color = "#00c851" if (pnl or 0) >= 0 else "#ff4444"
    pnl_str = f"${pnl:+,.2f}" if pnl is not None else "—"
    pnl_pct_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "—"

    pl_s = (analysis.get("price_levels") or {})
    support    = pl_s.get("support")    or "—"
    resistance = pl_s.get("resistance") or "—"
    target     = pl_s.get("target")     or "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>ATLAS — {ticker} Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d0d0d; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 20px; }}
  h1 {{ font-size: 2rem; color: #fff; }}
  .header {{ display: flex; align-items: center; gap: 16px; padding: 20px;
             background: {bg}; border: 2px solid {color}; border-radius: 12px; margin-bottom: 20px; }}
  .sentiment-badge {{ font-size: 2.5rem; }}
  .ticker-name {{ font-size: 2rem; font-weight: 700; color: {color}; }}
  .sub {{ color: #aaa; font-size: 0.85rem; margin-top: 4px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 20px; }}
  .card {{ background: #1a1a1a; border: 1px solid #333; border-radius: 10px; padding: 16px; }}
  .card h3 {{ color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
  .stat {{ font-size: 1.5rem; font-weight: 700; color: #fff; }}
  .stat.green {{ color: #00c851; }}
  .stat.red   {{ color: #ff4444; }}
  .pnl {{ color: {pnl_color}; font-size: 1.4rem; font-weight: 700; }}
  .action-box {{ background: #111; border: 2px solid {act_color}; border-radius: 10px;
                 padding: 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; }}
  .action-icon {{ font-size: 2rem; }}
  .action-text {{ font-size: 1.1rem; font-weight: 600; color: {act_color}; }}
  .action-reason {{ color: #aaa; font-size: 0.9rem; margin-top: 4px; }}
  .summary-box {{ background: #1a1a1a; border-left: 4px solid {color};
                  border-radius: 6px; padding: 16px; margin-bottom: 20px;
                  font-size: 0.95rem; line-height: 1.6; color: #ccc; }}
  .section {{ margin-bottom: 20px; }}
  .section h2 {{ font-size: 1rem; color: #888; text-transform: uppercase;
                 letter-spacing: 1px; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
  .headline-row {{ display: flex; align-items: flex-start; gap: 8px; padding: 6px 0;
                   border-bottom: 1px solid #1e1e1e; font-size: 0.88rem; }}
  .impact-dot {{ font-size: 1rem; flex-shrink: 0; margin-top: 2px; }}
  .headline-text {{ flex: 1; color: #ddd; }}
  .headline-why {{ color: #666; font-size: 0.78rem; flex-shrink: 0; max-width: 220px; text-align: right; }}
  .raw-headline {{ padding: 5px 0; border-bottom: 1px solid #1e1e1e; font-size: 0.82rem; }}
  .raw-headline a {{ color: #4da6ff; text-decoration: none; }}
  .raw-headline a:hover {{ text-decoration: underline; }}
  .raw-time {{ color: #555; margin-right: 6px; }}
  .raw-source {{ color: #555; font-size: 0.75rem; }}
  ul {{ padding-left: 18px; color: #bbb; line-height: 1.8; font-size: 0.9rem; }}
  .ts {{ color: #444; font-size: 0.75rem; margin-top: 20px; text-align: right; }}
  .score-badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px;
                  font-size: 0.8rem; font-weight: 600; margin-right: 8px; }}
  .score-cat {{ background: #003322; color: #00c851; }}
  .score-risk {{ background: #330000; color: #ff4444; }}
</style>
</head>
<body>
<div class="header">
  <span class="sentiment-badge">{icon}</span>
  <div>
    <div class="ticker-name">{ticker}</div>
    <div class="sub">
      {sentiment.upper()}
      <span class="score-badge score-cat">Catalyst {cat_score}/10</span>
      <span class="score-badge score-risk">Risk {risk_score}/10</span>
    </div>
  </div>
</div>

<div class="action-box">
  <span class="action-icon">{act_icon}</span>
  <div>
    <div class="action-text">{act_key.replace('_',' ').upper()}</div>
    <div class="action-reason">{analysis.get('action_reason','')}</div>
  </div>
</div>

<div class="summary-box">{analysis.get('summary','No summary available.')}</div>

<div class="grid">
  <div class="card">
    <h3>Position</h3>
    <div class="stat">{qty} {qty_key}</div>
    <div class="sub">Avg cost: {avg} | Current: {curr}</div>
  </div>
  <div class="card">
    <h3>P&amp;L</h3>
    <div class="pnl">{pnl_str} &nbsp; {pnl_pct_str}</div>
  </div>
  <div class="card">
    <h3>Price Levels</h3>
    <div class="sub" style="font-size:0.95rem;line-height:2">
      🟩 Support: {support}<br>
      🟥 Resistance: {resistance}<br>
      🎯 Target: {target}
    </div>
  </div>
</div>

<div class="section">
  <h2>Position Impact</h2>
  <div class="summary-box">{analysis.get('position_impact','—')}</div>
</div>

<div class="section">
  <h2>Key Headlines (Analyzed)</h2>
  {headlines_html or '<p style="color:#555">No headlines analyzed.</p>'}
</div>

<div class="grid">
  <div class="card section">
    <h3>Upcoming Catalysts</h3>
    <ul>{catalysts_html or '<li style="color:#555">None identified</li>'}</ul>
  </div>
  <div class="card section">
    <h3>Key Risks</h3>
    <ul>{risks_html or '<li style="color:#555">None identified</li>'}</ul>
  </div>
</div>

<div class="section">
  <h2>Raw Headlines (Source Feed)</h2>
  {raw_headlines_html or '<p style="color:#555">No headlines found.</p>'}
</div>

<div class="ts">Last analyzed: {ts} | Auto-refreshes every 60s</div>
</body>
</html>"""


def _render_live_reports(all_data: list[dict]) -> str:
    """
    Single-page master report — tabs per ticker + overview.
    all_data: list of {ticker, analysis, news, position}
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Sort: highest catalyst first, then alphabetically
    all_data = sorted(all_data,
                      key=lambda d: (-(d["analysis"].get("catalyst_score") or 0),
                                     d["ticker"]))

    # ── Tab buttons ─────────────────────────────────────────────
    tab_btns = '<button class="tab-btn active" onclick="showTab(\'overview\')" id="btn-overview">📊 Overview</button>\n'
    for d in all_data:
        t  = d["ticker"]
        a  = d["analysis"]
        sentiment = (a.get("overall_sentiment") or "neutral").lower()
        s_icon = _SENTIMENT_ICON.get(sentiment, ("⚪", "#888", "#111"))[0]
        tab_btns += f'<button class="tab-btn" onclick="showTab(\'{t}\')" id="btn-{t}">{s_icon} {t}</button>\n'

    # ── Overview cards ──────────────────────────────────────────
    overview_cards = ""
    for d in all_data:
        t   = d["ticker"]
        a   = d["analysis"]
        pos = d["position"]
        sentiment = (a.get("overall_sentiment") or "neutral").lower()
        s_icon, s_color, s_bg = _SENTIMENT_ICON.get(sentiment, ("⚪", "#888", "#1a1a1a"))
        act_key = (a.get("suggested_action") or "hold").lower()
        act_icon, act_color = _ACTION_ICON.get(act_key, ("❓", "#aaa"))
        cat  = a.get("catalyst_score", "?")
        risk = a.get("risk_score", "?")
        pnl  = pos.get("total_return")
        pnl_pct = pos.get("total_return_pct")
        pnl_color = "#00c851" if (pnl or 0) >= 0 else "#ff4444"
        pnl_str = f"${pnl:+,.2f}" if pnl is not None else "—"
        pnl_pct_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else ""
        overview_cards += f"""
        <div class="ov-card" style="border-color:{s_color};background:{s_bg}"
             onclick="showTab('{t}')" title="Click to open {t} full report">
          <div class="ov-header">
            <span style="font-size:1.8rem">{s_icon}</span>
            <span class="ov-ticker" style="color:{s_color}">{t}</span>
            <span class="ov-action" style="color:{act_color}">{act_icon} {act_key.replace("_"," ").upper()}</span>
          </div>
          <div class="ov-pnl" style="color:{pnl_color}">{pnl_str} &nbsp;<span style="font-size:.85rem">{pnl_pct_str}</span></div>
          <div class="ov-scores">
            <span class="badge cat">⚡ Catalyst {cat}/10</span>
            <span class="badge risk">🔥 Risk {risk}/10</span>
          </div>
          <p class="ov-summary">{a.get("summary","")[:160]}{"…" if len(a.get("summary",""))>160 else ""}</p>
          <div class="ov-link">Full Report →</div>
        </div>"""

    # ── Per-ticker detail sections ───────────────────────────────
    detail_sections = ""
    for d in all_data:
        detail_sections += _ticker_section_html(d["ticker"], d["analysis"], d["news"], d["position"])

    # ── Empty state ─────────────────────────────────────────────
    if not all_data:
        overview_cards = """
        <div style="grid-column:1/-1;text-align:center;padding:60px;color:#444">
          <div style="font-size:3rem;margin-bottom:16px">📭</div>
          <div style="font-size:1.1rem">No positions found yet.</div>
          <div style="font-size:.85rem;margin-top:8px">
            Open Robinhood with <code>python auto_bot.py --watch</code> running,<br>
            or add <code>RH_MANUAL_STOCKS</code> to your <code>.env</code> file.
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>ATLAS — LIVE Reports</title>
<style>
/* ── Reset & base ─────────────────────────────────────────── */
*  {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0a0a0a; color: #e0e0e0;
       font-family: 'Segoe UI', 'Inter', system-ui, sans-serif;
       min-height: 100vh; }}
a {{ color: #4da6ff; }}

/* ── Top bar ──────────────────────────────────────────────── */
.topbar {{ background: #0f0f0f; border-bottom: 1px solid #1e1e1e;
           padding: 14px 24px; display: flex; align-items: center; gap: 14px; }}
.logo {{ font-size: 1.3rem; font-weight: 800; color: #fff; letter-spacing: .5px; }}
.logo span {{ color: #4da6ff; }}
.topbar-ts {{ margin-left: auto; color: #444; font-size: .78rem; }}

/* ── Tab bar ──────────────────────────────────────────────── */
.tabbar {{ background: #0f0f0f; border-bottom: 1px solid #1e1e1e;
           padding: 0 24px; display: flex; gap: 4px; overflow-x: auto;
           scrollbar-width: thin; }}
.tab-btn {{ background: transparent; border: none; color: #666;
            padding: 12px 16px; cursor: pointer; font-size: .88rem;
            font-weight: 600; border-bottom: 3px solid transparent;
            white-space: nowrap; transition: color .15s, border-color .15s; }}
.tab-btn:hover  {{ color: #bbb; }}
.tab-btn.active {{ color: #fff; border-bottom-color: #4da6ff; }}

/* ── Main content area ────────────────────────────────────── */
.content {{ padding: 24px; max-width: 1400px; margin: 0 auto; }}

/* ── Overview grid ────────────────────────────────────────── */
.ov-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px,1fr)); gap: 16px; }}
.ov-card {{ border: 1px solid #333; border-radius: 14px; padding: 18px;
            display: flex; flex-direction: column; gap: 10px;
            cursor: pointer; transition: transform .15s, box-shadow .15s; }}
.ov-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.5); }}
.ov-header {{ display: flex; align-items: center; gap: 10px; }}
.ov-ticker {{ font-size: 1.6rem; font-weight: 800; flex: 1; }}
.ov-action {{ font-size: .78rem; font-weight: 700; }}
.ov-pnl  {{ font-size: 1.4rem; font-weight: 700; }}
.ov-scores {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.badge {{ display: inline-block; padding: 3px 12px; border-radius: 20px;
          font-size: .75rem; font-weight: 600; }}
.cat  {{ background: #003322; color: #00c851; }}
.risk {{ background: #330000; color: #ff4444; }}
.ov-summary {{ font-size: .83rem; color: #999; line-height: 1.5; flex: 1; }}
.ov-link {{ color: #4da6ff; font-size: .8rem; margin-top: auto; }}

/* ── Stat cards ───────────────────────────────────────────── */
.stat-card {{ background: #141414; border: 1px solid #222; border-radius: 10px; padding: 16px; }}
.stat-label {{ color: #666; font-size: .72rem; text-transform: uppercase;
               letter-spacing: 1px; margin-bottom: 6px; }}
.stat-val {{ font-size: 1.6rem; font-weight: 700; color: #fff; }}
.stat-sub {{ color: #888; font-size: .82rem; margin-top: 4px; }}

/* ── Dropdown sections ────────────────────────────────────── */
.section-drop {{ background: #111; border: 1px solid #222; border-radius: 10px;
                 margin-bottom: 14px; overflow: hidden; }}
.drop-title {{ padding: 14px 18px; cursor: pointer; font-size: .88rem;
               font-weight: 700; color: #ccc; list-style: none;
               display: flex; align-items: center; gap: 8px;
               user-select: none; }}
.drop-title::-webkit-details-marker {{ display: none; }}
.drop-title::after {{ content: "▸"; margin-left: auto; color: #444;
                      transition: transform .2s; }}
details[open] .drop-title::after {{ transform: rotate(90deg); }}
.drop-body {{ padding: 14px 18px; border-top: 1px solid #1e1e1e;
              color: #bbb; font-size: .9rem; line-height: 1.7; }}

/* ── Lists ────────────────────────────────────────────────── */
.bullet-list {{ padding-left: 18px; color: #bbb; line-height: 2; font-size: .9rem; }}
.bullet-list li {{ margin-bottom: 2px; }}

/* ── Tables ───────────────────────────────────────────────── */
table {{ font-size: .88rem; }}
tr:hover td {{ background: rgba(255,255,255,.02); }}

/* ── Ticker page (hidden by default) ─────────────────────── */
.ticker-page {{ display: none; }}
.overview-page {{ display: block; }}

/* ── Page title ───────────────────────────────────────────── */
.page-title {{ font-size: 1.1rem; font-weight: 700; color: #888;
               text-transform: uppercase; letter-spacing: 1px;
               margin-bottom: 18px; }}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">⚡ <span>ATLAS</span> LIVE Reports</div>
  <div style="color:#555;font-size:.85rem">Auto-refreshes every 60s</div>
  <div class="topbar-ts">Last scan: {now}</div>
</div>

<div class="tabbar">
  {tab_btns}
</div>

<div class="content">

  <!-- ── Overview tab ── -->
  <div class="overview-page" id="page-overview">
    <div class="page-title">All Positions — Overview</div>
    <div class="ov-grid">{overview_cards}</div>
  </div>

  <!-- ── Per-ticker tabs ── -->
  {detail_sections}

</div>

<script>
function showTab(id) {{
  // Hide all pages
  document.querySelectorAll('.ticker-page, .overview-page').forEach(el => {{
    el.style.display = 'none';
  }});
  // Remove active from all buttons
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  // Show selected page
  var page = document.getElementById('page-' + id);
  if (page) page.style.display = 'block';
  // Activate button
  var btn = document.getElementById('btn-' + id);
  if (btn) btn.classList.add('active');
  // Scroll tab button into view
  if (btn) btn.scrollIntoView({{ behavior: 'smooth', block: 'nearest', inline: 'center' }});
}}
</script>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Core scan logic
# ─────────────────────────────────────────────────────────────────────────────
def _load_positions() -> list[dict]:
    """
    Load all positions from positions_cache.json.
    """
    positions: list[dict] = []

    if POSITIONS_CACHE.exists():
        try:
            data = json.loads(POSITIONS_CACHE.read_text(encoding="utf-8"))
            for s in (data.get("stocks") or []):
                if s.get("ticker"):
                    positions.append(s)
            for o in (data.get("options") or []):
                if o.get("ticker"):
                    positions.append(o)
        except Exception:
            logging.debug("Could not read positions_cache.json.", exc_info=True)

    return positions


def _parse_analysis(raw_text: str, ticker: str) -> dict:
    """Parse Gemini response into a clean analysis dict."""
    import re
    analysis: dict = {}
    if raw_text:
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", clean)
            clean = re.sub(r"\s*```\s*$", "", clean).strip()
        try:
            analysis = json.loads(clean)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]+\}", clean)
            if m:
                try:
                    analysis = json.loads(m.group(0))
                except Exception:
                    pass
    if not analysis:
        analysis = {
            "ticker": ticker,
            "overall_sentiment": "neutral",
            "catalyst_score": 5,
            "risk_score": 5,
            "summary": f"Analysis unavailable for {ticker}.",
            "key_headlines": [],
            "position_impact": "—",
            "suggested_action": "watch",
            "action_reason": "Insufficient data.",
            "catalysts": [],
            "risks": [],
            "price_levels": {"support": None, "resistance": None, "target": None},
            "last_analyzed": datetime.now(timezone.utc).isoformat(),
        }
    return analysis


def scan_once(client) -> None:
    """Run one full news scan and write all reports."""
    REPORTS_DIR.mkdir(exist_ok=True)

    positions = _load_positions()
    if not positions:
        logging.warning("News scanner: no positions found in cache or .env. Nothing to scan.")
        _write_empty_reports()
        return

    tickers_seen = sorted({p["ticker"].upper() for p in positions if p.get("ticker")})
    logging.info("News scan started — tickers: %s", tickers_seen)

    all_data:     list[dict] = []   # {ticker, analysis, news, position}

    for i, ticker in enumerate(tickers_seen):
        if i > 0:
            time.sleep(3)   # avoid Gemini grounded-search 429 rate limits
        pos = next((p for p in positions if p.get("ticker", "").upper() == ticker), {})
        try:
            news, research_text, earnings = _gather_news(ticker, client)

            if client is None:
                logging.warning("  %s: Gemini unavailable — skipping analysis.", ticker)
                analysis = _parse_analysis("", ticker)
            else:
                prompt   = _build_analysis_prompt(ticker, pos, news, earnings, research_text)
                raw_text = _gemini_text(client, prompt)
                analysis = _parse_analysis(raw_text, ticker)
            # Attach earnings data so the HTML renderer can use it
            analysis["_earnings"] = earnings

            # Write individual ticker report (still works as standalone)
            report_html = _render_ticker_report(ticker, analysis, news, pos)
            report_path = REPORTS_DIR / f"{ticker}_report.html"
            report_path.write_text(report_html, encoding="utf-8")
            logging.info("  %s: report written → %s  [%s | action=%s]",
                         ticker, report_path.name,
                         analysis.get("overall_sentiment", "?"),
                         analysis.get("suggested_action", "?"))

            all_data.append({"ticker": ticker, "analysis": analysis,
                             "news": news, "position": pos})

            # Auto-learn: store key news facts in persistent memory
            try:
                import memory as _mem
                # Store news sentiment
                sentiment = analysis.get("overall_sentiment", "")
                if sentiment:
                    _mem.remember(
                        key="news_sentiment", ticker=ticker,
                        fact_type="sentiment",
                        value={"sentiment": sentiment,
                               "action": analysis.get("suggested_action",""),
                               "headline_count": len(news)},
                        confidence=2, sources=["news_scanner"]
                    )
                # Store top headlines
                if news:
                    _mem.remember(
                        key="recent_headlines", ticker=ticker,
                        fact_type="news",
                        value=[{"date": n.get("time",""), "title": n.get("title","")}
                               for n in news[:5]],
                        confidence=3, sources=["news_scanner"]
                    )
                # Store catalyst info if found
                catalysts = analysis.get("catalysts") or []
                if catalysts:
                    _mem.remember(
                        key="catalysts", ticker=ticker,
                        fact_type="earnings_upcoming",
                        value=catalysts[:3],
                        confidence=1, sources=["news_scanner_analysis"]
                    )
            except Exception:
                pass

        except Exception:
            logging.exception("  %s: scan failed.", ticker)

    # Write LIVE_REPORTS.html (main single-page app)
    live_html = _render_live_reports(all_data)
    LIVE_REPORTS.write_text(live_html, encoding="utf-8")
    logging.info("LIVE Reports written → %s", LIVE_REPORTS)


def _write_empty_reports() -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    LIVE_REPORTS.write_text(_render_live_reports([]), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Scan loop
# ─────────────────────────────────────────────────────────────────────────────
def scan_loop(interval_sec: int | None = None, once: bool = False) -> None:
    interval = interval_sec or SCAN_INTERVAL
    client   = _gemini_client()

    if client is None:
        logging.warning("News scanner: GOOGLE_API_KEY missing — "
                        "headlines will be fetched but NOT analyzed by Gemini.")

    logging.info("News scanner started. Interval: %d min.", interval // 60)

    while not _stop_event.is_set():
        try:
            scan_once(client)
        except Exception:
            logging.exception("News scan cycle failed.")

        if once:
            break

        next_scan = datetime.now().strftime("%H:%M:%S")
        logging.info("[NEWS HEARTBEAT] Next scan in %d min. Reports in: %s",
                     interval // 60, REPORTS_DIR)

        # Sleep in small chunks so we can honour _stop_event quickly
        for _ in range(interval * 2):
            if _stop_event.is_set():
                break
            time.sleep(0.5)

    logging.info("News scanner stopped.")


def start_background(interval_sec: int | None = None) -> threading.Thread:
    t = threading.Thread(
        target=scan_loop,
        kwargs={"interval_sec": interval_sec},
        name="NewsScanner",
        daemon=True,
    )
    t.start()
    return t


def stop() -> None:
    _stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="ATLAS News Scanner")
    ap.add_argument("--once",     action="store_true",  help="Scan once and exit")
    ap.add_argument("--interval", type=int, default=5,  help="Scan interval in minutes (default 5)")
    ap.add_argument("--verbose",  "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scan_loop(interval_sec=args.interval * 60, once=args.once)
