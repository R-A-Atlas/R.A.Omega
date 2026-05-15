# Current Priorities

## Priority 0 — Production Environment
- Run Supabase migration (chat_sessions, user_watchlist, queries.session_id, RLS policies)
- Verify in production: hosted project + Stripe keys in deployment secrets

## Priority 1 — Visual QA
- Start server, go to /app, run "Analyze NVDA — current setup and trade plan"
- Confirm: TLDR card + Executive Summary + Trade Plan table + Scenarios + Execution Rules + Failure Modes + Trader Memo + HTML Report + Copy JSON

## Priority 2 — Omega OS Layer (CURRENT)
- Build omega_os/ structure
- Create skills as markdown SOPs
- Wire omega_os_loader.py for progressive context loading
- Add 4C audit and level-up engine

## Priority 3 — Connection Registry
- Document all planned integrations in omega_connections.py
- No credentials required yet — use .env.example placeholders

## Priority 4 — Cadence
- Plan recurring jobs in omega_cadence.py
- No real scheduling yet — declarations only

## Priority 5 — Beta Launch
- Deploy to Railway (~$20/month)
- Get 50 free beta users via r/algotrading, r/options, FinTwit/X
- Hook: interactive HTML report ("Power BI for retail traders")

## Last Updated
2026-05-15
