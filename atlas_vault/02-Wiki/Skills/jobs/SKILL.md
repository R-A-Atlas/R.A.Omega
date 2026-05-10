---
name: Job Market/BLS Bot
description: Fetches BLS nonfarm payroll and unemployment data; classifies labor market as STRONG/HEALTHY/WEAK/RECESSIONARY by monthly jobs added
type: reference
agent: M6
division: Macro Risk & Geopolitics
---

# Skill: Job Market/BLS Bot (M6)

## [D] Direction
Fetch BLS series CES0000000001 (nonfarm payroll) and LNS14000000 (unemployment).
Compute jobs_added_thousands MoM. Classify: >=200k → STRONG, >=100k → HEALTHY,
>=0 → WEAK, <0 → RECESSIONARY. Save to data_cache/jobs_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/macro/inflation scraper (BLS API pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.bls.gov/publicAPI/v2/timeseries/data/ (no auth)
Output:     data_cache/jobs_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.jobs.jobs_scraper

Run tests:
  python -m pytest tests/test_jobs.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | labor_signal in valid set | STRONG/HEALTHY/WEAK/RECESSIONARY |
| 3 | unemployment_rate in (0, 20) | realistic range |
| 4 | sector_breakdown present | list with sector records |
| 5 | record_count == len(sector_breakdown) | count matches |
