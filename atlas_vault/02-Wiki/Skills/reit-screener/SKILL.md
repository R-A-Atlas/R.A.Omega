# Skill: REIT Screener
# ID: R6 | Division: 2-RealEstate
# DBS Framework

## [D] Direction
REIT Screener — part of the ATLAS 2-RealEstate division.
Output: data_cache/reits_latest.json
Source: yfinance + SEC EDGAR
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/realestate/reit_screener/__init__.py
  python atlas_agents/realestate/reit_screener/<scraper>.py --dry-run
  python -m pytest tests/test_reit_screener.py -v
  python -m atlas_core.validation.data_validator
