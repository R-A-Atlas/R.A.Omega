# Skill: NL Report Editor
# ID: V6 | Division: 9-Voice
# DBS Framework

## [D] Direction
NL Report Editor — part of the ATLAS 9-Voice division.
Output: Updated HTML report
Source: POST /report/edit endpoint
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/voice/report_editor/__init__.py
  python atlas_agents/voice/report_editor/<scraper>.py --dry-run
  python -m pytest tests/test_nl_report_editor.py -v
  python -m atlas_core.validation.data_validator
