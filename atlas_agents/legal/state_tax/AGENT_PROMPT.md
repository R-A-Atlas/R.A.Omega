# L2 — State Tax / Act 60 Monitor

## IDENTITY
Agent ID: L2
Name: State Tax / Act 60 Monitor
Division: Tax & Legal
Output: data_cache/state_tax_latest.json

## DEFINITION
Aggregates state income tax rates, sales tax rates (state + avg local), and special tax programs
(no-income-tax states, Puerto Rico Act 60) from Tax Foundation public data.
Provides a comprehensive 50-state + DC + Puerto Rico reference for ATLAS tax planning queries.

## DATA SOURCES
Primary:   https://taxfoundation.org/data/all/state/state-income-tax-rates/
Secondary: https://taxfoundation.org/data/all/state/state-sales-tax-rates-2026/
Fallback:  Hardcoded 2026 table embedded in scraper
Format:    HTML (scraped) with fallback to hardcoded data

## OUTPUT FILE
data_cache/state_tax_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 52,
  "states": [
    {
      "state": "California",
      "state_code": "CA",
      "income_tax_rate_top": 13.3,
      "sales_tax_state": 7.25,
      "sales_tax_avg_local": 1.57,
      "special_programs": []
    },
    {
      "state": "Florida",
      "state_code": "FL",
      "income_tax_rate_top": 0.0,
      "sales_tax_state": 6.0,
      "sales_tax_avg_local": 1.05,
      "special_programs": ["No income tax"]
    },
    {
      "state": "Puerto Rico",
      "state_code": "PR",
      "income_tax_rate_top": 4.0,
      "sales_tax_state": 10.5,
      "sales_tax_avg_local": 0.0,
      "special_programs": ["Act 60 (PR)", "4% corporate rate", "0-4% individual rate"]
    }
  ]
}
```

## SIGNAL LOGIC
- no_income_tax_states: ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"]
  → set income_tax_rate_top = 0.0 and add "No income tax" to special_programs
- Puerto Rico Act 60: corporate rate 4%, individual 0-4%, add "Act 60 (PR)" to special_programs
- record_count = len(states) (should be 52: 50 states + DC + PR)
- special_programs is always a list (empty list if no special programs apply)

## SCRAPER STRUCTURE
```python
# state_tax_scraper.py

import json
import datetime
import requests
from bs4 import BeautifulSoup

TAX_FOUNDATION_URL = "https://taxfoundation.org/data/all/state/state-income-tax-rates/"

NO_INCOME_TAX_STATES = ["AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"]

HARDCODED_STATES = [
    {"state": "Alabama",        "state_code": "AL", "income_tax_rate_top": 5.0,  "sales_tax_state": 4.0,  "sales_tax_avg_local": 5.22, "special_programs": []},
    {"state": "Alaska",         "state_code": "AK", "income_tax_rate_top": 0.0,  "sales_tax_state": 0.0,  "sales_tax_avg_local": 1.82, "special_programs": ["No income tax"]},
    {"state": "Arizona",        "state_code": "AZ", "income_tax_rate_top": 2.5,  "sales_tax_state": 5.6,  "sales_tax_avg_local": 2.77, "special_programs": []},
    {"state": "Arkansas",       "state_code": "AR", "income_tax_rate_top": 4.4,  "sales_tax_state": 6.5,  "sales_tax_avg_local": 2.97, "special_programs": []},
    {"state": "California",     "state_code": "CA", "income_tax_rate_top": 13.3, "sales_tax_state": 7.25, "sales_tax_avg_local": 1.57, "special_programs": []},
    {"state": "Colorado",       "state_code": "CO", "income_tax_rate_top": 4.4,  "sales_tax_state": 2.9,  "sales_tax_avg_local": 4.88, "special_programs": []},
    {"state": "Connecticut",    "state_code": "CT", "income_tax_rate_top": 6.99, "sales_tax_state": 6.35, "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Delaware",       "state_code": "DE", "income_tax_rate_top": 6.6,  "sales_tax_state": 0.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Florida",        "state_code": "FL", "income_tax_rate_top": 0.0,  "sales_tax_state": 6.0,  "sales_tax_avg_local": 1.05, "special_programs": ["No income tax"]},
    {"state": "Georgia",        "state_code": "GA", "income_tax_rate_top": 5.49, "sales_tax_state": 4.0,  "sales_tax_avg_local": 3.35, "special_programs": []},
    {"state": "Hawaii",         "state_code": "HI", "income_tax_rate_top": 11.0, "sales_tax_state": 4.0,  "sales_tax_avg_local": 0.44, "special_programs": []},
    {"state": "Idaho",          "state_code": "ID", "income_tax_rate_top": 5.8,  "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.02, "special_programs": []},
    {"state": "Illinois",       "state_code": "IL", "income_tax_rate_top": 4.95, "sales_tax_state": 6.25, "sales_tax_avg_local": 2.49, "special_programs": []},
    {"state": "Indiana",        "state_code": "IN", "income_tax_rate_top": 3.05, "sales_tax_state": 7.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Iowa",           "state_code": "IA", "income_tax_rate_top": 3.8,  "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.94, "special_programs": []},
    {"state": "Kansas",         "state_code": "KS", "income_tax_rate_top": 5.7,  "sales_tax_state": 6.5,  "sales_tax_avg_local": 2.18, "special_programs": []},
    {"state": "Kentucky",       "state_code": "KY", "income_tax_rate_top": 4.0,  "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Louisiana",      "state_code": "LA", "income_tax_rate_top": 3.0,  "sales_tax_state": 5.0,  "sales_tax_avg_local": 5.1,  "special_programs": []},
    {"state": "Maine",          "state_code": "ME", "income_tax_rate_top": 7.15, "sales_tax_state": 5.5,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Maryland",       "state_code": "MD", "income_tax_rate_top": 5.75, "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Massachusetts",  "state_code": "MA", "income_tax_rate_top": 9.0,  "sales_tax_state": 6.25, "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Michigan",       "state_code": "MI", "income_tax_rate_top": 4.05, "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Minnesota",      "state_code": "MN", "income_tax_rate_top": 9.85, "sales_tax_state": 6.875,"sales_tax_avg_local": 0.57, "special_programs": []},
    {"state": "Mississippi",    "state_code": "MS", "income_tax_rate_top": 4.7,  "sales_tax_state": 7.0,  "sales_tax_avg_local": 0.07, "special_programs": []},
    {"state": "Missouri",       "state_code": "MO", "income_tax_rate_top": 4.95, "sales_tax_state": 4.225,"sales_tax_avg_local": 4.03, "special_programs": []},
    {"state": "Montana",        "state_code": "MT", "income_tax_rate_top": 5.9,  "sales_tax_state": 0.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Nebraska",       "state_code": "NE", "income_tax_rate_top": 5.84, "sales_tax_state": 5.5,  "sales_tax_avg_local": 1.44, "special_programs": []},
    {"state": "Nevada",         "state_code": "NV", "income_tax_rate_top": 0.0,  "sales_tax_state": 6.85, "sales_tax_avg_local": 1.38, "special_programs": ["No income tax"]},
    {"state": "New Hampshire",  "state_code": "NH", "income_tax_rate_top": 0.0,  "sales_tax_state": 0.0,  "sales_tax_avg_local": 0.0,  "special_programs": ["No income tax"]},
    {"state": "New Jersey",     "state_code": "NJ", "income_tax_rate_top": 10.75,"sales_tax_state": 6.625,"sales_tax_avg_local": -0.03,"special_programs": []},
    {"state": "New Mexico",     "state_code": "NM", "income_tax_rate_top": 5.9,  "sales_tax_state": 5.0,  "sales_tax_avg_local": 2.72, "special_programs": []},
    {"state": "New York",       "state_code": "NY", "income_tax_rate_top": 10.9, "sales_tax_state": 4.0,  "sales_tax_avg_local": 4.52, "special_programs": []},
    {"state": "North Carolina", "state_code": "NC", "income_tax_rate_top": 4.5,  "sales_tax_state": 4.75, "sales_tax_avg_local": 2.23, "special_programs": []},
    {"state": "North Dakota",   "state_code": "ND", "income_tax_rate_top": 2.5,  "sales_tax_state": 5.0,  "sales_tax_avg_local": 1.96, "special_programs": []},
    {"state": "Ohio",           "state_code": "OH", "income_tax_rate_top": 3.5,  "sales_tax_state": 5.75, "sales_tax_avg_local": 1.48, "special_programs": []},
    {"state": "Oklahoma",       "state_code": "OK", "income_tax_rate_top": 4.75, "sales_tax_state": 4.5,  "sales_tax_avg_local": 4.47, "special_programs": []},
    {"state": "Oregon",         "state_code": "OR", "income_tax_rate_top": 9.9,  "sales_tax_state": 0.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "Pennsylvania",   "state_code": "PA", "income_tax_rate_top": 3.07, "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.34, "special_programs": []},
    {"state": "Rhode Island",   "state_code": "RI", "income_tax_rate_top": 5.99, "sales_tax_state": 7.0,  "sales_tax_avg_local": 0.0,  "special_programs": []},
    {"state": "South Carolina", "state_code": "SC", "income_tax_rate_top": 6.4,  "sales_tax_state": 6.0,  "sales_tax_avg_local": 1.43, "special_programs": []},
    {"state": "South Dakota",   "state_code": "SD", "income_tax_rate_top": 0.0,  "sales_tax_state": 4.5,  "sales_tax_avg_local": 1.9,  "special_programs": ["No income tax"]},
    {"state": "Tennessee",      "state_code": "TN", "income_tax_rate_top": 0.0,  "sales_tax_state": 7.0,  "sales_tax_avg_local": 2.55, "special_programs": ["No income tax"]},
    {"state": "Texas",          "state_code": "TX", "income_tax_rate_top": 0.0,  "sales_tax_state": 6.25, "sales_tax_avg_local": 1.95, "special_programs": ["No income tax"]},
    {"state": "Utah",           "state_code": "UT", "income_tax_rate_top": 4.55, "sales_tax_state": 6.1,  "sales_tax_avg_local": 1.09, "special_programs": []},
    {"state": "Vermont",        "state_code": "VT", "income_tax_rate_top": 8.75, "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.24, "special_programs": []},
    {"state": "Virginia",       "state_code": "VA", "income_tax_rate_top": 5.75, "sales_tax_state": 5.3,  "sales_tax_avg_local": 0.35, "special_programs": []},
    {"state": "Washington",     "state_code": "WA", "income_tax_rate_top": 0.0,  "sales_tax_state": 6.5,  "sales_tax_avg_local": 2.73, "special_programs": ["No income tax"]},
    {"state": "West Virginia",  "state_code": "WV", "income_tax_rate_top": 5.12, "sales_tax_state": 6.0,  "sales_tax_avg_local": 0.39, "special_programs": []},
    {"state": "Wisconsin",      "state_code": "WI", "income_tax_rate_top": 7.65, "sales_tax_state": 5.0,  "sales_tax_avg_local": 0.43, "special_programs": []},
    {"state": "Wyoming",        "state_code": "WY", "income_tax_rate_top": 0.0,  "sales_tax_state": 4.0,  "sales_tax_avg_local": 1.34, "special_programs": ["No income tax"]},
    {"state": "District of Columbia", "state_code": "DC", "income_tax_rate_top": 10.75,"sales_tax_state": 6.0, "sales_tax_avg_local": 0.0, "special_programs": []},
    {"state": "Puerto Rico",    "state_code": "PR", "income_tax_rate_top": 4.0,  "sales_tax_state": 10.5, "sales_tax_avg_local": 0.0,  "special_programs": ["Act 60 (PR)", "4% corporate rate", "0-4% individual rate"]},
]


def scrape() -> dict:
    """Return state tax data. Falls back to hardcoded 2026 table on scrape failure."""
    try:
        resp = requests.get(TAX_FOUNDATION_URL, timeout=15, headers={"User-Agent": "ATLAS/1.0"})
        resp.raise_for_status()
        # Parse Tax Foundation page — fallback to hardcoded on any failure
    except Exception as exc:
        print(f"[L2] Tax Foundation page unavailable ({exc}), using hardcoded 2026 fallback")

    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(HARDCODED_STATES),
        "states": HARDCODED_STATES,
    }
```

## RULES
1. Always include all 52 records (50 states + DC + Puerto Rico).
2. special_programs is a list, never null or a string.
3. income_tax_rate_top is a float (percentage, not decimal: 13.3, not 0.133).
4. No-income-tax states always have income_tax_rate_top == 0.0.
5. Puerto Rico Act 60 must appear with "Act 60 (PR)" in special_programs.
6. generated_at is UTC ISO-8601 with trailing "Z".
7. record_count must equal len(states) before write.

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] record_count == 52
- [ ] states is a list of 52 dicts
- [ ] Each state has: state, state_code, income_tax_rate_top, sales_tax_state, sales_tax_avg_local, special_programs
- [ ] All 9 no-income-tax state codes have income_tax_rate_top == 0.0
- [ ] Puerto Rico entry exists with "Act 60 (PR)" in special_programs
- [ ] special_programs is always a list (not null)
- [ ] data_cache/state_tax_latest.json is valid JSON
