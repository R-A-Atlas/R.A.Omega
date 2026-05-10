# Skill: Sector Rotation Agent
# ID: IQ4 | Division: 11-Intelligence
# DBS Framework

## [D] Direction
Sector Rotation Agent — part of the ATLAS 11-Intelligence division.
Output: data_cache/sector_rotation_latest.json
Source: equities + dark pool
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/intelligence/sector_rotation/__init__.py
  python atlas_agents/intelligence/sector_rotation/<scraper>.py --dry-run
  python -m pytest tests/test_sector_rotation_agent.py -v
  python -m atlas_core.validation.data_validator
