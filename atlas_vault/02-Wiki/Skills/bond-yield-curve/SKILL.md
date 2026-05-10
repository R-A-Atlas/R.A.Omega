# Skill: Bond Yield Curve
# ID: D10 | Division: 1-Trading
# DBS Framework

## [D] Direction
Bond Yield Curve — part of the ATLAS 1-Trading division.
Output: data_cache/bond_yields_latest.json
Source: api.fiscaldata.treasury.gov
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/trading/bond_yields/__init__.py
  python atlas_agents/trading/bond_yields/<scraper>.py --dry-run
  python -m pytest tests/test_bond_yield_curve.py -v
  python -m atlas_core.validation.data_validator
