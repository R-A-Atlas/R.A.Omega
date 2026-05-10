# Skill: Rental Yield Calculator
# ID: R2 | Division: 2-RealEstate
# DBS Framework

## [D] Direction
Rental Yield Calculator — part of the ATLAS 2-RealEstate division.
Output: data_cache/rental_yield_latest.json
Source: HUD FMR API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/realestate/rental_yield/__init__.py
  python atlas_agents/realestate/rental_yield/<scraper>.py --dry-run
  python -m pytest tests/test_rental_yield_calculator.py -v
  python -m atlas_core.validation.data_validator
