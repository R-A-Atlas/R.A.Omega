# Skill: UI UX Porter
# ID: E4 | Division: 0-Engineering
# DBS Framework

## [D] Direction
UI UX Porter — part of the ATLAS 0-Engineering division.
Output: ra_omega_app.html
Source: Internal
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/engineering/ui_porter/__init__.py
  python atlas_agents/engineering/ui_porter/<scraper>.py --dry-run
  python -m pytest tests/test_ui_ux_porter.py -v
  python -m atlas_core.validation.data_validator

