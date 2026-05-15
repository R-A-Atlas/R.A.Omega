"""
omega_sec_edgar.py — SEC EDGAR public API integration for Omega OS.

Uses only free public SEC EDGAR endpoints. No API key required.
Requires SEC_USER_AGENT in .env for compliance with EDGAR terms of service.

SEC terms: User-Agent header must identify your application and contact email.
  Format: "Application Name contact@example.com"

Public endpoints used:
  https://www.sec.gov/files/company_tickers.json  — CIK/ticker/name lookup
  https://data.sec.gov/submissions/CIK{cik}.json  — filings metadata
  Rate limit: 10 requests/second max (per EDGAR terms)

Usage:
    from omega_sec_edgar import get_filing_summary
    result = get_filing_summary("BlackRock")
    result = get_filing_summary("BLK")
"""
from __future__ import annotations

import os
import re
import time
import logging
import functools
from typing import Any

log = logging.getLogger(__name__)

# ── Public SEC EDGAR endpoints ────────────────────────────────────────────────
_TICKERS_URL      = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL  = "https://data.sec.gov/submissions/CIK{cik}.json"
_FILING_INDEX_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=5&search_text=&output=atom"

# ── Rate limiting ─────────────────────────────────────────────────────────────
_LAST_REQUEST_TIME: float = 0.0
_MIN_INTERVAL_S: float = 0.11  # 10 req/sec max → 100ms between requests; use 110ms for safety


def _get_user_agent() -> str:
    """Return User-Agent from SEC_USER_AGENT env var, or a safe default."""
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if ua:
        return ua
    return "R.A. Omega research-tool contact@example.com"


def _rate_limited_get(url: str, timeout: int = 10) -> dict | list | None:
    """
    Make a rate-limited GET request to SEC EDGAR.
    Respects 10 req/sec limit. Returns parsed JSON or None on error.
    """
    global _LAST_REQUEST_TIME
    try:
        import requests
    except ImportError:
        log.error("omega_sec_edgar: requests library not available")
        return None

    # Enforce rate limit
    elapsed = time.monotonic() - _LAST_REQUEST_TIME
    if elapsed < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - elapsed)

    headers = {
        "User-Agent": _get_user_agent(),
        "Accept": "application/json",
    }
    try:
        _LAST_REQUEST_TIME = time.monotonic()
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("omega_sec_edgar: request failed for %s — %s", url, exc)
        return None


# ── In-memory CIK cache (avoids repeat requests per session) ─────────────────
_cik_cache: dict[str, str] = {}   # normalized_name_or_ticker → zero-padded CIK string


@functools.lru_cache(maxsize=1)
def _load_company_tickers() -> dict[str, dict]:
    """
    Load and cache the SEC company_tickers.json.
    Returns dict keyed by normalized ticker/name for fast lookups.
    Returns {} on failure — callers must handle empty gracefully.
    """
    data = _rate_limited_get(_TICKERS_URL)
    if not isinstance(data, dict):
        return {}
    # data is {str_index: {cik_str, ticker, title}, ...}
    result: dict[str, dict] = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker", "")).strip().upper()
        title  = str(entry.get("title", "")).strip().lower()
        cik    = str(entry.get("cik_str", entry.get("cik", ""))).strip()
        if ticker:
            result[ticker] = {"cik": cik, "ticker": ticker, "title": title}
        if title:
            result[title] = {"cik": cik, "ticker": ticker, "title": title}
    return result


def _normalize_cik(cik: str | int) -> str:
    """Zero-pad CIK to 10 digits as required by EDGAR submissions API."""
    return str(int(str(cik).strip())).zfill(10)


# ── Public functions ──────────────────────────────────────────────────────────

def search_company_cik(company_name_or_ticker: str) -> str | None:
    """
    Look up a company's CIK from a name or ticker symbol.

    Returns a zero-padded 10-digit CIK string, or None if not found.
    Results are cached in _cik_cache for the lifetime of the process.

    Args:
        company_name_or_ticker: company name (e.g. "BlackRock") or ticker (e.g. "BLK")
    """
    query = company_name_or_ticker.strip()
    cache_key = query.upper()
    if cache_key in _cik_cache:
        return _cik_cache[cache_key]

    ticker_map = _load_company_tickers()
    if not ticker_map:
        log.warning("omega_sec_edgar: company_tickers.json unavailable — CIK lookup failed")
        return None

    # Try exact ticker match first
    upper = query.upper()
    if upper in ticker_map:
        cik = _normalize_cik(ticker_map[upper]["cik"])
        _cik_cache[cache_key] = cik
        return cik

    # Try exact name match (lowercased)
    lower = query.lower()
    if lower in ticker_map:
        cik = _normalize_cik(ticker_map[lower]["cik"])
        _cik_cache[cache_key] = cik
        return cik

    # Try partial name match
    for key, entry in ticker_map.items():
        if lower in key or key in lower:
            cik = _normalize_cik(entry["cik"])
            _cik_cache[cache_key] = cik
            log.debug("omega_sec_edgar: partial match '%s' → %s (CIK %s)", query, key, cik)
            return cik

    log.warning("omega_sec_edgar: no CIK found for '%s'", query)
    return None


def get_company_submissions(cik: str) -> dict | None:
    """
    Fetch company submissions metadata from EDGAR.
    Returns the full submissions JSON or None on failure.

    The submissions dict includes:
      - name, sic, stateOfIncorporation, fiscalYearEnd
      - filings.recent: accessionNumber, filingDate, form, primaryDocument, items
    """
    padded = _normalize_cik(cik)
    url = _SUBMISSIONS_URL.format(cik=padded)
    data = _rate_limited_get(url)
    if not isinstance(data, dict):
        return None
    return data


def get_recent_filings(
    cik: str,
    forms: list[str] | None = None,
    max_per_form: int = 3,
) -> dict[str, list[dict]]:
    """
    Extract recent filings of specified types from a company's submissions.

    Args:
        cik: EDGAR CIK (any format — will be normalized)
        forms: list of form types to filter, e.g. ["10-K", "10-Q", "8-K"]
               defaults to ["10-K", "10-Q", "8-K"]
        max_per_form: maximum number of filings to return per form type

    Returns:
        dict keyed by form type → list of filing dicts, each with:
          accession_number, filing_date, form, description, document_url
    """
    if forms is None:
        forms = ["10-K", "10-Q", "8-K"]

    submissions = get_company_submissions(cik)
    if not submissions:
        return {f: [] for f in forms}

    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return {f: [] for f in forms}

    form_list  = recent.get("form", [])
    date_list  = recent.get("filingDate", [])
    acc_list   = recent.get("accessionNumber", [])
    doc_list   = recent.get("primaryDocument", [])
    desc_list  = recent.get("items", recent.get("description", [""] * len(form_list)))

    padded_cik = _normalize_cik(cik)
    results: dict[str, list[dict]] = {f: [] for f in forms}

    for i, form_type in enumerate(form_list):
        if form_type not in forms:
            continue
        if len(results[form_type]) >= max_per_form:
            continue

        acc_no = acc_list[i] if i < len(acc_list) else ""
        acc_path = acc_no.replace("-", "")
        filing_date = date_list[i] if i < len(date_list) else ""
        primary_doc = doc_list[i] if i < len(doc_list) else ""
        description = desc_list[i] if i < len(desc_list) else ""

        doc_url = ""
        if acc_no and primary_doc:
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(padded_cik)}/"
                f"{acc_path}/{primary_doc}"
            )

        index_url = ""
        if acc_no:
            index_url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={padded_cik}&type={form_type}&dateb=&owner=include&count=5"
            )

        results[form_type].append({
            "form":             form_type,
            "filing_date":      filing_date,
            "accession_number": acc_no,
            "description":      str(description)[:200],
            "document_url":     doc_url,
            "index_url":        index_url,
        })

    return results


def get_filing_summary(company_name_or_ticker: str) -> dict[str, Any]:
    """
    High-level summary of recent SEC filings for a company.
    Returns metadata suitable for prompt injection and frontend display.

    Args:
        company_name_or_ticker: company name or ticker symbol

    Returns dict with:
        company: name as known to EDGAR
        cik: zero-padded CIK
        sec_filings_used: bool — True when real filings were found
        latest_10k: dict | None
        latest_10q: dict | None
        latest_8k: dict | None
        all_recent: dict[form_type, list[dict]]
        error: str | None — set when lookup failed
        filing_context: str — formatted text for prompt injection
    """
    result: dict[str, Any] = {
        "company":          company_name_or_ticker,
        "cik":              None,
        "sec_filings_used": False,
        "latest_10k":       None,
        "latest_10q":       None,
        "latest_8k":        None,
        "all_recent":       {},
        "error":            None,
        "filing_context":   "",
    }

    cik = search_company_cik(company_name_or_ticker)
    if not cik:
        result["error"] = f"No CIK found for '{company_name_or_ticker}'"
        return result

    result["cik"] = cik

    # Fetch company info
    submissions = get_company_submissions(cik)
    if submissions:
        result["company"] = submissions.get("name", company_name_or_ticker)

    # Fetch recent filings
    filings = get_recent_filings(cik, forms=["10-K", "10-Q", "8-K"])
    result["all_recent"] = filings

    latest_10k = filings.get("10-K", [{}])[0] if filings.get("10-K") else None
    latest_10q = filings.get("10-Q", [{}])[0] if filings.get("10-Q") else None
    latest_8k  = filings.get("8-K",  [{}])[0] if filings.get("8-K")  else None

    result["latest_10k"] = latest_10k
    result["latest_10q"] = latest_10q
    result["latest_8k"]  = latest_8k
    result["sec_filings_used"] = bool(latest_10k or latest_10q or latest_8k)

    # Build prompt-ready context string
    lines: list[str] = []
    company_label = result["company"]
    if cik:
        lines.append(f"SEC EDGAR Filings for {company_label} (CIK: {cik}):")
    if latest_10k:
        lines.append(f"  Latest 10-K (Annual Report): {latest_10k['filing_date']} — {latest_10k.get('document_url','')}")
    if latest_10q:
        lines.append(f"  Latest 10-Q (Quarterly Report): {latest_10q['filing_date']} — {latest_10q.get('document_url','')}")
    if latest_8k:
        lines.append(f"  Latest 8-K (Material Event): {latest_8k['filing_date']} — {latest_8k.get('description','')[:100]}")
    if not lines:
        lines.append(f"No recent SEC filings found for {company_label}")

    result["filing_context"] = "\n".join(lines)
    return result


def is_available() -> bool:
    """Return True if SEC EDGAR integration is configured and usable."""
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    # Available when user-agent is set to something other than the placeholder
    return bool(ua) and "contact@example.com" not in ua.lower()
