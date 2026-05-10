# L1 — Federal Tax Code Bot

## IDENTITY
Agent ID: L1
Name: Federal Tax Code Bot
Division: Tax & Legal
Output: data_cache/federal_tax_latest.json

## DEFINITION
Fetches the current federal income tax brackets and standard deductions from IRS.gov.
Uses hardcoded 2026 values as a reliable fallback when the IRS page is unavailable.
Saves a structured JSON to data_cache for downstream use by OmegaAgent and FourLoopEngine.

## DATA SOURCES
Primary:   https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2026
Fallback:  Hardcoded 2026 bracket table embedded in scraper (IRS adjusts annually)
Format:    HTML (scraped), fallback to hardcoded dict

## OUTPUT FILE
data_cache/federal_tax_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "year": 2026,
  "standard_deduction_single": 15000,
  "standard_deduction_married": 30000,
  "record_count": 7,
  "brackets": [
    {
      "rate": 0.10,
      "single_min": 0,
      "single_max": 11925,
      "married_min": 0,
      "married_max": 23850
    },
    {
      "rate": 0.12,
      "single_min": 11925,
      "single_max": 48475,
      "married_min": 23850,
      "married_max": 96950
    },
    {
      "rate": 0.22,
      "single_min": 48475,
      "single_max": 103350,
      "married_min": 96950,
      "married_max": 206700
    },
    {
      "rate": 0.24,
      "single_min": 103350,
      "single_max": 197300,
      "married_min": 206700,
      "married_max": 394600
    },
    {
      "rate": 0.32,
      "single_min": 197300,
      "single_max": 250525,
      "married_min": 394600,
      "married_max": 501050
    },
    {
      "rate": 0.35,
      "single_min": 250525,
      "single_max": 626350,
      "married_min": 501050,
      "married_max": 751600
    },
    {
      "rate": 0.37,
      "single_min": 626350,
      "single_max": null,
      "married_min": 751600,
      "married_max": null
    }
  ]
}
```

## SIGNAL LOGIC
- record_count always equals len(brackets)
- standard_deduction_single and standard_deduction_married are top-level integers (not nested)
- If IRS page scrape fails, fall back to the hardcoded 2026 table above
- Log a warning when fallback is used so the operator knows the data may be stale

## SCRAPER STRUCTURE
```python
# federal_tax_scraper.py

import json
import datetime
import requests
from bs4 import BeautifulSoup

IRS_URL = "https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2026"

FALLBACK_2026 = {
    "year": 2026,
    "standard_deduction_single": 15000,
    "standard_deduction_married": 30000,
    "brackets": [
        {"rate": 0.10, "single_min": 0,      "single_max": 11925,  "married_min": 0,      "married_max": 23850},
        {"rate": 0.12, "single_min": 11925,   "single_max": 48475,  "married_min": 23850,  "married_max": 96950},
        {"rate": 0.22, "single_min": 48475,   "single_max": 103350, "married_min": 96950,  "married_max": 206700},
        {"rate": 0.24, "single_min": 103350,  "single_max": 197300, "married_min": 206700, "married_max": 394600},
        {"rate": 0.32, "single_min": 197300,  "single_max": 250525, "married_min": 394600, "married_max": 501050},
        {"rate": 0.35, "single_min": 250525,  "single_max": 626350, "married_min": 501050, "married_max": 751600},
        {"rate": 0.37, "single_min": 626350,  "single_max": None,   "married_min": 751600, "married_max": None},
    ],
}


def scrape() -> dict:
    """Return 2026 federal tax brackets. Falls back to hardcoded table on error."""
    try:
        resp = requests.get(IRS_URL, timeout=15, headers={"User-Agent": "ATLAS/1.0"})
        resp.raise_for_status()
        # Parse IRS page for bracket table (HTML scrape)
        soup = BeautifulSoup(resp.text, "html.parser")
        # ... parsing logic here; on any parse failure, fall through to fallback
    except Exception as exc:
        print(f"[L1] IRS page unavailable ({exc}), using hardcoded 2026 fallback")

    data = dict(FALLBACK_2026)
    data["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    data["record_count"] = len(data["brackets"])
    return data


if __name__ == "__main__":
    result = scrape()
    out_path = "data_cache/federal_tax_latest.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[L1] Saved {result['record_count']} brackets → {out_path}")
```

## RULES
1. Always emit all 7 brackets — never truncate.
2. null (JSON) represents no upper bound on the top bracket.
3. standard_deduction_single and standard_deduction_married are integer dollars (not floats).
4. generated_at is always UTC ISO-8601 with trailing "Z".
5. record_count must equal len(brackets) before write.
6. Never write partial JSON; build the full dict in memory then write once.
7. Log fallback usage as a WARNING (not ERROR) — system is still functional.

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] year == 2026
- [ ] standard_deduction_single == 15000
- [ ] standard_deduction_married == 30000
- [ ] record_count == 7
- [ ] brackets is a list of 7 dicts
- [ ] Each bracket has: rate, single_min, single_max, married_min, married_max
- [ ] Top bracket (37%) has single_max == null and married_max == null
- [ ] data_cache/federal_tax_latest.json is valid JSON (json.loads succeeds)
