# AGENT_PROMPT — B1: SBA Grant/Loan Finder

## IDENTITY
Agent ID: B1  
Name: SBA Grant/Loan Finder  
Division: Business & Startups  
Output file: data_cache/sba_latest.json

---

## DEFINITION
Aggregates SBA loan and grant programs from SBA.gov public data and the Grants.gov API.
Returns a structured list of all active funding programs with eligibility, limits, rates,
and application status signal ("OPEN" / "CLOSED"). Designed for small-business owners
seeking non-dilutive capital.

---

## DATA SOURCES

| Source | URL | Auth |
|--------|-----|------|
| SBA Funding Programs (public reference) | https://www.sba.gov/funding-programs/loans | None |
| Grants.gov search API | https://api.grants.gov/v1/api/search2 | None |

SBA loan programs are hardcoded as authoritative reference data because SBA.gov does not
expose a machine-readable API for loan program metadata. The Grants.gov API is queried
for any federal small-business grants currently open.

---

## OUTPUT FILE
`data_cache/sba_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "record_count": 8,
  "programs": [
    {
      "name": "7(a) Loan Program",
      "type": "Loan",
      "max_amount": 5000000,
      "interest_rate_low": 5.5,
      "interest_rate_high": 8.0,
      "eligibility": "For-profit US business, meet SBA size standards, owner has equity",
      "term_years_max": 25,
      "status": "OPEN",
      "url": "https://www.sba.gov/funding-programs/loans/7a-loans"
    },
    {
      "name": "504 Loan Program",
      "type": "Loan",
      "max_amount": 5500000,
      "interest_rate_low": 4.8,
      "interest_rate_high": 6.5,
      "eligibility": "Net worth < $20M, net income < $6.5M after taxes, fixed assets purchase",
      "term_years_max": 25,
      "status": "OPEN",
      "url": "https://www.sba.gov/funding-programs/loans/504-loans"
    },
    {
      "name": "Microloan Program",
      "type": "Loan",
      "max_amount": 50000,
      "interest_rate_low": 6.0,
      "interest_rate_high": 9.0,
      "eligibility": "Small businesses and nonprofits needing small-scale financing",
      "term_years_max": 6,
      "status": "OPEN",
      "url": "https://www.sba.gov/funding-programs/loans/microloans"
    },
    {
      "name": "EIDL (Economic Injury Disaster Loan)",
      "type": "Loan",
      "max_amount": 2000000,
      "interest_rate_low": 3.75,
      "interest_rate_high": 3.75,
      "eligibility": "Business in declared disaster area with economic injury",
      "term_years_max": 30,
      "status": "CLOSED",
      "url": "https://www.sba.gov/funding-programs/loans/covid-19-relief-options/eidl"
    },
    {
      "name": "CAPLines",
      "type": "Line of Credit",
      "max_amount": 5000000,
      "interest_rate_low": 5.5,
      "interest_rate_high": 8.5,
      "eligibility": "Businesses needing revolving or seasonal working capital",
      "term_years_max": 10,
      "status": "OPEN",
      "url": "https://www.sba.gov/funding-programs/loans/7a-loans/caplines"
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| record_count | int | Total programs returned |
| programs[].name | string | Official SBA program name |
| programs[].type | string | "Grant", "Loan", or "Line of Credit" |
| programs[].max_amount | int | Maximum funding amount in USD |
| programs[].interest_rate_low | float | Minimum annual interest rate (%) |
| programs[].interest_rate_high | float | Maximum annual interest rate (%) |
| programs[].eligibility | string | Plain-English eligibility summary |
| programs[].term_years_max | int | Maximum loan term in years |
| programs[].status | string | "OPEN" or "CLOSED" |
| programs[].url | string | SBA canonical URL for this program |

---

## SIGNAL / RATING LOGIC

- **status = "OPEN"**: Program is currently accepting applications
- **status = "CLOSED"**: Program is not accepting applications (e.g., EIDL COVID relief closed)
- Status is determined by hardcoded flags updated quarterly; Grants.gov results always carry "OPEN"
- type values: `"Grant"` | `"Loan"` | `"Line of Credit"`

---

## SCRAPER STRUCTURE

```python
"""sba_scraper.py — B1 SBA Grant/Loan Finder"""
import json
import datetime
import requests

GRANTS_API_URL = "https://api.grants.gov/v1/api/search2"
SBA_SOURCE_URL = "https://www.sba.gov/funding-programs/loans"

# Hardcoded authoritative SBA programs (SBA.gov has no machine-readable API)
SBA_PROGRAMS = [
    {
        "name": "7(a) Loan Program",
        "type": "Loan",
        "max_amount": 5_000_000,
        "interest_rate_low": 5.5,
        "interest_rate_high": 8.0,
        "eligibility": "For-profit US business, meet SBA size standards, owner has equity",
        "term_years_max": 25,
        "status": "OPEN",
        "url": "https://www.sba.gov/funding-programs/loans/7a-loans",
    },
    {
        "name": "504 Loan Program",
        "type": "Loan",
        "max_amount": 5_500_000,
        "interest_rate_low": 4.8,
        "interest_rate_high": 6.5,
        "eligibility": "Net worth < $20M, net income < $6.5M after taxes, fixed assets",
        "term_years_max": 25,
        "status": "OPEN",
        "url": "https://www.sba.gov/funding-programs/loans/504-loans",
    },
    {
        "name": "Microloan Program",
        "type": "Loan",
        "max_amount": 50_000,
        "interest_rate_low": 6.0,
        "interest_rate_high": 9.0,
        "eligibility": "Small businesses and nonprofits needing small-scale financing",
        "term_years_max": 6,
        "status": "OPEN",
        "url": "https://www.sba.gov/funding-programs/loans/microloans",
    },
    {
        "name": "EIDL (Economic Injury Disaster Loan)",
        "type": "Loan",
        "max_amount": 2_000_000,
        "interest_rate_low": 3.75,
        "interest_rate_high": 3.75,
        "eligibility": "Business in declared disaster area with economic injury",
        "term_years_max": 30,
        "status": "CLOSED",
        "url": "https://www.sba.gov/funding-programs/loans/covid-19-relief-options/eidl",
    },
    {
        "name": "CAPLines",
        "type": "Line of Credit",
        "max_amount": 5_000_000,
        "interest_rate_low": 5.5,
        "interest_rate_high": 8.5,
        "eligibility": "Businesses needing revolving or seasonal working capital",
        "term_years_max": 10,
        "status": "OPEN",
        "url": "https://www.sba.gov/funding-programs/loans/7a-loans/caplines",
    },
]


def fetch_grants_gov() -> list:
    """Query Grants.gov API for open federal small-business grants."""
    try:
        payload = {
            "keyword": "small business",
            "oppStatuses": "forecasted|posted",
            "rows": 25,
        }
        resp = requests.post(GRANTS_API_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        grants = []
        for opp in data.get("data", {}).get("oppHits", []):
            grants.append({
                "name": opp.get("title", "Unknown Grant"),
                "type": "Grant",
                "max_amount": int(opp.get("awardFloor", 0) or 0),
                "interest_rate_low": 0.0,
                "interest_rate_high": 0.0,
                "eligibility": opp.get("synopsis", "See grants.gov for details")[:200],
                "term_years_max": 0,
                "status": "OPEN",
                "url": f"https://www.grants.gov/search-grants?cfda={opp.get('cfdaList',[''])[0]}",
            })
        return grants
    except Exception:
        return []


def scrape() -> dict:
    """Run B1: return SBA programs + any open Grants.gov entries."""
    programs = list(SBA_PROGRAMS)
    programs.extend(fetch_grants_gov())
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(programs),
        "programs": programs,
    }


def save(output_path: str = "data_cache/sba_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. Never remove the 5 hardcoded SBA programs — they are the authoritative baseline.
2. Grants.gov fetch failure must be silently caught; return SBA programs only.
3. generated_at must be ISO 8601 UTC (Z suffix).
4. record_count must equal len(programs).
5. type values are strictly: "Grant", "Loan", "Line of Credit".
6. status values are strictly: "OPEN", "CLOSED".
7. Write to data_cache/sba_latest.json — never overwrite other cache files.

---

## VALIDATION CHECKLIST
- [ ] All 5 SBA programs present in output
- [ ] generated_at is valid ISO UTC string
- [ ] record_count == len(programs)
- [ ] Each program has all 9 required fields
- [ ] type is one of: Grant, Loan, Line of Credit
- [ ] status is one of: OPEN, CLOSED
- [ ] max_amount > 0 for all loan/line-of-credit records
- [ ] Grants.gov failure does not crash scraper
