# Skill: CRM Sync Agent
# ID: G2 | Division: 8-Growth
# DBS Framework

## [D] Direction
CRM Sync Agent — part of the ATLAS 8-Growth division.
Output: Supabase direct
Source: n8n/ManyChat webhooks
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/growth/crm_sync/__init__.py
  python atlas_agents/growth/crm_sync/<scraper>.py --dry-run
  python -m pytest tests/test_crm_sync_agent.py -v
  python -m atlas_core.validation.data_validator
