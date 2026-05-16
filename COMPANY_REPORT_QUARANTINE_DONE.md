# COMPANY_REPORT_QUARANTINE_DONE

**Branch:** codex/chat-modes-settings  
**Date:** 2026-05-15  
**Tests:** 1692 passed, 0 failed, 16 warnings  
**py_compile:** PASS — api_server.py, query_router.py, atlas_omega.py, prompt_builder.py, output_modes.py, output_contracts.py, quality_firewall.py, response_judge.py, progress_state.py

---

## Goal

Fully quarantine trade-plan/decision-card formatting so company research outputs
do not render as trade reports. BlackRock/company queries must produce company
intelligence reports; trade-plan sections (THE SETUP, YOUR RULES, WHAT BREAKS THIS,
Entry, Stop Loss, Take Profit, Action: buy/sell, Rating: buy/sell/hold) must only
appear when output_mode == "trade_plan" or user explicitly requests trade execution.

**Goal condition met:**
- ✅ BlackRock/company queries render as company reports, not trade cards
- ✅ Trade-plan sections quarantined to trade_plan only
- ✅ company_report quality firewall detects and repairs trade bleed
- ✅ All tests pass

---

## Files Changed

### `output_contracts.py`
- Added `COMPANY_REPORT_TRADE_FORBIDDEN` list: superset of `COMMON_TRADE_FORBIDDEN`
  plus company-report-specific forbidden phrases ("the setup", "your rules",
  "what breaks this", "hold period", "action: buy/sell/avoid/short",
  "rating: buy/sell/hold/avoid")
- Updated `company_report` OutputContract:
  - `required_sections`: now 10 sections — Company Overview, What They Do,
    Business Model, Financial Snapshot, Key Executives, Recent News,
    Competitive Position, Risks, Sources, Bottom Line
  - `forbidden_phrases`: set to `tuple(COMPANY_REPORT_TRADE_FORBIDDEN)` (expanded)

### `prompt_builder.py`
- Rewrote company intelligence instruction block (was "LIVE COMPANY RESEARCH REQUIRED")
- New instruction explicitly tells the model:
  - "You are writing a company intelligence report, not a trade plan."
  - Lists all forbidden section headers (THE SETUP, YOUR RULES, WHAT BREAKS THIS,
    Entry, Stop Loss, Take Profit, Action, Rating)
  - Lists the 10 required company_report sections
- Instruction now fires when `output_mode == "company_report"` regardless of
  whether `company_name` is set (previously required company_name)

### `quality_firewall.py`
- Added `_COMPANY_REPORT_BLEED_HEADERS` tuple: 18 trade-specific phrases that
  must never appear in a company_report response
- Added `_COMPANY_REPORT_REPAIR` string: repair instruction text naming all
  forbidden sections and the 10 required company_report sections
- Added `bleed_detected: bool = False` field to `QualityResult` dataclass
- Wrapped outer `validate_response()` in try/except — never raises, returns
  `passed=False` with error reason on any internal exception
- Added dedicated company_report bleed check (runs before generic forbidden check):
  scans for any `_COMPANY_REPORT_BLEED_HEADERS` phrase and returns
  `bleed_detected=True` if found
- Generic forbidden phrase check also sets `bleed_detected=True` for company_report
  output mode

### `ra_omega_app.html`
**StructuredResponse React component:**
- Extracts `outputMode = data._output_mode || ''` and `isCompanyReport`
- Rating color block gated: `{fr.overall_rating && !isCompanyReport && <div ...>}`
- `<QuickStatsStrip>` now receives `outputMode={outputMode}` prop
- THE SETUP card: `{fr.trade_plan && !isCompanyReport && <CardWrap ...>}`
- YOUR RULES card: `{executionRules.length > 0 && !isCompanyReport && <CardWrap ...>}`
- WHAT BREAKS THIS card title: `isCompanyReport ? 'Risks' : 'WHAT BREAKS THIS'`
- Rating sub-label: `{fr.overall_rating && !isCompanyReport && ...}`

**QuickStatsStrip React component:**
- Now accepts `outputMode` prop
- `isCompanyReport` computed from prop
- Labels rename for company_report: "Research Confidence" / "Data Freshness"
  (vs "Risk Level" / "Financial Impact" for trade_plan)

**generateStandaloneReport string template:**
- Added `_srOutputMode` and `_srIsCompanyReport` variables
- `tpSection` (THE SETUP block): gated by `!_srIsCompanyReport`
- `rulesSection` (YOUR RULES block): gated by `!_srIsCompanyReport`
- `fmSection` (WHAT BREAKS THIS): title becomes "Risks" for company_report

### `tests/test_company_report_quarantine.py` (new, 56 tests)
- `TestCompanyReportContract` (18 tests): all 10 required sections, 8 forbidden phrases,
  COMPANY_REPORT_TRADE_FORBIDDEN superset check, trade_plan contract still has trade sections
- `TestPromptBuilderCompanyReport` (5 tests): "not a trade plan", forbidden sections named,
  required sections listed, trade_plan prompt exclusion, fires without company_name
- `TestUICardMapper` (6 tests): source inspection of ra_omega_app.html for all gates
- `TestQualityFirewallCompanyReport` (9 tests): bleed detection, repair instruction,
  clean report passes, never raises, bleed_detected field
- `TestEndToEndRouting` (18 tests): BlackRock → company_report, TSLA trade → trade_plan,
  clean/bleed report firewall, _CLEAN_REPORT content assertions

### `tests/test_brief_requirements.py` (updated)
- `test_company_report_contract_has_required_sections`: updated to check
  "Company Overview" (was "Overview"), "Key Executives" (was "Leadership"),
  added "Financial Snapshot"
- `test_quality_firewall_passes_clean_company_report`: updated test answer to
  include all 10 new required section names so it passes the firewall
- `test_prompt_builder_includes_company_instruction`: changed check from
  `"LIVE COMPANY RESEARCH REQUIRED"` to `"company intelligence report"` (case-insensitive)

### `tests/test_sec_synthesis_wiring.py` (updated)
- `TestTradeplanContaminationBlocked::test_quality_firewall_passes_clean_company_report`:
  updated test answer to use new required section names (Company Overview, What They Do,
  Key Executives, Sources, Bottom Line) to pass the updated firewall

---

## Diff Summary

```
output_contracts.py     +25 lines  COMPANY_REPORT_TRADE_FORBIDDEN, updated contract
prompt_builder.py       +12 lines  company_report instruction rewrite
quality_firewall.py     +40 lines  bleed detection, QualityResult.bleed_detected, try/except
ra_omega_app.html       +30 lines  isCompanyReport gates in StructuredResponse + generateStandaloneReport
tests/test_company_report_quarantine.py   +363 lines  new (56 tests)
tests/test_brief_requirements.py          +15 lines   3 test updates
tests/test_sec_synthesis_wiring.py        +8 lines    1 test update
```

---

## Test Results

```
pytest tests/ --maxfail=5 --disable-warnings -q
1692 passed, 16 warnings in 59.03s
```

New test files:
- `tests/test_company_report_quarantine.py` — 56 tests, all passing
- (Prior session) `tests/test_deep_query_control.py` — 36 tests, all passing

---

## Remaining Issues / Followup

- Visual QA on /app is still recommended after UI changes (cannot be automated):
  start server, run "Give me everything on BlackRock", confirm THE SETUP /
  YOUR RULES cards are suppressed and company overview sections render correctly
- Supabase production migration still pending (must be run manually by user
  in Supabase SQL Editor — see schema.sql footer for the runnable block)
- Production environment verification (Supabase + Stripe + deployment secrets)
  not yet confirmed for hosted environment
