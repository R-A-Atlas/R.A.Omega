---
name: API Integrator
description: Writes atlas_core/connectors/<name>.py modules with auth, rate limiting, and error handling for external APIs
type: reference
agent: E3
division: Engineering
---

# Skill: API Integrator (E3)

## [D] Direction
Given an API name, produce a connector module in atlas_core/connectors/<name>.py.
Each connector exposes authenticate() and get(endpoint, params).
Auth via env vars only. Use requests_get_json from agent_utils — never raw requests.

## [B] Blueprints
Output dir:   atlas_core/connectors/
Utils import: from atlas_core.utils.agent_utils import requests_get_json
Auth pattern: os.environ.get("ATLAS_<NAME>_KEY") — raise ValueError if required but missing

Priority connectors:
  coingecko.py     — CoinGecko public API (no auth)
  fred_api.py      — FRED economic data (free, api.stlouisfed.org)
  bls_api.py       — Bureau of Labor Statistics (data.bls.gov, no auth)
  treasury_api.py  — US Treasury fiscaldata.treasury.gov (no auth)
  sec_edgar.py     — SEC EDGAR efts.sec.gov (no auth)

## [S] Solutions
Validate connector:
  python -m py_compile atlas_core/connectors/<name>.py
  python -c "from atlas_core.connectors import <name>; print(<name>.get('/ping'))"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | authenticate() raises ValueError when key missing | ValueError raised |
| 3 | get() returns dict on public endpoint | type == dict |
| 4 | no hardcoded secrets in source | grep finds no API key strings |
| 5 | BASE_URL constant defined at module top | hasattr(module, 'BASE_URL') |
