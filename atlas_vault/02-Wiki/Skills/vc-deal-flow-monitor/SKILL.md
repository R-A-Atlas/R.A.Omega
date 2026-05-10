# Skill: VC Deal Flow Monitor
# ID: B6 | Division: 5-Business
# DBS Framework

## [D] Direction
VC Deal Flow Monitor — part of the ATLAS 5-Business division.
Output: data_cache/vc_deals_latest.json
Source: Crunchbase public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/business/vc_deals/__init__.py
  python atlas_agents/business/vc_deals/<scraper>.py --dry-run
  python -m pytest tests/test_vc_deal_flow_monitor.py -v
  python -m atlas_core.validation.data_validator
