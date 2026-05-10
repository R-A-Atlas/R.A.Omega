# Skill: Local File Creator
# ID: CR4 | Division: 14-Compute
# DBS Framework

## [D] Direction
Local File Creator — part of the ATLAS 14-Compute division.
Output: Written files on disk
Source: Pure Python file I/O
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/compute/local_file_creator/__init__.py
  python atlas_agents/compute/local_file_creator/<scraper>.py --dry-run
  python -m pytest tests/test_local_file_creator.py -v
  python -m atlas_core.validation.data_validator
