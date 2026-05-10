# Skill: Forex Radar
# ID: D6 | Division: 1-Trading
# DBS Framework

## [D] Direction
Forex Radar — part of the ATLAS 1-Trading division.
Output: data_cache/forex_latest.json
Source: frankfurter.app (free)
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/trading/forex_radar/__init__.py
  python atlas_agents/trading/forex_radar/<scraper>.py --dry-run
  python -m pytest tests/test_forex_radar.py -v
  python -m atlas_core.validation.data_validator
