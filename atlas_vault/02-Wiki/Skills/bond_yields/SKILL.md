---
name: Bond Yield Curve
description: Fetches US Treasury yields from FiscalData API; classifies curve as NORMAL, FLAT, or INVERTED based on 2y/10y spread
type: reference
agent: T10
division: Trading Desk
---

# Skill: Bond Yield Curve (T10)

## [D] Direction
Fetch daily Treasury par yield curve rates from FiscalData (api.fiscaldata.treasury.gov).
Parse 9 maturities: 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y.
Compute spread_2y_10y = rate_10y - rate_2y.
Classify: < 0 → INVERTED, -0.25 to 0.25 → FLAT, > 0.25 → NORMAL.
Save to data_cache/bond_yields_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (fetch + cache pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
API:        https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates
Output:     data_cache/bond_yields_latest.json

Curve signal thresholds:
  spread_2y_10y < 0              → INVERTED
  |spread_2y_10y| <= 0.25        → FLAT
  spread_2y_10y > 0.25           → NORMAL

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.bond_yields.bond_yields_scraper

Test API directly:
  python -c "import requests; r = requests.get('https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates?fields=record_date,security_desc,avg_interest_rate_amt&filter=security_desc:in:(2-Year,10-Year)&sort=-record_date&page[size]=2'); print(r.json())"

Run tests:
  python -m pytest tests/test_bond_yields.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | curve_signal in valid set | NORMAL or INVERTED or FLAT |
| 3 | spread_2y_10y = rate_10y - rate_2y | arithmetic correct |
| 4 | all rates are positive floats | min(rate) > 0 |
| 5 | record_count == len(yields) | count matches list length |
