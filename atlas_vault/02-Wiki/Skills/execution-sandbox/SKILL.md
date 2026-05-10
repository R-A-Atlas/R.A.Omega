# Skill: Execution Sandbox
# ID: C3 | Division: 13-Cognitive
# DBS Framework

## [D] Direction
Execution Sandbox — part of the ATLAS 13-Cognitive division.
Output: APPROVED or REJECTED with traceback
Source: Docker + pytest
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/cognitive/sandbox/__init__.py
  python atlas_agents/cognitive/sandbox/<scraper>.py --dry-run
  python -m pytest tests/test_execution_sandbox.py -v
  python -m atlas_core.validation.data_validator
