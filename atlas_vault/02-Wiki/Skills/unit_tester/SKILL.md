---
name: Unit Tester
description: Writes pytest files for every new agent; enforces 5-test standard (timeout, 429, missing keys, schema, file output)
type: reference
agent: E7
division: Engineering
---

# Skill: Unit Tester (E7)

## [D] Direction
Every new scraper agent ships with exactly 5 tests covering the failure modes
that matter in production. No agent merges without green tests.
Tests use unittest.mock — never live API calls. Use tmp_path for file I/O tests.

## [B] Blueprints
Canonical examples:
  tests/test_crypto_scraper.py     — timeout + 429 + invalid JSON + scrape() + categories
  tests/test_equities_scraper.py   — normalize + filter + validate + schema
  tests/security/test_security.py  — security layer (E6 pattern)

5-test standard per scraper:
  1. test_handles_api_timeout        — mock raises Exception("timeout")
  2. test_handles_429_rate_limit     — mock raises Exception("429")
  3. test_handles_missing_json_keys  — mock returns {}
  4. test_valid_output_schema        — check required fields in scrape() output
  5. test_file_output                — write_outputs() creates stable + stamped file

Non-scraper agents (E*, meta-agents):
  1. test_<id>_package_importable    — import smoke test
  2. test_<id>_agent_prompt_exists   — AGENT_PROMPT.md non-empty
  3. test_<id>_skill_md_exists       — SKILL.md in vault non-empty
  + domain-specific assertions (guardrails, exports, config checks)

## [S] Solutions
Run after writing any test file:
  python -m py_compile tests/test_<name>.py
  python -m pytest tests/test_<name>.py -v
  python -m pytest tests/ -q              # full regression check

Confirm no live API calls:
  grep -n "requests.get\b" tests/test_<name>.py  # should return nothing

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | all 5 tests present | grep "def test_" count >= 5 |
| 3 | no live requests.get calls | grep returns empty |
| 4 | full pytest suite green | 0 failures, 0 errors |
| 5 | tmp_path used for file tests | no writes to real data_cache/ |
