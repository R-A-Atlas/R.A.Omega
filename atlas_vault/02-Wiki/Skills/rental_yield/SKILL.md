---
name: Rental Yield Calculator
description: Combines HUD Fair Market Rents and Zillow ZORI with median home prices to estimate gross rental yield per metro; signals GOOD/AVERAGE/LOW
type: reference
agent: R2
division: Real Estate & Property
---

# Skill: Rental Yield Calculator (R2)

## [D] Direction
Fetch Zillow ZORI public CSV for metro-level rents (fallback: HUD FMR API with token).
Cross-reference median home prices from data_cache/residential_latest.json (R1 output).
Compute gross yield = (avg_rent_2br * 12 / median_home_price) * 100.
Classify: >= 6% → GOOD, >= 4% → AVERAGE, < 4% → LOW.
Save to data_cache/rental_yield_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (CSV fetch + compute pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv
Secondary:  HUD FMR API (requires HUD_API_TOKEN env var)
Cross-ref:  data_cache/residential_latest.json (R1 median prices)
Output:     data_cache/rental_yield_latest.json

Yield formula:
  yield_estimate = (avg_rent_2br * 12 / median_home_price) * 100

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.rental_yield.rental_yield_scraper

Test Zillow ZORI URL:
  python -c "import requests; r = requests.get('https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv', stream=True); print(r.status_code)"

Run tests:
  python -m pytest tests/test_rental_yield.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | yield_estimate > 0 for all records | min(yield_estimate) > 0 |
| 3 | yield_signal in valid set | GOOD or AVERAGE or LOW |
| 4 | formula correct | yield == round((rent_2br * 12 / price) * 100, 2) |
| 5 | record_count == len(markets) | count matches list length |
