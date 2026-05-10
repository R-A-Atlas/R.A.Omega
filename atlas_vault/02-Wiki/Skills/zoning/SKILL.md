---
name: Zoning & Permit Watcher
description: Fetches US Census BPS building permit counts by type; classifies YoY trend as SURGING/GROWING/STABLE/DECLINING/COLLAPSING
type: reference
agent: R5
division: Real Estate & Property
---

# Skill: Zoning & Permit Watcher (R5)

## [D] Direction
Fetch Building Permits Survey data from Census API (api.census.gov/data/timeseries/eits/bps).
Pull current month + same month prior year for 1-Unit, 2-4 Unit, 5+ Unit, Total Residential.
Compute yoy_change = (current - prior) / prior * 100.
Classify: >= 20% → SURGING, >= 5% → GROWING, >= -5% → STABLE,
          >= -20% → DECLINING, < -20% → COLLAPSING.
Save to data_cache/zoning_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (REST fetch + classify)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.census.gov/data/timeseries/eits/bps (no auth)
Secondary:  HUD SOCDS permits database (MSA-level)
Output:     data_cache/zoning_latest.json

Trend thresholds:
  yoy_change >= 20%   → SURGING
  yoy_change >= 5%    → GROWING
  yoy_change >= -5%   → STABLE
  yoy_change >= -20%  → DECLINING
  yoy_change < -20%   → COLLAPSING

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.zoning.zoning_scraper

Test Census BPS API:
  python -c "import requests; r = requests.get('https://api.census.gov/data/timeseries/eits/bps?get=cell_value,time_slot_id&for=us:1&time=2025-01'); print(r.status_code)"

Run tests:
  python -m pytest tests/test_zoning.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | trend_signal in valid set | SURGING/GROWING/STABLE/DECLINING/COLLAPSING |
| 3 | count >= 0 | no negative permit counts |
| 4 | period format correct | matches YYYY-MM |
| 5 | record_count == len(permits) | count matches list length |
