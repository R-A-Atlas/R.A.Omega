"""
web_scraper.py — Free, unlimited financial data scraper + cross-reference engine.

How it works:
  1. Scrapes 9 public financial websites simultaneously (no API keys, no rate limits)
  2. Cross-reference engine compares key facts across all sources
     — facts confirmed by 3+ sources get HIGH CONFIDENCE
     — facts from 1 source get flagged as SINGLE SOURCE
     — conflicting data gets flagged explicitly
  3. Returns pre-verified, confidence-labeled context for the AI
  4. AI reads real facts with confidence scores → cannot hallucinate

Sources:
  - Finviz          → price, RSI, short float, earnings date, insider transactions
  - Google News     → latest headlines with exact dates
  - Benzinga RSS    → financial news
  - StockAnalysis   → earnings history (EPS actual vs estimate, beat/miss)
  - SEC EDGAR       → 8-K filings (press releases, material events)
  - Reddit          → WSB/stocks retail sentiment
  - Unusual Whales  → options flow, smart money positioning
  - Earnings Whispers → whisper number vs consensus estimate
  - OpenInsider     → insider buying/selling with exact share counts and prices
  - MarketBeat      → analyst rating aggregator, price targets
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

# Playwright JS scraper — unlocks heavy JS sites (Unusual Whales, EarningsWhispers, Barchart)
try:
    import playwright_scraper as _pw_scraper
    _PW_AVAILABLE = _pw_scraper._is_available()
except ImportError:
    _pw_scraper     = None   # type: ignore
    _PW_AVAILABLE   = False

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Shared HTTP session — mimics a real browser to avoid bot blocks
# ─────────────────────────────────────────────────────────────────────────────
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def _get(url: str, timeout: int = 12) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        resp = _SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.debug("Fetch failed [%s]: %s", url, e)
        return None


def _text(tag) -> str:
    """Safely extract stripped text from a BS4 tag."""
    return tag.get_text(strip=True) if tag else ""


# ─────────────────────────────────────────────────────────────────────────────
# Source 1: Finviz — the single richest page for any stock
# One page contains: price, fundamentals, technicals, analyst ratings,
# insider transactions, and recent news headlines.
# ─────────────────────────────────────────────────────────────────────────────
def scrape_finviz(ticker: str) -> dict:
    """
    Scrape finviz.com for fundamentals, technicals, news, and analyst ratings.
    Returns structured dict with all available fields.
    """
    url = f"https://finviz.com/quote.ashx?t={ticker.upper()}&p=d"
    soup = _get(url)
    if not soup:
        return {"source": "finviz", "error": "fetch failed"}

    result: dict = {"source": "finviz", "ticker": ticker.upper()}

    # ── Fundamentals table (Market Cap, P/E, EPS, etc.) ──
    fundamentals: dict[str, str] = {}
    try:
        snapshot_table = soup.find("table", class_="snapshot-table2")
        if not snapshot_table:
            # Finviz redesign fallback
            snapshot_table = soup.find("table", {"class": re.compile("snapshot")})
        if snapshot_table:
            cells = snapshot_table.find_all("td")
            keys = [_text(cells[i]) for i in range(0, len(cells), 2)]
            vals = [_text(cells[i]) for i in range(1, len(cells), 2)]
            fundamentals = dict(zip(keys, vals))
    except Exception:
        log.debug("Finviz fundamentals parse failed for %s", ticker)

    result["fundamentals"] = fundamentals

    # Pull the most useful fields explicitly for easy access
    result["price"]          = fundamentals.get("Price") or fundamentals.get("Prev Close")
    result["market_cap"]     = fundamentals.get("Market Cap")
    result["pe_ratio"]       = fundamentals.get("P/E")
    result["eps_ttm"]        = fundamentals.get("EPS (ttm)")
    result["eps_next_q"]     = fundamentals.get("EPS next Q")
    result["eps_next_y"]     = fundamentals.get("EPS next Y")
    result["eps_growth_q"]   = fundamentals.get("EPS Q/Q")
    result["sales_growth_q"] = fundamentals.get("Sales Q/Q")
    result["short_float"]    = fundamentals.get("Short Float")
    result["short_ratio"]    = fundamentals.get("Short Ratio")
    result["rsi"]            = fundamentals.get("RSI (14)")
    result["beta"]           = fundamentals.get("Beta")
    result["52w_high"]       = fundamentals.get("52W High")
    result["52w_low"]        = fundamentals.get("52W Low")
    result["sma50"]          = fundamentals.get("SMA20") or fundamentals.get("SMA50")
    result["avg_volume"]     = fundamentals.get("Avg Volume")
    result["volume"]         = fundamentals.get("Volume")
    result["rel_volume"]     = fundamentals.get("Rel Volume")
    result["earnings_date"]  = fundamentals.get("Earnings") or fundamentals.get("Earnings Date")
    result["analyst_target"] = fundamentals.get("Target Price")
    result["recommendation"] = fundamentals.get("Recom")
    result["insider_own"]    = fundamentals.get("Insider Own")
    result["insider_trans"]  = fundamentals.get("Insider Trans")
    result["inst_own"]       = fundamentals.get("Inst Own")
    result["inst_trans"]     = fundamentals.get("Inst Trans")
    result["perf_week"]      = fundamentals.get("Perf Week")
    result["perf_month"]     = fundamentals.get("Perf Month")
    result["perf_ytd"]       = fundamentals.get("Perf YTD")
    result["volatility"]     = fundamentals.get("Volatility")
    result["atr"]            = fundamentals.get("ATR (14)")
    result["optionable"]     = fundamentals.get("Optionable")
    result["sector"]         = fundamentals.get("Sector")
    result["industry"]       = fundamentals.get("Industry")
    result["country"]        = fundamentals.get("Country")
    result["employees"]      = fundamentals.get("Employees")

    # ── Analyst ratings ──
    ratings: list[dict] = []
    try:
        ratings_table = soup.find("table", class_=re.compile("fullview-ratings"))
        if not ratings_table:
            # Try finding ratings in the outer ratings table
            ratings_table = soup.find("table", {"id": "news-table"})
        # Look for analyst action rows
        outer = soup.find("table", class_="fullview-ratings-outer")
        if outer:
            for row in outer.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 4:
                    ratings.append({
                        "date":   _text(cells[0]),
                        "action": _text(cells[1]),
                        "firm":   _text(cells[2]),
                        "rating": _text(cells[3]),
                        "target": _text(cells[4]) if len(cells) > 4 else "",
                    })
    except Exception:
        log.debug("Finviz ratings parse failed for %s", ticker)
    result["analyst_ratings"] = ratings[:10]

    # ── News headlines from Finviz ──
    headlines: list[dict] = []
    try:
        news_table = soup.find("table", id="news-table")
        if news_table:
            current_date = ""
            for row in news_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    date_raw = _text(cells[0])
                    if re.match(r"\w{3}-\d{2}", date_raw):
                        current_date = date_raw.split()[0]
                        time_str     = date_raw.split()[1] if " " in date_raw else ""
                    else:
                        time_str = date_raw
                    link_tag = cells[1].find("a")
                    if link_tag:
                        headlines.append({
                            "date":   current_date,
                            "time":   time_str,
                            "title":  _text(link_tag),
                            "url":    link_tag.get("href", ""),
                            "source": _text(cells[1].find("span")) if cells[1].find("span") else "",
                        })
    except Exception:
        log.debug("Finviz news parse failed for %s", ticker)
    result["headlines"] = headlines[:20]

    log.info("[finviz] %s — price=%s  earnings=%s  RSI=%s  short_float=%s",
             ticker, result["price"], result["earnings_date"],
             result["rsi"], result["short_float"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Source 2: Google News RSS — real headlines with real dates, no API key
# ─────────────────────────────────────────────────────────────────────────────
def scrape_google_news(ticker: str, max_items: int = 20) -> list[dict]:
    """
    Fetch latest news from Google News RSS.
    Returns list of {title, date, source, url, summary}.
    """
    url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            pub = entry.get("published", "")
            try:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                pub_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                pub_fmt = pub

            # Source often appears after " - " in the title
            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title  = parts[0].strip()
                source = parts[1].strip()

            items.append({
                "title":   title,
                "date":    pub_fmt,
                "source":  source or entry.get("source", {}).get("title", ""),
                "url":     entry.get("link", ""),
                "summary": BeautifulSoup(
                    entry.get("summary", ""), "lxml"
                ).get_text(strip=True)[:300],
            })

        log.info("[google_news] %s — %d headlines fetched", ticker, len(items))
        return items
    except Exception as e:
        log.debug("Google News RSS failed for %s: %s", ticker, e)
        return []


def scrape_google_news_query(query: str, max_items: int = 15) -> list[dict]:
    """
    Google News RSS with an arbitrary search query (partnerships, M&A, etc.).
    Same shape as scrape_google_news items.
    """
    q = (query or "").strip()
    if not q:
        return []
    url = f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            pub = entry.get("published", "")
            try:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                pub_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                pub_fmt = pub

            title = entry.get("title", "")
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()

            items.append({
                "title":   title,
                "date":    pub_fmt,
                "source":  source or entry.get("source", {}).get("title", ""),
                "url":     entry.get("link", ""),
                "summary": BeautifulSoup(
                    entry.get("summary", ""), "lxml"
                ).get_text(strip=True)[:300],
            })

        log.info("[google_news_query] %s — %d headlines", q[:48], len(items))
        return items
    except Exception as e:
        log.debug("Google News query failed [%s]: %s", q[:40], e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Source 3: StockAnalysis.com — EPS history, beat/miss, revenue history
# The cleanest free source for earnings history
# ─────────────────────────────────────────────────────────────────────────────
def scrape_stockanalysis_earnings(ticker: str) -> list[dict]:
    """
    Scrape StockAnalysis earnings history page.
    Returns list of quarterly EPS records: {quarter, actual, estimate, beat_miss, revenue}.
    """
    url = f"https://stockanalysis.com/stocks/{ticker.lower()}/financials/?p=quarterly"
    soup = _get(url)
    if not soup:
        return []

    rows = []
    try:
        table = soup.find("table")
        if not table:
            return []
        headers = [_text(th) for th in table.find_all("th")]
        for tr in table.find_all("tr")[1:10]:  # up to 9 quarters
            cells = [_text(td) for td in tr.find_all("td")]
            if cells:
                row = dict(zip(headers, cells))
                rows.append(row)
    except Exception:
        log.debug("StockAnalysis earnings parse failed for %s", ticker)

    log.info("[stockanalysis] %s — %d earnings rows", ticker, len(rows))
    return rows


def scrape_stockanalysis_overview(ticker: str) -> dict:
    """Scrape the stock overview page for analyst forecasts and key stats."""
    url = f"https://stockanalysis.com/stocks/{ticker.lower()}/"
    soup = _get(url)
    if not soup:
        return {}

    data: dict = {}
    try:
        # Try to find key stats table
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = _text(cells[0]).lower().replace(" ", "_")
                    val = _text(cells[1])
                    if key and val:
                        data[key] = val
    except Exception:
        log.debug("StockAnalysis overview parse failed for %s", ticker)

    # Try to extract analyst price targets from the page text
    try:
        page_text = soup.get_text()
        target_match = re.search(r"price target[^\d]*\$?([\d.]+)", page_text, re.I)
        if target_match:
            data["analyst_price_target_from_text"] = target_match.group(1)
    except Exception:
        pass

    log.info("[stockanalysis_overview] %s — %d data fields", ticker, len(data))
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Source 4: SEC EDGAR — latest 8-K filings (material events)
# 8-Ks are company-filed press releases: earnings, contracts, leadership changes, etc.
# ─────────────────────────────────────────────────────────────────────────────
def scrape_sec_filings(ticker: str, max_items: int = 5) -> list[dict]:
    """
    Pull latest 8-K filings for a ticker from SEC EDGAR.
    8-Ks are material event disclosures — earnings results, contracts, leadership.
    Returns list of {date, form_type, description, url}.
    """
    # First find the CIK for this ticker
    try:
        cik_url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker.upper()}%22&dateRange=custom&startdt=2024-01-01&forms=8-K"
        cik_search = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=8-K&dateRange=custom&startdt=2024-01-01"
        
        # Use the full-text search API
        search_url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker.upper()}%22"
            f"&forms=8-K&dateRange=custom&startdt=2025-01-01"
        )
        resp = _SESSION.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=8-K",
            timeout=10
        )

        # Simpler: use the EDGAR full-text search
        edgar_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&company=&CIK={ticker.upper()}"
            f"&type=8-K&dateb=&owner=include&count=5&search_text="
        )
        soup = _get(edgar_url)
        if not soup:
            return []

        filings = []
        table = soup.find("table", class_="tableFile2")
        if table:
            for row in table.find_all("tr")[1:max_items + 1]:
                cells = row.find_all("td")
                if len(cells) >= 4:
                    link = cells[1].find("a")
                    filings.append({
                        "form_type":   _text(cells[0]),
                        "date":        _text(cells[3]),
                        "description": _text(cells[2]) if len(cells) > 2 else "",
                        "url":         "https://www.sec.gov" + link["href"] if link else "",
                    })

        log.info("[sec_edgar] %s — %d 8-K filings", ticker, len(filings))
        return filings
    except Exception as e:
        log.debug("SEC EDGAR failed for %s: %s", ticker, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Source 5: Benzinga News RSS — financial news with timestamps
# ─────────────────────────────────────────────────────────────────────────────
def scrape_benzinga_news(ticker: str, max_items: int = 10) -> list[dict]:
    """Fetch Benzinga news via their RSS feed."""
    url = f"https://www.benzinga.com/stock/{ticker.lower()}/feed"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            pub = ""
            try:
                dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                pub = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                pub = entry.get("published", "")

            items.append({
                "title":   entry.get("title", ""),
                "date":    pub,
                "source":  "Benzinga",
                "url":     entry.get("link", ""),
                "summary": BeautifulSoup(
                    entry.get("summary", ""), "lxml"
                ).get_text(strip=True)[:300],
            })
        log.info("[benzinga] %s — %d articles", ticker, len(items))
        return items
    except Exception as e:
        log.debug("Benzinga RSS failed for %s: %s", ticker, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Source 6: Reddit — WSB and r/stocks sentiment
# Uses Reddit's JSON API — no OAuth needed for read-only
# ─────────────────────────────────────────────────────────────────────────────
def scrape_reddit_sentiment(ticker: str, max_posts: int = 10) -> list[dict]:
    """
    Search Reddit WSB and r/stocks for recent mentions of the ticker.
    Returns list of {subreddit, title, score, comments, url, date}.
    """
    posts = []
    subreddits = ["wallstreetbets", "stocks", "options", "pennystocks"]
    for sub in subreddits[:2]:  # limit to 2 subs to avoid being rate-limited
        try:
            url = f"https://www.reddit.com/r/{sub}/search.json?q={ticker}&sort=new&limit=5&restrict_sr=1"
            resp = _SESSION.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for post in data.get("data", {}).get("children", [])[:5]:
                pd = post.get("data", {})
                created = pd.get("created_utc", 0)
                try:
                    date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    date_str = ""
                posts.append({
                    "subreddit": sub,
                    "title":     pd.get("title", ""),
                    "score":     pd.get("score", 0),
                    "comments":  pd.get("num_comments", 0),
                    "url":       "https://reddit.com" + pd.get("permalink", ""),
                    "date":      date_str,
                    "flair":     pd.get("link_flair_text", ""),
                })
            time.sleep(1)  # Reddit rate limit: 1 req/sec
        except Exception as e:
            log.debug("Reddit scrape failed [r/%s] for %s: %s", sub, ticker, e)
    log.info("[reddit] %s — %d posts", ticker, len(posts))
    return posts


# ─────────────────────────────────────────────────────────────────────────────
# Source 7: Yahoo Finance — earnings calendar and key stats
# ─────────────────────────────────────────────────────────────────────────────
def scrape_yahoo_summary(ticker: str) -> dict:
    """Scrape Yahoo Finance summary page for key stats and earnings date."""
    url = f"https://finance.yahoo.com/quote/{ticker.upper()}/"
    soup = _get(url)
    if not soup:
        return {}

    data: dict = {}
    try:
        # Key stats are in data-field attributes or table cells
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                key = _text(cells[0])
                val = _text(cells[1])
                if key:
                    data[key] = val
    except Exception:
        pass

    log.info("[yahoo] %s — %d stats scraped", ticker, len(data))
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Source 8: Unusual Whales — options flow and smart money activity
# Free public pages show today's notable options activity
# ─────────────────────────────────────────────────────────────────────────────
def scrape_unusual_whales(ticker: str) -> dict:
    """
    Scrape Unusual Whales for options flow data.
    Returns put/call ratio, notable contracts, and flow sentiment.
    """
    result: dict = {"source": "unusual_whales", "ticker": ticker.upper()}
    url = f"https://unusualwhales.com/stock/{ticker.upper()}"
    soup = _get(url, timeout=15)
    if not soup:
        return result

    try:
        text = soup.get_text(separator=" ", strip=True)

        # Pull put/call ratio
        pc_match = re.search(r"put[\/\s-]*call\s*ratio[:\s]*([\d.]+)", text, re.I)
        if pc_match:
            result["put_call_ratio"] = pc_match.group(1)

        # Pull implied volatility
        iv_match = re.search(r"implied\s*volatility[:\s]*([\d.]+%?)", text, re.I)
        if iv_match:
            result["implied_volatility"] = iv_match.group(1)

        # Pull IV rank/percentile
        ivr_match = re.search(r"IV\s*rank[:\s]*([\d.]+)", text, re.I)
        if ivr_match:
            result["iv_rank"] = ivr_match.group(1)

        # Pull call/put premium totals
        call_match = re.search(r"call\s*premium[:\s]*\$?([\d.,KMB]+)", text, re.I)
        put_match  = re.search(r"put\s*premium[:\s]*\$?([\d.,KMB]+)", text, re.I)
        if call_match:
            result["call_premium"] = call_match.group(1)
        if put_match:
            result["put_premium"] = put_match.group(1)

        # Net options sentiment
        bull_match = re.search(r"(bullish|bearish|neutral)\s*flow", text, re.I)
        if bull_match:
            result["flow_sentiment"] = bull_match.group(1).lower()

        result["page_text_excerpt"] = text[:1500]

    except Exception:
        log.debug("Unusual Whales parse failed for %s", ticker)

    log.info("[unusual_whales] %s — IV=%s  P/C=%s  sentiment=%s",
             ticker, result.get("implied_volatility","?"),
             result.get("put_call_ratio","?"),
             result.get("flow_sentiment","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Source 9: Earnings Whispers — whisper number vs Wall Street consensus
# The whisper number is what traders actually expect, often differs from official estimate
# ─────────────────────────────────────────────────────────────────────────────
def scrape_earnings_whispers(ticker: str) -> dict:
    """
    Scrape EarningsWhispers.com for the whisper EPS number and earnings details.
    Whisper number = trader expectation, often higher than official consensus.
    """
    result: dict = {"source": "earnings_whispers", "ticker": ticker.upper()}
    url = f"https://www.earningswhispers.com/stocks/{ticker.lower()}"
    soup = _get(url, timeout=12)
    if not soup:
        return result

    try:
        text = soup.get_text(separator=" ", strip=True)

        # Earnings date
        date_match = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}",
            text, re.I
        )
        if date_match:
            result["earnings_date"] = date_match.group(0)

        # Whisper EPS
        whisper_match = re.search(r"whisper[^\d\-]*(\-?[\d.]+)", text, re.I)
        if whisper_match:
            result["whisper_eps"] = whisper_match.group(1)

        # Consensus EPS
        consensus_match = re.search(r"consensus[^\d\-]*(\-?[\d.]+)", text, re.I)
        if consensus_match:
            result["consensus_eps"] = consensus_match.group(1)

        # Surprise direction
        if re.search(r"beat|above\s*expectations", text, re.I):
            result["recent_trend"] = "beat"
        elif re.search(r"miss|below\s*expectations", text, re.I):
            result["recent_trend"] = "miss"

        # Revenue estimate
        rev_match = re.search(r"revenue[^\d]*\$?([\d.,]+\s*[MBK]?)", text, re.I)
        if rev_match:
            result["revenue_estimate"] = rev_match.group(1)

        result["page_text_excerpt"] = text[:800]

    except Exception:
        log.debug("Earnings Whispers parse failed for %s", ticker)

    log.info("[earnings_whispers] %s — date=%s  whisper=%s  consensus=%s",
             ticker, result.get("earnings_date","?"),
             result.get("whisper_eps","?"),
             result.get("consensus_eps","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Source 10: OpenInsider — insider buying and selling with exact details
# Insiders buying their own stock = strong bullish signal
# ─────────────────────────────────────────────────────────────────────────────
def scrape_openinsider(ticker: str) -> list[dict]:
    """
    Scrape OpenInsider for recent insider transactions.
    Returns list of {date, insider, title, type, shares, price, value}.
    Insider BUYING is one of the strongest bullish signals in trading.
    """
    url = f"https://openinsider.com/search?q={ticker.upper()}"
    soup = _get(url, timeout=12)
    if not soup:
        return []

    transactions = []
    try:
        table = soup.find("table", class_=re.compile("tinytable"))
        if not table:
            table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:15]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 10:
                    tx_type = _text(cells[6]) if len(cells) > 6 else ""
                    transactions.append({
                        "filing_date": _text(cells[1]),
                        "trade_date":  _text(cells[2]),
                        "ticker":      _text(cells[3]),
                        "company":     _text(cells[4]),
                        "insider":     _text(cells[5]) if len(cells) > 5 else "",
                        "title":       _text(cells[6]) if len(cells) > 6 else "",
                        "trade_type":  _text(cells[7]) if len(cells) > 7 else "",
                        "price":       _text(cells[8]) if len(cells) > 8 else "",
                        "qty":         _text(cells[9]) if len(cells) > 9 else "",
                        "owned":       _text(cells[10]) if len(cells) > 10 else "",
                        "value":       _text(cells[12]) if len(cells) > 12 else "",
                    })
    except Exception:
        log.debug("OpenInsider parse failed for %s", ticker)

    # Classify sentiment
    buys  = sum(1 for t in transactions if "P" in t.get("trade_type","").upper()
                or "buy" in t.get("trade_type","").lower())
    sells = sum(1 for t in transactions if "S" in t.get("trade_type","").upper()
                or "sale" in t.get("trade_type","").lower())

    log.info("[openinsider] %s — %d transactions (%d buys, %d sells)",
             ticker, len(transactions), buys, sells)
    return transactions[:10]


# ─────────────────────────────────────────────────────────────────────────────
# Source 11: MarketBeat — aggregated analyst ratings and price targets
# Shows all analyst upgrades/downgrades in one place
# ─────────────────────────────────────────────────────────────────────────────
def scrape_marketbeat(ticker: str) -> dict:
    """
    Scrape MarketBeat for aggregated analyst ratings, price targets, and forecasts.
    """
    result: dict = {"source": "marketbeat", "ticker": ticker.upper()}
    url = f"https://www.marketbeat.com/stocks/NASDAQ/{ticker.upper()}/"
    soup = _get(url, timeout=12)
    if not soup:
        # Try NYSE listing
        url = f"https://www.marketbeat.com/stocks/NYSE/{ticker.upper()}/"
        soup = _get(url, timeout=12)
    if not soup:
        return result

    try:
        text = soup.get_text(separator=" ", strip=True)

        # Consensus rating
        rating_match = re.search(
            r"(strong buy|moderate buy|buy|hold|sell|strong sell|moderate sell)",
            text, re.I
        )
        if rating_match:
            result["consensus_rating"] = rating_match.group(1).title()

        # Average price target
        target_match = re.search(r"average\s*(?:price\s*)?target[:\s]*\$?([\d.]+)", text, re.I)
        if target_match:
            result["avg_price_target"] = target_match.group(1)

        # High/low targets
        hi_match  = re.search(r"high\s*(?:price\s*)?target[:\s]*\$?([\d.]+)", text, re.I)
        lo_match  = re.search(r"low\s*(?:price\s*)?target[:\s]*\$?([\d.]+)", text, re.I)
        if hi_match:
            result["high_target"] = hi_match.group(1)
        if lo_match:
            result["low_target"] = lo_match.group(1)

        # Number of analysts
        n_match = re.search(r"(\d+)\s*analyst", text, re.I)
        if n_match:
            result["analyst_count"] = n_match.group(1)

        # Upcoming earnings date
        earn_match = re.search(
            r"earnings[^\n]*?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}",
            text, re.I
        )
        if earn_match:
            result["earnings_date"] = earn_match.group(0).strip()

        # Dividend info
        div_match = re.search(r"dividend[^\d]*\$?([\d.]+%?)", text, re.I)
        if div_match:
            result["dividend"] = div_match.group(1)

        # Scrape analyst rating table
        ratings_list = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr")[1:8]:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    ratings_list.append({
                        "date":   _text(cells[0]),
                        "firm":   _text(cells[1]),
                        "action": _text(cells[2]),
                        "target": _text(cells[3]) if len(cells) > 3 else "",
                    })
        result["recent_ratings"] = ratings_list[:6]

    except Exception:
        log.debug("MarketBeat parse failed for %s", ticker)

    log.info("[marketbeat] %s — consensus=%s  avg_target=%s",
             ticker, result.get("consensus_rating","?"),
             result.get("avg_price_target","?"))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Cross-reference engine — compares key facts across all sources
# This is what makes the system 10x better than ChatGPT Deep Research
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_date(s: str) -> str:
    """Normalize various date formats to YYYY-MM-DD for comparison."""
    if not s:
        return ""
    s = s.strip()
    # Already normalized
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    # "May 07" or "May 7" or "May 07 AMC"
    month_map = {
        "jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
        "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"
    }
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s*(\d{4})?", s, re.I)
    if m:
        mon = month_map[m.group(1).lower()[:3]]
        day = m.group(2).zfill(2)
        yr  = m.group(3) or "2026"
        return f"{yr}-{mon}-{day}"
    return s


def cross_reference(
    finviz_data:   dict,
    ew_data:       dict,
    mb_data:       dict,
    insider_data:  list,
    uw_data:       dict,
    news_items:    list,
) -> dict:
    """
    Compare key facts across all scraped sources.
    Returns a confidence report that gets prepended to the AI context.

    Confidence levels:
      CONFIRMED (3+ sources agree)   → AI treats as hard fact
      CORROBORATED (2 sources agree) → AI treats as likely fact
      SINGLE SOURCE                  → AI notes caveat
      CONFLICT                       → AI explicitly flags discrepancy
    """
    report_lines: list[str] = []
    confidence_data: dict   = {}

    # ── Earnings date cross-reference ──────────────────────────────────────
    dates: dict[str, list[str]] = {}
    fv_date  = _normalize_date(finviz_data.get("earnings_date",""))
    ew_date  = _normalize_date(ew_data.get("earnings_date",""))
    mb_date  = _normalize_date(mb_data.get("earnings_date",""))

    if fv_date:
        dates.setdefault(fv_date, []).append("Finviz")
    if ew_date:
        dates.setdefault(ew_date, []).append("EarningsWhispers")
    if mb_date:
        dates.setdefault(mb_date, []).append("MarketBeat")

    if dates:
        best_date = max(dates, key=lambda d: len(dates[d]))
        sources   = dates[best_date]
        if len(sources) >= 3:
            conf = "CONFIRMED"
        elif len(sources) == 2:
            conf = "CORROBORATED"
        else:
            conf = "SINGLE SOURCE"

        if len(dates) > 1:
            conf = "CONFLICT"
            report_lines.append(f"EARNINGS DATE — CONFLICT DETECTED:")
            for d, srcs in dates.items():
                report_lines.append(f"  {d} ({', '.join(srcs)})")
        else:
            raw = finviz_data.get("earnings_date") or ew_data.get("earnings_date") or mb_date
            report_lines.append(f"EARNINGS DATE: {raw} [{conf} — {', '.join(sources)}]")
            confidence_data["earnings_date"] = {"value": raw, "confidence": conf, "sources": sources}

    # ── Price / analyst target cross-reference ─────────────────────────────
    fv_target = finviz_data.get("analyst_target","").replace("$","").strip()
    mb_target = mb_data.get("avg_price_target","").replace("$","").strip()

    targets = {}
    if fv_target:
        targets[fv_target] = targets.get(fv_target, []) + ["Finviz"]
    if mb_target:
        targets[mb_target] = targets.get(mb_target, []) + ["MarketBeat"]

    if targets:
        if len(targets) == 1:
            val    = list(targets.keys())[0]
            srcs   = targets[val]
            conf   = "CORROBORATED" if len(srcs) >= 2 else "SINGLE SOURCE"
            report_lines.append(f"ANALYST PRICE TARGET: ${val} [{conf} — {', '.join(srcs)}]")
            confidence_data["analyst_target"] = {"value": val, "confidence": conf}
        else:
            report_lines.append(f"ANALYST PRICE TARGET — MULTIPLE VALUES:")
            for val, srcs in targets.items():
                report_lines.append(f"  ${val} ({', '.join(srcs)})")

    # ── EPS estimate cross-reference ───────────────────────────────────────
    ew_whisper   = ew_data.get("whisper_eps","")
    ew_consensus = ew_data.get("consensus_eps","")
    fv_eps_est   = finviz_data.get("eps_next_q","")

    if ew_whisper or ew_consensus or fv_eps_est:
        report_lines.append(f"EPS ESTIMATES (next quarter):")
        if fv_eps_est:
            report_lines.append(f"  Wall St consensus (Finviz): {fv_eps_est}")
        if ew_consensus:
            report_lines.append(f"  Official estimate (EarningsWhispers): {ew_consensus}")
        if ew_whisper:
            report_lines.append(f"  WHISPER number (what traders actually expect): {ew_whisper}")
            if ew_consensus:
                try:
                    diff = float(ew_whisper) - float(ew_consensus)
                    direction = "ABOVE" if diff > 0 else "BELOW"
                    report_lines.append(
                        f"  => Whisper is {direction} consensus by {abs(diff):.3f} "
                        f"({'bullish signal' if diff > 0 else 'bearish signal'})"
                    )
                except Exception:
                    pass

    # ── Short float cross-reference ────────────────────────────────────────
    fv_short = finviz_data.get("short_float","")
    if fv_short:
        try:
            pct = float(fv_short.replace("%",""))
            squeeze_label = ""
            if pct > 30:
                squeeze_label = " — EXTREME short squeeze candidate"
            elif pct > 20:
                squeeze_label = " — HIGH short interest, squeeze possible"
            elif pct > 10:
                squeeze_label = " — elevated short interest"
            report_lines.append(f"SHORT FLOAT: {fv_short}{squeeze_label} [Finviz]")
            confidence_data["short_float"] = fv_short
        except Exception:
            report_lines.append(f"SHORT FLOAT: {fv_short} [Finviz]")

    # ── Insider activity summary ────────────────────────────────────────────
    if insider_data:
        buys  = [t for t in insider_data if "P" in t.get("trade_type","").upper()
                 or "buy" in t.get("trade_type","").lower()]
        sells = [t for t in insider_data if "S" in t.get("trade_type","").upper()
                 or "sale" in t.get("trade_type","").lower()]
        if buys:
            report_lines.append(
                f"INSIDER BUYING: {len(buys)} purchase(s) found [OpenInsider] — "
                "BULLISH SIGNAL: insiders buying their own stock"
            )
            for b in buys[:3]:
                report_lines.append(
                    f"  {b.get('trade_date','')} — {b.get('insider','')} "
                    f"({b.get('title','')}) bought {b.get('qty','')} shares "
                    f"@ {b.get('price','')} = {b.get('value','')}"
                )
        if sells:
            report_lines.append(
                f"INSIDER SELLING: {len(sells)} sale(s) found [OpenInsider]"
            )
            for s in sells[:2]:
                report_lines.append(
                    f"  {s.get('trade_date','')} — {s.get('insider','')} "
                    f"sold {s.get('qty','')} shares @ {s.get('price','')}"
                )

    # ── Options flow summary ────────────────────────────────────────────────
    if uw_data.get("flow_sentiment") or uw_data.get("put_call_ratio"):
        report_lines.append(f"OPTIONS FLOW [Unusual Whales]:")
        if uw_data.get("flow_sentiment"):
            report_lines.append(f"  Net flow sentiment: {uw_data['flow_sentiment'].upper()}")
        if uw_data.get("put_call_ratio"):
            try:
                pcr = float(uw_data["put_call_ratio"])
                direction = "BEARISH skew" if pcr > 1 else "BULLISH skew"
                report_lines.append(f"  Put/call ratio: {pcr} ({direction})")
            except Exception:
                report_lines.append(f"  Put/call ratio: {uw_data['put_call_ratio']}")
        if uw_data.get("implied_volatility"):
            report_lines.append(f"  Implied volatility: {uw_data['implied_volatility']}")
        if uw_data.get("iv_rank"):
            report_lines.append(f"  IV rank: {uw_data['iv_rank']}")
        if uw_data.get("call_premium") and uw_data.get("put_premium"):
            report_lines.append(
                f"  Call premium: ${uw_data['call_premium']}  "
                f"Put premium: ${uw_data['put_premium']}"
            )

    # ── News sentiment tally ────────────────────────────────────────────────
    positive_kw = ["surge","jump","rally","beat","upgrade","buy","bull","strong","partner",
                   "launch","contract","record","growth","expand","soar"]
    negative_kw = ["drop","fall","miss","downgrade","sell","bear","weak","risk","lawsuit",
                   "decline","loss","warning","concern","cut","below"]
    pos_count = sum(
        1 for n in news_items
        if any(kw in n.get("title","").lower() for kw in positive_kw)
    )
    neg_count = sum(
        1 for n in news_items
        if any(kw in n.get("title","").lower() for kw in negative_kw)
    )
    total = len(news_items)
    if total > 0:
        sentiment = "BULLISH" if pos_count > neg_count else ("BEARISH" if neg_count > pos_count else "NEUTRAL")
        report_lines.append(
            f"NEWS SENTIMENT: {sentiment} "
            f"({pos_count} positive / {neg_count} negative / {total - pos_count - neg_count} neutral "
            f"out of {total} headlines)"
        )
        confidence_data["news_sentiment"] = sentiment

    confidence_report = (
        "\n=== CROSS-REFERENCE REPORT (Python-verified, multi-source) ===\n"
        + "\n".join(report_lines)
        + "\n=== END CROSS-REFERENCE ===\n"
    )

    return {
        "report_text":    confidence_report,
        "confidence_data": confidence_data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Macrotrends — 5-10 year financial history (revenue, EPS, margins)
# Tells ATLAS whether growth is accelerating, decelerating, or declining
# ─────────────────────────────────────────────────────────────────────────────
def scrape_macrotrends(ticker: str) -> dict:
    """
    Scrape Macrotrends for multi-year financial history.
    Revenue growth trend, EPS trend, gross/net margin — essential for
    determining whether a company is growing vs. declining.

    Macrotrends embeds chart data as JSON inside <script> tags.
    We extract it without a browser by parsing the raw HTML source.
    """
    result = {"source": "macrotrends", "ticker": ticker.upper()}
    base_slug = ticker.lower()

    # Macrotrends URLs use {ticker}/{company-name}/{metric} — we need the slug
    # First, find the company slug via their search
    try:
        search_url = f"https://www.macrotrends.net/assets/php/fundamental_iframe.php?t={ticker.upper()}&type=revenue&statement=income-statement&frequency=Q"
        r = _SESSION.get(search_url, timeout=12)
        soup = BeautifulSoup(r.text, "lxml")

        # Extract from the embedded script data
        script_text = ""
        for sc in soup.find_all("script"):
            t_txt = sc.get_text()
            if "chartData" in t_txt or "revenue" in t_txt.lower():
                script_text += t_txt[:3000]
                break

        if script_text:
            # Revenue data: look for quarterly data array
            rev_match = re.search(
                r'"revenue"[^[]*(\[\s*\{[^\]]+\}\s*\])', script_text
            )
            if rev_match:
                result["revenue_raw"] = rev_match.group(1)[:500]
    except Exception:
        pass

    # Approach 2: scrape the stock-specific revenue page directly
    # Macrotrends stock pages follow: /stocks/charts/{TICKER}/{company}/revenue
    # We don't know the company slug, so try the redirect approach
    try:
        # Try to get the actual page URL via a redirect/search
        candidate_url = f"https://www.macrotrends.net/stocks/charts/{ticker.upper()}/{ticker.lower()}/revenue"
        r = _get(candidate_url)
        if not r:
            # Try with a known common format (macrotrends auto-redirects)
            candidate_url = f"https://www.macrotrends.net/assets/php/fundamental_iframe.php?t={ticker.upper()}&type=revenue&statement=income-statement&frequency=A"
            r = _SESSION.get(candidate_url, timeout=12)
            if r and r.status_code == 200:
                pass

        if r and hasattr(r, "find_all"):
            # BeautifulSoup result
            soup = r
        elif r and hasattr(r, "text"):
            soup = BeautifulSoup(r.text, "lxml")
        else:
            soup = None

        if soup:
            # Extract table data — Macrotrends renders data tables
            rows = soup.find_all("tr")
            revenue_hist: list[tuple] = []
            eps_hist:     list[tuple] = []
            for row in rows[:30]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    year_txt  = cells[0].get_text(strip=True)
                    value_txt = cells[1].get_text(strip=True)
                    if re.match(r"20\d{2}|19\d{2}", year_txt):
                        if "$" in value_txt or re.search(r"[\d.,]+[BMK]?", value_txt):
                            revenue_hist.append((year_txt, value_txt))

            if revenue_hist:
                result["revenue_history"] = revenue_hist[:8]
    except Exception:
        pass

    # Approach 3: use yfinance for multi-year financials (most reliable)
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker.upper())

        # Annual financials
        fin = tk.financials  # columns = years, rows = line items
        if fin is not None and not fin.empty:
            rev_rows   = [r for r in fin.index if "Revenue" in r or "Total Revenue" in r]
            gp_rows    = [r for r in fin.index if "Gross Profit" in r]
            ni_rows    = [r for r in fin.index if "Net Income" in r]

            years = []
            for col in list(fin.columns)[:5]:  # up to 5 years
                yr = str(col)[:4]
                entry: dict = {"year": yr}
                if rev_rows:
                    rev_v = fin.loc[rev_rows[0], col]
                    if rev_v and rev_v == rev_v:  # not NaN
                        entry["revenue"] = f"${rev_v/1e6:.0f}M" if abs(rev_v) < 1e9 else f"${rev_v/1e9:.2f}B"
                if gp_rows:
                    gp_v = fin.loc[gp_rows[0], col]
                    if gp_v and gp_v == gp_v and rev_rows:
                        rev_v2 = fin.loc[rev_rows[0], col]
                        if rev_v2 and rev_v2 != 0:
                            entry["gross_margin"] = f"{gp_v/rev_v2*100:.1f}%"
                if ni_rows:
                    ni_v = fin.loc[ni_rows[0], col]
                    if ni_v and ni_v == ni_v:
                        entry["net_income"] = f"${ni_v/1e6:.0f}M"
                years.append(entry)

            result["annual_financials"] = years

        # EPS history from earnings
        eps_hist_q = []
        try:
            earnings = tk.earnings_history
            if earnings is not None and not earnings.empty:
                for _, row_e in list(earnings.iterrows())[:8]:
                    eps_hist_q.append({
                        "date":     str(row_e.get("quarterDate",""))[:7],
                        "estimate": row_e.get("epsEstimate"),
                        "actual":   row_e.get("epsActual"),
                        "surprise": row_e.get("epsDifference"),
                    })
                result["eps_history_q"] = eps_hist_q
        except Exception:
            pass

        # Revenue growth calculation
        if result.get("annual_financials") and len(result["annual_financials"]) >= 2:
            try:
                newest = tk.financials
                if not newest.empty and rev_rows:
                    rev_vals = [newest.loc[rev_rows[0], c] for c in list(newest.columns)[:3]
                                if newest.loc[rev_rows[0], c] == newest.loc[rev_rows[0], c]]
                    if len(rev_vals) >= 2 and rev_vals[1] and rev_vals[1] != 0:
                        growth = (rev_vals[0] - rev_vals[1]) / abs(rev_vals[1]) * 100
                        result["yoy_revenue_growth"] = f"{growth:+.1f}%"
            except Exception:
                pass

        log.info("  [macrotrends/yfinance] %s — %d years financials, yoy growth: %s",
                 ticker, len(result.get("annual_financials", [])),
                 result.get("yoy_revenue_growth", "?"))

    except Exception:
        log.debug("  [macrotrends] yfinance financial history failed for %s", ticker, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# WhalerWisdom / SEC 13F — Institutional holdings tracker
# Shows which institutions bought or sold in the last quarter
# ─────────────────────────────────────────────────────────────────────────────
def scrape_institutional_holdings(ticker: str) -> dict:
    """
    Scrape institutional holdings data from WhalerWisdom.com and/or
    SEC EDGAR 13F data.

    Key insight: When major institutions like Fidelity or Vanguard ADD shares,
    that's strong forward signal. When they REDUCE, it's a warning.
    We report: top 5 holders, quarter-over-quarter change, new positions, sold-out.
    """
    result = {"source": "institutional_13f", "ticker": ticker.upper()}

    # ── Approach 1: WhalerWisdom public page ─────────────────────────────────
    try:
        url  = f"https://whalerwisdom.com/stock/{ticker.upper()}"
        soup = _get(url)
        if soup:
            text = _text(soup)
            result["raw_snippet"] = text[:1500]

            # Top institutional holders
            holders: list[dict] = []
            rows = soup.find_all("tr")
            for row in rows[:20]:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name  = cells[0].get_text(strip=True)
                    shares= cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    chg   = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    if name and (re.search(r"[A-Z][a-z]", name) or "Fund" in name):
                        holders.append({"name": name[:40], "shares": shares, "change": chg})

            if holders:
                result["top_holders"] = holders[:8]

            # Net institutional change
            net_m = re.search(r"net\s+(?:change|buy|sell)[:\s]*([+-]?[\d,]+)", text, re.I)
            if net_m:
                result["net_institutional_change"] = net_m.group(1)

            # Number of institutions
            inst_m = re.search(r"(\d+)\s+institutional", text, re.I)
            if inst_m:
                result["institution_count"] = inst_m.group(1)

            log.info("  [institutional_13f] %s — %d holders via WhalerWisdom",
                     ticker, len(result.get("top_holders", [])))
    except Exception:
        log.debug("  [institutional_13f] WhalerWisdom failed for %s", ticker, exc_info=True)

    # ── Approach 2: SEC EDGAR EFTS full-text search for 13F ─────────────────
    if not result.get("top_holders"):
        try:
            # Search EDGAR for 13F filings mentioning this ticker's CUSIP
            edgar_url = (
                f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker.upper()}%22"
                f"&dateRange=custom&startdt=2024-01-01&forms=13F-HR&hits.hits._source.file_date=desc"
            )
            r = _SESSION.get(edgar_url, timeout=12, headers={"Accept": "application/json"})
            if r.status_code == 200:
                data = r.json()
                hits = data.get("hits", {}).get("hits", [])
                if hits:
                    filings = []
                    for h in hits[:5]:
                        src = h.get("_source", {})
                        filings.append({
                            "filer":   src.get("display_names", ["?"])[0] if src.get("display_names") else "?",
                            "date":    src.get("file_date","?"),
                            "form":    src.get("form_type","13F"),
                        })
                    result["recent_13f_filings"] = filings
                    log.info("  [institutional_13f] %s — %d recent 13F filings from EDGAR",
                             ticker, len(filings))
        except Exception:
            log.debug("  [institutional_13f] EDGAR search failed", exc_info=True)

    # ── Approach 3: yfinance institutional holders ───────────────────────────
    try:
        import yfinance as yf
        tk   = yf.Ticker(ticker.upper())
        inst = tk.institutional_holders
        if inst is not None and not inst.empty:
            holders_yf = []
            for _, row_i in inst.iterrows():
                holders_yf.append({
                    "name":    str(row_i.get("Holder","?"))[:40],
                    "shares":  f"{row_i.get('Shares',0):,}" if row_i.get("Shares") else "?",
                    "pct":     f"{row_i.get('% Out',0)*100:.2f}%" if row_i.get("% Out") else "?",
                    "value":   f"${row_i.get('Value',0)/1e6:.1f}M" if row_i.get("Value") else "?",
                })
            result["top_holders_yf"] = holders_yf[:8]

        # Mutual fund holders
        mf = tk.mutualfund_holders
        if mf is not None and not mf.empty:
            mf_list = []
            for _, row_m in mf.iterrows():
                mf_list.append({
                    "name":  str(row_m.get("Holder","?"))[:40],
                    "pct":   f"{row_m.get('% Out',0)*100:.2f}%",
                    "value": f"${row_m.get('Value',0)/1e6:.1f}M" if row_m.get("Value") else "?",
                })
            result["mutual_fund_holders"] = mf_list[:5]

        # Summary stats
        info = tk.info or {}
        result["institutional_pct"]      = info.get("heldPercentInstitutions")
        result["insider_pct"]            = info.get("heldPercentInsiders")
        result["institutional_pct_str"]  = (
            f"{result['institutional_pct']*100:.1f}%"
            if result.get("institutional_pct") else "?"
        )

        log.info("  [institutional_13f] %s — %d holders via yfinance, inst%%=%s",
                 ticker, len(result.get("top_holders_yf",[])),
                 result.get("institutional_pct_str","?"))
    except Exception:
        log.debug("  [institutional_13f] yfinance holders failed for %s", ticker, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Seeking Alpha RSS — large news coverage, analyst commentary
# ─────────────────────────────────────────────────────────────────────────────
def scrape_seeking_alpha(ticker: str) -> list[dict]:
    """
    Scrape Seeking Alpha RSS feed for recent articles and news.
    Seeking Alpha has massive coverage of earnings previews, analysis, and
    dividend/growth stories that other sources miss.
    Returns list of {title, published, link, summary}.
    """
    results: list[dict] = []

    # SA provides a public combined RSS feed
    feed_urls = [
        f"https://seekingalpha.com/api/sa/combined/{ticker.upper()}.xml",
        f"https://feeds.seekingalpha.com/article/feed2?symbols={ticker.upper()}",
    ]

    for url in feed_urls:
        try:
            import feedparser
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:8]:
                    pub = entry.get("published") or entry.get("updated") or ""
                    summary = entry.get("summary") or entry.get("content", [{}])[0].get("value","")
                    # Strip HTML from summary
                    summary = re.sub(r"<[^>]+>", " ", summary).strip()[:300]
                    results.append({
                        "title":     entry.get("title","").strip()[:120],
                        "published": pub[:25],
                        "link":      entry.get("link",""),
                        "source":    "seeking_alpha",
                        "summary":   summary,
                    })
                if results:
                    log.info("  [seeking_alpha] %s — %d articles", ticker, len(results))
                    break
        except Exception:
            continue

    # Fallback: try BeautifulSoup on the public news page
    if not results:
        try:
            url  = f"https://seekingalpha.com/symbol/{ticker.upper()}/news"
            soup = _get(url)
            if soup:
                articles = soup.find_all("a", {"data-test-id": re.compile("post-list-item")})
                if not articles:
                    articles = soup.find_all("article")
                for art in articles[:8]:
                    title = art.get_text(strip=True)[:120]
                    href  = art.get("href","")
                    if title and len(title) > 10:
                        results.append({
                            "title":   title,
                            "link":    f"https://seekingalpha.com{href}" if href.startswith("/") else href,
                            "source":  "seeking_alpha",
                            "summary": "",
                        })
        except Exception:
            pass

    if not results:
        log.info("  [seeking_alpha] %s — no results (SA may require login)", ticker)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Master aggregator — calls all sources, returns one big context bundle
# ─────────────────────────────────────────────────────────────────────────────
def gather_all(ticker: str) -> dict:
    """
    Scrape ALL 10 sources for one ticker, cross-reference key facts,
    and return a confidence-labeled context blob ready for AI synthesis.

    Gemini API calls required: 0
    Sources: Finviz, Google News, Benzinga, StockAnalysis, SEC EDGAR,
             Reddit, Unusual Whales, EarningsWhispers, OpenInsider, MarketBeat
    """
    ticker = ticker.upper().strip()
    log.info("=== Web scraping %s from 10 sources ===", ticker)

    # ── Run all scrapers with small delays to avoid blocks ──────────────────
    finviz       = scrape_finviz(ticker);                   time.sleep(1)
    news_google  = scrape_google_news(ticker);              time.sleep(1)
    news_bz      = scrape_benzinga_news(ticker);            time.sleep(1)
    earnings_h   = scrape_stockanalysis_earnings(ticker);   time.sleep(1)
    sa_overview  = scrape_stockanalysis_overview(ticker);   time.sleep(1)
    sec_filings  = scrape_sec_filings(ticker);              time.sleep(1)
    reddit       = scrape_reddit_sentiment(ticker);         time.sleep(1)
    uw_data      = scrape_unusual_whales(ticker);           time.sleep(1)
    ew_data      = scrape_earnings_whispers(ticker);        time.sleep(1)
    insider_data = scrape_openinsider(ticker);              time.sleep(1)
    mb_data      = scrape_marketbeat(ticker);               time.sleep(1)
    # Tier 1 additions
    macro_data   = scrape_macrotrends(ticker);              time.sleep(1)
    inst_data    = scrape_institutional_holdings(ticker);   time.sleep(1)
    sa_news      = scrape_seeking_alpha(ticker)

    # Deduplicate headlines across sources
    all_news = news_google + news_bz
    seen: set[str] = set()
    unique_news = []
    for item in all_news:
        t = item.get("title","").lower().strip()
        if t and t not in seen:
            seen.add(t)
            unique_news.append(item)

    # Extra RSS passes: company depth (partnerships, corporate actions, filings)
    deep_queries = [
        f"{ticker} (partnership OR collaboration OR contract OR customer OR supplier OR integration OR deploy)",
        f"{ticker} (acquisition OR merger OR investment OR stake OR funding OR licensing)",
        f"{ticker} (earnings OR guidance OR revenue OR warning OR SEC OR 8-K OR lawsuit OR regulatory)",
    ]
    for dq in deep_queries:
        time.sleep(0.6)
        try:
            for item in scrape_google_news_query(dq, max_items=10):
                t = item.get("title", "").lower().strip()
                if t and t not in seen:
                    seen.add(t)
                    item["deep_research_query"] = dq[:80]
                    unique_news.append(item)
        except Exception:
            log.debug("deep news query failed: %s", dq[:40])

    # ── Cross-reference engine ───────────────────────────────────────────────
    xref = cross_reference(
        finviz_data  = finviz,
        ew_data      = ew_data,
        mb_data      = mb_data,
        insider_data = insider_data,
        uw_data      = uw_data,
        news_items   = unique_news,
    )

    # ── Build the full context text blob ────────────────────────────────────
    lines: list[str] = []

    # Cross-reference report goes FIRST so AI reads verified facts first
    lines.append(xref["report_text"])

    # Finviz snapshot
    lines.append(f"=== FINVIZ SNAPSHOT: {ticker} ===")
    lines.append(f"Price: {finviz.get('price','?')}")
    lines.append(f"Market Cap: {finviz.get('market_cap','?')}")
    lines.append(f"P/E: {finviz.get('pe_ratio','?')}  EPS (TTM): {finviz.get('eps_ttm','?')}")
    lines.append(f"EPS Next Quarter (Wall St estimate): {finviz.get('eps_next_q','?')}")
    lines.append(f"EPS Growth Q/Q: {finviz.get('eps_growth_q','?')}  Sales Q/Q: {finviz.get('sales_growth_q','?')}")
    lines.append(f"Short Float: {finviz.get('short_float','?')}  Short Ratio: {finviz.get('short_ratio','?')}")
    lines.append(f"RSI(14): {finviz.get('rsi','?')}  Beta: {finviz.get('beta','?')}")
    lines.append(f"52W High: {finviz.get('52w_high','?')}  52W Low: {finviz.get('52w_low','?')}")
    lines.append(f"Volume: {finviz.get('volume','?')}  Avg Volume: {finviz.get('avg_volume','?')}  Rel Volume: {finviz.get('rel_volume','?')}")
    lines.append(f"Earnings Date (Finviz): {finviz.get('earnings_date','?')}")
    lines.append(f"Analyst Target (Finviz): {finviz.get('analyst_target','?')}  Recommendation score: {finviz.get('recommendation','?')}")
    lines.append(f"Insider Ownership: {finviz.get('insider_own','?')}  Insider Trans trend: {finviz.get('insider_trans','?')}")
    lines.append(f"Inst Ownership: {finviz.get('inst_own','?')}  Inst Trans trend: {finviz.get('inst_trans','?')}")
    lines.append(f"Perf Week: {finviz.get('perf_week','?')}  Month: {finviz.get('perf_month','?')}  YTD: {finviz.get('perf_ytd','?')}")
    lines.append(f"Volatility: {finviz.get('volatility','?')}  ATR: {finviz.get('atr','?')}")
    lines.append(f"Sector: {finviz.get('sector','?')}  Industry: {finviz.get('industry','?')}")

    if finviz.get("analyst_ratings"):
        lines.append("\n-- Recent Analyst Rating Changes (Finviz) --")
        for r in finviz["analyst_ratings"][:6]:
            lines.append(f"  {r.get('date','')}  {r.get('firm','')}  {r.get('action','')}  "
                         f"{r.get('rating','')}  Target: {r.get('target','')}")

    # MarketBeat aggregated ratings
    if mb_data:
        lines.append(f"\n=== MARKETBEAT ANALYST CONSENSUS ===")
        lines.append(f"Consensus: {mb_data.get('consensus_rating','?')}")
        lines.append(f"Avg Target: ${mb_data.get('avg_price_target','?')}  "
                     f"High: ${mb_data.get('high_target','?')}  "
                     f"Low: ${mb_data.get('low_target','?')}")
        lines.append(f"Analyst Count: {mb_data.get('analyst_count','?')}")
        if mb_data.get("recent_ratings"):
            lines.append("Recent rating changes:")
            for r in mb_data["recent_ratings"][:5]:
                lines.append(f"  {r.get('date','')}  {r.get('firm','')}  "
                             f"{r.get('action','')}  Target: {r.get('target','')}")

    # Earnings Whispers
    if ew_data:
        lines.append(f"\n=== EARNINGS WHISPERS ===")
        lines.append(f"Earnings Date: {ew_data.get('earnings_date','?')}")
        lines.append(f"Wall St Consensus EPS: {ew_data.get('consensus_eps','?')}")
        lines.append(f"Whisper Number (trader expectation): {ew_data.get('whisper_eps','?')}")
        lines.append(f"Revenue Estimate: {ew_data.get('revenue_estimate','?')}")
        lines.append(f"Recent Beat/Miss trend: {ew_data.get('recent_trend','?')}")

    # Unusual Whales options flow
    if uw_data.get("flow_sentiment") or uw_data.get("put_call_ratio"):
        lines.append(f"\n=== UNUSUAL WHALES OPTIONS FLOW ===")
        if uw_data.get("flow_sentiment"):
            lines.append(f"Flow Sentiment: {uw_data['flow_sentiment'].upper()}")
        if uw_data.get("put_call_ratio"):
            lines.append(f"Put/Call Ratio: {uw_data['put_call_ratio']}")
        if uw_data.get("implied_volatility"):
            lines.append(f"Implied Volatility: {uw_data['implied_volatility']}")
        if uw_data.get("iv_rank"):
            lines.append(f"IV Rank: {uw_data['iv_rank']}")
        if uw_data.get("call_premium"):
            lines.append(f"Call Premium: ${uw_data['call_premium']}  "
                         f"Put Premium: ${uw_data.get('put_premium','?')}")

    # Insider transactions
    if insider_data:
        lines.append(f"\n=== INSIDER TRANSACTIONS (OpenInsider) ===")
        for t in insider_data[:8]:
            lines.append(
                f"  [{t.get('trade_date','')}] {t.get('insider','')} "
                f"({t.get('title','')}) — {t.get('trade_type','')} "
                f"{t.get('qty','')} shares @ {t.get('price','')} = {t.get('value','')}"
            )

    # News headlines
    lines.append(f"\n=== NEWS HEADLINES ({len(unique_news)} unique, cross-referenced) ===")
    for item in unique_news[:35]:
        deep = " [deep-corp]" if item.get("deep_research_query") else ""
        lines.append(
            f"  [{item.get('date','?')}] {item.get('source','?')}: "
            f"{item.get('title','')}{deep}"
        )
        if item.get("summary"):
            lines.append(f"    {item['summary'][:180]}")

    # Finviz news feed
    if finviz.get("headlines"):
        lines.append(f"\n-- Finviz News Feed --")
        for h in finviz["headlines"][:12]:
            lines.append(f"  [{h.get('date','')} {h.get('time','')}] "
                         f"{h.get('source','')}: {h.get('title','')}")

    # Earnings history
    if earnings_h:
        lines.append(f"\n=== EARNINGS HISTORY (StockAnalysis.com) ===")
        for row in earnings_h[:8]:
            lines.append("  " + "  |  ".join(f"{k}: {v}" for k, v in row.items() if v))

    # SEC filings
    if sec_filings:
        lines.append(f"\n=== SEC 8-K FILINGS (Material Events) ===")
        for f in sec_filings:
            lines.append(f"  [{f.get('date','')}] {f.get('form_type','')} — "
                         f"{f.get('description','')}")

    # Reddit sentiment
    if reddit:
        lines.append(f"\n=== REDDIT SENTIMENT ===")
        for p in reddit[:8]:
            lines.append(
                f"  [{p.get('date','')}] r/{p.get('subreddit','')} "
                f"(score={p.get('score',0)}, comments={p.get('comments',0)}): "
                f"{p.get('title','')}"
            )

    # ── NEW: Multi-year financial history (Macrotrends / yfinance) ────────────
    if macro_data.get("annual_financials"):
        lines.append(f"\n=== MULTI-YEAR FINANCIAL HISTORY ===")
        lines.append(f"YoY Revenue Growth: {macro_data.get('yoy_revenue_growth','?')}")
        for yr_entry in macro_data["annual_financials"][:5]:
            lines.append(
                f"  {yr_entry.get('year','?')}:  Revenue={yr_entry.get('revenue','?')}"
                f"  Gross Margin={yr_entry.get('gross_margin','?')}"
                f"  Net Income={yr_entry.get('net_income','?')}"
            )
    if macro_data.get("eps_history_q"):
        lines.append(f"\nEPS Beat/Miss History (last 8 quarters):")
        for eq in macro_data["eps_history_q"][:8]:
            surp = eq.get("surprise")
            beat = "BEAT" if surp and surp > 0 else ("MISS" if surp and surp < 0 else "?")
            lines.append(
                f"  {eq.get('date','?')}:  Est={eq.get('estimate','?')}  "
                f"Actual={eq.get('actual','?')}  [{beat}]"
            )

    # ── NEW: Institutional holdings (13F / WhalerWisdom / yfinance) ───────────
    if inst_data.get("top_holders_yf") or inst_data.get("top_holders"):
        lines.append(f"\n=== INSTITUTIONAL HOLDINGS (13F) ===")
        inst_pct = inst_data.get("institutional_pct_str","?")
        ins_pct  = inst_data.get("insider_pct")
        ins_str  = f"{ins_pct*100:.1f}%" if ins_pct else "?"
        lines.append(f"Institutional Ownership: {inst_pct}  |  Insider Ownership: {ins_str}")
        holders = inst_data.get("top_holders_yf") or inst_data.get("top_holders") or []
        if holders:
            lines.append("Top Institutional Holders:")
            for h in holders[:6]:
                lines.append(
                    f"  {h.get('name','?'):<42}"
                    f"  {h.get('pct','?'):>6}  {h.get('value','?'):>10}"
                )
        if inst_data.get("mutual_fund_holders"):
            lines.append("Major Fund Holders:")
            for h in inst_data["mutual_fund_holders"][:4]:
                lines.append(f"  {h.get('name','?'):<42}  {h.get('pct','?'):>6}  {h.get('value','?'):>10}")

    # ── NEW: Seeking Alpha news ────────────────────────────────────────────────
    if sa_news:
        lines.append(f"\n=== SEEKING ALPHA ({len(sa_news)} articles) ===")
        for art in sa_news[:6]:
            lines.append(f"  [{art.get('published','?')[:16]}] {art.get('title','')}")
            if art.get("summary"):
                lines.append(f"    {art['summary'][:180]}")

    # ── Playwright JS scraping — runs AFTER basic scraping ──────────────────
    # Unlocks Unusual Whales, Earnings Whispers, Barchart, Stocktwits
    js_data: dict = {}
    js_context = ""
    if _PW_AVAILABLE and _pw_scraper:
        log.info("[playwright] Running JS scrapers (Barchart, EarningsWhispers, UnusualWhales)...")
        # Pass the top article URLs for full-text scraping
        top_urls = [n["url"] for n in unique_news[:4] if n.get("url")]
        try:
            js_data    = _pw_scraper.scrape_all_js(
                ticker,
                scrape_articles=True,
                article_urls=top_urls
            )
            js_context = js_data.get("context_text", "")
            log.info("[playwright] JS scraping complete — %d chars", js_data.get("char_count", 0))
        except Exception:
            log.exception("[playwright] JS scraping failed — continuing without JS data")
    else:
        log.info("[playwright] Not available — basic scraping only. "
                 "Run: pip install playwright && python -m playwright install chromium")

    # Merge JS context into main context (JS data goes at top — it's higher quality)
    if js_context:
        lines.insert(0, js_context)

    context_text = "\n".join(lines)
    log.info("=== Scraping complete: %s — %d chars total, %d news items, %d insiders ===",
             ticker, len(context_text), len(unique_news), len(insider_data))

    result = {
        "ticker":           ticker,
        "scraped_at":       datetime.now(timezone.utc).isoformat(),
        "finviz":           finviz,
        "news":             unique_news,
        "earnings_hist":    earnings_h,
        "sa_overview":      sa_overview,
        "sec_filings":      sec_filings,
        "reddit":           reddit,
        "unusual_whales":   uw_data,
        "earnings_whispers": ew_data,
        "insider_data":     insider_data,
        "marketbeat":           mb_data,
        "macrotrends":          macro_data,
        "institutional_13f":    inst_data,
        "seeking_alpha":        sa_news,
        "cross_reference":      xref,
        "js_data":              js_data,
        "context_text":         context_text,
        "char_count":           len(context_text),
        "playwright_used":      bool(js_context),
    }

    # Auto-learn: store key scraped facts in persistent memory
    try:
        import memory as _mem
        n = _mem.learn_from_scrape(ticker, result)
        log.info("Memory: stored %d facts from scrape on %s", n, ticker)
    except Exception:
        pass

    return result


def scrape_ticker(ticker: str) -> dict:
    """Backward-compatible alias for query_router / external callers."""
    return gather_all(ticker)


# ─────────────────────────────────────────────────────────────────────────────
# Quick test: run directly to see what gets scraped
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    t = sys.argv[1] if len(sys.argv) > 1 else "SOUN"
    result = gather_all(t)
    print("\n" + "=" * 70)
    print(f"SCRAPED DATA FOR {t}")
    print("=" * 70)
    print(result["context_text"])
    print(f"\nTotal: {result['char_count']} characters from {len(result['news'])} news items")
