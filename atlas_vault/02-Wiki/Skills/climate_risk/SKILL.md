---
name: Climate Risk/FEMA Bot
description: Tracks FEMA flood zone changes and NFIP data by region; classifies risk as EXTREME/HIGH/MODERATE/LOW and insurance impact
type: reference
agent: M4
division: Macro Risk & Geopolitics
---

# Skill: Climate Risk/FEMA Bot (M4)

## [D] Direction
Fetch FEMA NFIP policy data and flood zone map changes. Classify risk_level per region:
Zone AE → EXTREME, Zone A → HIGH, Zone X500 → MODERATE, Zone X → LOW.
Classify insurance impact: UNINSURABLE/HIGH_PREMIUM/NORMAL/LOW_PREMIUM.
Save to data_cache/climate_risk_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/macro scraper pattern
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://www.fema.gov/api/open/v1/fimaNfipPolicies (public FEMA API)
Secondary:  NOAA climate data API
Output:     data_cache/climate_risk_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.climate_risk.climate_risk_scraper

Run tests:
  python -m pytest tests/test_climate_risk.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | risk_level in valid set | EXTREME/HIGH/MODERATE/LOW |
| 3 | impact_on_insurance in valid set | UNINSURABLE/HIGH_PREMIUM/NORMAL/LOW_PREMIUM |
| 4 | change in valid set | INCREASING/STABLE/DECREASING |
| 5 | record_count == len(flood_zone_changes) | count matches |
