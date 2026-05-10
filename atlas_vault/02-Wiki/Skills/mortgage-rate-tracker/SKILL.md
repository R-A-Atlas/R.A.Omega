# Skill: Mortgage Rate Tracker
# ID: R7 | Division: 2-RealEstate
# DBS Framework

## [D] Direction
Mortgage Rate Tracker — part of the ATLAS 2-RealEstate division.
Output: data_cache/mortgage_rates_latest.json
Source: Freddie Mac PMMS
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/realestate/mortgage_rates/__init__.py
  python atlas_agents/realestate/mortgage_rates/<scraper>.py --dry-run
  python -m pytest tests/test_mortgage_rate_tracker.py -v
  python -m atlas_core.validation.data_validator
