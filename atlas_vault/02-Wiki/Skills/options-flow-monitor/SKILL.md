# Skill: Options Flow Monitor
# ID: D3 | Division: 1-Trading
# DBS Framework

## [D] Direction
Options Flow Monitor — part of the ATLAS 1-Trading division.
Output: data_cache/options_flow_latest.json
Source: CBOE public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/trading/options_flow/__init__.py
  python atlas_agents/trading/options_flow/<scraper>.py --dry-run
  python -m pytest tests/test_options_flow_monitor.py -v
  python -m atlas_core.validation.data_validator
