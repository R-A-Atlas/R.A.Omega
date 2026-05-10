---
name: Labor Law Monitor
description: Tracks 2026 state minimum wages across all 50 states + DC using a hardcoded table; federal minimum wage hardcoded at $7.25 (unchanged since 2009)
type: reference
agent: L6
division: Tax & Legal
---

# Skill: Labor Law Monitor (L6)

## [D] Direction
Return 2026 state minimum wage data for all 50 states + DC (51 records).
federal_min_wage is always 7.25 (hardcoded — unchanged since July 24, 2009).
Use hardcoded STATES_2026 table as primary data source (DOL HTML is unreliable for scraping).
Optionally attempt scrape of https://www.dol.gov/agencies/whd/minimum-wage/state for live updates.
Save to data_cache/labor_law_latest.json.

Highest 2026 rates: DC=$17.50, WA=$16.66, CA=$16.50, NY=$16.50, CT=$16.35
No-state-minimum (uses federal $7.25): AL, GA, ID, IN, IA, KS, KY, LA, MS, OK, SC, TN, TX, WY, WV, PA, NC, ND, NH

## [B] Blueprints
Pattern:   atlas_agents/legal/labor_law/labor_law_scraper.py
DOL URL:   https://www.dol.gov/agencies/whd/minimum-wage/state
Output:    data_cache/labor_law_latest.json
Fallback:  Hardcoded STATES_2026 dict in scraper

Schema fields per state:
  state:          Full state name (string)
  state_code:     2-letter postal code (string)
  min_wage:       Dollars per hour (float)
  effective_date: "YYYY-MM-DD" (string)
  tipped_wage:    Dollars per hour (float); equals min_wage if no tip credit
  notes:          Context string (empty string "" if none)

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.labor_law.labor_law_scraper

Check highest wages:
  python -c "import json; d=json.load(open('data_cache/labor_law_latest.json')); top5=sorted(d['states'],key=lambda x:x['min_wage'],reverse=True)[:5]; [print(s['state_code'],s['min_wage']) for s in top5]"

Run tests:
  python -m pytest tests/test_labor_law.py -v

Compile check:
  python -m py_compile atlas_agents/legal/labor_law/labor_law_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on labor_law_scraper.py |
| 2 | federal_min_wage == 7.25 | top-level float field |
| 3 | record_count == 51 | 50 states + DC |
| 4 | WA min_wage == 16.66 | Washington entry present with correct value |
| 5 | All federal-only states have min_wage == 7.25 | AL/GA/TX/etc. match federal |
