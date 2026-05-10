# Skill: HYSA Tracker
# ID: W4 | Division: 3-Wealth
# DBS Framework

## [D] Direction
HYSA Tracker — part of the ATLAS 3-Wealth division.
Output: data_cache/hysa_latest.json
Source: FDIC BankFind API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/wealth/hysa/__init__.py
  python atlas_agents/wealth/hysa/<scraper>.py --dry-run
  python -m pytest tests/test_hysa_tracker.py -v
  python -m atlas_core.validation.data_validator
