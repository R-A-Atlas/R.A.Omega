# Skill: Webhook Publisher Agent
# ID: P4 | Division: 12-Platform
# DBS Framework

## [D] Direction
Webhook Publisher Agent — part of the ATLAS 12-Platform division.
Output: User-defined webhook URL
Source: httpx async
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/platform/webhooks/__init__.py
  python atlas_agents/platform/webhooks/<scraper>.py --dry-run
  python -m pytest tests/test_webhook_publisher_agent.py -v
  python -m atlas_core.validation.data_validator
