# Skill: Ecommerce Trends Bot
# ID: B3 | Division: 5-Business
# DBS Framework

## [D] Direction
Ecommerce Trends Bot — part of the ATLAS 5-Business division.
Output: data_cache/ecommerce_latest.json
Source: pytrends (Google Trends)
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/business/ecommerce/__init__.py
  python atlas_agents/business/ecommerce/<scraper>.py --dry-run
  python -m pytest tests/test_ecommerce_trends_bot.py -v
  python -m atlas_core.validation.data_validator
