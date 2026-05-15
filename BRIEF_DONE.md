# BRIEF_DONE — ra_omega_claude_code_implementation_brief.md

Date: 2026-05-15
Branch: codex/chat-modes-settings
Test result: 1074 passed (was 1027; +47 new tests from test_brief_requirements.py)

---

## Files Created (6 new files)

| File | Purpose |
|------|---------|
| `output_modes.py` | Output mode resolver; `resolve_output_mode(raw_query, intent) -> str` with trade/doc/HTML trigger detection and company-name fallback |
| `output_contracts.py` | `OutputContract` dataclass + `OUTPUT_CONTRACTS` dict — required/forbidden sections per mode |
| `quality_firewall.py` | `validate_response()` — checks forbidden phrases and required sections using OUTPUT_CONTRACTS |
| `response_judge.py` | `judge_response()` — wraps quality_firewall in PASS/FAIL JudgeResult |
| `progress_state.py` | `ProgressState` Enum + `JobProgress` dataclass with terminal-state guard and emit callback |
| `prompt_builder.py` | `build_synthesis_prompt()` — structured sections: raw query, intent, output_mode, memory, live data, required/forbidden |

---

## Files Modified

### query_router.py
- Added 3 new intent constants: `INTENT_HTML_ARTIFACT`, `INTENT_MARKET_DATA`, `INTENT_TRADING_ANALYSIS`
- Added `KNOWN_COMPANIES` dict (16 companies with aliases including "blk", "aapl", "tsla", etc.)
- Added `NON_COMPANY_CONTEXT` dict (apple/amazon/tesla disambiguation)
- Added `_company_phrase_match()` helper (word-boundary regex)
- Added `detect_company_name(raw_query) -> Optional[str]` — alias-based detection with disambiguation
- Added `_EXPLICIT_TRADE_RE` — catches "trade setup", "buy calls", "stop loss", etc.
- Updated `classify_intent_route()`:
  - Explicit trade requests checked FIRST (before company detection) so "trade setup for TSLA" → MARKET_DEEP_DIVE, not COMPANY_RESEARCH
  - HTML artifact detection → INTENT_HTML_ARTIFACT
  - Document generation detection (handles "make me a PDF report") → INTENT_DOCUMENT_GENERATION
  - Company detection via `detect_company_name()` → INTENT_COMPANY_RESEARCH
  - Empty query fallback → INTENT_GENERAL_CHAT (was INTENT_GENERAL_FINANCE)
  - No-signal fallback → INTENT_GENERAL_CHAT (was INTENT_GENERAL_FINANCE)
- Updated `resolve_output_mode()` to delegate to `output_modes.py`; kept legacy fallback if output_modes missing
- Updated `route()` to send INTENT_COMPANY_RESEARCH, INTENT_HTML_ARTIFACT, INTENT_DOCUMENT_GENERATION to Omega

### api_server.py
- Updated import: `resolve_output_mode` now imported from `output_modes.py` (falls back to query_router)
- Added `_qfw_validate` and `_judge_response` imports from `quality_firewall` and `response_judge`
- Added `_QFW_AVAILABLE` guard with no-op stubs for graceful fallback
- After synthesis: runs quality_firewall + response_judge, logs warnings, adds `_quality_firewall` / `_response_judge` to shaped response

### atlas_omega.py
- Company detection in `query()` updated from naive `KNOWN_LARGE_COMPANIES` substring to `detect_company_name()` from query_router (alias + disambiguation)
- Company enrichment is synthesis-time only (not routing-time)
- `_synthesize()` now imports `resolve_output_mode` from `output_modes.py` (falls back to query_router)
- `_synthesize()` now uses `OUTPUT_CONTRACTS` for required/forbidden sections in prompt constraints
- Added `document` and `html_artifact` output mode handling in prompt constraints

---

## Diff Summary

### Routing changes
- `classify_intent_route("Give me everything on BlackRock")` → `COMPANY_RESEARCH` (was `GENERAL_FINANCE`)
- `classify_intent_route("apple pie recipe")` → `CASUAL` (unchanged, NON_COMPANY_CONTEXT blocks)
- `classify_intent_route("give me a trade setup for TSLA")` → `MARKET_DEEP_DIVE` (EXPLICIT_TRADE_RE fires before company check)
- `classify_intent_route("make me a PDF report")` → `DOCUMENT_GENERATION` (was `GENERAL_CHAT` via "make me")
- `classify_intent_route("create an HTML dashboard")` → `HTML_ARTIFACT`
- `classify_intent_route("")` → `GENERAL_CHAT` (was `GENERAL_FINANCE`)

### Output mode changes
- All modes now backed by `OUTPUT_CONTRACTS` with required/forbidden sections
- `resolve_output_mode("anything", "DOCUMENT_GENERATION")` → `"document"` (was missing)
- `resolve_output_mode(query, "GENERAL_FINANCE")` → `"company_report"` when query mentions known company

---

## Tests Added/Updated

### Updated (7 tests — now accept COMPANY_RESEARCH or GENERAL_FINANCE for known companies)
- `tests/test_output_modes.py`: `test_blackrock_query_resolves_company_report`, `test_general_finance_without_trade_keywords_resolves_company_report`
- `tests/test_prompt_loader.py`: `test_apple_revenue_routes_to_general_finance`, `test_blackrock_aum_routes_to_general_finance`, `test_microsoft_routes_to_general_finance` + added `INTENT_COMPANY_RESEARCH` import

### Created (47 new tests in `tests/test_brief_requirements.py`)
Tests cover:
- Intent constants exist (HTML_ARTIFACT, MARKET_DATA, TRADING_ANALYSIS)
- Company detection (aliases, NON_COMPANY_CONTEXT disambiguation)
- Full routing matrix (BlackRock, apple pie, sports chat, PDF, HTML, TSLA trade)
- Trade bleed prevention for company/chat output modes
- output_contracts required/forbidden sections
- quality_firewall blocking and passing
- response_judge PASS/FAIL
- progress_state transitions, terminal state guard, emit callback, COMPLETE event
- prompt_builder content and structure
- user_explicitly_requested_trade() for options/stop-loss/casual

---

## py_compile Results

```
python -m py_compile api_server.py query_router.py atlas_omega.py \
  output_modes.py output_contracts.py quality_firewall.py \
  response_judge.py progress_state.py prompt_builder.py
→ ALL COMPILE OK ✅
```

---

## pytest Results

```
pytest --maxfail=1 --disable-warnings -q
→ 1074 passed in 57.53s ✅  (was 1027 before this sprint)
```

---

## Not Completed / Deferred

- **Repair loop synthesis call**: The quality firewall logs warnings and annotates the response with `_quality_firewall`/`_response_judge` keys, but does not make a second Gemini synthesis call for repair. A re-synthesis would require threading an LLM client into `dispatch_query_request()` — deferred to avoid scope creep.
- **deep_research.py and gemini_limiter.py**: Unchanged per brief requirements (READ-ONLY this run).
- **prompt_builder integration in atlas_omega._synthesize()**: The brief's `build_synthesis_prompt()` is available but `_synthesize()` uses its own prompt construction; it now appends output_contract-based forbidden/required sections. Full migration to prompt_builder deferred.
- **Section 15 (Agent Archetype Prompt Registry)** and **Section 16 (Memory Vault)**: Deferred per brief — marked "do not start until output-mode and quality-firewall system works."
