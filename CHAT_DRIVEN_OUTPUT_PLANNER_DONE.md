# CHAT_DRIVEN_OUTPUT_PLANNER_DONE

**Branch:** codex/chat-modes-settings  
**Date:** 2026-05-15  
**Tests:** 1750 passed, 0 failed, 16 warnings  
**py_compile:** PASS — api_server.py, atlas_omega.py, query_router.py, prompt_builder.py, output_modes.py, output_contracts.py, atlas_db.py

---

## Goal

Make R.A. Omega behave like ChatGPT/Gemini: users ask naturally in chat, and the
system automatically detects intent, chooses tools/output mode, and renders the
right format. Buttons/toggles are optional overrides only.

---

## Files Changed

### `output_modes.py` (PHASE 1)
- Added `"chart"` to `HTML_TRIGGER_WORDS` so queries like "show me a chart of TSLA"
  auto-route to `html_artifact`

### `query_router.py` (PHASE 1)
- Added `_DEEP_RESEARCH_RE` module-level regex matching "deep research", "full research",
  "comprehensive research", "exhaustive research"
- In `route()`, added auto-promotion: if `research_mode != "deep"` and the raw query
  matches `_DEEP_RESEARCH_RE`, promotes `research_mode = "deep"` — triggers the
  10-loop engine without the user needing to click the Deep button

### `atlas_omega.py` (PHASE 2 — Gemini tool/JSON fix)
- In the `generate_content()` call for the OmegaAgent Gemini synthesis:
  - When Google Search tools are enabled (`query.startswith("search the web")`),
    removed `response_mime_type="application/json"` from the config
  - Gemini rejects combining tools with a JSON MIME constraint; the model now receives
    JSON instructions via the prompt rather than the MIME type
  - Non-tool path still uses `response_mime_type="application/json"` for structured output

### `atlas_db.py` (PHASE 3 — Supabase UUID fix)
- In `list_research_queries()`, added early return for `user_id == TEST_USER_LOCAL`
  or non-UUID values (via `_is_uuidish()`)
- Previously: `test_user_local` was sent as a UUID to Supabase, causing PostgreSQL
  to reject the query. Now: returns `[]` immediately for dev/local users
- Fixes `/history/reports` 500 crash in local dev mode

### `output_contracts.py` (PHASE 3 — Paper contract)
- Added `"Executive Summary"` to `company_report` required sections
- Changed `"Risks"` → `"Key Risks"` in required sections
- Added `"tripwire"` and `"how this plays out"` to `COMPANY_REPORT_TRADE_FORBIDDEN`
- company_report now requires 11 sections:
  Executive Summary, Company Overview, What They Do, Business Model, Financial Snapshot,
  Key Executives, Recent News, Competitive Position, Key Risks, Sources, Bottom Line

### `prompt_builder.py` (PHASE 4)
- Updated company_report instruction:
  - Now says: "You are writing a professional company intelligence report in clean markdown."
  - "This is not a trade plan. Do not write a trade plan."
  - Explicitly forbids: entries, exits, position sizing, trade ratings, tripwires, execution rules
  - Explicitly forbids headers: THE SETUP, YOUR RULES, WHAT BREAKS THIS, Entry, Stop Loss,
    Take Profit, Action: buy/sell/avoid, Rating: buy/sell/hold
  - Lists the 11 required sections

### `ra_omega_app.html` (PHASE 5 — UI renderer)
- In `ExportBar` component:
  - Reads `data._output_mode` to detect company_report mode
  - Shows a "Report" button (FileText icon + "Report" label) for company_report only
  - Button calls `openHTMLReport()` which opens the standalone HTML report in a new tab
  - Button is hidden for all other output modes (trade_plan, chat, etc.)
  - No user button click required before asking — output_mode is auto-detected

### `tests/test_chat_driven_output_planner.py` (new, 58 tests)
- `TestAutoOutputModeSelection` (13 tests): company_report, chat, trade_plan, document,
  html_artifact all auto-selected from query text alone
- `TestDeepResearchAutoDetect` (6 tests): _DEEP_RESEARCH_RE matches, route() uses it
- `TestGeminiToolJsonConfig` (3 tests): Gemini tool branch does not combine with JSON MIME
- `TestHistoryReportsLocalUser` (4 tests): list_research_queries returns [] for test_user_local
- `TestCompanyReportPaperContract` (18 tests): all required/forbidden sections verified,
  clean report passes firewall, all forbidden phrases absent
- `TestPromptBuilderCompanyReport` (3 tests): professional markdown, not-a-trade-plan, tripwires
- `TestUICompanyReportRenderer` (6 tests): source inspection of ra_omega_app.html

### Updated existing tests
- `tests/test_company_report_quarantine.py`:
  - `_CLEAN_REPORT` fixture: added "Executive Summary" and changed "Risks" → "Key Risks"
  - `test_required_section_risks` → now checks "Key Risks"
  - Added `test_required_section_executive_summary`
- `tests/test_brief_requirements.py`:
  - `test_quality_firewall_passes_clean_company_report`: answer now includes "Executive Summary"
    and "Key Risks" to match the updated required sections
- `tests/test_sec_synthesis_wiring.py`:
  - Same answer update

---

## Diff Summary

```
output_modes.py       +1 line   add "chart" to HTML_TRIGGER_WORDS
query_router.py       +8 lines  _DEEP_RESEARCH_RE regex + route() auto-promote
atlas_omega.py        -1 line   remove response_mime_type from tools branch
atlas_db.py           +3 lines  early return for test_user_local in list_research_queries()
output_contracts.py   +6 lines  Executive Summary, Key Risks, tripwire, how this plays out
prompt_builder.py     +5 lines  rewritten company_report instruction
ra_omega_app.html     +14 lines Download Report button in ExportBar
tests/test_chat_driven_output_planner.py  +215 lines  new (58 tests)
tests/test_company_report_quarantine.py   +5 lines    fixture + 1 new test
tests/test_brief_requirements.py          +3 lines    updated answer
tests/test_sec_synthesis_wiring.py        +2 lines    updated answer
```

---

## Test Results

```
pytest tests/ --maxfail=5 --disable-warnings -q
1750 passed, 16 warnings in 62.27s
```

New test file: `tests/test_chat_driven_output_planner.py` — 58 tests, all passing

---

## Goal Conditions Met

- ✅ Users can ask naturally in chat without switching buttons
- ✅ output_mode is auto-selected from query intent by default
- ✅ "deep research" in query text → auto-promotes to 10-loop engine
- ✅ "chart" → html_artifact (added to trigger words)
- ✅ Manual buttons remain optional overrides only
- ✅ Gemini tool/JSON config error is fixed
- ✅ /history/reports local UUID error is fixed
- ✅ company_report requires Executive Summary + Key Risks in paper contract
- ✅ "Download Report" button appears for company_report mode only
- ✅ All tests pass (1750 total)

---

## Remaining Issues / Followup

- Visual QA on /app still recommended (cannot be automated):
  start server, run "Give me everything on BlackRock" → confirm:
  (1) company_report auto-selected without clicking any button
  (2) "Report" button appears in ExportBar
  (3) Clicking Report opens standalone HTML report
  (4) No trade cards (THE SETUP, YOUR RULES) visible
- Supabase production migration still pending (user must run manually in SQL Editor)
- Hosted production environment verification (Supabase + Stripe + deployment secrets)
