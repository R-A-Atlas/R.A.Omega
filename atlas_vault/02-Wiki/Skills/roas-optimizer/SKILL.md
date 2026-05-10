# Skill: ROAS Optimizer
# ID: G10 | Division: 8-Growth
# DBS Framework

## [D] Direction
ROAS Optimizer — part of the ATLAS 8-Growth division.
Output: data_cache/roas_latest.json
Source: Meta Ads API + Google Ads API
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/growth/roas/__init__.py
  python atlas_agents/growth/roas/<scraper>.py --dry-run
  python -m pytest tests/test_roas_optimizer.py -v
  python -m atlas_core.validation.data_validator
