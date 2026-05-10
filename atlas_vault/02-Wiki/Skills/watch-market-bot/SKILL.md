# Skill: Watch Market Bot
# ID: A1 | Division: 6-Alternative
# DBS Framework

## [D] Direction
Watch Market Bot — part of the ATLAS 6-Alternative division.
Output: data_cache/watches_latest.json
Source: Chrono24 public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/alternative/watches/__init__.py
  python atlas_agents/alternative/watches/<scraper>.py --dry-run
  python -m pytest tests/test_watch_market_bot.py -v
  python -m atlas_core.validation.data_validator
