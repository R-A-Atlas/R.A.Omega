# PROMPTS_APPLIED — Tasks 1-8 Complete

Date: 2026-05-14
Branch: codex/chat-modes-settings
Test result: 1010 passed (was 995 before this sprint; +15 new tests)

---

## All Files Created or Modified

| File | Action | Task |
|------|--------|------|
| `query_router.py` | Modified | 1, 2, 6 |
| `atlas_omega.py` | Modified | 2, 5, 6 |
| `atlas_prompts/__init__.py` | Created | 3 |
| `atlas_prompts/prompts.json` | Created | 3 |
| `atlas_prompts/prompt_loader.py` | Created | 4 |
| `atlas_prompts/generate_prompts.py` | Created | 7 |
| `tests/test_prompt_loader.py` | Created | 8 |
| `PART1_DONE.md` | Created | 1-4 confirmation |
| `PROMPTS_APPLIED.md` | Created | this file |

---

## Task Summary

### Task 1 — Word-boundary fix (query_router.py)
Replaced `any(company in lc ...)` substring check with `re.search(r'\b' + re.escape(c) + r'\b', lc)`.
"pineapple" or "snapple" no longer trigger GENERAL_FINANCE.

### Task 2 — KNOWN_LARGE_COMPANIES to module level
Moved frozenset to module level in both `query_router.py` (after `INTENT_MACRO_RISK_SCAN`) and `atlas_omega.py` (after `_OMEGA_ETF_SYMBOLS`). Removed local definitions inside functions.

### Task 3 — atlas_prompts/ package
Created `atlas_prompts/__init__.py` (empty) and `atlas_prompts/prompts.json` with 6 archetypes:
- `finance_analyst`, `data_retriever`, `ui_generator`, `scheduler`, `moderator`, `document_creator`
- Each has: role, system_prompt, examples (2), tools, output_format, guardrails
- Plus `domain_map` mapping 20 intent strings to archetypes

### Task 4 — prompt_loader.py
`get_agent_prompt(agent_type, query)` — finds archetype, injects query, fallback to generic finance.
`get_domain_prompt(domain)` — maps domain → archetype → returns system prompt (no query placeholder).

### Task 5 — Wire prompt_loader into _synthesize()
In `atlas_omega.py:_synthesize()`: lazy-imports `get_domain_prompt`, computes `agent_system_prompt`,
prepends it to `prompt` before Gemini call if non-empty.

### Task 6 — INTENT_CASUAL
- `INTENT_CASUAL = "CASUAL"` added to `query_router.py`
- `CASUAL_PATTERNS` tuple added at module level
- Company name check now guards against casual queries (so "apple pie recipe" → INTENT_CASUAL, not GENERAL_FINANCE)
- `if gen == 0.0 and mkt == 0.0 and any(casual pattern)` → `return INTENT_CASUAL`
- `route()` in QueryRouter: `INTENT_CASUAL` routes to OmegaAgent with `intent_route=route_kind`
- `OmegaAgent.query()`: new `intent_route` parameter; early return to `_respond_casual()` when CASUAL
- `OmegaAgent._respond_casual()`: returns plain conversational response using friendly Gemini prompt

### Task 7 — generate_prompts.py
Jinja2 script reads `AGENT_REGISTRY.md`, parses 19 agent rows, maps division prefixes to archetypes,
generates `system_prompt` per agent, and writes to `prompts.json` under `generated_agents` key.
Dry-run: `python atlas_prompts/generate_prompts.py --dry-run`

### Task 8 — tests/test_prompt_loader.py
15 tests covering:
- `get_agent_prompt` returns non-empty, injects query, fallback on unknown type
- `get_domain_prompt` returns finance analyst for GENERAL_FINANCE and REAL_ESTATE_SCAN, empty for unknown
- "apple pie recipe" does NOT route to GENERAL_FINANCE ✅
- "Tell me about Apple revenue" routes to GENERAL_FINANCE ✅
- "hey how are you" routes to INTENT_CASUAL ✅
- hello, weather → INTENT_CASUAL ✅
- "Analyze NVDA" → INTENT_MARKET_DEEP_DIVE ✅
- BlackRock, Microsoft → INTENT_GENERAL_FINANCE ✅
- `INTENT_CASUAL == "CASUAL"` ✅

---

## Verification
- `python -m py_compile query_router.py atlas_omega.py atlas_prompts/prompt_loader.py atlas_prompts/generate_prompts.py` ✅
- `python atlas_prompts/generate_prompts.py --dry-run` ✅ (19 agents parsed)
- `python -m pytest tests/ -q` → **1010 passed** ✅
- deep_research.py and gemini_limiter.py: untouched ✅
- atlas_memory.db and atlas_tracker.db: untouched ✅
