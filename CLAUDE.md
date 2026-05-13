# ATLAS — MASTER GUIDE (Agentic OS + Engineering SOT)
# Read this ENTIRE file before touching any code.
# This is the single source of truth for every session.
#
# FIRST ACTION every new session:
#   Say: "Read CLAUDE.md completely, then run a full audit:
#         check every file, confirm what is working, identify
#         every bug, and tell me the next priority."

---

## 1. OPERATING MODEL

You are the Lead Architect of the ATLAS Agentic OS.
We do not use AI like a slot machine. We build systems.

Hierarchy: Domains → Tasks → Skills → Automations → Architecture

On-disk memory:
  atlas_vault/01-Raw/         Raw logs, transcripts, clippings (not authoritative until processed)
  atlas_vault/02-Wiki/        Authoritative notes, skills, decisions, indices
  atlas_vault/03-Outputs/     Shipped artifacts, final reports
  atlas_vault/04-Projects/    Active project changelogs and notes

When unsure which doc wins:
  Runtime safety + repo conventions  →  CLAUDE.md (this file)
  Personal OS + vault layout         →  claude_os_core.md + atlas_vault/02-Wiki/

---

## 2. THREE DOMAINS (Wiki roots)

  Architecture & Engineering   atlas_vault/02-Wiki/ATLAS/00-Architecture-Engineering/
  Agentic-OS / Ops             atlas_vault/02-Wiki/ATLAS/10-Agentic-OS-Ops/
  Market & AI Research         atlas_vault/02-Wiki/ATLAS/20-Market-AI-Research/

---

## 3. WHAT R.A. OMEGA IS

R.A. Omega is a finance-first AI intelligence platform.
User types any finance question. 10+ free data sources fetched in
parallel. One Gemini call synthesizes everything. User gets
institutional-grade analysis in under 3 minutes for ~$0.017.

Two AI brains:
  POST /query  →  QueryRouter + FourLoopEngine (10 loops, deep equity/options)
  POST /omega  →  OmegaAgent (fast, cross-domain: debt, cars, mortgages, macro)

Intent router (NEW):
  classify_intent_route() in query_router.py runs BEFORE the 10-loop engine.
  MARKET_DEEP_DIVE  →  FourLoopEngine (10 loops)
  GENERAL_FINANCE   →  OmegaAgent (returns same envelope shape)
  Fallback: if Omega errors, router falls back to 10-loop (logged)
  IM added to QueryParser._STOPWORDS so "I'm relocating" never spawns a ticker

---

## 4. HOW TO START THE SERVER

  cd "C:\Users\crist\Projects\R.A.Omega"
  uvicorn api_server:app --host 127.0.0.1 --port 8000

Wait for: INFO: Application startup complete.
Port conflict fix: netstat -ano | findstr :8000  then  taskkill /PID <PID> /F

URLs:
  http://127.0.0.1:8000/        Zenith 3D landing page (entry point)
  http://127.0.0.1:8000/auth    Sign in / Create account
  http://127.0.0.1:8000/app     Main R.A. Omega chat app
  http://127.0.0.1:8000/option1 Legacy app alias — redirects to /auth if no token
  http://127.0.0.1:8000/v2      Old dashboard (keep, backwards compat)
  http://127.0.0.1:8000/health  Health check JSON

---

## 5. FILE MAP

### NEVER MODIFY THESE
  query_router.py       10-loop engine. Minimal edits only for Omega data_cache routing (`classify_sector_cache_intent`).
  atlas_omega.py        OmegaAgent. Minimal edits only for `data_cache/` INTERNAL KNOWLEDGE ingest.
  deep_research.py      Deep research. Never touch.
  gemini_limiter.py     Gemini rate limiter. Never touch.

### SAFE TO MODIFY
  api_server.py                 FastAPI routes. Use BASE_DIR not SCRIPT_DIR.
                                Voice/docs: `POST /voice/query` (Whisper→same as /query), `POST /tts` (OpenAI/ElevenLabs),
                                `POST /export/pdf|pptx|xlsx` (body = POST /query JSON; files under `atlas_vault/03-Outputs/`).
                                WeasyPrint/GTK may be required on Windows for server PDF.
  atlas_core/summaries/         Summary layer. `summary_generator.py` distills all `data_cache/*_latest.json` files.
  atlas_core/data_map.py        Generates `atlas_vault/03-Outputs/data_map.html`.
  atlas_agents/cognitive/critical_paths/  Deterministic SOPs for high-value query types.
  .claude/hooks/                Session continuity and pre-commit context hooks.
  .claude/commands/             Slash commands for repeatable workflows.
  atlas_digest.py               Optional daily 7am digest email (`DIGEST_EMAIL`, `DIGEST_TZ`, SendGrid or SMTP).
  atlas_export/                 Builders: `pdf_render.py`, `build_deck.py`, `build_workbook.py`.
  atlas_db.py                   Supabase client + sessions + watchlist + positions.
  atlas_personalization.py      Loop 5 personalization bundle.
  market_scanner.py             Regime + squeeze detection.
  alerts.py                     Price/notification alerts.

### ACTIVE FRONTEND
  index_1778228972988.html      Zenith 3D landing. Served at /.
  auth.html                     Sign In + Create Account. Served at /auth.
  ra_omega_app.html             Main app UI. Served at /app and /option1.
  atlas_dashboard_v4.html       Old dashboard. Served at /v2. Keep for compat.

### DO NOT DELETE (data moat)
  atlas_memory.db               SQLite long-term memory. Gets smarter every query.
  atlas_tracker.db              Trade tracking + outcomes. Do not delete.
  positions_cache.json          User portfolio positions (legacy local path).
  paper_trades.json             Paper trade history.
  atlas_rag/                    Chroma vector DB. SOUN(124) + O(109) + NVDA(122) = 355 chunks.
  schema.sql                    Supabase schema (run migration block if needed).

### VAULT KNOWLEDGE BASE
  atlas_vault/04-Projects/ATLAS/Notes/session_log.md              One line per session (PASS / FAIL / PARTIAL)
  atlas_vault/04-Projects/ATLAS/Notes/2026-05-09-vault-writer-protocol.md  Vault Writer workflow; Section 8 edits only after C1 QA Enforcer PASS or explicit chat approval
  atlas_vault/02-Wiki/Skills/phase-gated-integration/SKILL.md   DBS skill (deployed)
  atlas_vault/02-Wiki/Skills/phase-gated-integration/evals.json 5 binary assertions
  atlas_vault/02-Wiki/_Index.md                                  Wiki MOC
  atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Intent-Routing-Session-UX.md
  atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Loop5-Migration.md
  atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Watchlist-Regime-Migration.md

### IGNORE (redundant, do not delete, just skip reading)
  atlas_dashboard_v2.html, atlas_dashboard_v3.html, dashboard.html
  dashboard_server.py, START_ATLAS.py, auto_bot.py
  ATLAS_FULL_AGENT_AUDIT.md/.docx, ATLAS_v3_Full_Audit.docx
  ATLAS_PROJECT_FILE_INVENTORY.md/.docx (auto-generated, stale)
  ATLAS_Master_Roadmap_to_1B (1).docx (superseded by this file)
  CANVAS_*.html, LIVE_*.html, ATLAS_OUTPUT_MAP.html, ATLAS_OVERVIEW.html
  Prompt.md (old debug note, superseded)
  build_audit_docx.py, generate_project_inventory.py, self_coder.py

---

## 6. ARCHITECTURE: SESSIONS + LOOP 5 + OBSERVABILITY

### Session-aware history (NEW)
  public.chat_sessions  +  queries.session_id in Supabase
  API: POST|GET|PATCH|DELETE /sessions
  Dashboard v4 sidebar: New chat, list, rename, archive, delete sessions
  Context pill shows context_topic for active session
  POST /query and POST /omega accept session_id on request body
  test_user_local: in-memory sessions in atlas_db (no Supabase needed in dev)
  Vault log: atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Intent-Routing-Session-UX.md

### Loop 5 — Personalization (user_id-aware)
  Plumbing: api_server → QueryRouter.route(query, user_id, session_id)
            → FourLoopEngine.run(user_id) → loop5_personalize(user_id)
            → build_personalization_bundle(base, user_id)

  user_id = real Supabase UUID   → atlas_db.fetch_positions_cache_shapes(user_id)
  user_id = test_user_local      → empty lists (mock, matches /positions in dev)
  user_id = None (CLI)           → positions_cache.json (legacy local file)

  atlas_tracker.db is still shared on-disk for all paths (not yet multi-tenant)
  Vault log: atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Loop5-Migration.md

### Observability Layer (atlas_dashboard_v4.html at /v2)
  Regime (#regimeLabel)     GET /regime → detect_market_regime() — live, not hardcoded
  Watchlist                 GET/POST/DELETE /watchlist → public.user_watchlist (Supabase)
  Positions                 GET/POST/DELETE /positions → Supabase + paper_trades.json
  Alerts                    GET /alerts → active price alerts (alerts.py; server-local JSON until multi-tenant)
  Voice                     POST /voice/query → OpenAI Whisper → same envelope as POST /query
  Compare                   POST /compare → body {tickers} → single combined /query run (_compare.compare_mode)
  Report NL edit            POST /report/edit → {report_id, instruction} → Gemini patch of queries.result_json
  Developer API             GET /api/v1/query?q= → X-ATLAS-DEV-KEY; billing stub atlas_dev_api_billing.log
  Chats                     GET/POST/PATCH/DELETE /sessions → named threads
  Research runs             GET /history/reports?session_id= → session-scoped
  Intent routing            parsed_query.intent_route in every response
  RYG meters                inferRiskLevelQuick() + inferFinancialImpactQuick()
  Vault log: atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Watchlist-Regime-Migration.md

---

## 7. WHAT THE API RETURNS (POST /query)

Top-level envelope:
  query, parsed_query (type, tickers, urgency, intent_route, confidence)
  final_report, tldr, trader_memo, hedge_fund_brief
  execution_rules    Array of 5 [{type, ticker, trigger_price, action, priority}]
  failure_modes      Array of 3 [{mode, severity, probability, tripwire, response}]
  scenarios          Array of 3 [{label, probability, trigger, outcome, your_action}]
  timing             {loop1_scrape, loop_batch_llm, total, all loops}

final_report: overall_rating, confidence, price_now, executive_summary,
  bull_thesis, bear_thesis, trade_plan, options_play, catalysts_timeline,
  key_risks, price_levels, earnings_analysis, analyst_consensus, 100x_potential

---

## 8. CONFIRMED WORKING (last verified 2026-05-13)

Backend:
  ✅ Full test suite — 990 passed — test with `python -m pytest tests/ -q`
  ✅ POST /query async dispatch — api_server.py:2197 — test with `python -m pytest tests/test_api_endpoints.py -q`
  ✅ Query controls and specialist packet routing — api_server.py:1305 — test with `python -m pytest tests/test_agent_graph.py tests/test_api_endpoints.py -q`
  ✅ OmegaAgent summary-first data cache loading — atlas_omega.py:773 — test with `python -m pytest tests/test_api_endpoints.py::test_internal_knowledge_payload_accepts_new_macro_intent -q`
  ✅ Summary generator for 64 cache files — atlas_core/summaries/summary_generator.py:301 — test with `python atlas_core/summaries/summary_generator.py`
  ✅ Data map generator and HTML output — atlas_core/data_map.py:205 — test with `python atlas_core/data_map.py`
  ✅ Critical paths for crypto/equity/macro/options/portfolio — atlas_agents/cognitive/critical_paths/ — inspect files or regenerate data map
  ✅ Intent router — classify_intent_route() routing correctly
  ✅ Loop 5 user_id tri-state portfolio loading
  ✅ Sessions CRUD API — 4 routes + mock support for test_user_local
  ✅ Watchlist API — list/add/remove in atlas_db.py
  ✅ RAG — local Chroma database present under atlas_rag/

Auth + Database:
  ✅ Supabase tables: queries, user_folders, positions (schema present)
  ✅ auth.html Sign In + Create Account with Supabase JWT
  ✅ /auth and /login routes in api_server.py
  ✅ Auth guard on /option1 → redirects to /auth if no token
  ✅ Stripe billing endpoints — api_server.py:2066 and api_server.py:2104 — test with `python -m pytest tests/test_api_endpoints.py -q`
  ✅ Subscription tier gate — api_server.py:1036 — test with `python -m pytest tests/test_api_endpoints.py -q`
  ✅ Sign Out button in Option 1 header
  ✅ / root → Zenith with Supabase config injected
  ✅ ATLAS_DISABLE_AUTH=true in .env for local dev
  ⚠️ Production Supabase still needs environment-specific verification: hosted project must have the latest migration applied and Stripe keys configured in deployment secrets.

UI — Main Chat (ra_omega_app.html at /app):
  ✅ StructuredResponse cards + QuickStatsStrip (RYG-style risk / impact meters)
  ✅ ExportBar — HTML Report, Export PDF (print dialog), Infographic, Copy JSON
  ✅ generateStandaloneReport() — dark theme, Inter + JetBrains Mono, R.A. Omega branding,
     price-level rail + bar chart, scenarios donut, horizontal catalyst timeline,
     contenteditable narrative fields, print/PDF export bar
  ✅ Message renderer branches on rawData → StructuredResponse + ExportBar (~line 2170+)
  ✅ Sessions sidebar — New chat, list, rename, archive, delete, context_topic under titles
  ✅ session_id on POST /query; auto-create session on first message when none selected
  ✅ Live market regime via GET /regime (loading → label; sidebar + header chip)
  ✅ Normal/web/deep research mode controls and personalization settings
  ⚠️ Visual screenshot checks are still recommended after UI changes.

UI — Dashboard v4 (atlas_dashboard_v4.html at /v2):
  ✅ Sessions sidebar with New chat, list, rename, archive, delete
  ✅ Context topic pills on sessions
  ✅ RYG meters on every result (inferRiskLevelQuick + inferFinancialImpactQuick)
  ✅ syncWatchlistFromServer() + one-time localStorage migration
  ✅ refreshRegimeNav() calls GET /regime live
  ⚠️ regimeLabel still hardcoded "BULL MARKET" on initial load (minor flash)

Not Working / Not Fully Production:
  ❌ Hosted production is not complete until deployment secrets, Supabase production migrations, and Stripe webhook signing are verified in the live environment.
  ⚠️ Some market feeds can be fallback-backed when public sources fail; label fallback data in user-facing analysis.
  ⚠️ In-app browser policy blocks direct `file://` opening of generated HTML artifacts; verify generated HTML from disk or serve it from FastAPI when needed.

---

## 9. PRIORITY BUILD LIST

### PRIORITY 0 — YOU run the Supabase migration (not Claude Code)
  supabase.com → your project → SQL Editor → New Query
  Copy the runnable block at bottom of schema.sql (B6 header, Section A then Section B):
    Section A: chat_sessions, user_watchlist, queries.session_id (IF NOT EXISTS / ADD COLUMN)
    Section B: ENABLE ROW LEVEL SECURITY + *_owner policies on five tenant tables
  Confirm: chat_sessions, user_watchlist exist; queries.session_id exists; rowsecurity on all five
    tables; policies listed (see verification comments in schema.sql footer)

### PRIORITY 1 — Visual confirm cards in main chat
  Start server. Go to /app. Run "Analyze NVDA — current setup and trade plan"
  Take screenshot.
  Expected: TLDR card (colored border) + Executive Summary + Trade Plan table +
            Scenarios bars + Execution Rules + Failure Modes + Trader Memo +
            HTML Report button + Copy JSON button
  If broken: fix rawData flow in message renderer (search for `log.rawData` in ra_omega_app.html)

### PRIORITY 2 — Port sessions sidebar into main chat UI — DONE (in repo)
  Implemented: sidebar, POST /sessions, session_id on /query, context topics,
  QuickStatsStrip meters, live regime fetch. Treat regressions as bugs, not greenfield.

### PRIORITY 3 — Interactive HTML report upgrade — DONE (in repo; refine as needed)
  Standalone report includes: dark theme, Inter, ATLAS_ branding, price levels (rail + bars),
  scenarios donut, catalyst strip, contenteditable annotations, Export PDF via print.

### PRIORITY 4 — Fix dev log noise — DONE (in repo)
  _persist_query_report_bg and _persist_omega_report_bg return early when user_id == "test_user_local".
  If UUID noise persists, trace other call sites — do not re-add duplicate guards without diagnosis.

### PRIORITY 5 — Silver platter summary/data-map layer — DONE (in repo)
  Implemented: `atlas_core/summaries/summary_generator.py`, 64 tracked summaries,
  Omega summary-first loading, `.claude/hooks/`, 5 critical paths, and
  `atlas_core/data_map.py` output to `atlas_vault/03-Outputs/data_map.html`.

### PRIORITY 6 — Add transcripts to vault + RAG
  Save Claude Code workflow transcripts as .md files in:
    atlas_vault/01-Raw/Transcripts/
  Then ingest via rag_engine.py into Chroma.
  Gives ATLAS institutional memory of how to build and improve itself.

---

## 10. BUSINESS ROADMAP

### Phase 1 — Polish / Production Readiness (NOW, weeks 1-4)
  Current state: core app, auth guard, billing routes, summary layer, critical paths,
  and data map are built with 990 passing tests. Remaining work is production
  environment verification, deployment, visual QA, and final hosted auth/payment checks.

### Phase 2 — First users (months 1-3)
  Deploy to cloud (Railway or Render, ~$20/month).
  Get 50 free beta users via r/algotrading, r/options, FinTwit/X.
  Post hook: interactive HTML report ("Power BI for retail traders")

### Phase 3 — Revenue (months 3-9)
  $49/month starter, $149/month pro.
  Goal: 300 paying users = $15-45k MRR.
  Conversion hook: interactive HTML report.
  Retention hook: atlas_memory.db switching cost.

### Phase 4 — B2B (months 9-24)
  RIAs: $500/month | Small hedge funds: $2-5k/month | Advisors: $200/month
  Goal: 50 B2B accounts = $100k-250k MRR.

### Phase 5 — Exit (year 3-5)
  Acquisition by Bloomberg, Morningstar, Robinhood, Schwab, or Tastytrade.
  Range: $50-150M (requires traction + clean IP + enterprise contracts)

### KEY DIFFERENTIATORS
  1. atlas_memory.db grows smarter with every query → switching cost moat
  2. Summary-first data layer keeps normal answers fast and token-efficient
  3. Critical paths make top agent workflows deterministic
  4. Cross-domain: stocks + crypto + mortgages + cars + debt
  5. Interactive editable HTML reports → Power BI for retail traders
  6. ~$0.017/query target vs Bloomberg-scale pricing
  7. Loop 5 personalized to user's actual portfolio
  8. Intent router: works for prose finance AND ticker analysis equally

---

## 11. D.B.S. SKILL FRAMEWORK

When creating or refining a Skill, use DBS strictly:
  [D] Direction:   SKILL.md — name, description, step-by-step, rules, guardrails
  [B] Blueprints:  Examples, references, style guides, templates
  [S] Solutions:   Scripts, API calls, bash checks embedded in the skill

Evals: every skill needs evals.json with binary True/False assertions only.
  Good: "python -m py_compile api_server.py exits 0"
  Bad:  "is the code good?"

Active skills:
  Priority 1: phase-gated-integration    atlas_vault/02-Wiki/Skills/phase-gated-integration/
  Priority 2: session-context-bootstrap  (to be built)
  Priority 3: post-session-memory-sync   (to be built)

After any complex task: ask "Should we codify this into a reusable Skill?"

---

## 12. EXECUTION PROTOCOL

1. PLAN    — Dependency scan. In-scope/out-of-scope files. Risks. Stop condition.
             No code until plan approved by user.
2. EXECUTE — Smallest diff for approved phase only. No drive-by refactors.
3. REVIEW  — Self-validate: python -m py_compile <file> and python -c "import api_server"
             Fix failures before reporting done.
4. MEMORY  — Add/link notes in atlas_vault/04-Projects/ATLAS/Notes/ after meaningful progress; append
             atlas_vault/04-Projects/ATLAS/Notes/session_log.md (PASS / FAIL / PARTIAL). Update Section 8
             only after C1 QA Enforcer confirms PASS or the user explicitly approves a Section 8 change.
             After any bug fix or rollback: complete the Incident Logger steps in Section 14 (same session).

Sub-agents: ONLY for cleanly isolated tasks. For interdependent tasks use ONE context window.

---

## 13. CLAUDE CODE SHORTCUTS

  Shift+Tab+Tab    Plan Mode — reads files, shows plan, NO edits until approved
  Shift+Tab        Cycle: plan → auto-accept → manual approve
  Escape           Stop mid-run (context preserved)
  Esc + Esc        Rewind to any checkpoint
  /clear           Reset context (use between unrelated tasks)
  /resume          Pick previous session from list
  /model           Switch model (Opus 4.6 for complex, Sonnet for speed)
  /btw             Side question without interrupting current task
  claude --continue   Resume last session (best way to start every day)

### How to start each session
  claude --continue
  Then: "Read CLAUDE.md completely, run a full audit, tell me next priority."

### Giving tasks
  Short (1-2 lines): type directly
  Long: write task.md in project root, then "read task.md and implement it"

### Context hygiene
  /clear between unrelated tasks
  After 2 failed corrections: /clear and restart with cleaner prompt
  Big multi-file tasks: always Plan Mode first

---

## 14. RULES THAT CANNOT BE BROKEN

  1. NEVER modify: deep_research.py, gemini_limiter.py. Do not change the 10-loop body in query_router.py; only coarse routing/helpers for Omega data_cache may touch query_router.py and atlas_omega.py.
  2. NEVER delete: atlas_memory.db, atlas_tracker.db
  3. NEVER commit .env to git
  4. ALWAYS use BASE_DIR (not SCRIPT_DIR) in api_server.py
  5. ALWAYS test after changes: restart server, Ctrl+Shift+R, run real query
  6. ATLAS_DISABLE_AUTH=true is LOCAL DEV ONLY
  7. Read files before editing
  8. One task at a time
  9. INCIDENT LOGGER — After any bug fix or rollback in the same session: ask "What broke, what caused it,
     and how was it fixed?" and wait for answers; then write atlas_vault/04-Projects/ATLAS/Notes/
     incident_<YYYY-MM-DD>_<slug>.md (title, date, severity, status, What Broke, Root Cause, How It Was Fixed,
     Impact, Prevention with Y/N for CLAUDE.md + C2 Security test, Related Files). Full template: ATLAS_25_CURSOR_AGENTS.md
     AGENT E3. Never skip, even for minor bugs.
  10. When incident prevention is a concrete, durable guardrail, add a new numbered rule to this section;
      do not add vague items.
  11. Bug patterns worth reuse → document for D2 Skill Codifier (ATLAS_25_CURSOR_AGENTS.md) and/or a DBS skill
      under atlas_vault/02-Wiki/Skills/.

---

## 15. QUICK NAVIGATION

  Wiki MOC:           atlas_vault/02-Wiki/_Index.md
  Skills:             atlas_vault/02-Wiki/Skills/
  Transcripts:        atlas_vault/01-Raw/Transcripts/
  Project notes:      atlas_vault/04-Projects/ATLAS/Notes/
  Incident log:       atlas_vault/04-Projects/ATLAS/Notes/incident_*.md (post-fix; see Section 14)
  Agentic OS core:    claude_os_core.md
  OS playbook:        ATLAS_AGENTIC_OS_PLAYBOOK.md

---

## 16. AUDIT SEQUENCE — RUN THIS EVERY SESSION START

  1. In ra_omega_app.html, locate `log.rawData` in the message list JSX
     Confirm `<StructuredResponse data={log.rawData} />` (and ExportBar) still render for agent rows

  2. Start server: uvicorn api_server:app --host 127.0.0.1 --port 8000
     Go to /option1. Run "Analyze NVDA — current setup and trade plan"
     Take screenshot. Confirm structured cards render.

  3. Check migration: GET /sessions with auth header (real JWT user)
     503 / “not configured” → Supabase env or schema migration still needed

  4. Report:
     CARDS: rendering / not rendering (reason if broken)
     MIGRATION: done / not done
     NEXT PRIORITY: [single next thing to build]

*Memory root: atlas_vault/ | Engineering SOT: this file*
