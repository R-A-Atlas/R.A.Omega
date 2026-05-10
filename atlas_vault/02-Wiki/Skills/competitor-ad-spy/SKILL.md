# Skill: Competitor Ad Spy
# ID: G3 | Division: 8-Growth
# DBS Framework

## [D] Direction
Competitor Ad Spy — part of the ATLAS 8-Growth division.
Output: data_cache/competitor_ads_latest.json
Source: Meta Ad Library API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/growth/ad_spy/__init__.py
  python atlas_agents/growth/ad_spy/<scraper>.py --dry-run
  python -m pytest tests/test_competitor_ad_spy.py -v
  python -m atlas_core.validation.data_validator
