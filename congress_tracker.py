"""
congress_tracker.py — ATLAS Congressional Trade Intelligence

Politicians legally trade on material non-public information. Their trades
have been independently verified to beat the S&P 500 by a documented margin.
When a senator buys a defense stock two weeks before a DoD contract —
ATLAS sees it now.

Primary source: Capitol Trades (capitoltrades.com) — fully public, no auth needed.
  Scrapes the trades table: 96 trades per page, paginated.

Data extracted per trade:
  Ticker, Politician name, Party (D/R), Chamber (Senate/House),
  Transaction type (buy/sell), Trade date, Amount range, Disclosure lag

ATLAS uses this to:
  - Detect cluster buys (3+ politicians in the same stock = strong signal)
  - Score ticker conviction based on recency, volume, and cluster size
  - Inject context into every deep research synthesis prompt
  - Power `--hot-congress` discovery command (find what pols are buying NOW)
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_CACHE_DIR  = Path(__file__).parent / "congress_cache"
_CACHE_DIR.mkdir(exist_ok=True)
_CACHE_FILE    = _CACHE_DIR / "all_trades.json"
_CACHE_TTL_HRS = 6     # refresh every 6 hours (disclosures update daily)
_MAX_PAGES     = 5     # up to 5 pages × 96 trades = 480 most recent trades

_HEADERS = {
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":           "text/html,application/xhtml+xml",
    "Accept-Language":  "en-US,en;q=0.9",
}

_BASE_URL = "https://www.capitoltrades.com/trades"

# Month abbreviation lookup for date parsing
_MONTHS = {
    "jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
    "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12",
}


# ─────────────────────────────────────────────────────────────────────────────
# Scraping
# ─────────────────────────────────────────────────────────────────────────────
def _parse_date(raw: str) -> str:
    """
    Parse Capitol Trades date strings like '15 Apr 2026', '29 Apr 2026' → 'YYYY-MM-DD'.
    Also handles 'Today' → today's date.
    """
    raw = raw.strip()
    if not raw or raw.lower() == "today":
        return datetime.now().strftime("%Y-%m-%d")
    try:
        # "15 Apr 2026"
        parts = raw.split()
        if len(parts) == 3:
            day   = parts[0].zfill(2)
            month = _MONTHS.get(parts[1].lower()[:3], "01")
            year  = parts[2]
            return f"{year}-{month}-{day}"
    except Exception:
        pass
    return raw[:10]


def _parse_amount(raw: str) -> str:
    """Normalize amount strings like '50K–100K' or '1K–15K'."""
    raw = raw.replace("\u2013", "-").replace("–", "-").replace("\ufffd", "-").strip()
    if not raw or raw == "N/A":
        return "?"
    # Map to dollar brackets
    mapping = {
        "1K-15K":    "$1K–$15K",
        "15K-50K":   "$15K–$50K",
        "50K-100K":  "$50K–$100K",
        "100K-250K": "$100K–$250K",
        "250K-500K": "$250K–$500K",
        "500K-1M":   "$500K–$1M",
        "1M-5M":     "$1M–$5M",
        "5M+":       "$5M+",
    }
    for k, v in mapping.items():
        if k.replace("-","") in raw.replace("-","").replace("–",""):
            return v
    return raw


def _scrape_page(page: int = 1) -> list[dict]:
    """Scrape one page of the Capitol Trades trades table."""
    try:
        # Important: pass pageSize as part of the URL string.
        # Next.js SSR breaks when sortBy or other params with special chars are added via params dict.
        url = f"{_BASE_URL}?pageSize=96"
        r = requests.get(url, headers=_HEADERS, timeout=15)
        if r.status_code != 200:
            log.debug("[congress] Capitol Trades HTTP %d (page %d)", r.status_code, page)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.find_all("tr")
        trades = []

        for row in rows[1:]:  # skip header row
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            # Cell 0: Name | Party | Chamber | State
            c0_parts  = cells[0].get_text(separator="|", strip=True).split("|")
            name      = c0_parts[0].strip() if c0_parts else "Unknown"
            party     = c0_parts[1].strip() if len(c0_parts) > 1 else ""
            chamber   = c0_parts[2].strip() if len(c0_parts) > 2 else ""

            # Cell 1: Company Name | Ticker (e.g. "NVIDIA CORP|NVDA:US")
            c1_parts  = cells[1].get_text(separator="|", strip=True).split("|")
            company   = c1_parts[0].strip() if c1_parts else ""
            ticker_raw = c1_parts[1].strip() if len(c1_parts) > 1 else "N/A"
            # Strip ":US" suffix
            ticker    = ticker_raw.replace(":US", "").replace(":CA","").strip()
            if ticker == "N/A" or not ticker:
                continue  # skip private company trades (no ticker = not tradeable)

            # Cell 3: Trade date
            trade_date_raw = cells[3].get_text(separator=" ", strip=True)
            trade_date     = _parse_date(trade_date_raw)

            # Cell 4: Disclosure lag days
            c4_parts       = cells[4].get_text(separator="|", strip=True).split("|")
            disclose_days  = None
            for p in c4_parts:
                try:
                    disclose_days = int(p.strip())
                    break
                except Exception:
                    pass

            # Cell 6: buy/sell
            tx_raw  = cells[6].get_text(strip=True).lower()
            tx_type = "BUY" if "buy" in tx_raw else ("SELL" if "sell" in tx_raw else tx_raw.upper())

            # Cell 7: amount
            amount = _parse_amount(cells[7].get_text(strip=True))

            # Disclosure date (trade_date + disclose_days)
            disclose_date = ""
            if trade_date and disclose_days is not None:
                try:
                    dt  = datetime.strptime(trade_date, "%Y-%m-%d")
                    disclose_date = (dt + timedelta(days=disclose_days)).strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Normalize chamber
            if "representative" in chamber.lower() or "house" in chamber.lower():
                chamber_norm = "House"
            elif "senator" in chamber.lower() or "senate" in chamber.lower():
                chamber_norm = "Senate"
            else:
                chamber_norm = chamber or "Congress"

            trades.append({
                "ticker":           ticker.upper(),
                "company":          company,
                "name":             name,
                "party":            party,
                "chamber":          chamber_norm,
                "tx_type":          tx_type,
                "tx_date":          trade_date,
                "disclosure_date":  disclose_date,
                "days_to_disclose": disclose_days,
                "amount":           amount,
                "is_option":        False,
                "excess_return":    None,
            })

        return trades

    except Exception as e:
        log.debug("[congress] Scrape failed (page %d): %s", page, e)
        return []


def _load_all_trades(force_refresh: bool = False) -> list[dict]:
    """Load trades from cache or scrape Capitol Trades (up to _MAX_PAGES)."""
    if not force_refresh and _CACHE_FILE.exists():
        age = time.time() - _CACHE_FILE.stat().st_mtime
        if age < _CACHE_TTL_HRS * 3600:
            try:
                data = json.loads(_CACHE_FILE.read_text())
                if data:
                    return data
            except Exception:
                pass

    # Capitol Trades SSR always returns the same ~96 most recent trades
    # regardless of page param — so we just load once.
    all_trades = _scrape_page(1)

    if all_trades:
        _CACHE_FILE.write_text(json.dumps(all_trades))
        log.info("[congress] Capitol Trades: %d public-ticker trades loaded", len(all_trades))
    else:
        log.warning("[congress] No trades scraped — Capitol Trades may be temporarily unavailable")

    if not all_trades:
        try:
            if _CACHE_FILE.exists():
                stale = json.loads(_CACHE_FILE.read_text())
                if isinstance(stale, list) and stale:
                    log.warning(
                        "[congress] Scrape empty — using stale cache (%d trades)",
                        len(stale),
                    )
                    return stale
        except Exception as e:
            log.debug("[congress] Stale cache read failed: %s", e)

    return all_trades


# ─────────────────────────────────────────────────────────────────────────────
# Intelligence functions
# ─────────────────────────────────────────────────────────────────────────────
def get_trades_for_ticker(ticker: str, days_back: int = 180) -> dict:
    """
    Get all Congressional trades for a specific ticker in the last N days.
    Returns: normalized trades, cluster signal, conviction score, context text.
    """
    ticker = ticker.upper().strip()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    trades = [t for t in _load_all_trades()
              if t["ticker"] == ticker and t["tx_date"] >= cutoff]

    result = {
        "ticker":         ticker,
        "trades":         [],
        "cluster_signal": False,
        "conviction":     "NONE",
        "summary":        "",
        "context_text":   f"\nCongressional Trades ({ticker}): No disclosures in last {days_back} days.\n",
    }

    if not trades:
        return result

    trades.sort(key=lambda x: x.get("tx_date", ""), reverse=True)
    result["trades"] = trades[:20]

    buys       = [t for t in trades if t["tx_type"] == "BUY"]
    sells      = [t for t in trades if t["tx_type"] == "SELL"]
    recent_30d = [t for t in trades
                  if t.get("tx_date","") >= (datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d")]

    unique_buyers = set(t["name"] for t in buys)
    cluster_signal = len(unique_buyers) >= 3
    result["cluster_signal"] = cluster_signal

    # Score
    score  = min(len(buys) * 8, 40)
    score += 15 if cluster_signal else 0
    score += 10 if len(recent_30d) >= 2 else (5 if len(recent_30d) == 1 else 0)
    score -= min(len(sells) * 5, 20)
    score = max(0, min(score, 100))

    if   score >= 50: result["conviction"] = "VERY HIGH"
    elif score >= 35: result["conviction"] = "HIGH"
    elif score >= 20: result["conviction"] = "MODERATE"
    elif score >= 5:  result["conviction"] = "LOW"
    else:             result["conviction"] = "NEGATIVE"

    # Context text
    lines = [f"\n=== CONGRESSIONAL TRADES — {ticker} (last {days_back} days) ==="]
    lines.append(
        f"Total: {len(trades)}  |  Buys: {len(buys)}  Sells: {len(sells)}  "
        f"|  Unique buyers: {len(unique_buyers)}"
    )
    lines.append(
        f"Cluster signal: {'YES — ' + str(len(unique_buyers)) + ' politicians buying' if cluster_signal else 'No'}"
    )
    lines.append(f"Congressional conviction: {result['conviction']} (score {score}/100)")
    if recent_30d:
        lines.append(f"Recent 30d activity: {len(recent_30d)} trades")

    lines.append("\nRecent trades (most recent first):")
    for t in trades[:10]:
        party_ch = t.get("party", "?")[:1]
        disclose = f" +{t['days_to_disclose']}d disclose" if t.get("days_to_disclose") else ""
        lines.append(
            f"  {t['tx_date']}  {t['chamber'][:1]}({party_ch})  "
            f"{t['name'][:28]:<28}  {t['tx_type']:<5}  {t['amount']}{disclose}"
        )

    if cluster_signal:
        names_str = ", ".join(sorted(unique_buyers)[:5])
        lines.append(f"\n  CLUSTER ALERT: {len(unique_buyers)} politicians bought — {names_str}")
        lines.append("  Cluster buys are a documented alpha signal. Check for pending legislation,")
        lines.append("  regulatory approvals, DoD contracts, or FDA decisions in this sector.")

    if sells and len(sells) > len(buys):
        lines.append(f"\n  NET SELLING: {len(sells)} sells vs {len(buys)} buys — politicians reducing.")

    lines.append("=== END CONGRESSIONAL DATA ===\n")

    result["summary"]      = (
        f"{len(buys)} buys / {len(sells)} sells | {len(unique_buyers)} unique buyers | "
        f"conviction: {result['conviction']}"
    )
    result["context_text"] = "\n".join(lines)
    log.info("[congress] %s — %d trades, %d buyers, conviction=%s",
             ticker, len(trades), len(unique_buyers), result["conviction"])
    return result


def get_recent_all_trades(top_n: int = 50, days_back: int = 14) -> list[dict]:
    """Get the most recent BUY trades across all tickers."""
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    trades = [t for t in _load_all_trades()
              if t["tx_type"] == "BUY" and t["tx_date"] >= cutoff]
    trades.sort(key=lambda x: x.get("tx_date", ""), reverse=True)
    return trades[:top_n]


def hot_congressional_tickers(days_back: int = 30, min_buys: int = 2) -> list[dict]:
    """Rank tickers by Congressional buying pressure in the last N days."""
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    counts: dict[str, dict] = {}

    for t in _load_all_trades():
        if t["tx_type"] != "BUY" or t["tx_date"] < cutoff:
            continue
        tk = t["ticker"]
        if not tk or len(tk) > 6:
            continue
        if tk not in counts:
            counts[tk] = {"ticker": tk, "buy_count": 0, "buyers": set(), "latest": "", "company": t.get("company","")}
        counts[tk]["buy_count"]  += 1
        counts[tk]["buyers"].add(t["name"])
        if t["tx_date"] > counts[tk]["latest"]:
            counts[tk]["latest"] = t["tx_date"]

    results = []
    for tk, d in counts.items():
        unique = len(d["buyers"])
        if d["buy_count"] < min_buys and unique < 2:
            continue
        results.append({
            "ticker":         tk,
            "company":        d["company"],
            "buy_count":      d["buy_count"],
            "unique_buyers":  unique,
            "latest_date":    d["latest"],
            "cluster_signal": unique >= 3,
            "score":          d["buy_count"] * 5 + unique * 10,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    log.info("[congress] Hot tickers: %d (min_buys=%d, last %dd)", len(results), min_buys, days_back)
    return results[:20]


def render_congress_html(ticker: str) -> str:
    """HTML block for deep research reports."""
    data   = get_trades_for_ticker(ticker)
    trades = data.get("trades", [])
    conv   = data.get("conviction", "NONE")

    color_map = {
        "VERY HIGH": "#4caf50", "HIGH": "#8bc34a",
        "MODERATE": "#ffca28",  "LOW": "#ff9800",
        "NEGATIVE": "#f44336",  "NONE": "#555",
    }
    color = color_map.get(conv, "#888")

    if not trades:
        return (
            f'<div style="background:#0a0e1a;border:1px solid #1e2a3a;border-radius:8px;'
            f'padding:12px;margin:10px 0;font-size:12px;color:#555">'
            f'Congressional Trades ({ticker}): No public-stock disclosures found.</div>'
        )

    rows_html = ""
    for t in trades[:10]:
        party_col  = "#4488ff" if "D" in t.get("party","")[:1] else "#ff6644"
        type_color = "#4caf50" if t["tx_type"] == "BUY" else "#f44336"
        rows_html += (
            f'<tr><td style="padding:4px 8px;border-bottom:1px solid #111a26;font-size:11px;color:#aaa">{t["tx_date"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #111a26;font-size:11px;color:#ccc">{t["name"][:26]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #111a26;font-size:11px;color:{party_col}">{t.get("party","?")[:1]} {t["chamber"][:1]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #111a26;font-size:11px;font-weight:700;color:{type_color}">{t["tx_type"]}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #111a26;font-size:11px;color:#aaa">{t["amount"]}</td></tr>'
        )

    cluster_html = ""
    if data.get("cluster_signal"):
        cluster_html = (
            '<div style="background:#0a2a0a;border:1px solid #2a5a2a;border-radius:6px;'
            'padding:8px 12px;margin-bottom:10px;font-size:12px;color:#9dce9d">'
            f'CLUSTER SIGNAL — Multiple politicians buying {ticker}. '
            'Check for pending legislation, contracts, or regulatory catalysts.</div>'
        )

    return (
        f'<div style="background:#0a0e1a;border:1px solid #1e2a3a;border-radius:8px;padding:14px;margin:10px 0">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:10px">'
        f'<span style="font-size:11px;color:#555;text-transform:uppercase;letter-spacing:1px">Congressional Trades — {ticker}</span>'
        f'<span style="font-size:12px;font-weight:700;color:{color}">Conviction: {conv}</span></div>'
        f'{cluster_html}'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<tr style="background:#141c2e"><th style="padding:4px 8px;text-align:left;font-size:10px;color:#00d4ff">Date</th>'
        f'<th style="padding:4px 8px;text-align:left;font-size:10px;color:#00d4ff">Official</th>'
        f'<th style="padding:4px 8px;text-align:left;font-size:10px;color:#00d4ff">P/Ch</th>'
        f'<th style="padding:4px 8px;text-align:left;font-size:10px;color:#00d4ff">Action</th>'
        f'<th style="padding:4px 8px;text-align:left;font-size:10px;color:#00d4ff">Size</th></tr>'
        f'{rows_html}</table></div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd    = sys.argv[1] if len(sys.argv) > 1 else "hot"
    ticker = sys.argv[2].upper() if len(sys.argv) > 2 else None

    if cmd == "ticker" and ticker:
        data = get_trades_for_ticker(ticker)
        print(data["context_text"])

    elif cmd == "hot":
        print("\nHot Congressional Tickers (last 30 days, min 2 buys):")
        hot = hot_congressional_tickers()
        if not hot:
            print("  No clusters found — try `recent` to see individual trades")
        for h in hot:
            cluster = "  *** CLUSTER" if h["cluster_signal"] else ""
            print(f"  {h['ticker']:<6} {h['buy_count']:>3} buys  "
                  f"{h['unique_buyers']} buyers  {h['latest_date']}{cluster}")

    elif cmd == "recent":
        print("\nRecent Congressional Buys (last 14 days):")
        recent = get_recent_all_trades(top_n=40)
        if not recent:
            print("  No recent public-stock buys found")
        for t in recent:
            print(f"  {t['tx_date']}  {t['chamber'][:1]}({t.get('party','?')[:1]})  "
                  f"{t['name'][:28]:<28}  BUY  {t['ticker']:<6}  {t['amount']}")

    elif cmd == "refresh":
        _load_all_trades(force_refresh=True)
        print("Cache refreshed.")

    else:
        print("Usage: python congress_tracker.py hot | ticker SOUN | recent | refresh")
