# Skill: Diff Synthesizer
# ID: C6 | Division: 13-Cognitive
# DBS Framework

## [D] Direction
Diff Synthesizer — part of the ATLAS 13-Cognitive division.
Output: Unified diff output
Source: difflib stdlib
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/cognitive/diff_synthesizer/__init__.py
  python atlas_agents/cognitive/diff_synthesizer/<scraper>.py --dry-run
  python -m pytest tests/test_diff_synthesizer.py -v
  python -m atlas_core.validation.data_validator
