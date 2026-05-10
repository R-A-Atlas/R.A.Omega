# Skill: White Label Agent
# ID: P5 | Division: 12-Platform
# DBS Framework

## [D] Direction
White Label Agent — part of the ATLAS 12-Platform division.
Output: Rebranded HTML/PDF
Source: B2B RIA feature
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/platform/white_label/__init__.py
  python atlas_agents/platform/white_label/<scraper>.py --dry-run
  python -m pytest tests/test_white_label_agent.py -v
  python -m atlas_core.validation.data_validator
