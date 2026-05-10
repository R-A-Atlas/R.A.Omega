---
name: Energy Grid Monitor
description: Fetches EIA electricity and gas prices plus grid mix breakdown; classifies trend as GREENING/STABLE/FOSSIL_RECOVERY based on renewables share
type: reference
agent: M3
division: Macro Risk & Geopolitics
---

# Skill: Energy Grid Monitor (M3)

## [D] Direction
Fetch EIA API for national electricity avg price (cents/kWh), gas avg ($/gallon),
and generation mix by source (Coal/Gas/Nuclear/Wind/Solar/Hydro/Other).
Classify: renewables YoY up >=2% → GREENING, down → FOSSIL_RECOVERY, else STABLE.
Save to data_cache/energy_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/macro/fed_watch scraper (REST + classify)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.eia.gov/v2/ (no auth required)
Output:     data_cache/energy_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.energy.energy_scraper

Run tests:
  python -m pytest tests/test_energy.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | electricity_avg_kwh_cents > 0 | positive float |
| 3 | trend in valid set | GREENING, STABLE, or FOSSIL_RECOVERY |
| 4 | breakdown pct sums to ~100 | abs(sum - 100) <= 1 |
| 5 | record_count == len(breakdown) | count matches |
