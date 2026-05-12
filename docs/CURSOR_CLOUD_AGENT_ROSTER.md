# R.A. Omega Cursor Cloud Agent Roster

Purpose: keep 25 parallel Cursor Cloud agents productive without conflicts. Each agent has one clear ownership zone. Agents should open PRs or commits by scope, run focused tests, and never modify files outside their ownership unless the task explicitly says so.

Global rules:
- Do not rename the project back to ATLAS in user-facing copy.
- Do not edit `.env`, secrets, generated cache snapshots, or unrelated files.
- Do not weaken auth, billing, security, or compliance tests.
- Every code agent must add or update tests.
- UI agents must verify `/app` visually before claiming done.
- Data agents must preserve fallback metadata when public sources fail.

## Tier 1: Ship/Revenue Agents

### CC-01 Production Deploy Agent
Ownership: deployment docs/config only.
Files: `README.md`, `DEPLOYMENT.md`, `railway.toml`, render/railway env docs if added.
Mission: document exact Railway/Render deployment with `ATLAS_DISABLE_AUTH=false`, Supabase, Stripe, Gemini, and CORS.
Done when: a fresh user can follow the doc and deploy.

### CC-02 Supabase Migration Agent
Ownership: `schema.sql`, Supabase setup docs, migration validation notes.
Mission: make migrations idempotent and clearly ordered.
Done when: all tables, RLS policies, subscription fields, and comments are documented.

### CC-03 Stripe Billing QA Agent
Ownership: billing tests and docs.
Files: `api_server.py` billing tests only, docs.
Mission: test checkout failure, webhook success, bad signature, inactive subscription.
Done when: billing has positive and negative coverage.

### CC-04 Auth Session QA Agent
Ownership: auth/session tests and login copy.
Mission: verify cookie/localStorage session behavior, sign-out clearing, `/app` redirect behavior.
Done when: auth tests cover browser-session edge cases.

### CC-05 Pricing Page Agent
Ownership: pricing UI route or section.
Mission: create production pricing copy for Free/Pro/Business with query caps.
Done when: user can reach pricing and start checkout.

## Tier 2: R.A. Omega Brand/UI Agents

### CC-06 Brand Palette Porter
Ownership: `ra_omega_app.html` styles only.
Mission: apply Midnight Navy `#0B1020`, Quantum Teal `#18C6C8`, Signal Emerald `#2ED47A`, reduce cobalt usage.
Done when: `/app` looks like R.A. Omega, not generic ATLAS.

### CC-07 Brand Voice Copy Agent
Ownership: UI text only.
Mission: replace generic labels with R.A. Omega language: Bottom Line, The Setup, What Breaks This, Intelligence Brief, Agents Active.
Done when: no generic "future of finance" style copy remains in `/app`.

### CC-08 Chat/Dashboard Split Agent
Ownership: new `/dashboard` static page and FastAPI route.
Mission: keep `/app` chat-first; move portfolio/watchlist/gadgets to `/dashboard`.
Done when: sidebar opens dashboard without cluttering chat.

### CC-09 Report Polish Agent
Ownership: standalone HTML/PDF report templates.
Mission: make exported reports match R.A. Omega brand and use client-ready labels.
Done when: report looks credible enough to email to an RIA.

### CC-10 Mobile UX Agent
Ownership: responsive CSS/classes in `ra_omega_app.html`.
Mission: make chat, settings, composer, and response cards clean on mobile.
Done when: no overlap/truncation at mobile widths.

## Tier 3: Agent Graph / Intelligence Agents

### CC-11 Agent Graph Expansion Agent
Ownership: `orchestration/agent_graph.py`, `tests/test_agent_graph.py`.
Mission: add more route clusters and packet-key coverage without touching synthesizer.
Done when: 20 common query examples route to correct clusters.

### CC-12 Specialist Packet Agent
Ownership: new `orchestration/agent_packets.py`.
Mission: load compact JSON packets for active agents from `data_cache`.
Done when: `_specialist_packets` can be attached to `/query`.

### CC-13 Synthesizer Prompt Agent
Ownership: prompt blocks in `query_router.py`/`atlas_omega.py`.
Mission: teach final synthesis to use `_active_agents` and specialist packets without hallucinating.
Done when: tests verify prompt includes active-agent context.

### CC-14 Compliance Guard Agent
Ownership: compliance rules/tests.
Mission: add finance-safe response checks for guaranteed returns, leverage, tax/legal boundaries.
Done when: risky prompts produce safe framing.

### CC-15 Evaluation Harness Agent
Ownership: `tests/evals/`, eval scripts.
Mission: build an eval suite for 25 real user prompts across trading, debt, real estate, tax, and business.
Done when: eval report scores route, evidence, safety, and answer quality.

## Tier 4: Trading Mastery Agents

### CC-16 Trading Foundations Agent
Ownership: new Division 15 docs/agent files.
Mission: build T-F1 to T-F5 knowledge agents: account setup, market structure, risk, execution, psychology.
Done when: agent prompts/tests exist and route graph can activate them.

### CC-17 Technical Analysis Agent
Ownership: Division 15 TA agents.
Mission: candlesticks, chart patterns, moving averages, oscillators, volume, support/resistance.
Done when: TA questions route to specialist knowledge.

### CC-18 Options Strategy Agent
Ownership: Division 15 options mastery agents.
Mission: covered calls, CSPs, spreads, IV rank, Greeks, 0DTE risk, LEAPS.
Done when: options education answers use dedicated specialist packets.

### CC-19 Futures Trading Agent
Ownership: Division 15 futures agents.
Mission: futures basics, margin, tick value, contract specs, prop firms, risk.
Done when: futures questions no longer use generic stock framing.

### CC-20 Crypto Trading Agent
Ownership: Division 15 crypto trading agents.
Mission: wallets, CEX/DEX transfers, perpetuals, funding rates, stablecoins, taxes.
Done when: crypto transfer/trading questions route properly.

## Tier 5: Cost/Automation Agents

### CC-21 Cost Router Agent
Ownership: compute routing docs/code.
Mission: route simple classification/formatting to cheap/local model paths when available.
Done when: cost metadata is exposed per request.

### CC-22 Local Model Scout Agent
Ownership: local model setup docs and adapters.
Mission: document Ollama/LiteLLM path for local classification and simple replies.
Done when: local model can be enabled by env var without breaking Gemini.

### CC-23 Training Data Logger Agent
Ownership: query history/eval storage.
Mission: save high-quality prompt/response/active-agent/eval metadata for future fine-tuning.
Done when: a training JSONL can be exported.

### CC-24 Automation Runner Agent
Ownership: scripts/automation docs.
Mission: create safe commands for nightly tests, cache refresh, eval report, and dependency scan.
Done when: one command can run the daily health loop.

### CC-25 Growth Launch Agent
Ownership: launch assets/docs.
Mission: create demo prompt set, NVDA sample report, RIA outreach email, Reddit post draft.
Done when: first outreach campaign assets are ready.
