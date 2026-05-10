---
name: Skill Scripter
description: Writes boilerplate Python scrapers and DBS skill files following the crypto_scraper.py pattern
type: reference
agent: E1
division: Engineering
---

# Skill: Skill Scripter (E1)

## [D] Direction
Write boilerplate Python scrapers following the crypto_scraper.py pattern.
Always use atlas_core.utils.agent_utils. Always write a matching test file.
Output three files per request: scraper, SKILL.md, test.

## [B] Blueprints
Pattern:  atlas_agents/crypto/crypto_scraper.py
Utils:    atlas_core/utils/agent_utils.py
Tests:    tests/test_crypto_scraper.py
Schema:   { generated_at, source, record_count, <domain>: [...] }

## [S] Solutions
Validation:
  python -m py_compile atlas_agents/<division>/<name>/<name>_scraper.py
  python -m pytest tests/test_<name>_scraper.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | key exists, non-empty ISO string |
| 3 | record_count matches array length | int == len(data_array) |
| 4 | write_cache_json_pair creates two files | stable + stamped both exist |
| 5 | test file imports without error | pytest collect passes |
