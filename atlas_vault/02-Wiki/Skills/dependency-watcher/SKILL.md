# Skill: Dependency Watcher
# ID: E9 | Division: 0-Engineering
# DBS Framework

## [D] Direction
Dependency Watcher — part of the ATLAS 0-Engineering division.
Output: requirements.txt
Source: pip
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/engineering/dep_watcher/__init__.py
  python atlas_agents/engineering/dep_watcher/<scraper>.py --dry-run
  python -m pytest tests/test_dependency_watcher.py -v
  python -m atlas_core.validation.data_validator
