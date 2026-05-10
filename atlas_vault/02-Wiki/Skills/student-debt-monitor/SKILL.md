# Skill: Student Debt Monitor
# ID: W3 | Division: 3-Wealth
# DBS Framework

## [D] Direction
Student Debt Monitor — part of the ATLAS 3-Wealth division.
Output: data_cache/student_debt_latest.json
Source: StudentAid.gov public
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/wealth/student_debt/__init__.py
  python atlas_agents/wealth/student_debt/<scraper>.py --dry-run
  python -m pytest tests/test_student_debt_monitor.py -v
  python -m atlas_core.validation.data_validator
