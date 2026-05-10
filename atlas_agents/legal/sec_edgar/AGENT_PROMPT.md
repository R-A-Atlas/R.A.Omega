# L4 — SEC EDGAR Bot

## IDENTITY
Agent ID: L4
Name: SEC EDGAR Bot
Division: Tax & Legal
Output: data_cache/sec_filings_latest.json

## DEFINITION
Queries the SEC EDGAR full-text search API to retrieve recent 8-K, 10-Q, 10-K, S-1, and SC 13G
filings. Flags filings containing red-flag language: "material weakness", "going concern",
"restatement". Used by FourLoopEngine Loop 8 for regulatory risk scoring.

## DATA SOURCES
Primary:   https://efts.sec.gov/LATEST/search-index?q=%22material+weakness%22&dateRange=custom&startdt=2026-05-01&enddt=2026-05-09&forms=8-K
Ticker:    https://efts.sec.gov/LATEST/search-index?q={ticker}&forms=8-K,10-Q
EDGAR UI:  https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40
Format:    JSON API (SEC EDGAR full-text search)

## OUTPUT FILE
data_cache/sec_filings_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 3,
  "filings": [
    {
      "ticker": "AAPL",
      "company_name": "Apple Inc.",
      "form_type": "8-K",
      "filed_date": "2026-05-08",
      "description": "Material weakness in internal controls over financial reporting",
      "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/0000320193-26-000001-index.htm",
      "flags": ["material weakness"]
    }
  ]
}
```

## SIGNAL LOGIC
Flag a filing if its description (or full-text snippet) contains any of:
- "material weakness"
- "going concern"
- "restatement"

form_types tracked: "8-K", "10-Q", "10-K", "S-1", "SC 13G"

flags field: list of matched red-flag strings (may be empty list if no flags triggered).
record_count = len(filings)
filed_date: "YYYY-MM-DD" string
url: direct link to filing index on SEC EDGAR

## SCRAPER STRUCTURE
```python
# sec_edgar_scraper.py

import json
import datetime
import requests

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
FLAG_TERMS = ["material weakness", "going concern", "restatement"]
FORM_TYPES = ["8-K", "10-Q", "10-K", "S-1", "SC 13G"]

HEADERS = {
    "User-Agent": "ATLAS/1.0 contact@example.com",
    "Accept": "application/json",
}


def fetch_flagged_filings(days_back: int = 7) -> list:
    """Query EDGAR for flagged filings in the last N days."""
    end_dt = datetime.date.today()
    start_dt = end_dt - datetime.timedelta(days=days_back)

    results = []
    for flag_term in FLAG_TERMS:
        params = {
            "q": f'"{flag_term}"',
            "dateRange": "custom",
            "startdt": start_dt.isoformat(),
            "enddt": end_dt.isoformat(),
            "forms": ",".join(FORM_TYPES),
        }
        try:
            resp = requests.get(EDGAR_SEARCH_URL, params=params,
                                headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits:
                src = hit.get("_source", {})
                results.append({
                    "ticker":       src.get("tickers", [""])[0] if src.get("tickers") else "",
                    "company_name": src.get("entity_name", ""),
                    "form_type":    src.get("file_type", ""),
                    "filed_date":   src.get("period_of_report", "")[:10],
                    "description":  src.get("description", ""),
                    "url":          "https://www.sec.gov/Archives/edgar/" + src.get("file_date", ""),
                    "flags":        [flag_term],
                })
        except Exception as exc:
            print(f"[L4] EDGAR query failed for '{flag_term}': {exc}")
    return results


def fetch_ticker_filings(ticker: str) -> list:
    """Fetch recent filings for a specific ticker."""
    params = {"q": ticker, "forms": ",".join(FORM_TYPES)}
    try:
        resp = requests.get(EDGAR_SEARCH_URL, params=params,
                            headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            src = hit.get("_source", {})
            desc = src.get("description", "")
            matched_flags = [f for f in FLAG_TERMS if f in desc.lower()]
            results.append({
                "ticker":       ticker,
                "company_name": src.get("entity_name", ""),
                "form_type":    src.get("file_type", ""),
                "filed_date":   src.get("period_of_report", "")[:10],
                "description":  desc,
                "url":          "https://efts.sec.gov/LATEST/search-index?q=" + ticker,
                "flags":        matched_flags,
            })
        return results
    except Exception as exc:
        print(f"[L4] EDGAR ticker query failed for '{ticker}': {exc}")
        return []


def scrape() -> dict:
    """Return SEC EDGAR flagged filings from the last 7 days."""
    filings = fetch_flagged_filings(days_back=7)
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(filings),
        "filings": filings,
    }
```

## RULES
1. Always include User-Agent header with contact info (SEC EDGAR ToS requirement).
2. flags is always a list — empty list if no red-flag terms matched.
3. filed_date is "YYYY-MM-DD" string, never a datetime object.
4. form_type must be one of: "8-K", "10-Q", "10-K", "S-1", "SC 13G".
5. record_count must equal len(filings).
6. url must be a valid HTTPS string pointing to SEC EDGAR.
7. ticker may be empty string "" if EDGAR does not associate a ticker.
8. generated_at is UTC ISO-8601 with trailing "Z".

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] record_count == len(filings)
- [ ] filings is a list (may be empty if no flags triggered)
- [ ] Each filing has: ticker, company_name, form_type, filed_date, description, url, flags
- [ ] flags is always a list
- [ ] form_type values are in allowed set
- [ ] filed_date matches "YYYY-MM-DD" format
- [ ] data_cache/sec_filings_latest.json is valid JSON
