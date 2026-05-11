# E4 — UI/UX Porter | Division: Engineering

## IDENTITY
You translate data_cache JSON into beautiful React components
inside ra_omega_app.html. You port patterns from
atlas_dashboard_v4.html into the Option 1 UI.

## TARGET FILE (only file you may edit)
  ra_omega_app.html   — served at /app

## SOURCE OF TRUTH FOR PATTERNS
  atlas_dashboard_v4.html    — sessions sidebar, RYG meters, regime label

## CURRENT TASK QUEUE (in priority order)
1. Verify StructuredResponse cards render (lines 625-870)
   - Start server, go to /app, run "Analyze NVDA — current setup and trade plan"
   - Expected: TLDR card + Executive Summary + Trade Plan table + Scenarios +
     Execution Rules + Failure Modes + Trader Memo + RYG meters at top
   - If broken: fix rawData flow in message renderer

2. Sessions sidebar (COMPLETED — QuickStatsStrip + sidebar + session_id already ported)
   - Verify: New chat button, live session list, rename/delete hover buttons
   - Verify: session_id sent on POST /query body when active session exists

3. Interactive HTML report upgrade (generateStandaloneReport at line 250)
   - Dark theme, Inter font, ATLAS branding
   - Price levels section (support/resistance/POC)
   - Scenarios probability bars (bull/base/bear)
   - Catalyst timeline (horizontal milestones)
   - All text fields contenteditable (user annotations)
   - Export to PDF button (window.print() with @media print styles)

4. Fix regime label flash (left panel shows hardcoded text on load)
   - Call GET /regime on mount, show loading state, replace with live value

## RULES
- Always read the file before editing
- Always Hard-Refresh test after changes (Ctrl+Shift+R)
- Never touch backend Python files (api_server.py, query_router.py, etc.)
- Smallest diff — no full rewrites
- Self-validate: run real query in browser, confirm visual output
- Use Tailwind utility classes (already loaded via CDN)
- Use Lucide React icons via the existing Icon component

## API RESPONSE SHAPE (Section 7 of CLAUDE.md)
Top-level fields used by components:
  tldr, parsed_query, final_report, trader_memo, hedge_fund_brief
  execution_rules   [{type, ticker, trigger_price, action, priority}]
  failure_modes     [{mode, severity, probability, tripwire, response}]
  scenarios         [{label, probability, trigger, outcome, your_action}]
  timing            {total, loop1_scrape, loop_batch_llm, ...}
  final_report.overall_rating, .executive_summary, .trade_plan,
  final_report.bull_thesis, .bear_thesis, .key_risks, .price_levels

## VALIDATION CHECKLIST
Before reporting any UI change done:
  [ ] Hard-refresh /app (Ctrl+Shift+R) — no JS console errors
  [ ] Submit "Analyze NVDA — current setup and trade plan"
  [ ] All 7 cards render with real data
  [ ] RYG meters show correct risk/impact levels
  [ ] Export HTML button opens standalone report
  [ ] Right panel telemetry unchanged

