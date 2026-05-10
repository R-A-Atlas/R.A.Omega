# Skill: Supabase B6 tenant migration (sessions + watchlist + RLS)

**ID:** SK-12  
**Created:** 2026-05-09  
**Proven:** 1 (migration SQL authored, idempotent, deployed checklist in `schema.sql`; operator applies in Supabase SQL Editor)

---

## [D] Direction

**What this skill does:** Run the **B6** block at the bottom of `schema.sql` to add tenant-scoped chat sessions, watchlist, `queries.session_id`, and **RLS owner policies** on five tables.

**When to use it:** New environment, `GET /sessions` 503, Option 1 shows migration hint, or `supabase_schema` / health indicates missing objects.

**Step-by-step workflow**

1. Open Supabase project → **SQL Editor** → New query.
2. Copy the block starting at the comment **`-- Migration: Sessions/watchlist objects`** (B6 header) through the end of **Section B** policies (ends after `user_watchlist_owner` policy). Do not run unrelated DDL above unless you intend to.
3. Run **Section A** first (tables, indexes, `ALTER TABLE queries ADD COLUMN session_id`), then **Section B** (enable RLS + `CREATE POLICY` for each table).
4. Run the **verification queries** in the footer comments (`pg_tables.rowsecurity`, `pg_policies`, `to_regclass`, `information_schema.columns` for `session_id`).
5. **FastAPI keys:** Prefer `SUPABASE_KEY=service_role` on the backend so PostgREST/RLS does not block server-side writes; RLS still protects `anon` / `authenticated` direct clients per `CLAUDE.md`.

**Rules and guardrails**

- Block is safe to **re-run** (`IF NOT EXISTS`, `DROP POLICY IF EXISTS`).
- Order matters: **A before B** (objects before policies).
- Never paste service role keys into client-side HTML; keep them server-only.
- After apply, refresh Option 1 and confirm `GET /sessions` returns 200 (with auth as configured).

---

## [B] Blueprints

**Reference files**

- `schema.sql` — B6 section (~lines 99–181): Section A, Section B, verification SQL footer
- `CLAUDE.md` §8 — migration + RLS + service_role note
- `api_server.py` — `/sessions` routes and health/supabase hints
- `atlas_db.py` — Supabase client usage for sessions and watchlist

**Good output**

- `public.chat_sessions` and `public.user_watchlist` exist; `queries.session_id` exists; all five tables show `rowsecurity = true` and expected owner policies in `pg_policies`.

**Bad output to avoid**

- Running only Section B (policies on missing tables).
- Using anon key on server for bulk admin fixes without understanding RLS failures.

---

## [S] Solutions

**Locate the block in repo**

```powershell
findstr /C:"Migration: Sessions/watchlist" schema.sql
findstr /C:"Section A:" schema.sql
findstr /C:"Section B:" schema.sql
```

**Post-apply checks (Supabase SQL Editor)**

```sql
SELECT tablename, rowsecurity FROM pg_tables
  WHERE schemaname = 'public'
    AND tablename = ANY (ARRAY['chat_sessions','queries','user_folders','positions','user_watchlist']);

SELECT to_regclass('public.chat_sessions') AS chat_sessions,
       to_regclass('public.user_watchlist') AS user_watchlist;

SELECT column_name FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'queries' AND column_name = 'session_id';
```

**Validation**

- Run evals in `evals.json` after confirming the SQL file still contains the full B6 contract.
