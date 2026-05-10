---
name: Mortgage Rate Tracker
description: Fetches Freddie Mac PMMS weekly mortgage rates via FRED for 30y/15y/ARM; classifies WoW trend as RISING/FALLING/STABLE with 5bps threshold
type: reference
agent: R7
division: Real Estate & Property
---

# Skill: Mortgage Rate Tracker (R7)

## [D] Direction
Fetch FRED series MORTGAGE30US, MORTGAGE15US, MORTGAGE5US (Freddie Mac PMMS).
Compare latest week vs prior week on 30y fixed to compute wow_change_30y.
Classify: > +0.05 → RISING, < -0.05 → FALLING, else STABLE.
Save to data_cache/mortgage_rates_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/trading/bond_yields/bond_yields_scraper.py (FRED fetch pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    FRED MORTGAGE30US, MORTGAGE15US, MORTGAGE5US (no auth)
Output:     data_cache/mortgage_rates_latest.json

Trend threshold (WoW on 30y fixed):
  wow_change_30y > +0.05  → RISING
  wow_change_30y < -0.05  → FALLING
  else                    → STABLE

FRED series IDs:
  30-Year Fixed: MORTGAGE30US
  15-Year Fixed: MORTGAGE15US
  5/1 ARM:       MORTGAGE5US

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.mortgage_rates.mortgage_rates_scraper

Test FRED mortgage series:
  python -c "import requests; r = requests.get('https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE30US&file_type=json&sort_order=desc&limit=2'); print(r.json().get('observations', []))"

Run tests:
  python -m pytest tests/test_mortgage_rates.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | trend in valid set | RISING or FALLING or STABLE |
| 3 | rate > 0 for all terms | all rates positive |
| 4 | wow_change_30y present | top-level float field |
| 5 | record_count == len(rates) | count matches list length |
