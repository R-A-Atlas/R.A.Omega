---
name: Inflation/CPI Bot
description: Fetches BLS CPI series CUUR0000SA0 for headline and core inflation; classifies as HOT/ELEVATED/ON_TARGET/DEFLATIONARY by YoY change
type: reference
agent: M7
division: Macro Risk & Geopolitics
---

# Skill: Inflation/CPI Bot (M7)

## [D] Direction
Fetch BLS CPI series CUUR0000SA0 (all items) and CUUR0000SA0L1E (core ex food/energy).
Compute MoM and YoY change. Classify: >=4% → HOT, >=2.5% → ELEVATED,
>=1.5% → ON_TARGET, <1.5% → DEFLATIONARY. Save to data_cache/cpi_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/macro/jobs scraper (BLS API pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.bls.gov/publicAPI/v2/timeseries/data/
Series:     CUUR0000SA0, CUUR0000SA0L1E, CUUR0000SAF1, CUUR0000SA0E, CUUR0000SEHA
Output:     data_cache/cpi_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.inflation.inflation_scraper

Run tests:
  python -m pytest tests/test_inflation.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | inflation_signal in valid set | HOT/ELEVATED/ON_TARGET/DEFLATIONARY |
| 3 | cpi_index > 0 | positive float |
| 4 | yoy_change_pct present | top-level field |
| 5 | categories present | list with name + yoy_change_pct |
