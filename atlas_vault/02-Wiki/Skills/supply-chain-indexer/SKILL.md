# Skill: Supply Chain Indexer
# ID: M2 | Division: 7-Macro
# DBS Framework

## [D] Direction
Supply Chain Indexer — part of the ATLAS 7-Macro division.
Output: data_cache/supply_chain_latest.json
Source: Freightos public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/macro/supply_chain/__init__.py
  python atlas_agents/macro/supply_chain/<scraper>.py --dry-run
  python -m pytest tests/test_supply_chain_indexer.py -v
  python -m atlas_core.validation.data_validator
