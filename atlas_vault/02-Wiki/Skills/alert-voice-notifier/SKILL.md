# Skill: Alert Voice Notifier
# ID: V4 | Division: 9-Voice
# DBS Framework

## [D] Direction
Alert Voice Notifier — part of the ATLAS 9-Voice division.
Output: Twilio voice call
Source: Twilio API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/voice/notifier/__init__.py
  python atlas_agents/voice/notifier/<scraper>.py --dry-run
  python -m pytest tests/test_alert_voice_notifier.py -v
  python -m atlas_core.validation.data_validator
