# Skill: Residential Scout
# ID: R1 | Division: 2-RealEstate
# DBS Framework

## [D] Direction
Residential Scout — part of the ATLAS 2-RealEstate division.
Output: data_cache/residential_latest.json
Source: Redfin/Zillow public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/realestate/residential/__init__.py
  python atlas_agents/realestate/residential/<scraper>.py --dry-run
  python -m pytest tests/test_residential_scout.py -v
  python -m atlas_core.validation.data_validator
