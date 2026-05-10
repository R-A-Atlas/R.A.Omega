#!/usr/bin/env python3
"""
stock_universe.py — ATLAS Progressive Universe Scanner
========================================================
No paid API. No screener subscription. Everything is scraped free.

HOW IT WORKS — 4 progressive passes (funnel logic):
─────────────────────────────────────────────────────
PASS 1 │ Universe Pull   │ Scrape Finviz free screener → 200-500 tickers
       │                 │ Also pulls from StockAnalysis trending lists
       │                 │ Organized by theme: AI, biotech, energy, small-cap, etc.
       ▼
PASS 2 │ Fast Filter     │ yfinance quick stats on all 200+ (parallel, ~30s)
       │                 │ Kills: low volume, no price movement, broken data
       │                 │ Output: 40-60 candidates
       ▼
PASS 3 │ Signal Filter   │ Checks RSI, relative volume, short float, price trend
       │                 │ Bonus points for: upcoming earnings, recent news velocity
       │                 │ Output: 10-20 high-probability setups
       ▼
PASS 4 │ Deep Rank       │ Feeds survivors into multi_ranker → full ATLAS score
       │                 │ Output: top 5-10 with entry/target/stop + options ideas

THEMES SUPPORTED (via Finviz screener params):
  - ai_tech        → AI, ML, cloud, data companies
  - biotech        → FDA catalysts, clinical trials
  - energy         → oil, gas, solar, nuclear
  - squeeze        → high short float + momentum
  - penny          → under $5, high volume
  - momentum       → RSI breakout, relative volume spike
  - dividend       → yield + stability
  - small_cap      → $50M-$2B market cap
  - all_market     → broad scan, no filter (slowest, most comprehensive)

USAGE:
  from stock_universe import run_progressive_scan
  results = run_progressive_scan(theme="ai_tech", budget=1000, top_n=5)
  
  # Or from command line:
  python stock_universe.py --theme squeeze --budget 500 --top 5
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent / "reports"
_REPORTS_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Shared session — mimics browser to avoid bot detection
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
    "Referer": "https://finviz.com/",
})


# ─────────────────────────────────────────────────────────────────────────────
# PASS 1: UNIVERSE PULL — Finviz Free Screener + supplemental lists
# ─────────────────────────────────────────────────────────────────────────────

# Finviz screener filter sets by theme.
# All free, no login required.
# Format: finviz.com/screener.ashx?v=111&f=<filters>&o=<sort>
_FINVIZ_THEMES: dict[str, dict] = {
    "ai_tech": {
        "filters": "ind_softwareapplication,ind_semiconductors,sh_avgvol_o300",
        "order": "-change",
        "description": "AI, software, semiconductors — high volume movers",
    },
    "biotech": {
        "filters": "ind_biotechnology,ind_drugmanufacturers,sh_avgvol_o300",
        "order": "-change",
        "description": "Biotech + pharma — catalyst-driven",
    },
    "energy": {
        "filters": "ind_oilgase&p,ind_oilgasintegrated,ind_utilities,sh_avgvol_o200",
        "order": "-change",
        "description": "Energy sector — oil, gas, utilities",
    },
    "squeeze": {
        "filters": "sh_short_o20,sh_avgvol_o500,sh_price_u50",
        "order": "-shortfloat",
        "description": "Short squeeze setups — high short float + volume",
    },
    "penny": {
        "filters": "sh_price_u5,sh_avgvol_o1000",
        "order": "-change",
        "description": "Penny stocks — under $5, high relative volume",
    },
    "momentum": {
        "filters": "ta_rsi_nos50,sh_avgvol_o500,sh_relvol_o1.5",
        "order": "-relvol",
        "description": "Momentum breakouts — RSI above 50, relative volume spike",
    },
    "dividend": {
        "filters": "fa_div_o3,sh_avgvol_o200,fa_pb_u3",
        "order": "-dividendyield",
        "description": "Dividend plays — yield >3%, solid book value",
    },
    "small_cap": {
        "filters": "cap_small,sh_avgvol_o300",
        "order": "-change",
        "description": "Small caps $50M-$2B — most volatile, highest upside",
    },
    "all_market": {
        "filters": "sh_avgvol_o500",
        "order": "-change",
        "description": "Broad market scan — all sectors, high volume only",
    },
}

# Price range buckets for progressive breakdowns
_PRICE_BUCKETS = {
    "penny":      (0.01,  5.0),
    "low_entry":  (5.0,   20.0),
    "mid":        (20.0,  100.0),
    "high":       (100.0, 9999.0),
}

# Supplemental curated universe lists (when Finviz is blocked or slow)
_BACKUP_UNIVERSE: dict[str, list[str]] = {
    "ai_tech": [
        # Large AI / semis
        "NVDA", "AMD", "INTC", "QCOM", "AVGO", "MRVL", "ARM", "TSM", "AMAT", "LRCX",
        # AI software & cloud
        "MSFT", "GOOGL", "META", "AMZN", "ORCL", "CRM", "SNOW", "DDOG", "PLTR", "AI",
        # Smaller AI plays
        "SOUN", "IONQ", "BBAI", "GFAI", "ARQQ", "QBTS", "RGTI", "AAON", "PEGA", "UPST",
        # ETFs for comparison
        "SMH", "SOXX", "BOTZ", "QQQ", "XLK",
    ],
    "biotech": [
        "MRNA", "BNTX", "BIIB", "GILD", "REGN", "VRTX", "BMRN", "ALNY", "INCY",
        "SAVA", "ACAD", "AXSM", "SAGE", "PRAX", "ARQT", "DAWN", "KYMR", "BEAM",
        "IBB", "XBI",
    ],
    "squeeze": [
        "GME", "AMC", "MARA", "RIOT", "CIFR", "BTBT", "HUT", "CLSK",
        "SOUN", "IONQ", "ASTS", "RKLB", "ACHR", "JOBY",
        "RZLV", "NKLA", "BLNK", "CHPT", "HYLN",
        "BBIG", "CENN", "MULN", "GOEV", "ARVL",
    ],
    "penny": [
        "SOUN", "GFAI", "BBAI", "MULN", "NKLA", "CENN", "GOEV", "HYLN",
        "CLNE", "RIDE", "WKHS", "XPEV", "NIO", "LI", "BLNK", "CHPT",
        "MVIS", "IDEANOMICS", "CYCC", "HLTH",
    ],
    "energy": [
        "XOM", "CVX", "COP", "EOG", "PXD", "OXY", "SLB", "HAL",
        "FSLR", "ENPH", "SEDG", "RUN", "CSIQ", "SPWR",
        "CCJ", "UEC", "DNN", "URG",
        "XLE", "XOP", "TAN", "URA",
    ],
    "small_cap": [
        "SOUN", "IONQ", "ASTS", "RKLB", "RZLV", "ACHR", "JOBY",
        "MARA", "RIOT", "CIFR", "ARQQ", "QBTS", "RGTI", "BBAI",
        "APLD", "BTDR", "CORZ", "IREN", "WULF",
        "IWM",  # small cap ETF as benchmark
    ],
    "all_market": [],  # will be built dynamically
}


def pull_finviz_universe(theme: str = "all_market", max_pages: int = 5) -> list[dict]:
    """
    Scrape Finviz free screener for a given theme.
    Returns list of {ticker, price, change, volume, market_cap, sector} dicts.
    Paginates up to max_pages (20 tickers per page = up to 100 per call).
    """
    cfg = _FINVIZ_THEMES.get(theme, _FINVIZ_THEMES["all_market"])
    results: list[dict] = []

    for page_num in range(max_pages):
        row_start = 1 + page_num * 20
        url = (
            f"https://finviz.com/screener.ashx"
            f"?v=111"
            f"&f={cfg['filters']}"
            f"&o={cfg['order']}"
            f"&r={row_start}"
        )
        try:
            resp = _SESSION.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Finviz screener table — find rows with ticker data
            table = soup.find("table", {"id": "screener-views-table"})
            if not table:
                # Try alternate table structure
                table = soup.find("table", class_="screener_table")
            if not table:
                # Find by looking for ticker links
                ticker_links = soup.select("a.screener-link-primary")
                if not ticker_links:
                    log.debug("[universe] No ticker links found on page %d for theme '%s'", page_num + 1, theme)
                    break
                for link in ticker_links:
                    ticker = link.get_text(strip=True)
                    if ticker and re.match(r'^[A-Z]{1,5}$', ticker):
                        results.append({"ticker": ticker, "source": "finviz"})
                time.sleep(0.5)
                continue

            rows = table.find_all("tr")
            found_on_page = 0
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 11:
                    continue
                ticker_cell = row.find("a", class_="screener-link-primary")
                if not ticker_cell:
                    continue
                ticker = ticker_cell.get_text(strip=True)
                if not ticker or not re.match(r'^[A-Z]{1,5}$', ticker):
                    continue

                def _safe(idx: int) -> str:
                    try:
                        return cells[idx].get_text(strip=True)
                    except Exception:
                        return ""

                results.append({
                    "ticker":     ticker,
                    "company":    _safe(1),
                    "sector":     _safe(2),
                    "price":      _safe(8),
                    "change":     _safe(9),
                    "volume":     _safe(10),
                    "source":     "finviz",
                })
                found_on_page += 1

            log.info("[universe] Finviz page %d: found %d tickers (theme=%s)", page_num + 1, found_on_page, theme)
            if found_on_page < 19:
                break  # Last page

            time.sleep(0.8)  # Polite rate limit

        except Exception as e:
            log.warning("[universe] Finviz page %d failed: %s", page_num + 1, e)
            break

    # Deduplicate
    seen: set[str] = set()
    unique = []
    for r in results:
        t = r["ticker"]
        if t not in seen:
            seen.add(t)
            unique.append(r)

    log.info("[universe] Finviz pull complete: %d unique tickers for theme '%s'", len(unique), theme)
    return unique


def get_universe(theme: str = "all_market", max_tickers: int = 200) -> list[str]:
    """
    Get a broad universe of tickers for a theme.
    Tries Finviz first, falls back to curated backup list.
    Returns a flat list of ticker strings.
    """
    # Try live Finviz pull
    pages_needed = min(10, max(1, max_tickers // 20))
    live = pull_finviz_universe(theme, max_pages=pages_needed)

    tickers = [r["ticker"] for r in live]

    # Supplement with backup list (add any not already included)
    backup = _BACKUP_UNIVERSE.get(theme, [])
    for t in backup:
        if t not in tickers:
            tickers.append(t)

    # For all_market, also merge backups from all themes
    if theme == "all_market" and len(tickers) < 50:
        for _, btickers in _BACKUP_UNIVERSE.items():
            for t in btickers:
                if t not in tickers:
                    tickers.append(t)

    log.info("[universe] Final universe: %d tickers for theme '%s'", len(tickers), theme)
    return tickers[:max_tickers]


# ─────────────────────────────────────────────────────────────────────────────
# PASS 2: FAST FILTER — parallel yfinance quick stats
# ─────────────────────────────────────────────────────────────────────────────

def _quick_stats(ticker: str) -> Optional[dict]:
    """
    Fetch minimal yfinance stats for one ticker.
    Returns None if the ticker is dead/broken/illiquid.
    Fast: only fetches .info and 5 days of history.
    """
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        price = float(info.get("regularMarketPrice") or info.get("currentPrice") or 0)
        if price <= 0:
            return None

        avg_vol = float(info.get("averageVolume") or 0)
        vol     = float(info.get("volume") or 0)
        mkt_cap = float(info.get("marketCap") or 0)

        if avg_vol < 50_000:  # too illiquid to trade
            return None

        rvol  = vol / avg_vol if avg_vol else 1.0
        sf    = float(info.get("shortPercentOfFloat") or 0) * 100  # as %
        beta  = float(info.get("beta") or 1.0)
        sector = info.get("sector", "Unknown")

        # Quick RSI from 14-day history
        hist = tk.history(period="14d")
        rsi = None
        if not hist.empty and len(hist) >= 5:
            closes = hist["Close"].tolist()
            diffs  = [closes[i+1] - closes[i] for i in range(len(closes)-1)]
            gains  = [max(d, 0) for d in diffs]
            losses = [abs(min(d, 0)) for d in diffs]
            ag = sum(gains) / len(gains) if gains else 0
            al = sum(losses) / len(losses) if losses else 0
            rsi = round(100 - (100 / (1 + ag / al)), 1) if al > 0 else 100.0

        # 5-day price change
        change_5d = None
        if not hist.empty and len(hist) >= 2:
            change_5d = round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)

        return {
            "ticker":    ticker,
            "price":     round(price, 4),
            "price_bucket": _price_bucket(price),
            "avg_vol":   int(avg_vol),
            "volume":    int(vol),
            "rvol":      round(rvol, 2),
            "mkt_cap":   mkt_cap,
            "mkt_cap_b": round(mkt_cap / 1e9, 3),
            "short_float": round(sf, 1),
            "beta":      beta,
            "sector":    sector,
            "rsi":       rsi,
            "change_5d": change_5d,
        }
    except Exception as e:
        log.debug("[quick_stats] %s failed: %s", ticker, e)
        return None


def _price_bucket(price: float) -> str:
    for name, (lo, hi) in _PRICE_BUCKETS.items():
        if lo <= price < hi:
            return name
    return "high"


def fast_filter(tickers: list[str], max_workers: int = 20) -> list[dict]:
    """
    PASS 2: Run _quick_stats on all tickers in parallel.
    Filters out dead/illiquid stocks.
    Returns sorted list of stat dicts (by relative volume, descending).
    """
    log.info("[pass2] Fast filtering %d tickers (parallel, workers=%d)...", len(tickers), max_workers)
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_quick_stats, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                stat = fut.result(timeout=15)
                if stat:
                    results.append(stat)
            except Exception as e:
                log.debug("[pass2] %s: %s", ticker, e)

    results.sort(key=lambda x: x.get("rvol", 0), reverse=True)
    log.info("[pass2] After fast filter: %d live tickers from %d", len(results), len(tickers))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PASS 3: SIGNAL FILTER — score each candidate, keep the best
# ─────────────────────────────────────────────────────────────────────────────

def signal_score(stat: dict) -> float:
    """
    Quick composite score (0-100) using only the data already in stat dict.
    Purpose: narrow 40-60 → 10-20 candidates for deep research.
    NOT the same as the full multi_ranker score — this is the fast pre-filter.
    """
    score = 0.0

    # Relative volume (most important fast signal — something is happening)
    rvol = stat.get("rvol", 1.0)
    if rvol >= 5.0:   score += 30
    elif rvol >= 3.0: score += 22
    elif rvol >= 2.0: score += 14
    elif rvol >= 1.5: score += 8
    else:             score += 2

    # RSI positioning (looking for setups, not extended)
    rsi = stat.get("rsi")
    if rsi is not None:
        if 45 <= rsi <= 65:   score += 20   # sweet spot: momentum building but not overbought
        elif 35 <= rsi < 45:  score += 15   # oversold recovery potential
        elif 65 < rsi <= 75:  score += 10   # strong but watch for reversal
        elif rsi > 75:        score += 4    # overbought
        elif rsi < 35:        score += 6    # deeply oversold — bounce watch

    # Short float (squeeze fuel)
    sf = stat.get("short_float", 0)
    if sf >= 30:   score += 20
    elif sf >= 20: score += 14
    elif sf >= 10: score += 7
    else:          score += 1

    # Price action momentum (5-day change)
    ch5 = stat.get("change_5d", 0) or 0
    if ch5 >= 15:   score += 15
    elif ch5 >= 7:  score += 10
    elif ch5 >= 3:  score += 6
    elif ch5 >= 0:  score += 3
    elif ch5 < -10: score += 4  # oversold bounce watch
    else:           score += 1

    # Price bucket bonus (low-entry stocks have more room / retail interest)
    bucket = stat.get("price_bucket", "mid")
    if bucket == "penny":     score += 5
    elif bucket == "low_entry": score += 8
    elif bucket == "mid":     score += 4
    # high: no bonus (still valid but harder for small accounts)

    # Small-mid cap bonus (more volatile, more upside)
    cap = stat.get("mkt_cap_b", 10)
    if cap < 0.5:    score += 5  # micro cap — explosive but risky
    elif cap < 2.0:  score += 8  # small cap
    elif cap < 10.0: score += 4  # mid cap

    return round(min(score, 100), 1)


def signal_filter(stats: list[dict], top_n: int = 20, price_min: float = 0.10,
                  price_max: float = 9999.0) -> list[dict]:
    """
    PASS 3: Score and rank candidates, apply price range filter, return top_n.
    price_min / price_max: optional filter to focus on a price range.
    """
    filtered = [
        s for s in stats
        if price_min <= s.get("price", 0) <= price_max
    ]

    for s in filtered:
        s["signal_score"] = signal_score(s)

    filtered.sort(key=lambda x: x.get("signal_score", 0), reverse=True)
    top = filtered[:top_n]

    log.info("[pass3] Signal filter: %d → top %d candidates", len(filtered), len(top))
    for s in top[:5]:
        log.info("  %s  $%.2f  rvol=%.1fx  rsi=%s  sf=%.0f%%  score=%.0f  [%s]",
                 s["ticker"], s["price"], s["rvol"],
                 s.get("rsi", "?"), s.get("short_float", 0),
                 s["signal_score"], s.get("price_bucket", "?"))

    return top


# ─────────────────────────────────────────────────────────────────────────────
# PASS 4: DEEP RANK — feed survivors into multi_ranker
# ─────────────────────────────────────────────────────────────────────────────

def deep_rank(candidates: list[dict], budget: float = 1000.0,
              top_n: int = 5, delay: float = 3.0) -> list[dict]:
    """
    PASS 4: Run full multi_ranker on top candidates.
    Merges the multi_ranker results with our signal_score context.
    """
    try:
        import multi_ranker as mr
    except ImportError:
        log.error("[pass4] multi_ranker.py not found")
        # Return candidates with signal scores as fallback
        return candidates[:top_n]

    tickers = [c["ticker"] for c in candidates]
    signal_map = {c["ticker"]: c for c in candidates}

    log.info("[pass4] Deep ranking %d tickers...", len(tickers))
    ranked = mr.rank_tickers(tickers, budget=budget, delay_between=delay)

    # Enrich with our signal context
    for r in ranked:
        t = r["ticker"]
        if t in signal_map:
            s = signal_map[t]
            r["signal_score"] = s.get("signal_score", 0)
            r["price"]        = s.get("price")
            r["price_bucket"] = s.get("price_bucket")
            r["rvol"]         = s.get("rvol")
            r["rsi"]          = s.get("rsi")
            r["short_float"]  = s.get("short_float")
            r["mkt_cap_b"]    = s.get("mkt_cap_b")
            r["change_5d"]    = s.get("change_5d")

    return ranked[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT — run_progressive_scan()
# ─────────────────────────────────────────────────────────────────────────────

def run_progressive_scan(
    theme: str = "all_market",
    budget: float = 1000.0,
    top_n: int = 5,
    price_min: float = 0.10,
    price_max: float = 9999.0,
    universe_size: int = 200,
    pass3_candidates: int = 15,
    skip_deep_rank: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run the full 4-pass progressive scan.
    
    Args:
        theme:             Scan theme (see _FINVIZ_THEMES keys)
        budget:            Dollar amount to allocate (used in deep rank sizing)
        top_n:             Final number of recommendations
        price_min:         Min stock price filter (e.g. 1.0 for pennies and up)
        price_max:         Max stock price filter (e.g. 50.0 for low-entry only)
        universe_size:     How many tickers to pull in pass 1 (more = slower but broader)
        pass3_candidates:  How many to send to deep rank
        skip_deep_rank:    If True, stop at pass 3 (faster, less accurate)
        verbose:           Print progress to console
    
    Returns dict with:
        theme, budget, passes, final_recommendations, timing
    """
    start = time.time()
    timing: dict[str, float] = {}
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"  ATLAS PROGRESSIVE SCAN — Theme: {theme.upper()}")
        print(f"  Budget: ${budget:,.0f}  |  Price range: ${price_min}–${price_max}")
        print(f"{'='*60}")

    # ── PASS 1: Universe Pull ─────────────────────────────────────────────────
    t0 = time.time()
    if verbose:
        print(f"\n[PASS 1] Pulling universe (target: {universe_size} tickers)...")
    
    raw_universe = get_universe(theme, max_tickers=universe_size)
    timing["pass1_s"] = round(time.time() - t0, 1)
    
    if verbose:
        print(f"  → {len(raw_universe)} tickers from {theme} universe  ({timing['pass1_s']}s)")

    if not raw_universe:
        return {"error": "Could not build universe — check internet connection", "theme": theme}

    # ── PASS 2: Fast Filter ───────────────────────────────────────────────────
    t0 = time.time()
    if verbose:
        print(f"\n[PASS 2] Fast-filtering {len(raw_universe)} tickers (parallel yfinance)...")

    stats = fast_filter(raw_universe, max_workers=min(len(raw_universe), 25))
    timing["pass2_s"] = round(time.time() - t0, 1)

    if verbose:
        print(f"  → {len(stats)} live, liquid tickers  ({timing['pass2_s']}s)")
        # Show price bucket breakdown
        buckets: dict[str, int] = {}
        for s in stats:
            b = s.get("price_bucket", "?")
            buckets[b] = buckets.get(b, 0) + 1
        bucket_str = "  ".join(f"{k}({v})" for k, v in sorted(buckets.items()))
        print(f"  Buckets: {bucket_str}")

    if not stats:
        return {"error": "All tickers failed fast filter", "theme": theme}

    # ── PASS 3: Signal Filter ─────────────────────────────────────────────────
    t0 = time.time()
    if verbose:
        print(f"\n[PASS 3] Signal scoring → selecting top {pass3_candidates} setups...")

    top_candidates = signal_filter(
        stats,
        top_n=pass3_candidates,
        price_min=price_min,
        price_max=price_max,
    )
    timing["pass3_s"] = round(time.time() - t0, 1)

    if verbose:
        print(f"  → {len(top_candidates)} candidates selected  ({timing['pass3_s']}s)")
        print(f"\n  Top candidates by signal score:")
        for i, c in enumerate(top_candidates[:10]):
            print(f"    {i+1:2}. {c['ticker']:<7} ${c['price']:>8.2f}  "
                  f"rvol={c.get('rvol','?'):.1f}x  "
                  f"rsi={str(c.get('rsi','?')):<6}  "
                  f"sf={c.get('short_float',0):.0f}%  "
                  f"5d={c.get('change_5d','?')}%  "
                  f"signal={c.get('signal_score',0):.0f}  [{c.get('price_bucket','?')}]")

    if skip_deep_rank or not top_candidates:
        timing["total_s"] = round(time.time() - start, 1)
        return {
            "theme":         theme,
            "budget":        budget,
            "universe_size": len(raw_universe),
            "pass2_survived": len(stats),
            "pass3_top":     top_candidates,
            "final_recommendations": top_candidates[:top_n],
            "timing":        timing,
            "note":          "Deep rank skipped (skip_deep_rank=True)",
        }

    # ── PASS 4: Deep Rank ─────────────────────────────────────────────────────
    t0 = time.time()
    if verbose:
        print(f"\n[PASS 4] Deep ranking top {len(top_candidates)} with full ATLAS analysis...")
        print(f"  (This takes ~{len(top_candidates) * 5}s — each ticker gets full research)")

    final = deep_rank(top_candidates, budget=budget, top_n=top_n)
    timing["pass4_s"] = round(time.time() - t0, 1)
    timing["total_s"] = round(time.time() - start, 1)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  FINAL TOP {top_n} PICKS  (total: {timing['total_s']}s)")
        print(f"{'='*60}")
        for r in final:
            price_str = f"${r.get('price', '?')}"
            print(f"  #{r.get('rank',0)}  {r['ticker']:<7}  "
                  f"{r.get('grade','?')}  {r.get('score',0):.0f}/100  "
                  f"Action: {r.get('action','?')}  "
                  f"Entry: {r.get('entry','?')}  "
                  f"Target: {r.get('target_1','?')}  "
                  f"Stop: {r.get('stop','?')}  "
                  f"Price: {price_str}  [{r.get('price_bucket','?')}]")
            if r.get("summary"):
                print(f"         {r['summary'][:80]}")

    return {
        "theme":               theme,
        "budget":              budget,
        "universe_size":       len(raw_universe),
        "pass2_survived":      len(stats),
        "pass3_candidates":    top_candidates,
        "final_recommendations": final,
        "timing":              timing,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION: hook into atlas_omega.py discovery queries
# ─────────────────────────────────────────────────────────────────────────────

def omega_discovery_to_scan_params(query: str, dollar_amount: float = 1000.0) -> dict:
    """
    Convert an Omega discovery query into scan parameters.
    Called by atlas_omega.py when it detects a discovery/allocation question.
    """
    ql = query.lower()

    # Theme detection
    if any(k in ql for k in ("ai", "artificial intelligence", "machine learning", "llm", "chip", "semi")):
        theme = "ai_tech"
    elif any(k in ql for k in ("bio", "biotech", "fda", "drug", "pharma", "clinical")):
        theme = "biotech"
    elif any(k in ql for k in ("energy", "oil", "gas", "solar", "nuclear", "uranium")):
        theme = "energy"
    elif any(k in ql for k in ("squeeze", "short", "reddit", "wsb", "meme")):
        theme = "squeeze"
    elif any(k in ql for k in ("penny", "cheap", "low price", "under $5", "under 5")):
        theme = "penny"
    elif any(k in ql for k in ("momentum", "breakout", "rsi", "trend")):
        theme = "momentum"
    elif any(k in ql for k in ("dividend", "yield", "income")):
        theme = "dividend"
    elif any(k in ql for k in ("small cap", "small-cap", "micro", "growth")):
        theme = "small_cap"
    else:
        theme = "all_market"

    # Price range from query
    price_min, price_max = 0.10, 9999.0
    if "penny" in ql or "under $5" in ql:
        price_max = 5.0
    elif "low entry" in ql or "under $20" in ql or "under 20" in ql:
        price_max = 20.0
    elif "under $50" in ql or "under 50" in ql:
        price_max = 50.0
    elif "over $100" in ql or "over 100" in ql:
        price_min = 100.0

    return {
        "theme":      theme,
        "budget":     dollar_amount,
        "price_min":  price_min,
        "price_max":  price_max,
        "universe_size": 150 if theme == "all_market" else 100,
        "pass3_candidates": 12,
        "top_n": 5,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    parser = argparse.ArgumentParser(description="ATLAS Progressive Universe Scanner")
    parser.add_argument("--theme",   default="momentum",
                        choices=list(_FINVIZ_THEMES.keys()),
                        help="Scan theme")
    parser.add_argument("--budget",  type=float, default=1000.0,
                        help="Dollar amount to allocate")
    parser.add_argument("--top",     type=int,   default=5,
                        help="Number of final recommendations")
    parser.add_argument("--min-price", type=float, default=0.10,
                        help="Minimum stock price filter")
    parser.add_argument("--max-price", type=float, default=9999.0,
                        help="Maximum stock price filter")
    parser.add_argument("--universe", type=int, default=150,
                        help="Universe size (more = slower but broader)")
    parser.add_argument("--fast",    action="store_true",
                        help="Skip deep rank (passes 1-3 only, much faster)")
    args = parser.parse_args()

    print(f"\nAvailable themes:")
    for k, v in _FINVIZ_THEMES.items():
        print(f"  {k:<15} — {v['description']}")

    results = run_progressive_scan(
        theme           = args.theme,
        budget          = args.budget,
        top_n           = args.top,
        price_min       = args.min_price,
        price_max       = args.max_price,
        universe_size   = args.universe,
        skip_deep_rank  = args.fast,
        verbose         = True,
    )

    print(f"\n\nTiming breakdown:")
    for k, v in results.get("timing", {}).items():
        print(f"  {k}: {v}s")
