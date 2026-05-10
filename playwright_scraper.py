"""
playwright_scraper.py — Headless browser scraper for JavaScript-heavy sites.

Why Playwright:
  Some financial sites (Unusual Whales, Earnings Whispers, Barchart) render
  their data using JavaScript after the page loads. A normal requests+BeautifulSoup
  scraper only gets the HTML shell — the actual numbers never appear.
  Playwright launches a real headless Chromium browser, fully executes the JS,
  waits for data to render, then extracts it — exactly like a human using Chrome.

Sites unlocked by this module:
  - Unusual Whales   → full options flow, net flow chart, dark pool, IV data
  - Earnings Whispers → actual whisper EPS number, expected move, surprise history
  - Barchart         → IV rank/percentile, put/call ratio, options volume (critical for options plays)
  - Stocktwits       → live sentiment score, bull/bear ratio, message volume
  - Article scraper  → full text of non-paywalled news articles

Install:
  pip install playwright
  python -m playwright install chromium
"""

from __future__ import annotations

import logging
import re
import time
import concurrent.futures as _cf
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Playwright availability check
# ─────────────────────────────────────────────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PWTimeout
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False
    log.warning("playwright not installed. Run: pip install playwright && python -m playwright install chromium")


def _is_available() -> bool:
    return _PLAYWRIGHT_OK


# ─────────────────────────────────────────────────────────────────────────────
# Shared browser context — reuse one browser instance for all scrapes
# ─────────────────────────────────────────────────────────────────────────────
class HeadlessBrowser:
    """Context manager that launches one Chromium instance for multiple scrapes."""

    def __init__(self):
        self._pw    = None
        self._browser: Optional[Browser] = None

    def __enter__(self):
        if not _PLAYWRIGHT_OK:
            return self
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",  # hide bot fingerprint
                "--disable-dev-shm-usage",
            ]
        )
        return self

    def __exit__(self, *_):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def new_page(self) -> Optional[Page]:
        """Create a new browser tab with realistic headers to avoid bot detection."""
        if not self._browser:
            return None
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
        )
        # Add extra headers to look like a real browser
        ctx.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })
        return ctx.new_page()

    def get_text(self, url: str, wait_selector: str = "body",
                 wait_ms: int = 5000, extra_wait_ms: int = 2000) -> str:
        """
        Navigate to URL, wait for selector to appear, return full page text.
        wait_selector: CSS selector to wait for before extracting text
        extra_wait_ms: additional wait after selector found (for dynamic data)
        """
        page = self.new_page()
        if not page:
            return ""
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(wait_selector, timeout=wait_ms)
            if extra_wait_ms:
                page.wait_for_timeout(extra_wait_ms)
            text = page.inner_text("body")
            page.close()
            return text
        except Exception as e:
            log.debug("Playwright get_text failed [%s]: %s", url, e)
            try:
                page.close()
            except Exception:
                pass
            return ""


# ─────────────────────────────────────────────────────────────────────────────
# Unusual Whales — full options flow (JS-rendered)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_unusual_whales_full(ticker: str, browser: HeadlessBrowser) -> dict:
    """
    Scrape Unusual Whales stock page with full JavaScript execution.
    Returns options flow data: IV, IV rank, put/call, net flow, dark pool info.
    """
    result = {"source": "unusual_whales_js", "ticker": ticker.upper()}
    url = f"https://unusualwhales.com/stock/{ticker.upper()}"

    log.info("  [playwright] Unusual Whales: %s...", ticker)
    text = browser.get_text(
        url,
        wait_selector="body",
        wait_ms=8000,
        extra_wait_ms=3000
    )
    if not text:
        return result

    result["raw_text"] = text[:3000]

    # Extract key options metrics
    patterns = {
        "iv_rank":          r"IV\s*Rank[:\s]*([\d.]+)",
        "iv_percentile":    r"IV\s*Percentile[:\s]*([\d.]+%?)",
        "implied_volatility": r"Implied\s*Volatility[:\s]*([\d.]+%?)",
        "put_call_ratio":   r"Put[/\s]*Call\s*Ratio[:\s]*([\d.]+)",
        "call_premium":     r"Call\s*Premium[:\s]*\$?([\d.,KMB]+)",
        "put_premium":      r"Put\s*Premium[:\s]*\$?([\d.,KMB]+)",
        "net_call_premium": r"Net\s*(?:Call\s*)?Premium[:\s]*\$?([\d.,KMB]+)",
        "avg_30d_call_vol": r"30[dD]?\s*Avg\s*Call[:\s]*([\d.,K]+)",
        "avg_30d_put_vol":  r"30[dD]?\s*Avg\s*Put[:\s]*([\d.,K]+)",
        "oi_pcr":           r"OI\s*P[/\s]*C[:\s]*([\d.]+)",
        "bullish_bearish":  r"(Bullish|Bearish|Neutral)\s*Flow",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.I)
        if m:
            result[key] = m.group(1).strip()

    # Dark pool
    dp_match = re.search(r"dark\s*pool[^\n]*?(\$[\d.,KMB]+|[\d.]+%)", text, re.I)
    if dp_match and len(dp_match.group(1)) > 1:
        result["dark_pool"] = dp_match.group(1)

    # Expected move
    em_match = re.search(r"expected\s*move[:\s]*[+±]?\$?([\d.]+%?)", text, re.I)
    if em_match:
        result["expected_move"] = em_match.group(1)

    # Most active strikes
    strikes = re.findall(r"\$(\d+(?:\.\d+)?)\s*(?:C|Call|P|Put)", text)
    if strikes:
        result["active_strikes"] = list(dict.fromkeys(strikes))[:6]

    log.info("  [unusual_whales_js] %s — IV_rank=%s  P/C=%s  sentiment=%s",
             ticker, result.get("iv_rank","?"),
             result.get("put_call_ratio","?"),
             result.get("bullish_bearish","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Earnings Whispers — whisper number (JS-rendered)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_earnings_whispers_full(ticker: str, browser: "HeadlessBrowser" = None) -> dict:
    """
    Scrape EarningsWhispers.com — whisper EPS number, consensus, expected move.

    UPGRADED: Uses precise CSS element selectors instead of full-page regex.
    The whisper number is the UNOFFICIAL EPS estimate traders actually expect.
    Beating the whisper = rally. Missing it = dump even on a "beat".

    EarningsWhispers DOM structure (as of 2025-2026):
      #mainvalue / .mainvalue   — the big Whisper number displayed center-page
      #consensus / .consensus   — Wall St consensus EPS
      #epsgraph / .eps-table    — historical EPS beat/miss chart
      .expectedmove             — options-implied expected move %
    """
    url = f"https://www.earningswhispers.com/stocks/{ticker.lower()}"
    log.info("  [playwright] Earnings Whispers: %s...", ticker)

    if not _PLAYWRIGHT_OK:
        log.warning("  playwright not installed — skipping EarningsWhispers")
        return {"source": "earnings_whispers_js", "ticker": ticker.upper()}

    def _run_sync() -> dict:
        """Run sync playwright in a thread to avoid asyncio conflict."""
        result = {"source": "earnings_whispers_js", "ticker": ticker.upper()}
        with sync_playwright() as pw:
            brow = pw.chromium.launch(headless=True)
            ctx  = brow.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.goto(url, timeout=20000, wait_until="domcontentloaded")

            # Wait for the primary whisper value element to appear
            # Try multiple possible selectors — the site redesigns occasionally
            whisper_selectors = [
                "#mainvalue",
                ".mainvalue",
                "#epswhisper",
                ".whisper-number",
                "[class*='whisper'][class*='value']",
                "[id*='whisper']",
            ]
            whisper_val = None
            for sel in whisper_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=3000):
                        raw = el.inner_text().strip()
                        # Extract number from text like "$0.42" or "-0.05"
                        m = re.search(r"-?\$?([\d]+\.[\d]{1,4})", raw)
                        if m:
                            whisper_val = m.group(1)
                            log.info("  [ew] whisper found via selector '%s': %s", sel, whisper_val)
                            break
                except Exception:
                    continue

            # Consensus EPS
            consensus_val = None
            consensus_selectors = [
                "#consensus", ".consensus",
                "#wallst", ".wallst-estimate",
                "[id*='consensus']", "[class*='consensus']",
            ]
            for sel in consensus_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        raw = el.inner_text().strip()
                        m = re.search(r"-?\$?([\d]+\.[\d]{1,4})", raw)
                        if m:
                            consensus_val = m.group(1)
                            break
                except Exception:
                    continue

            # Expected move (from options market)
            expected_move = None
            move_selectors = [
                ".expectedmove", "#expectedmove",
                "[class*='expected']", "[class*='move']",
            ]
            for sel in move_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        raw = el.inner_text()
                        m = re.search(r"([\d.]+)\s*%", raw)
                        if m:
                            expected_move = m.group(1)
                            break
                except Exception:
                    continue

            # Earnings date — try structured element first
            earnings_date = None
            date_selectors = [
                "#reportdate", ".reportdate", ".earnings-date",
                "[class*='date'][class*='report']",
            ]
            for sel in date_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        earnings_date = el.inner_text().strip()[:30]
                        break
                except Exception:
                    continue

            # Revenue estimate
            revenue_est = None
            rev_selectors = [
                "#revest", ".revest", ".revenue-estimate",
                "[id*='revenue']", "[class*='revenue']",
            ]
            for sel in rev_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=2000):
                        raw = el.inner_text()
                        m = re.search(r"\$?([\d.]+\s*[BMK]?)", raw)
                        if m:
                            revenue_est = m.group(1)
                            break
                except Exception:
                    continue

            # Beat history from EPS table rows
            beat_count = 0
            miss_count = 0
            try:
                rows = page.locator(".eps-table tr, #epsgraph tr, [class*='eps'] tr").all()
                for row in rows[:12]:
                    row_text = row.inner_text().lower()
                    if "beat" in row_text:   beat_count += 1
                    elif "miss" in row_text: miss_count += 1
            except Exception:
                pass

            # FALLBACK: if element selectors found nothing, grab all page text
            # and use improved regex as a last resort
            page_text = ""
            if not whisper_val:
                try:
                    page_text = page.inner_text("body")
                    result["raw_text"] = page_text[:3000]
                    # Try regex on full text as fallback
                    fallback_pats = [
                        r"[Ww]hisper[^\n]{0,30}?(-?(?:\$?)(0\.\d{2,4}|\d{1,3}\.\d{1,4}))",
                        r"Estimated\s+EPS[:\s$]*(-?[\d]+\.[\d]{1,4})",
                        r"EPS\s+Whisper[:\s$]*(-?[\d]+\.[\d]{1,4})",
                    ]
                    for pat in fallback_pats:
                        m = re.search(pat, page_text, re.I)
                        if m:
                            candidate = m.group(1).replace("$","")
                            if re.fullmatch(r"-?[\d]+\.[\d]+", candidate):
                                whisper_val = candidate
                                log.info("  [ew] whisper via regex fallback: %s", whisper_val)
                                break
                except Exception:
                    pass

            # Earnings time (BMO / AMC)
            earnings_time = None
            if page_text:
                time_m = re.search(
                    r"\b(before\s+(?:the\s+)?(?:open|market)|after\s+(?:the\s+)?(?:close|hours?)|BMO|AMC|pre.?market)\b",
                    page_text, re.I
                )
                if time_m:
                    earnings_time = time_m.group(0)

            brow.close()

        # Assemble result
        if whisper_val:   result["whisper_eps"]       = whisper_val
        if consensus_val: result["consensus_eps"]     = consensus_val
        if expected_move: result["expected_move_pct"] = expected_move
        if earnings_date: result["earnings_date"]     = earnings_date
        if revenue_est:   result["revenue_estimate"]  = revenue_est
        if earnings_time: result["earnings_time"]     = earnings_time
        if beat_count + miss_count > 0:
            result["beat_count"] = beat_count
            result["miss_count"] = miss_count
            result["beat_rate"]  = f"{beat_count/(beat_count+miss_count)*100:.0f}%"
        return result

    try:
        with _cf.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_sync)
            result = future.result(timeout=30)
    except _cf.TimeoutError:
        log.warning("[earnings_whispers_js] Timed out for %s", ticker)
        result = {"source": "earnings_whispers_js", "ticker": ticker.upper()}
    except Exception as e:
        log.warning("[earnings_whispers_js] scrape failed for %s: %s", ticker, e)
        result = {"source": "earnings_whispers_js", "ticker": ticker.upper()}

    log.info("  [earnings_whispers_js] %s — date=%s  whisper=%s  consensus=%s  move=%s",
             ticker,
             result.get("earnings_date","?"),
             result.get("whisper_eps","?"),
             result.get("consensus_eps","?"),
             result.get("expected_move_pct","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Barchart — IV Rank, IV Percentile, Options Volume, Put/Call ratio
# THIS IS CRITICAL for options plays — IV rank tells you if options are cheap or expensive
# ─────────────────────────────────────────────────────────────────────────────
def scrape_barchart_options(ticker: str, browser: HeadlessBrowser) -> dict:
    """
    Scrape Barchart.com for options volatility metrics.

    IV Rank (IVR): 0-100. 
      - Below 20 = options are CHEAP → good time to buy options
      - Above 80 = options are EXPENSIVE → IV crush risk after earnings
    
    This single number determines whether buying options is smart right now.
    ChatGPT Deep Research cannot get this. We can.
    """
    result = {"source": "barchart", "ticker": ticker.upper()}
    url = f"https://www.barchart.com/stocks/quotes/{ticker.upper()}/volatility-greeks"

    log.info("  [playwright] Barchart options: %s...", ticker)
    text = browser.get_text(
        url,
        wait_selector="body",
        wait_ms=8000,
        extra_wait_ms=2000
    )
    if not text:
        # Try the overview page instead
        url2 = f"https://www.barchart.com/stocks/quotes/{ticker.upper()}/overview"
        text = browser.get_text(url2, wait_ms=6000, extra_wait_ms=2000)
    if not text:
        return result

    result["raw_text"] = text[:2000]

    patterns = {
        "iv_rank":           r"IV\s*Rank[:\s]*([\d.]+)",
        "iv_percentile":     r"IV\s*Percentile[:\s]*([\d.]+)",
        "iv_30d":            r"(?:Historical|30[- ]Day)\s*(?:Implied\s*)?Volatility[:\s]*([\d.]+%?)",
        "put_call_vol_ratio":r"(?:Volume\s*)?Put[/\s]*Call(?:\s*Volume)?\s*Ratio[:\s]*([\d.]+)",
        "put_call_oi_ratio": r"(?:OI|Open\s*Interest)\s*Put[/\s]*Call[:\s]*([\d.]+)",
        "call_volume":       r"Call\s*Volume[:\s]*([\d,]+)",
        "put_volume":        r"Put\s*Volume[:\s]*([\d,]+)",
        "implied_move":      r"[Ii]mplied\s*[Mm]ove[:\s]*[±]?\s*([\d.]+%?)",
    }

    for key, pat in patterns.items():
        m = re.search(pat, text, re.I)
        if m:
            result[key] = m.group(1).strip()

    # Interpret IV rank
    if result.get("iv_rank"):
        try:
            ivr = float(result["iv_rank"])
            if ivr < 20:
                result["iv_rank_interpretation"] = "LOW — options are CHEAP, good time to buy"
            elif ivr < 50:
                result["iv_rank_interpretation"] = "MODERATE — options fairly priced"
            elif ivr < 80:
                result["iv_rank_interpretation"] = "HIGH — options expensive, IV crush risk"
            else:
                result["iv_rank_interpretation"] = "EXTREME — options very expensive, high crush risk"
        except Exception:
            pass

    log.info("  [barchart] %s — IV_rank=%s (%s)  P/C_vol=%s",
             ticker,
             result.get("iv_rank","?"),
             result.get("iv_rank_interpretation","?"),
             result.get("put_call_vol_ratio","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Barchart Historical IV — Is volatility expanding or contracting?
# This shows the IV TREND, not just the snapshot — critical for timing options
# ─────────────────────────────────────────────────────────────────────────────
def scrape_barchart_historical_iv(ticker: str, browser: HeadlessBrowser) -> dict:
    """
    Scrape Barchart for historical implied volatility trend data.

    Current IV rank tells you WHERE you are. Historical IV tells you WHERE you've been.
    If IV is at 45 but was at 90 last month → IV is contracting → buying options risky
    If IV is at 45 but was at 10 last month → IV is expanding → momentum in play

    Data points: 30-day, 60-day, 90-day, 6-month historical IV + current IV vs 52w range
    """
    result = {"source": "barchart_hist_iv", "ticker": ticker.upper()}
    url = f"https://www.barchart.com/stocks/quotes/{ticker.upper()}/volatility-greeks"

    log.info("  [playwright] Barchart Historical IV: %s...", ticker)
    text = browser.get_text(url, wait_selector="body", wait_ms=8000, extra_wait_ms=3000)
    if not text:
        return result

    result["raw_text"] = text[:2500]

    # Historical IV at different periods
    hist_patterns = {
        "hv_30d":   r"(?:30[- ]?day|1[- ]?month)\s*(?:hist(?:orical)?|HV)[^\n]*?([\d.]+%?)",
        "hv_60d":   r"(?:60[- ]?day|2[- ]?month)\s*(?:hist(?:orical)?|HV)[^\n]*?([\d.]+%?)",
        "hv_90d":   r"(?:90[- ]?day|3[- ]?month)\s*(?:hist(?:orical)?|HV)[^\n]*?([\d.]+%?)",
        "hv_180d":  r"(?:180[- ]?day|6[- ]?month)\s*(?:hist(?:orical)?|HV)[^\n]*?([\d.]+%?)",
        "iv_30d":   r"(?:30[- ]?day|1[- ]?month)\s*(?:impl(?:ied)?|IV)[^\n]*?([\d.]+%?)",
        "iv_52w_hi":r"52[- ]?(?:week|wk)\s*(?:high|hi)\s*(?:IV)?[:\s]*([\d.]+%?)",
        "iv_52w_lo":r"52[- ]?(?:week|wk)\s*(?:low|lo)\s*(?:IV)?[:\s]*([\d.]+%?)",
    }

    for key, pat in hist_patterns.items():
        m = re.search(pat, text, re.I)
        if m:
            result[key] = m.group(1).strip()

    # Also get the IV percentile (different from rank — based on distribution)
    ivp_m = re.search(r"IV\s*Percentile[:\s]*([\d.]+)", text, re.I)
    if ivp_m:
        result["iv_percentile"] = ivp_m.group(1)

    # Trend analysis — compare current IV to historical
    iv_rank_m = re.search(r"IV\s*Rank[:\s]*([\d.]+)", text, re.I)
    if iv_rank_m:
        result["iv_rank_current"] = iv_rank_m.group(1)
        try:
            ivr = float(iv_rank_m.group(1))
            # Is IV expanding or contracting based on rank vs historical patterns
            if ivr > 70:
                result["iv_trend_signal"] = "ELEVATED — IV at high point relative to year. Sell premium or expect crush post-event."
            elif ivr < 20:
                result["iv_trend_signal"] = "DEPRESSED — IV at low point. Options cheap. Good time to buy calls/puts."
            else:
                result["iv_trend_signal"] = "NEUTRAL — IV in middle of 52-week range."
        except Exception:
            pass

    log.info("  [barchart_hist_iv] %s — IV_rank=%s  HV30=%s  HV90=%s  trend: %s",
             ticker,
             result.get("iv_rank_current","?"),
             result.get("hv_30d","?"),
             result.get("hv_90d","?"),
             result.get("iv_trend_signal","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stocktwits — live retail sentiment score
# ─────────────────────────────────────────────────────────────────────────────
def scrape_stocktwits(ticker: str, browser: HeadlessBrowser) -> dict:
    """
    Scrape Stocktwits for live retail sentiment: bull%, bear%, message volume.
    Stocktwits is where retail traders post in real-time — high signal for momentum stocks.
    """
    result = {"source": "stocktwits", "ticker": ticker.upper()}
    url = f"https://stocktwits.com/symbol/{ticker.upper()}"

    log.info("  [playwright] Stocktwits: %s...", ticker)
    text = browser.get_text(
        url,
        wait_selector="body",
        wait_ms=8000,
        extra_wait_ms=2000
    )
    if not text:
        return result

    # Bull/bear sentiment percentages
    bull_m = re.search(r"Bullish[:\s]*([\d.]+)%", text, re.I)
    bear_m = re.search(r"Bearish[:\s]*([\d.]+)%", text, re.I)
    if bull_m:
        result["bullish_pct"] = bull_m.group(1)
    if bear_m:
        result["bearish_pct"] = bear_m.group(1)

    # Watchers / followers
    watch_m = re.search(r"([\d,KM]+)\s*[Ww]atchers?", text)
    if watch_m:
        result["watchers"] = watch_m.group(1)

    # Message volume / trending
    if re.search(r"trending|hot|popular", text, re.I):
        result["trending"] = True

    # Price mentioned
    price_m = re.search(r"\$([\d.]+)", text)
    if price_m:
        result["price_mentioned"] = price_m.group(1)

    # Recent message snippets (first 3 messages)
    messages = re.findall(r'"body"[:\s]*"([^"]{20,200})"', text)
    if not messages:
        # Try to find message-like text
        lines = [l.strip() for l in text.split("\n") if 20 < len(l.strip()) < 200]
        messages = lines[:3]
    result["sample_messages"] = messages[:3]

    log.info("  [stocktwits] %s — bull=%s%%  bear=%s%%  trending=%s",
             ticker,
             result.get("bullish_pct","?"),
             result.get("bearish_pct","?"),
             result.get("trending", False))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Article full-text scraper — get real content from news URLs
# ─────────────────────────────────────────────────────────────────────────────
def scrape_article_text(url: str, browser: HeadlessBrowser, max_chars: int = 2500) -> str:
    """
    Scrape full article text from a news URL (non-paywalled).
    Uses targeted CSS selectors to find the article body — not all page text.
    Skips paywalled content gracefully.
    """
    SKIP_DOMAINS = [
        "wsj.com", "ft.com", "bloomberg.com", "barrons.com",
        "seekingalpha.com", "thestreet.com",
    ]
    if any(domain in url for domain in SKIP_DOMAINS):
        return ""

    # CSS selectors for article body — tried in order, first match wins
    ARTICLE_SELECTORS = [
        "article",
        "[class*='article-body']",
        "[class*='articleBody']",
        "[class*='post-body']",
        "[class*='story-body']",
        "[class*='story-content']",
        "[class*='content-body']",
        "[class*='entry-content']",
        "[itemprop='articleBody']",
        "main article",
        "main .content",
        "main",
    ]

    log.debug("  [article] Scraping: %s", url[:80])

    page = browser.new_page()
    if not page:
        return ""

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=18000)
        page.wait_for_timeout(2500)

        # Try each selector until we get meaningful text
        text = ""
        for selector in ARTICLE_SELECTORS:
            try:
                el = page.query_selector(selector)
                if el:
                    candidate = el.inner_text()
                    if len(candidate.strip()) > 200:
                        text = candidate
                        break
            except Exception:
                continue

        # Fallback: full page text
        if not text:
            text = page.inner_text("body")

        page.close()
    except Exception as e:
        log.debug("  [article] Failed: %s — %s", url[:60], e)
        try:
            page.close()
        except Exception:
            pass
        return ""

    # Clean the text
    lines = text.split("\n")
    body_lines = []
    skip_patterns = re.compile(
        r"^(Home|Menu|Subscribe|Sign\s*[Ii]n|Log\s*[Ii]n|Cookie|Privacy|Copyright|"
        r"Advertisement|Share\s*this|Related\s*Articles?|Newsletter|Follow\s*us|"
        r"Read\s*More|Comments?\s*\(\d+\)|Skip\s*to|Jump\s*to)",
        re.I
    )
    for line in lines:
        line = line.strip()
        if len(line) < 35:
            continue
        if skip_patterns.match(line):
            continue
        body_lines.append(line)

    body = " ".join(body_lines)[:max_chars]
    return body


# ─────────────────────────────────────────────────────────────────────────────
# Master function — run all JS scrapers for one ticker
# ─────────────────────────────────────────────────────────────────────────────
def scrape_all_js(ticker: str, scrape_articles: bool = False,
                  article_urls: list[str] | None = None) -> dict:
    """
    Run all Playwright scrapers for a ticker using one shared browser instance.
    Falls back gracefully if Playwright is not installed.

    Returns dict with keys:
      unusual_whales_js, earnings_whispers_js, barchart, stocktwits,
      article_texts, context_text (pre-formatted for AI)
    """
    if not _PLAYWRIGHT_OK:
        log.warning("Playwright not available — skipping JS scraping. "
                    "Run: pip install playwright && python -m playwright install chromium")
        return {"available": False, "ticker": ticker.upper()}

    ticker = ticker.upper().strip()
    log.info("=== Playwright JS scraping: %s ===", ticker)

    results: dict = {"available": True, "ticker": ticker}

    with HeadlessBrowser() as browser:
        # Unusual Whales — options flow
        results["unusual_whales_js"] = scrape_unusual_whales_full(ticker, browser)
        time.sleep(2)

        # Earnings Whispers — whisper number
        results["earnings_whispers_js"] = scrape_earnings_whispers_full(ticker, browser)
        time.sleep(2)

        # Barchart — IV rank + historical IV trend
        results["barchart"]     = scrape_barchart_options(ticker, browser)
        time.sleep(1)
        results["barchart_hist_iv"] = scrape_barchart_historical_iv(ticker, browser)
        time.sleep(2)

        # Stocktwits — retail sentiment
        results["stocktwits"] = scrape_stocktwits(ticker, browser)
        time.sleep(1)

        # Article full-text (optional — for top headlines)
        article_texts: list[dict] = []
        if scrape_articles and article_urls:
            for url in article_urls[:4]:  # limit to 4 articles
                text = scrape_article_text(url, browser)
                if text:
                    article_texts.append({"url": url, "text": text})
                time.sleep(1)
        results["article_texts"] = article_texts

    # Build context text for AI
    lines: list[str] = []

    uw   = results.get("unusual_whales_js", {})
    ew   = results.get("earnings_whispers_js", {})
    bc   = results.get("barchart", {})
    bchi = results.get("barchart_hist_iv", {})
    st   = results.get("stocktwits", {})

    # Barchart IV data — leads the section since it's critical for options decisions
    if bc.get("iv_rank") or bc.get("iv_percentile"):
        lines.append(f"\n=== BARCHART OPTIONS VOLATILITY ===")
        if bc.get("iv_rank"):
            lines.append(f"IV Rank: {bc['iv_rank']} — {bc.get('iv_rank_interpretation','')}")
        if bc.get("iv_percentile"):
            lines.append(f"IV Percentile: {bc['iv_percentile']}")
        if bc.get("iv_30d"):
            lines.append(f"30-Day Historical Vol: {bc['iv_30d']}")
        if bc.get("put_call_vol_ratio"):
            lines.append(f"Put/Call Volume Ratio: {bc['put_call_vol_ratio']}")
        if bc.get("put_call_oi_ratio"):
            lines.append(f"Put/Call OI Ratio: {bc['put_call_oi_ratio']}")
        if bc.get("call_volume") and bc.get("put_volume"):
            lines.append(f"Call Volume: {bc['call_volume']}  Put Volume: {bc['put_volume']}")
        if bc.get("implied_move"):
            lines.append(f"Implied Earnings Move: {bc['implied_move']}")

    # Historical IV trend — is IV expanding or contracting?
    if bchi.get("iv_rank_current") or bchi.get("hv_30d") or bchi.get("hv_90d"):
        lines.append(f"\n=== BARCHART HISTORICAL IV TREND ===")
        if bchi.get("iv_trend_signal"):
            lines.append(f"IV Trend Signal: {bchi['iv_trend_signal']}")
        if bchi.get("iv_rank_current"):
            lines.append(f"Current IV Rank: {bchi['iv_rank_current']}")
        if bchi.get("iv_percentile"):
            lines.append(f"IV Percentile: {bchi['iv_percentile']}")
        if bchi.get("iv_52w_hi") and bchi.get("iv_52w_lo"):
            lines.append(f"52-Week IV Range: {bchi['iv_52w_lo']} — {bchi['iv_52w_hi']}")
        for lbl, key in [("30-Day HV", "hv_30d"), ("60-Day HV", "hv_60d"),
                          ("90-Day HV", "hv_90d"), ("180-Day HV", "hv_180d")]:
            if bchi.get(key):
                lines.append(f"{lbl}: {bchi[key]}")

    # Unusual Whales — options flow
    if uw.get("iv_rank") or uw.get("bullish_bearish") or uw.get("put_call_ratio"):
        lines.append(f"\n=== UNUSUAL WHALES OPTIONS FLOW (JS) ===")
        if uw.get("bullish_bearish"):
            lines.append(f"Net Flow Sentiment: {uw['bullish_bearish'].upper()}")
        if uw.get("iv_rank"):
            lines.append(f"IV Rank: {uw['iv_rank']}")
        if uw.get("iv_percentile"):
            lines.append(f"IV Percentile: {uw['iv_percentile']}")
        if uw.get("implied_volatility"):
            lines.append(f"Implied Volatility: {uw['implied_volatility']}")
        if uw.get("put_call_ratio"):
            lines.append(f"Put/Call Ratio: {uw['put_call_ratio']}")
        if uw.get("call_premium") and uw.get("put_premium"):
            lines.append(f"Call Premium: ${uw['call_premium']}  Put Premium: ${uw['put_premium']}")
        if uw.get("active_strikes"):
            lines.append(f"Most Active Strikes: {', '.join(uw['active_strikes'])}")
        if uw.get("expected_move"):
            lines.append(f"Expected Move: {uw['expected_move']}")
        if uw.get("dark_pool"):
            lines.append(f"Dark Pool Activity: {uw['dark_pool']}")

    # Earnings Whispers — the whisper number
    if ew.get("whisper_eps") or ew.get("earnings_date"):
        lines.append(f"\n=== EARNINGS WHISPERS (JS — TRADER EXPECTATIONS) ===")
        if ew.get("earnings_date"):
            lines.append(f"Earnings Date: {ew['earnings_date']}")
        if ew.get("earnings_time"):
            lines.append(f"Time: {ew['earnings_time']}")
        if ew.get("consensus_eps"):
            lines.append(f"Wall St Consensus EPS: {ew['consensus_eps']}")
        if ew.get("whisper_eps"):
            lines.append(f"WHISPER NUMBER (trader real expectation): {ew['whisper_eps']}")
            if ew.get("consensus_eps"):
                try:
                    diff = float(ew["whisper_eps"]) - float(ew["consensus_eps"])
                    direction = "ABOVE" if diff > 0 else "BELOW"
                    lines.append(
                        f"  => Whisper is {direction} consensus by {abs(diff):.3f} EPS "
                        f"({'bullish signal — market expects beat' if diff > 0 else 'bearish — market skeptical'})"
                    )
                except Exception:
                    pass
        if ew.get("revenue_estimate"):
            lines.append(f"Revenue Estimate: {ew['revenue_estimate']}")
        if ew.get("expected_move_pct"):
            lines.append(f"Expected Earnings Move: ±{ew['expected_move_pct']}%")
        if ew.get("beat_rate"):
            lines.append(
                f"Historical Beat Rate: {ew['beat_rate']} "
                f"({ew.get('beat_count',0)} beats / {ew.get('miss_count',0)} misses)"
            )

    # Stocktwits retail sentiment
    if st.get("bullish_pct") or st.get("bearish_pct"):
        lines.append(f"\n=== STOCKTWITS RETAIL SENTIMENT ===")
        if st.get("bullish_pct"):
            lines.append(f"Bullish: {st['bullish_pct']}%")
        if st.get("bearish_pct"):
            lines.append(f"Bearish: {st['bearish_pct']}%")
        if st.get("watchers"):
            lines.append(f"Watchers: {st['watchers']}")
        if st.get("trending"):
            lines.append(f"Status: TRENDING on Stocktwits")
        if st.get("sample_messages"):
            lines.append("Sample trader comments:")
            for msg in st["sample_messages"]:
                lines.append(f"  - {msg[:120]}")

    # Article full texts
    if article_texts:
        lines.append(f"\n=== FULL ARTICLE CONTENT ({len(article_texts)} articles) ===")
        for art in article_texts:
            lines.append(f"Source: {art['url']}")
            lines.append(art["text"][:800])
            lines.append("---")

    results["context_text"] = "\n".join(lines)
    results["char_count"]   = len(results["context_text"])

    log.info("=== JS scraping complete: %s — %d chars ===",
             ticker, results["char_count"])
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    if not _PLAYWRIGHT_OK:
        print("ERROR: Playwright not installed.")
        print("Run:  pip install playwright")
        print("Then: python -m playwright install chromium")
        sys.exit(1)

    t = sys.argv[1] if len(sys.argv) > 1 else "SOUN"
    result = scrape_all_js(t)
    print("\n" + "="*70)
    print(f"JS SCRAPED DATA FOR {t}")
    print("="*70)
    print(result.get("context_text","(no data)"))
    print(f"\nTotal: {result.get('char_count',0)} chars")
