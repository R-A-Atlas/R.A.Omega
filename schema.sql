-- ATLAS Phase 2 — Supabase (PostgreSQL) schema
-- Run this in the Supabase SQL Editor after creating your project.
--
-- Prerequisites:
-- - Supabase Auth enabled (default). Rows use auth.users(id) as tenant key.
-- - Backend uses SUPABASE_URL + SUPABASE_KEY. Prefer the service_role key for
--   server-side FastAPI (bypasses RLS); the API still filters every query by user_id.
-- - If you use the anon key from the browser only, add RLS policies that mirror
--   user_id = auth.uid() and never trust client-side filters alone.
--
-- auth.users
--   Managed by Supabase Auth. Do not duplicate as public.users unless you add a trigger
--   to sync profile fields; ATLAS uses auth.users.id directly.

-- Chat sessions first (queried by FK from public.queries.session_id)
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    title TEXT,
    archived_at TIMESTAMPTZ,
    context_topic TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
    ON public.chat_sessions (user_id, updated_at DESC);

COMMENT ON TABLE public.chat_sessions IS 'Named chat sessions; links to queries via queries.session_id.';

-- Saved research runs (replaces research_history.json query_reports)
CREATE TABLE IF NOT EXISTS public.queries (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    title TEXT,
    domain_tag TEXT,
    folder_name TEXT,
    result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    session_id UUID REFERENCES public.chat_sessions (id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_queries_user_created
    ON public.queries (user_id, created_at DESC);

COMMENT ON TABLE public.queries IS 'ATLAS research history; one row per POST /query or /omega run.';

-- Optional folder labels (for POST /folders); distinct folder_name on queries also counts.
CREATE TABLE IF NOT EXISTS public.user_folders (
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, name)
);

COMMENT ON TABLE public.user_folders IS 'User-defined report folder names.';

-- Portfolio rows (Phase 2 — FastAPI /positions uses Supabase; legacy scripts may still read positions_cache.json)
CREATE TABLE IF NOT EXISTS public.positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'option')),
    strike NUMERIC,
    option_type TEXT,
    expiry DATE,
    avg_cost NUMERIC,
    quantity NUMERIC NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_positions_user ON public.positions (user_id);

-- One stock row per (user, ticker); one option leg per (user, ticker, strike, call/put)
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_user_ticker_stock
    ON public.positions (user_id, ticker)
    WHERE asset_type = 'stock';

CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_user_option_leg
    ON public.positions (user_id, ticker, strike, option_type)
    WHERE asset_type = 'option';

COMMENT ON TABLE public.positions IS 'Per-user portfolio; migrate from positions_cache.json.';

-- Per-user watchlist (replaces shared watchlist.json for authenticated /watchlist API)
CREATE TABLE IF NOT EXISTS public.user_watchlist (
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_user_watchlist_user ON public.user_watchlist (user_id);

COMMENT ON TABLE public.user_watchlist IS 'ATLAS dashboard watchlist; one row per user per ticker.';

-- Durable research job control plane (Deep Research / Web Search activity UX)
CREATE TABLE IF NOT EXISTS public.research_jobs (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.chat_sessions (id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'in_progress', 'completed', 'failed', 'cancelled')),
    route_band TEXT NOT NULL DEFAULT 'deep_research',
    progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
    current_stage TEXT,
    current_message TEXT,
    search_count INTEGER NOT NULL DEFAULT 0,
    plan_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    events_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifacts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    route_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_user_updated
    ON public.research_jobs (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_jobs_session_updated
    ON public.research_jobs (session_id, updated_at DESC);

COMMENT ON TABLE public.research_jobs IS 'Deep Research/Web Search jobs, visible activity state, cancellation flag, and artifacts.';

-- User-scoped personalization/settings for the chat experience.
CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    display_name TEXT,
    default_research_mode TEXT NOT NULL DEFAULT 'normal'
        CHECK (default_research_mode IN ('normal', 'web', 'deep')),
    answer_style TEXT NOT NULL DEFAULT 'balanced',
    risk_profile TEXT NOT NULL DEFAULT 'balanced',
    market_focus TEXT NOT NULL DEFAULT 'US equities',
    source_strictness TEXT NOT NULL DEFAULT 'balanced',
    report_depth TEXT NOT NULL DEFAULT 'standard',
    card_density TEXT NOT NULL DEFAULT 'comfortable',
    voice_dictation BOOLEAN NOT NULL DEFAULT true,
    citation_preference TEXT NOT NULL DEFAULT 'balanced',
    compliance_level TEXT NOT NULL DEFAULT 'standard',
    memory_enabled BOOLEAN NOT NULL DEFAULT true,
    notifications_enabled BOOLEAN NOT NULL DEFAULT false,
    accent_color TEXT NOT NULL DEFAULT 'teal',
    subscription_tier TEXT NOT NULL DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'starter', 'pro', 'business', 'enterprise', 'developer')),
    subscription_status TEXT NOT NULL DEFAULT 'active',
    stripe_customer_id TEXT,
    current_period_end TIMESTAMPTZ,
    extra_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.user_preferences IS 'Per-user R.A. Omega settings, personalization, mode defaults, and UI preferences.';

ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS report_depth TEXT NOT NULL DEFAULT 'standard',
    ADD COLUMN IF NOT EXISTS card_density TEXT NOT NULL DEFAULT 'comfortable',
    ADD COLUMN IF NOT EXISTS voice_dictation BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS citation_preference TEXT NOT NULL DEFAULT 'balanced',
    ADD COLUMN IF NOT EXISTS compliance_level TEXT NOT NULL DEFAULT 'standard';

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Migration: Sessions/watchlist objects (if missing) + RLS owner policies on tenant tables
-- Date: 2026-05-09
-- Agent: B6 DB Architect
-- Status: PENDING — run in Supabase SQL Editor
--
-- Run Section A first, then Section B. Safe to re-run (IF NOT EXISTS + DROP POLICY IF EXISTS).
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- --- Section A: structural objects (legacy projects that lack chat_sessions / session_id / watchlist) ---
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    title TEXT,
    archived_at TIMESTAMPTZ,
    context_topic TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
    ON public.chat_sessions (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.user_watchlist (
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_user_watchlist_user ON public.user_watchlist (user_id);

ALTER TABLE public.queries
    ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES public.chat_sessions (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS public.research_jobs (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    session_id UUID REFERENCES public.chat_sessions (id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'in_progress', 'completed', 'failed', 'cancelled')),
    route_band TEXT NOT NULL DEFAULT 'deep_research',
    progress_pct INTEGER NOT NULL DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100),
    current_stage TEXT,
    current_message TEXT,
    search_count INTEGER NOT NULL DEFAULT 0,
    plan_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    events_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifacts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    route_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_user_updated
    ON public.research_jobs (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_jobs_session_updated
    ON public.research_jobs (session_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    display_name TEXT,
    default_research_mode TEXT NOT NULL DEFAULT 'normal'
        CHECK (default_research_mode IN ('normal', 'web', 'deep')),
    answer_style TEXT NOT NULL DEFAULT 'balanced',
    risk_profile TEXT NOT NULL DEFAULT 'balanced',
    market_focus TEXT NOT NULL DEFAULT 'US equities',
    source_strictness TEXT NOT NULL DEFAULT 'balanced',
    memory_enabled BOOLEAN NOT NULL DEFAULT true,
    notifications_enabled BOOLEAN NOT NULL DEFAULT false,
    accent_color TEXT NOT NULL DEFAULT 'blue',
    subscription_tier TEXT NOT NULL DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'starter', 'pro', 'business', 'enterprise', 'developer')),
    subscription_status TEXT NOT NULL DEFAULT 'active',
    stripe_customer_id TEXT,
    current_period_end TIMESTAMPTZ,
    extra_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- Section B: row level security (owner = auth.uid()) ---

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "chat_sessions_owner" ON public.chat_sessions;
CREATE POLICY "chat_sessions_owner" ON public.chat_sessions
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.queries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "queries_owner" ON public.queries;
CREATE POLICY "queries_owner" ON public.queries
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.user_folders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "user_folders_owner" ON public.user_folders;
CREATE POLICY "user_folders_owner" ON public.user_folders
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "positions_owner" ON public.positions;
CREATE POLICY "positions_owner" ON public.positions
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.user_watchlist ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "user_watchlist_owner" ON public.user_watchlist;
CREATE POLICY "user_watchlist_owner" ON public.user_watchlist
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.research_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "research_jobs_owner" ON public.research_jobs;
CREATE POLICY "research_jobs_owner" ON public.research_jobs
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "user_preferences_owner" ON public.user_preferences;
CREATE POLICY "user_preferences_owner" ON public.user_preferences
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Migration: subscription tier fields for hosted query gating
-- Date: 2026-05-12
-- Agent: E5 DB Architect
-- Run in: Supabase SQL Editor -> New Query

ALTER TABLE public.user_preferences
    ADD COLUMN IF NOT EXISTS subscription_tier TEXT NOT NULL DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS subscription_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMPTZ;

ALTER TABLE public.user_preferences
    DROP CONSTRAINT IF EXISTS user_preferences_subscription_tier_check;

ALTER TABLE public.user_preferences
    ADD CONSTRAINT user_preferences_subscription_tier_check
    CHECK (subscription_tier IN ('free', 'starter', 'pro', 'business', 'enterprise', 'developer'));

COMMENT ON COLUMN public.user_preferences.subscription_tier IS
    'Hosted R.A. Omega plan tier used by API query gating.';

COMMENT ON COLUMN public.user_preferences.subscription_status IS
    'Billing/subscription status from the payment provider.';

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Confirm after running (paste in SQL Editor):
--
-- SELECT tablename, rowsecurity FROM pg_tables
--   WHERE schemaname = 'public'
--     AND tablename = ANY (ARRAY['chat_sessions','queries','user_folders','positions','user_watchlist']);
--
-- SELECT schemaname, tablename, policyname, cmd, roles FROM pg_policies
--   WHERE schemaname = 'public'
--     AND tablename = ANY (ARRAY['chat_sessions','queries','user_folders','positions','user_watchlist'])
--   ORDER BY tablename, policyname;
--
-- SELECT to_regclass('public.chat_sessions') AS chat_sessions,
--        to_regclass('public.user_watchlist') AS user_watchlist;
--
-- SELECT column_name FROM information_schema.columns
--   WHERE table_schema = 'public' AND table_name = 'queries' AND column_name = 'session_id';
--
-- SELECT COUNT(*) FROM public.chat_sessions;
-- SELECT COUNT(*) FROM public.user_watchlist;
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
