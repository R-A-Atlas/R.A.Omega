# Skill: Credit Card Optimizer
# ID: W1 | Division: 3-Wealth
# DBS Framework

## [D] Direction
Credit Card Optimizer — part of the ATLAS 3-Wealth division.
Output: data_cache/credit_cards_latest.json
Source: CFPB public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/wealth/credit_cards/__init__.py
  python atlas_agents/wealth/credit_cards/<scraper>.py --dry-run
  python -m pytest tests/test_credit_card_optimizer.py -v
  python -m atlas_core.validation.data_validator
