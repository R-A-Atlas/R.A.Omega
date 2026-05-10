# Skill: Comparison Report Agent
# ID: DOC6 | Division: 10-Documents
# DBS Framework

## [D] Direction
Comparison Report Agent — part of the ATLAS 10-Documents division.
Output: Multi-ticker HTML report
Source: POST /compare endpoint
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/documents/comparison/__init__.py
  python atlas_agents/documents/comparison/<scraper>.py --dry-run
  python -m pytest tests/test_comparison_report_agent.py -v
  python -m atlas_core.validation.data_validator
