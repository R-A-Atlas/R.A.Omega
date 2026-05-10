---
name: Supply Chain Indexer
description: Tracks Freightos Baltic Index container shipping rates by route; classifies WoW trend as SPIKING/RISING/STABLE/FALLING/COLLAPSING
type: reference
agent: M2
division: Macro Risk & Geopolitics
---

# Skill: Supply Chain Indexer (M2)

## [D] Direction
Fetch Freightos Baltic Index (FBX) data for major container shipping routes.
Compute WoW change. Classify: >=20% → SPIKING, >=5% → RISING, -5% to 5% → STABLE,
<=-5% → FALLING, <=-20% → COLLAPSING. Save to data_cache/supply_chain_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/trading/forex_radar/forex_scraper.py (REST fetch + classify)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://fbx.freightos.com/ (Freightos Baltic Index public page)
Output:     data_cache/supply_chain_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.supply_chain.supply_chain_scraper

Run tests:
  python -m pytest tests/test_supply_chain.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | trend in valid set | SPIKING/RISING/STABLE/FALLING/COLLAPSING |
| 3 | rate_usd_40ft > 0 | all routes positive |
| 4 | record_count == len(indices) | count matches |
| 5 | route field present | all records have route name |
