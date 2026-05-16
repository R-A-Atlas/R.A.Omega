# COMPANY_REPORT_PAPER_RENDERER_DONE

**Branch:** codex/chat-modes-settings  
**Date:** 2026-05-15  
**Tests:** 1820 passed, 0 failed, 16 warnings  
**py_compile:** PASS — api_server.py, atlas_omega.py, prompt_builder.py, output_modes.py, output_contracts.py, quality_firewall.py, response_judge.py

---

## Goal

Make company_report render as a clean professional paper/document style automatically.
Trade cards are quarantined — only visible when output_mode == trade_plan or user
explicitly requests a trade setup/entry/stop/options execution.

---

## Files Changed

### `output_contracts.py` (PHASE 1 — Paper contract)
- Added to `COMPANY_REPORT_TRADE_FORBIDDEN`:
  - `"position sizing"`
  - `"trade rating"`
- company_report now forbids 20+ trade-plan phrases, including all common AND company-specific bleed terms

### `quality_firewall.py` (PHASE 4 — Quality firewall + repair)
- Added `import re`
- Added `_INLINE_SECTION_RE = re.compile(r'^[A-Z][A-Za-z ]{2,30}:\s')` module-level regex
- Expanded `_COMPANY_REPORT_BLEED_HEADERS` (added: "how this plays out", "position sizing", "trade rating", "tripwire")
- Updated `_COMPANY_REPORT_REPAIR` instruction to list all 11 required sections and all forbidden headers
- Added `_strip_trade_sections(text)` helper:
  - Scans lines; when a forbidden phrase appears in a header line, skips that section
  - Resumes on the next non-forbidden header (detected by `#`, endswith `:`, or `_INLINE_SECTION_RE` inline format)
  - `_INLINE_SECTION_RE` handles "Bottom Line: Strong." style headers that don't end with bare `:`
- Added `repair_response(answer, output_mode) -> tuple[str, bool]`:
  - Single pass only — no recursion, no external calls
  - Returns `(repaired_text, True)` when result >= 30 chars; otherwise `(original, False)`
  - Only operates on `output_mode == "company_report"`; all other modes return `(text, False)`
  - Never raises

### `ra_omega_app.html` (PHASE 3 — UI renderer)
- **Gated scenarios card** (HOW THIS PLAYS OUT):
  ```
  {scenarios.length > 0 && !isCompanyReport && (<CardWrap title="HOW THIS PLAYS OUT">
  ```
- **Gated failure modes card** (WHAT BREAKS THIS):
  ```
  {failureModes.length > 0 && !isCompanyReport && (<CardWrap title="WHAT BREAKS THIS">
  ```
- **Gated QuickStatsStrip** (risk/impact meters):
  ```
  {!isCompanyReport && <QuickStatsStrip data={data} outputMode={outputMode} />}
  ```
- **generateStandaloneReport** — scenarios and failure modes sections also gated:
  ```javascript
  const _srIsCompanyReport = (_srOutputMode === 'company_report');
  const scSection = (scenariosBlock && !_srIsCompanyReport) && `...HOW THIS PLAYS OUT...`;
  const fmSection = (fmBlock && !_srIsCompanyReport) && `...WHAT BREAKS THIS...`;
  ```
- THE SETUP card already gated by `!isCompanyReport` (no change needed)
- YOUR RULES card already gated by `!isCompanyReport` (no change needed)

### `tests/test_company_report_paper_renderer.py` (new, 69 tests)
- `TestCompanyReportPaperContract` (19 tests) — required sections, all forbidden phrases
- `TestPromptBuilderPaperReport` (5 tests) — clean markdown, not-a-trade-plan, tripwires, position sizing
- `TestUICompanyReportPaperRenderer` (8 tests) — source inspection of ra_omega_app.html
- `TestQualityFirewallBleedAndRepair` (11 tests) — bleed detection, `bleed_detected` field
- `TestRepairResponse` (9 tests) — repair_response behavior, never-raises, one-pass-max
- `TestCleanReportContent` (17 tests) — verifies `_CLEAN_REPORT` fixture has no forbidden phrases

### Updated existing tests
- `tests/test_company_report_quarantine.py`:
  - `test_what_breaks_this_renamed_for_company_report` → `test_what_breaks_this_gated_for_company_report`
  - Renamed to reflect hiding (not renaming) as the implementation; checks `!isCompanyReport` in src
- `tests/test_company_report_paper_renderer.py`:
  - `test_repair_one_pass_max_source`: fixed to check for call pattern `repair_response(` (not just the string, which appeared in log messages)
  - UI gate tests: updated to accept either `isCompanyReport` or `_srIsCompanyReport` in nearby context (both are valid — JSX uses the former, standalone template uses the latter)

---

## Diff Summary

```
output_contracts.py                         +2 lines   position sizing, trade rating added to forbidden
quality_firewall.py                         +50 lines  _INLINE_SECTION_RE, _strip_trade_sections, repair_response
ra_omega_app.html                           +6 lines   gate scenarios, failure_modes, QuickStatsStrip; standalone report gates
tests/test_company_report_paper_renderer.py +340 lines new (69 tests)
tests/test_company_report_quarantine.py     +2 lines   rename + fix test_what_breaks_this
```

---

## Test Results

```
pytest tests/ --maxfail=5 --disable-warnings -q
1820 passed, 16 warnings in 62.91s
```

New test file: `tests/test_company_report_paper_renderer.py` — 69 tests, all passing

---

## Goal Conditions Met

- ✅ BlackRock/company queries render clean paper-style reports
- ✅ Trade cards (THE SETUP, YOUR RULES, HOW THIS PLAYS OUT, WHAT BREAKS THIS, QuickStatsStrip) hidden for company_report
- ✅ Trade cards only appear when explicitly requested (output_mode == trade_plan)
- ✅ Download Report button (FileText icon) shown for company_report only
- ✅ Standalone HTML report also gates trade sections via `_srIsCompanyReport`
- ✅ Quality firewall detects trade bleed in company_report (bleed_detected field)
- ✅ repair_response() strips bleed sections in a single pass without recursion
- ✅ All tests pass (1820 total)

---

## Remaining Issues / Followup

- Visual QA on /app still recommended (cannot be automated):
  Start server, run "Give me everything on BlackRock" → confirm:
  (1) company_report auto-selected without clicking any button
  (2) "Report" button appears in ExportBar
  (3) No trade cards (THE SETUP, YOUR RULES, HOW THIS PLAYS OUT, WHAT BREAKS THIS) visible
  (4) Standalone HTML report (click "Report") also has no trade sections
- Supabase production migration still pending (user must run manually in SQL Editor)
- Hosted production environment verification (Supabase + Stripe + deployment secrets)
