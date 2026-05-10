# Skill: Bankruptcy Parser
# ID: L3 | Division: 4-Legal
# DBS Framework

## [D] Direction
Bankruptcy Parser — part of the ATLAS 4-Legal division.
Output: data_cache/bankruptcy_latest.json
Source: US Courts public stats
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/legal/bankruptcy/__init__.py
  python atlas_agents/legal/bankruptcy/<scraper>.py --dry-run
  python -m pytest tests/test_bankruptcy_parser.py -v
  python -m atlas_core.validation.data_validator
