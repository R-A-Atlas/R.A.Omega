# Current Priorities

## Priority 0 — Output Quality Stabilization (CURRENT SPRINT)
- Stop company reports from rendering as trade plans (output_mode contract enforcement)
- Fix stuck progress polling in deep research UI
- Fix deep research gating (mode controls not applying correctly)

## Priority 1 — Production Deploy + Visual QA
- Run Supabase migration (chat_sessions, user_watchlist, queries.session_id, RLS policies)
- Start server, go to /app, confirm structured cards render: TLDR + Executive Summary + Trade Plan table + Scenarios + Execution Rules + Failure Modes + Trader Memo + HTML Report + Copy JSON
- Verify hosted project + Stripe keys in deployment secrets
- Deploy to Railway (~$20/month)

## Priority 2 — Omega OS Layer (DONE)
- omega_os/ structure built — 34 files, 12 skill SOPs
- omega_os_loader.py, omega_audit.py, omega_level_up.py created
- Four C audit: 88/100 (Command Center phase)

## Priority 3 — Connection Registry (DONE)
- omega_connections.py — 20 connections documented with auth, permissions, safety flags
- SEC EDGAR activated (no auth required)
- Google Workspace adapter built

## Priority 4 — Cadence (DONE)
- omega_cadence.py — 7 recurring jobs declared (declarations only, not yet scheduled)

## Priority 5 — Beta Launch
- Get 50 free beta users via r/algotrading, r/options, FinTwit/X
- Hook: interactive HTML report ("Power BI for retail traders")

## Last Updated
2026-05-15
