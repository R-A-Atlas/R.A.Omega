# L6 — Labor Law Monitor

## IDENTITY
Agent ID: L6
Name: Labor Law Monitor
Division: Tax & Legal
Output: data_cache/labor_law_latest.json

## DEFINITION
Tracks state minimum wage laws across all 50 states + DC, incorporating 2026 effective rates.
Federal minimum wage ($7.25) is hardcoded (unchanged since 2009). State rates use a hardcoded
2026 table as primary source (DOL HTML page is unreliable for scraping).
Used by OmegaAgent for employment law and compensation planning queries.

## DATA SOURCES
Primary:   https://www.dol.gov/agencies/whd/minimum-wage/state  (HTML reference, often unreliable)
Fallback:  Hardcoded 2026 state wage table embedded in scraper
Federal:   $7.25/hr (hardcoded — unchanged since July 24, 2009)
Format:    HTML (scraped), fallback to hardcoded data

## OUTPUT FILE
data_cache/labor_law_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "federal_min_wage": 7.25,
  "record_count": 51,
  "states": [
    {
      "state": "Washington",
      "state_code": "WA",
      "min_wage": 16.66,
      "effective_date": "2026-01-01",
      "tipped_wage": 16.66,
      "notes": "Highest state minimum wage; no tip credit"
    },
    {
      "state": "California",
      "state_code": "CA",
      "min_wage": 16.50,
      "effective_date": "2026-01-01",
      "tipped_wage": 16.50,
      "notes": "No tip credit allowed"
    },
    {
      "state": "Texas",
      "state_code": "TX",
      "min_wage": 7.25,
      "effective_date": "2009-07-24",
      "tipped_wage": 2.13,
      "notes": "Uses federal minimum; no state minimum"
    }
  ]
}
```

## SIGNAL LOGIC
- federal_min_wage is always 7.25 (hardcoded, unchanged since 2009)
- States with no state minimum wage defer to federal $7.25
  No-state-minimum states: AL, GA, ID, IN, IA, KS, KY, LA, MS, OK, SC, TN, TX, WY, WV
- Highest state rates (2026): WA=$16.66, CA=$16.50, CO=$14.81, NY=$16.50, MA=$15.00
- tipped_wage: federal tipped minimum is $2.13; state may differ or equal state minimum
- record_count = len(states) (51 = 50 states + DC)
- effective_date: "YYYY-MM-DD" string

## SCRAPER STRUCTURE
```python
# labor_law_scraper.py

import json
import datetime

FEDERAL_MIN_WAGE = 7.25

STATES_2026 = [
    {"state": "Alabama",              "state_code": "AL", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Alaska",               "state_code": "AK", "min_wage": 11.91, "effective_date": "2026-01-01", "tipped_wage": 11.91, "notes": "No tip credit"},
    {"state": "Arizona",              "state_code": "AZ", "min_wage": 14.70, "effective_date": "2026-01-01", "tipped_wage": 11.70, "notes": "Tipped: $3.00 below minimum"},
    {"state": "Arkansas",             "state_code": "AR", "min_wage": 11.00, "effective_date": "2026-01-01", "tipped_wage": 2.63,  "notes": ""},
    {"state": "California",           "state_code": "CA", "min_wage": 16.50, "effective_date": "2026-01-01", "tipped_wage": 16.50, "notes": "No tip credit allowed"},
    {"state": "Colorado",             "state_code": "CO", "min_wage": 14.81, "effective_date": "2026-01-01", "tipped_wage": 11.79, "notes": "Tipped: $3.02 tip credit"},
    {"state": "Connecticut",          "state_code": "CT", "min_wage": 16.35, "effective_date": "2026-06-01", "tipped_wage": 8.23,  "notes": "Service: $8.23, Bartenders: $9.15"},
    {"state": "Delaware",             "state_code": "DE", "min_wage": 15.00, "effective_date": "2025-01-01", "tipped_wage": 2.23,  "notes": ""},
    {"state": "Florida",              "state_code": "FL", "min_wage": 13.00, "effective_date": "2026-09-30", "tipped_wage": 10.98, "notes": "Increasing to $15 by 2026"},
    {"state": "Georgia",              "state_code": "GA", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Hawaii",               "state_code": "HI", "min_wage": 14.00, "effective_date": "2026-01-01", "tipped_wage": 12.75, "notes": ""},
    {"state": "Idaho",                "state_code": "ID", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 3.35,  "notes": "No state minimum; uses federal"},
    {"state": "Illinois",             "state_code": "IL", "min_wage": 15.00, "effective_date": "2025-01-01", "tipped_wage": 9.00,  "notes": ""},
    {"state": "Indiana",              "state_code": "IN", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Iowa",                 "state_code": "IA", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Kansas",               "state_code": "KS", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Kentucky",             "state_code": "KY", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Louisiana",            "state_code": "LA", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Maine",                "state_code": "ME", "min_wage": 14.65, "effective_date": "2026-01-01", "tipped_wage": 7.33,  "notes": "Tipped: half of minimum"},
    {"state": "Maryland",             "state_code": "MD", "min_wage": 15.00, "effective_date": "2024-01-01", "tipped_wage": 3.63,  "notes": ""},
    {"state": "Massachusetts",        "state_code": "MA", "min_wage": 15.00, "effective_date": "2023-01-01", "tipped_wage": 6.75,  "notes": ""},
    {"state": "Michigan",             "state_code": "MI", "min_wage": 10.56, "effective_date": "2026-02-01", "tipped_wage": 3.93,  "notes": "Tipped minimum increasing"},
    {"state": "Minnesota",            "state_code": "MN", "min_wage": 10.85, "effective_date": "2026-01-01", "tipped_wage": 10.85, "notes": "No tip credit; small employers $8.85"},
    {"state": "Mississippi",          "state_code": "MS", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Missouri",             "state_code": "MO", "min_wage": 13.75, "effective_date": "2026-01-01", "tipped_wage": 6.875, "notes": "Tipped: half of minimum"},
    {"state": "Montana",              "state_code": "MT", "min_wage": 10.55, "effective_date": "2026-01-01", "tipped_wage": 10.55, "notes": "No tip credit"},
    {"state": "Nebraska",             "state_code": "NE", "min_wage": 13.50, "effective_date": "2026-01-01", "tipped_wage": 2.13,  "notes": ""},
    {"state": "Nevada",               "state_code": "NV", "min_wage": 12.00, "effective_date": "2024-07-01", "tipped_wage": 12.00, "notes": "No tip credit"},
    {"state": "New Hampshire",        "state_code": "NH", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 3.26,  "notes": "Follows federal"},
    {"state": "New Jersey",           "state_code": "NJ", "min_wage": 15.49, "effective_date": "2026-01-01", "tipped_wage": 5.92,  "notes": ""},
    {"state": "New Mexico",           "state_code": "NM", "min_wage": 12.00, "effective_date": "2023-01-01", "tipped_wage": 3.00,  "notes": ""},
    {"state": "New York",             "state_code": "NY", "min_wage": 16.50, "effective_date": "2026-01-01", "tipped_wage": 13.35, "notes": "NYC/Long Island/Westchester; upstate lower"},
    {"state": "North Carolina",       "state_code": "NC", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "Follows federal"},
    {"state": "North Dakota",         "state_code": "ND", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 4.86,  "notes": "Follows federal"},
    {"state": "Ohio",                 "state_code": "OH", "min_wage": 10.45, "effective_date": "2026-01-01", "tipped_wage": 5.25,  "notes": "Small employers under $394k gross revenue: $7.25"},
    {"state": "Oklahoma",             "state_code": "OK", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Oregon",               "state_code": "OR", "min_wage": 14.70, "effective_date": "2026-07-01", "tipped_wage": 14.70, "notes": "Portland metro: $15.45; No tip credit"},
    {"state": "Pennsylvania",         "state_code": "PA", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.83,  "notes": "Follows federal"},
    {"state": "Rhode Island",         "state_code": "RI", "min_wage": 14.00, "effective_date": "2024-01-01", "tipped_wage": 3.89,  "notes": ""},
    {"state": "South Carolina",       "state_code": "SC", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "South Dakota",         "state_code": "SD", "min_wage": 11.20, "effective_date": "2026-01-01", "tipped_wage": 5.60,  "notes": "Tipped: half of minimum"},
    {"state": "Tennessee",            "state_code": "TN", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Texas",                "state_code": "TX", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Utah",                 "state_code": "UT", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "Follows federal"},
    {"state": "Vermont",              "state_code": "VT", "min_wage": 13.67, "effective_date": "2026-01-01", "tipped_wage": 6.84,  "notes": "Tipped: half of minimum"},
    {"state": "Virginia",             "state_code": "VA", "min_wage": 12.41, "effective_date": "2026-01-01", "tipped_wage": 2.13,  "notes": ""},
    {"state": "Washington",           "state_code": "WA", "min_wage": 16.66, "effective_date": "2026-01-01", "tipped_wage": 16.66, "notes": "Highest state minimum wage; no tip credit"},
    {"state": "West Virginia",        "state_code": "WV", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "Wisconsin",            "state_code": "WI", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.33,  "notes": "Follows federal"},
    {"state": "Wyoming",              "state_code": "WY", "min_wage": 7.25,  "effective_date": "2009-07-24", "tipped_wage": 2.13,  "notes": "No state minimum; uses federal"},
    {"state": "District of Columbia", "state_code": "DC", "min_wage": 17.50, "effective_date": "2024-07-01", "tipped_wage": 10.00, "notes": "DC has highest minimum in nation"},
]


def scrape() -> dict:
    """Return 2026 state minimum wage data."""
    return {
        "generated_at":     datetime.datetime.utcnow().isoformat() + "Z",
        "federal_min_wage": FEDERAL_MIN_WAGE,
        "record_count":     len(STATES_2026),
        "states":           STATES_2026,
    }


if __name__ == "__main__":
    result = scrape()
    with open("data_cache/labor_law_latest.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"[L6] Saved {result['record_count']} state wage records")
```

## RULES
1. federal_min_wage is always 7.25 (float, not int).
2. record_count must equal len(states) (51 = 50 states + DC).
3. min_wage is a float in dollars per hour.
4. effective_date is "YYYY-MM-DD" string.
5. tipped_wage is a float; if no tip credit, equals min_wage.
6. notes is a string (empty string "", never null).
7. generated_at is UTC ISO-8601 with trailing "Z".
8. States using federal minimum have min_wage == 7.25 and effective_date == "2009-07-24".

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] federal_min_wage == 7.25
- [ ] record_count == 51
- [ ] states is a list of 51 dicts
- [ ] Each state has: state, state_code, min_wage, effective_date, tipped_wage, notes
- [ ] WA min_wage == 16.66 (highest)
- [ ] Federal-only states have min_wage == 7.25
- [ ] DC included with state_code == "DC"
- [ ] data_cache/labor_law_latest.json is valid JSON
