# Skill: Local Scaffolding Ollama
# ID: CR3 | Division: 14-Compute
# DBS Framework

## [D] Direction
Local Scaffolding Ollama — part of the ATLAS 14-Compute division.
Output: Empty files and folders
Source: Ollama local LLM
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/compute/local_scaffold/__init__.py
  python atlas_agents/compute/local_scaffold/<scraper>.py --dry-run
  python -m pytest tests/test_local_scaffolding_ollama.py -v
  python -m atlas_core.validation.data_validator
