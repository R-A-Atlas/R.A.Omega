---
name: Residential Scout
description: Fetches Redfin/Zillow public CSV data for top 20 US metros; tracks median price, YoY change, days on market, inventory
type: reference
agent: R1
division: Real Estate & Property
---

# Skill: Residential Scout (R1)

## [D] Direction
Download Redfin Metro Market Tracker public TSV (gzip). Filter to top 20 metros,
latest period. Extract: city, state, median_price, yoy_change, days_on_market, inventory.
Save to data_cache/residential_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (CSV fetch + parse pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz
Secondary:  Zillow ZHVI metro CSV (public S3)
Output:     data_cache/residential_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.residential.residential_scraper

Test Redfin URL:
  python -c "import requests; r = requests.get('https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz', stream=True); print(r.status_code)"

Run tests:
  python -m pytest tests/test_residential.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | all records have required fields | city, state, median_price, yoy_change, days_on_market, inventory |
| 3 | median_price > 0 | min(median_price) > 0 |
| 4 | record_count == len(markets) | count matches list length |
| 5 | generated_at is ISO UTC string | parseable as datetime |
