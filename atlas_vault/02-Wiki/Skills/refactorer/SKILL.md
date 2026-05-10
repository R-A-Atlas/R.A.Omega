---
name: Refactorer
description: Scans repo for duplicate code patterns (3+ occurrences) and extracts them into atlas_core/utils/agent_utils.py
type: reference
agent: E2
division: Engineering
---

# Skill: Refactorer (E2)

## [D] Direction
Find duplicate logic across .py files. Extract patterns that appear 3+ times
into atlas_core/utils/agent_utils.py. Update all callers. Never break imports.
One refactor at a time. Never touch protected core files.

## [B] Blueprints
Target file:  atlas_core/utils/agent_utils.py
Pattern ref:  requests_get_json(), write_cache_json_pair(), sleep_backoff()
Caller ref:   atlas_agents/crypto/crypto_scraper.py (canonical import example)

Protected (never touch):
  query_router.py | atlas_omega.py | deep_research.py | gemini_limiter.py

## [S] Solutions
Scan for duplicates:
  grep -rn "def fetch_" atlas_agents/ --include="*.py"
  grep -rn "import requests" atlas_agents/ --include="*.py"

Validate after refactor:
  python -m py_compile <every touched file>
  python -m pytest tests/ -q
  python -c "import api_server"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile all touched files | all exit 0 |
| 2 | pytest suite passes | 0 failures |
| 3 | api_server importable | no ImportError |
| 4 | net line reduction positive | removed > added |
| 5 | no caller left using old duplicate | grep finds 0 old usages |
