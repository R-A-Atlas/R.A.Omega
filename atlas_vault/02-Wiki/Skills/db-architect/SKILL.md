# Skill: DB Architect
# ID: E5 | Division: 0-Engineering
# DBS Framework

## [D] Direction
DB Architect — part of the ATLAS 0-Engineering division.
Output: schema.sql
Source: Supabase
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/engineering/db_architect/__init__.py
  python atlas_agents/engineering/db_architect/<scraper>.py --dry-run
  python -m pytest tests/test_db_architect.py -v
  python -m atlas_core.validation.data_validator
