# Part 1 Complete — Tasks 1-4

Date: 2026-05-14
Branch: codex/chat-modes-settings
Test result: 995 passed, 0 failed

## Task 1 — Word boundary fix in query_router.py
- **File:** `query_router.py`
- **Change:** Replaced `any(company in lc for company in KNOWN_LARGE_COMPANIES)` with
  `any(re.search(r'\b' + re.escape(c) + r'\b', lc) for c in KNOWN_LARGE_COMPANIES)`
- **Effect:** "apple pie" no longer triggers GENERAL_FINANCE; "Tell me about Apple" still does.
- `import re` was already present at line 31.

## Task 2 — KNOWN_LARGE_COMPANIES moved to module level
- **File:** `query_router.py` — added `KNOWN_LARGE_COMPANIES: frozenset[str]` after `INTENT_MACRO_RISK_SCAN` constant; removed local definition inside `classify_intent_route()`.
- **File:** `atlas_omega.py` — added `KNOWN_LARGE_COMPANIES: frozenset[str]` after `_OMEGA_ETF_SYMBOLS`; removed local definition inside `OmegaAgent.query()`.

## Task 3 — atlas_prompts/ directory and prompts.json
- **Created:** `atlas_prompts/__init__.py` (empty, makes it a package)
- **Created:** `atlas_prompts/prompts.json` with 6 agent archetypes:
  - `finance_analyst` — tools: Alpaca, GoogleSearch — output: JSON
  - `data_retriever` — tools: GoogleSearch — output: JSON
  - `ui_generator` — tools: Figma — output: HTML
  - `scheduler` — tools: GoogleCalendar — output: JSON
  - `moderator` — tools: none — output: text
  - `document_creator` — tools: GoogleDrive — output: HTML
  - Each has: role, system_prompt, examples (2), tools, output_format, guardrails
  - Also includes `domain_map` mapping 20 intent strings to archetypes

## Task 4 — atlas_prompts/prompt_loader.py
- **Created:** `atlas_prompts/prompt_loader.py`
- `get_agent_prompt(agent_type, query)` — loads archetype by name, injects query, fallback to generic finance prompt
- `get_domain_prompt(domain)` — maps domain string via domain_map, returns archetype system prompt (query-placeholder stripped, ready for caller to prepend)

## Verification
- `python -m py_compile query_router.py` ✅
- `python -m py_compile atlas_omega.py` ✅
- `python -m py_compile atlas_prompts/prompt_loader.py` ✅
- `python -m pytest tests/ -q` → **995 passed** ✅

## Files created or modified
| File | Action |
|------|--------|
| `query_router.py` | Modified — module-level constant + word-boundary regex |
| `atlas_omega.py` | Modified — module-level constant, removed local definition |
| `atlas_prompts/__init__.py` | Created |
| `atlas_prompts/prompts.json` | Created |
| `atlas_prompts/prompt_loader.py` | Created |
