# Skill: News Catalyst Agent
# ID: IQ5 | Division: 11-Intelligence
# DBS Framework

## [D] Direction
News Catalyst Agent — part of the ATLAS 11-Intelligence division.
Output: data_cache/news_catalysts_latest.json
Source: Reuters/Bloomberg RSS
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/intelligence/news_catalyst/__init__.py
  python atlas_agents/intelligence/news_catalyst/<scraper>.py --dry-run
  python -m pytest tests/test_news_catalyst_agent.py -v
  python -m atlas_core.validation.data_validator
