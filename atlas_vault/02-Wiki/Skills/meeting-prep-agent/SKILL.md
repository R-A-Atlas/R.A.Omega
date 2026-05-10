# Skill: Meeting Prep Agent
# ID: V5 | Division: 9-Voice
# DBS Framework

## [D] Direction
Meeting Prep Agent — part of the ATLAS 9-Voice division.
Output: atlas_vault/03-Outputs/Reports/meeting_prep_*.html
Source: Internal
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/voice/meeting_prep/__init__.py
  python atlas_agents/voice/meeting_prep/<scraper>.py --dry-run
  python -m pytest tests/test_meeting_prep_agent.py -v
  python -m atlas_core.validation.data_validator
