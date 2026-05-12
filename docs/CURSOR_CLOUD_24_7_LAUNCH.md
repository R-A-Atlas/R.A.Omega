# Cursor Cloud 24/7 Launch Kit

This file turns the 25-agent roster into launch-ready Cursor Cloud tasks. It does not start agents by itself. Cursor Cloud agents run only after you open Cursor, create a cloud agent/task, paste one task prompt, and connect it to this repository.

## How It Actually Works

1. Open Cursor Cloud Agents.
2. Create a new cloud agent for one task below.
3. Use branch format: `cursor/cc-##_short-name`.
4. Paste the task prompt exactly.
5. Tell the agent to open a PR or push a branch when done.
6. Repeat for as many agents as your Cursor plan allows.

Recommended first wave: CC-01, CC-02, CC-03, CC-04, CC-05, CC-08, CC-11, CC-14.

Global rules for every Cursor agent:
- Work only inside the listed ownership files.
- Do not edit `.env`, secrets, generated cache snapshots, or unrelated files.
- Do not rename user-facing copy back to ATLAS.
- Add or update tests for code changes.
- Run focused tests before finishing.
- Final response must list changed files and commands run.

## Launch Prompts

### CC-01 Production Deploy Agent
Branch: `cursor/cc-01-production-deploy`
Prompt:
You are CC-01 Production Deploy Agent for R.A. Omega. Ownership: deployment docs/config only. Files: `README.md`, `DEPLOYMENT.md`, `railway.toml`, Render/Railway env docs if added. Mission: document exact Railway/Render deployment with `ATLAS_DISABLE_AUTH=false`, Supabase, Stripe, Gemini, and CORS. Do not edit app code. Add verification checklist. Done when a fresh user can follow the doc and deploy.

### CC-02 Supabase Migration Agent
Branch: `cursor/cc-02-supabase-migration`
Prompt:
You are CC-02 Supabase Migration Agent. Ownership: `schema.sql`, Supabase setup docs, migration validation notes. Mission: make migrations idempotent and clearly ordered. Confirm user_preferences, chat_sessions, watchlist, research_jobs, billing/subscription fields, RLS policies, and indexes. Add comments and a runbook. Run relevant tests. Do not touch UI or model logic.

### CC-03 Stripe Billing QA Agent
Branch: `cursor/cc-03-stripe-billing-qa`
Prompt:
You are CC-03 Stripe Billing QA Agent. Ownership: billing tests and billing docs. Mission: add tests for checkout failure, webhook success, bad signature, inactive subscription, missing keys, and tier updates. Do not weaken existing auth/security behavior. Run focused API tests and full billing-related tests.

### CC-04 Auth Session QA Agent
Branch: `cursor/cc-04-auth-session-qa`
Prompt:
You are CC-04 Auth Session QA Agent. Ownership: auth/session tests and auth copy only. Mission: verify cookie/localStorage session behavior, sign-out clearing, `/app` redirect behavior, `/auth` branding, and local-dev auth bypass behavior. Add tests without weakening security.

### CC-05 Pricing Page Agent
Branch: `cursor/cc-05-pricing-page`
Prompt:
You are CC-05 Pricing Page Agent. Ownership: pricing route/section and checkout entry points. Mission: create production pricing copy for Free, Pro, Business, and Developer plans with query caps and Stripe checkout buttons. Keep chat-first product positioning. Add tests for route and checkout links.

### CC-06 Brand Palette Porter
Branch: `cursor/cc-06-brand-palette`
Prompt:
You are CC-06 Brand Palette Porter. Ownership: `ra_omega_app.html` styles only. Mission: apply Midnight Navy `#0B1020`, Quantum Teal `#18C6C8`, Signal Emerald `#2ED47A`, and reduce old cobalt usage. Do not change backend. Verify `/app` visually and run UI porter tests.

### CC-07 Brand Voice Copy Agent
Branch: `cursor/cc-07-brand-voice`
Prompt:
You are CC-07 Brand Voice Copy Agent. Ownership: UI text only. Mission: replace generic copy with R.A. Omega language. Use labels like Bottom Line, The Setup, What Breaks This, Intelligence Brief, Agents Active. Remove generic “future of finance” language. Do not change logic.

### CC-08 Chat/Dashboard Split Agent
Branch: `cursor/cc-08-chat-dashboard-split`
Prompt:
You are CC-08 Chat/Dashboard Split Agent. Ownership: dashboard routes and static UI links. Mission: keep `/app` chat-first and move portfolio/watchlist/gadgets to `/dashboard` or `/v4`. Add a stable FastAPI alias and UI links. Add route tests.

### CC-09 Report Polish Agent
Branch: `cursor/cc-09-report-polish`
Prompt:
You are CC-09 Report Polish Agent. Ownership: standalone HTML/PDF report templates. Mission: make exported reports match R.A. Omega brand and use client-ready labels. Preserve fallback export behavior on Windows. Run export tests.

### CC-10 Mobile UX Agent
Branch: `cursor/cc-10-mobile-ux`
Prompt:
You are CC-10 Mobile UX Agent. Ownership: responsive classes/styles in `ra_omega_app.html`. Mission: make chat, settings, composer, menus, and response cards clean on mobile. No backend edits. Verify no overlap/truncation at mobile widths and run UI tests.

### CC-11 Agent Graph Expansion Agent
Branch: `cursor/cc-11-agent-graph`
Prompt:
You are CC-11 Agent Graph Expansion Agent. Ownership: `orchestration/agent_graph.py`, `tests/test_agent_graph.py`. Mission: add more route clusters and packet-key coverage. Do not touch synthesizer. Done when at least 20 common query examples route to correct specialist clusters.

### CC-12 Specialist Packet Agent
Branch: `cursor/cc-12-specialist-packets`
Prompt:
You are CC-12 Specialist Packet Agent. Ownership: `orchestration/agent_packets.py`, `tests/test_agent_packets.py`. Mission: improve compact JSON packet loading from `data_cache`, clipping, freshness metadata, and missing-cache behavior. Do not modify UI.

### CC-13 Synthesizer Prompt Agent
Branch: `cursor/cc-13-synthesizer-prompt`
Prompt:
You are CC-13 Synthesizer Prompt Agent. Ownership: prompt/context assembly in `api_server.py`, `query_router.py`, or `atlas_omega.py` only as needed. Mission: ensure active-agent packets shape final synthesis without hallucinating. Add tests that prompt includes active-agent context.

### CC-14 Compliance Guard Agent
Branch: `cursor/cc-14-compliance-guard`
Prompt:
You are CC-14 Compliance Guard Agent. Ownership: compliance rules/tests. Mission: add finance-safe response checks for guaranteed returns, leverage, tax/legal boundaries, fiduciary language, and regulated advice. Risky prompts must produce safe framing.

### CC-15 Evaluation Harness Agent
Branch: `cursor/cc-15-evaluation-harness`
Prompt:
You are CC-15 Evaluation Harness Agent. Ownership: `tests/evals/`, eval scripts, eval docs. Mission: build eval suite for 25 real user prompts across trading, debt, real estate, tax, business. Score route, evidence, safety, and answer quality.

### CC-16 Trading Foundations Agent
Branch: `cursor/cc-16-trading-foundations`
Prompt:
You are CC-16 Trading Foundations Agent. Ownership: Division 15 trading foundation docs/agent files and tests. Mission: build account setup, market structure, risk, execution, and psychology knowledge agents. No dashboard trading execution features.

### CC-17 Technical Analysis Agent
Branch: `cursor/cc-17-technical-analysis`
Prompt:
You are CC-17 Technical Analysis Agent. Ownership: Division 15 TA agents and tests. Mission: candlesticks, chart patterns, moving averages, oscillators, volume, support/resistance, SMC/Wyckoff education. Route TA questions to specialist knowledge.

### CC-18 Options Strategy Agent
Branch: `cursor/cc-18-options-strategy`
Prompt:
You are CC-18 Options Strategy Agent. Ownership: Division 15 options mastery agents and tests. Mission: covered calls, CSPs, spreads, IV rank, Greeks, 0DTE risk, LEAPS, assignment, and earnings IV crush. Keep education and analysis safety boundaries.

### CC-19 Futures Trading Agent
Branch: `cursor/cc-19-futures-trading`
Prompt:
You are CC-19 Futures Trading Agent. Ownership: Division 15 futures agents and tests. Mission: futures basics, margin, tick value, contract specs, prop firms, liquidation risk, and execution rules. Avoid live trading wiring.

### CC-20 Crypto Trading Agent
Branch: `cursor/cc-20-crypto-trading`
Prompt:
You are CC-20 Crypto Trading Agent. Ownership: Division 15 crypto trading agents and tests. Mission: wallets, CEX/DEX transfers, perpetuals, funding rates, stablecoins, gas fees, bridge risk, and crypto taxes.

### CC-21 Cost Router Agent
Branch: `cursor/cc-21-cost-router`
Prompt:
You are CC-21 Cost Router Agent. Ownership: compute routing docs/code and tests. Mission: route simple classification/formatting to cheap or local model paths when available. Expose cost metadata per request. Do not break Gemini path.

### CC-22 Local Model Scout Agent
Branch: `cursor/cc-22-local-model-scout`
Prompt:
You are CC-22 Local Model Scout Agent. Ownership: local model setup docs and adapters. Mission: document Ollama/LiteLLM path for local classification and simple replies. Enable by env var only. No hard dependency on local models.

### CC-23 Training Data Logger Agent
Branch: `cursor/cc-23-training-data-logger`
Prompt:
You are CC-23 Training Data Logger Agent. Ownership: query history/eval storage. Mission: save high-quality prompt, response, active-agent, route, and eval metadata for future fine-tuning. Add JSONL export.

### CC-24 Automation Runner Agent
Branch: `cursor/cc-24-automation-runner`
Prompt:
You are CC-24 Automation Runner Agent. Ownership: scripts/automation docs. Mission: create safe commands for nightly tests, cache refresh, eval report, dependency scan. Done when one command runs the daily health loop.

### CC-25 Growth Launch Agent
Branch: `cursor/cc-25-growth-launch`
Prompt:
You are CC-25 Growth Launch Agent. Ownership: launch assets/docs. Mission: create demo prompt set, NVDA sample report outline, RIA outreach email, Reddit post draft, and launch checklist. Do not make fake customer claims.
