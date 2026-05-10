# Skill: Physical Metals Bot
# ID: A5 | Division: 6-Alternative
# DBS Framework

## [D] Direction
Physical Metals Bot — part of the ATLAS 6-Alternative division.
Output: data_cache/metals_latest.json
Source: APMEX/JM Bullion public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/alternative/metals/__init__.py
  python atlas_agents/alternative/metals/<scraper>.py --dry-run
  python -m pytest tests/test_physical_metals_bot.py -v
  python -m atlas_core.validation.data_validator
