# Skill: Excel Model Agent
# ID: DOC4 | Division: 10-Documents
# DBS Framework

## [D] Direction
Excel Model Agent — part of the ATLAS 10-Documents division.
Output: atlas_vault/03-Outputs/Models/*.xlsx
Source: openpyxl
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/documents/excel/__init__.py
  python atlas_agents/documents/excel/<scraper>.py --dry-run
  python -m pytest tests/test_excel_model_agent.py -v
  python -m atlas_core.validation.data_validator
