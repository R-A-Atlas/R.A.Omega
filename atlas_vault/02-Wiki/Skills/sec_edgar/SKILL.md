---
name: SEC EDGAR Bot
description: Queries SEC EDGAR full-text search API for recent 8-K/10-Q/10-K/S-1/SC 13G filings; flags material weakness, going concern, and restatement language
type: reference
agent: L4
division: Tax & Legal
---

# Skill: SEC EDGAR Bot (L4)

## [D] Direction
Query https://efts.sec.gov/LATEST/search-index for the past 7 days of filings.
Search for three red-flag terms: "material weakness", "going concern", "restatement".
Track form types: 8-K, 10-Q, 10-K, S-1, SC 13G.
For each filing, record ticker, company_name, form_type, filed_date, description, url, flags.
flags = list of matched red-flag strings (empty list if none).
Save to data_cache/sec_filings_latest.json.
Always include User-Agent header per SEC EDGAR fair-access policy.

## [B] Blueprints
Pattern:   atlas_agents/legal/sec_edgar/sec_edgar_scraper.py
Source:    https://efts.sec.gov/LATEST/search-index
EDGAR UI:  https://www.sec.gov/cgi-bin/browse-edgar
Output:    data_cache/sec_filings_latest.json

Red-flag terms:
  "material weakness"  → accounting control failure, high severity
  "going concern"      → auditor doubts solvency, critical
  "restatement"        → prior financials corrected, high severity

form_types: ["8-K", "10-Q", "10-K", "S-1", "SC 13G"]
User-Agent: "ATLAS/1.0 contact@example.com" (required by SEC ToS)
filed_date: "YYYY-MM-DD"
flags: list[str] (always a list)

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.sec_edgar.sec_edgar_scraper

Fetch ticker-specific:
  python -c "import sys; sys.path.insert(0,'.'); from atlas_agents.legal.sec_edgar.sec_edgar_scraper import fetch_ticker_filings; print(fetch_ticker_filings('NVDA')[:2])"

Test EDGAR API directly:
  python -c "import requests; r=requests.get('https://efts.sec.gov/LATEST/search-index?q=%22material+weakness%22&forms=8-K',headers={'User-Agent':'ATLAS/1.0 test@example.com'}); print(r.status_code, list(r.json().keys())[:5])"

Run tests:
  python -m pytest tests/test_sec_edgar.py -v

Compile check:
  python -m py_compile atlas_agents/legal/sec_edgar/sec_edgar_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on sec_edgar_scraper.py |
| 2 | record_count == len(filings) | count matches list length |
| 3 | flags is always a list | isinstance(flags, list) for every filing |
| 4 | form_type in allowed set | one of 8-K/10-Q/10-K/S-1/SC 13G |
| 5 | filed_date matches YYYY-MM-DD | len == 10 and matches regex |
