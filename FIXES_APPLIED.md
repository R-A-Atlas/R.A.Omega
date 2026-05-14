# FIXES_APPLIED.md
**Date:** 2026-05-14  
**Source:** deep-research-report.md  
**Status:** All three fixes applied, all files compile clean, 995 tests passing.

---

## FIX 1 — api_server.py: raw query to router

**File:** `api_server.py`  
**Change:** `router.route(route_input, ...)` → `router.route(q_store, ...)`

The router now receives only the stripped user query (`q_store`) instead of
the pre-enriched `route_input` (which contained request-control hints, memory
context, and vault context). This ensures `classify_intent_route()` sees
the original plain query for clean intent classification. Request controls
and context are still applied to the response via `shaped["_request_controls"]`.

**Tests updated:** Two test assertions that checked for "Research mode: DEEP/NORMAL"
and specialist-packet content inside the router's query argument were updated to
verify `calls[0]["query"] == <raw query>` instead.

---

## FIX 2 — query_router.py: KNOWN_LARGE_COMPANIES early-return

**File:** `query_router.py`  
**Function:** `classify_intent_route()`  
**Change:** Added `KNOWN_LARGE_COMPANIES` set check immediately after the empty-query
guard, before the keyword scoring loop. If any known company name is found in the
lowercase query, returns `INTENT_GENERAL_FINANCE` immediately.

Companies covered: blackrock, apple, microsoft, google, amazon, tesla, jpmorgan,
goldman sachs, morgan stanley, berkshire, warren buffett, vanguard, fidelity,
citadel, bridgewater, sequoia, softbank.

**Verified:**
- "Give me everything on BlackRock" → `GENERAL_FINANCE` ✅
- "Tell me about Apple" → `GENERAL_FINANCE` ✅
- "Analyze NVDA setup" → `MARKET_DEEP_DIVE` ✅ (not affected)

---

## FIX 3 — atlas_omega.py: web search for company queries

**File:** `atlas_omega.py`  
**Functions:** `OmegaAgent.query()` and `OmegaAgent._synthesize()`

**Part 1 — query():** When `domain == "GENERAL_FINANCE"` and a known company name is
found in `user_query`, prepend a structured web search instruction to the query:
`"Search the web for current information about {company}. Include: what they do,
AUM/revenue, recent news, key executives, business model, competitive position. "`

**Part 2 — _synthesize():** Conditionally enable the `gtypes.GoogleSearch()` Gemini
grounding tool when `query.lower().startswith("search the web")`. Otherwise uses the
original config (JSON mode only, no web search).

---

## Compile Status

```
python -m py_compile api_server.py       → OK
python -m py_compile query_router.py     → OK
python -m py_compile atlas_omega.py      → OK
```

## Test Status

```
python -m pytest tests/ -q → 995 passed, 0 failed, 2 warnings
```
