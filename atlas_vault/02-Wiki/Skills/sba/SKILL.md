---
name: SBA Grant/Loan Finder
description: Aggregates SBA loan programs (7a, 504, Microloan, EIDL, CAPLines) and live Grants.gov federal opportunities; returns structured funding options with eligibility, rates, and OPEN/CLOSED status
type: reference
agent: B1
division: Business & Startups
---

# Skill: SBA Grant/Loan Finder (B1)

## [D] Direction
Combine 5 hardcoded SBA loan/line-of-credit programs with live federal grant results
from the Grants.gov search API. Classify each program with status (OPEN/CLOSED) and
type (Grant/Loan/Line of Credit). Save result to data_cache/sba_latest.json.

Step-by-step:
1. Load hardcoded SBA_PROGRAMS list (5 programs, always authoritative baseline).
2. POST to https://api.grants.gov/v1/api/search2 with keyword="small business".
3. Parse oppHits from Grants.gov response; map each to unified schema.
4. Merge SBA_PROGRAMS + Grants.gov results into programs list.
5. Set generated_at (ISO UTC), record_count = len(programs).
6. Write to data_cache/sba_latest.json.

Rules:
- Grants.gov failure must NOT crash the scraper — return SBA baseline only.
- type values: "Grant", "Loan", "Line of Credit" only.
- status values: "OPEN", "CLOSED" only.
- max_amount must be an integer (not a float string).
- Never remove the 5 hardcoded SBA programs.

## [B] Blueprints
Pattern:    atlas_agents/business/sba/AGENT_PROMPT.md (full scraper stub)
Utils:      Standard requests.post + json.dump
Primary:    https://www.sba.gov/funding-programs/loans
Grants API: https://api.grants.gov/v1/api/search2
Output:     data_cache/sba_latest.json

Schema reference:
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
      "eligibility": "...",
      "term_years_max": 25,
      "status": "OPEN",
      "url": "https://www.sba.gov/funding-programs/loans/7a-loans"
    }
  ]
}
```

## [S] Solutions
Run scraper:
  python -m atlas_agents.business.sba.sba_scraper

Test Grants.gov API:
  python -c "import requests; r = requests.post('https://api.grants.gov/v1/api/search2', json={'keyword':'small business','rows':5}, timeout=10); print(r.status_code, r.json().get('data',{}).get('oppHits',[])[:1])"

Run tests:
  python -m pytest tests/test_sba.py -v

Validate output:
  python -c "import json; d=json.load(open('data_cache/sba_latest.json')); print(d['record_count'], [p['name'] for p in d['programs'][:3]])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | All 5 SBA programs present | names include 7(a), 504, Microloan, EIDL, CAPLines |
| 2 | record_count == len(programs) | integer equality |
| 3 | All type values valid | values in {"Grant","Loan","Line of Credit"} |
| 4 | All status values valid | values in {"OPEN","CLOSED"} |
| 5 | generated_at is ISO UTC | datetime.fromisoformat(generated_at.replace("Z","+00:00")) succeeds |
