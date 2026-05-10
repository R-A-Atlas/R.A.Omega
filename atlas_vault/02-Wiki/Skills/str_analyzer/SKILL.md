---
name: Airbnb/STR Analyzer
description: Fetches Inside Airbnb public listings CSVs to compute avg daily rate, occupancy, annual revenue; classifies regulation risk as HIGH/MEDIUM/LOW
type: reference
agent: R3
division: Real Estate & Property
---

# Skill: Airbnb/STR Analyzer (R3)

## [D] Direction
Fetch Inside Airbnb listings.csv.gz for top US STR markets.
Compute avg_daily_rate (mean price from active listings), occupancy_rate
(availability_365 / 365), annual_revenue_est = round(ADR * occupancy * 365).
Classify regulation_risk from hardcoded reference table.
Save to data_cache/str_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (CSV fetch + parse)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    http://insideairbnb.com/get-the-data/ (public CC-licensed datasets)
Output:     data_cache/str_latest.json

Revenue formula:
  annual_revenue_est = round(avg_daily_rate * occupancy_rate * 365)

Regulation risk (hardcoded):
  HIGH:   NYC, San Francisco, Santa Monica, Honolulu, New Orleans
  MEDIUM: Nashville, Austin, Denver, Miami, LA, Seattle
  LOW:    Phoenix, Tampa, Charlotte, Atlanta, Dallas, Houston

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.str_analyzer.str_analyzer_scraper

Test Inside Airbnb availability:
  python -c "import requests; r = requests.get('http://insideairbnb.com/get-the-data/'); print(r.status_code)"

Run tests:
  python -m pytest tests/test_str_analyzer.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | occupancy_rate in (0, 1] | all records 0 < occ <= 1.0 |
| 3 | annual_revenue_est formula correct | round(ADR * occ * 365) |
| 4 | regulation_risk in valid set | HIGH or MEDIUM or LOW |
| 5 | avg_daily_rate > 0 | min(avg_daily_rate) > 0 |
