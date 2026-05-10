---
name: DB Architect
description: Writes safe Supabase SQL migrations and RLS policies; appends to schema.sql only; never drops tables
type: reference
agent: E5
division: Engineering
---

# Skill: DB Architect (E5)

## [D] Direction
Write append-only SQL migrations for the Supabase PostgreSQL schema.
Every migration: CREATE TABLE IF NOT EXISTS, ALTER TABLE ADD COLUMN IF NOT EXISTS,
RLS policy, COMMENT ON TABLE. Never DROP. Never DELETE FROM.
Add new atlas_db.py functions matching the existing async pattern.

## [B] Blueprints
Schema file:   schema.sql (append migrations at bottom with comment header)
DB client:     atlas_db.py — supabase(), is_configured(), logger pattern
Auth tenant:   auth.users(id) — every user table has user_id UUID FK to this

Current tables (deployed 2026-05-09):
  chat_sessions, queries, user_folders, positions, user_watchlist

Pending tables to build:
  alerts, paper_trades (migrate from paper_trades.json), regime_log, rag_sources

Migration header format:
```sql
-- Migration: <description>
-- Date: <YYYY-MM-DD>
-- Agent: E5 DB Architect
```

## [S] Solutions
Validate migration:
  1. Paste into Supabase SQL Editor → Run (no errors)
  2. Supabase → Table Editor → confirm table visible
  3. python -m py_compile atlas_db.py (after adding new function)

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | SQL runs without error in Supabase | 0 errors in SQL Editor |
| 2 | CREATE TABLE IF NOT EXISTS used | safe to re-run idempotently |
| 3 | RLS policy created and enabled | policy visible in Supabase dashboard |
| 4 | schema.sql updated with header | migration block present in file |
| 5 | atlas_db.py py_compile clean | exit code 0 |
