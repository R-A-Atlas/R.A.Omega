# Skill: Zoning Permit Watcher
# ID: R5 | Division: 2-RealEstate
# DBS Framework

## [D] Direction
Zoning Permit Watcher — part of the ATLAS 2-RealEstate division.
Output: data_cache/zoning_latest.json
Source: City open data portals
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/realestate/zoning/__init__.py
  python atlas_agents/realestate/zoning/<scraper>.py --dry-run
  python -m pytest tests/test_zoning_permit_watcher.py -v
  python -m atlas_core.validation.data_validator
