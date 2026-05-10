# Skill: Voice Input Whisper
# ID: V1 | Division: 9-Voice
# DBS Framework

## [D] Direction
Voice Input Whisper — part of the ATLAS 9-Voice division.
Output: POST /voice/query endpoint
Source: OpenAI Whisper API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/voice/input/__init__.py
  python atlas_agents/voice/input/<scraper>.py --dry-run
  python -m pytest tests/test_voice_input_whisper.py -v
  python -m atlas_core.validation.data_validator
