# Portfolio Profile

## Purpose
This file describes the user's portfolio characteristics for personalized analysis.
Loaded by Loop 5 personalization in the query pipeline.

## Portfolio Style
- Primary focus: equities + defined-risk options (paper trading only currently)
- Holding period: swing (days to weeks) — no day trading while in financial recovery
- Typical position size: small — sized to paper trading account; no real capital deployment until income/debt is stable
- Max positions at once: 3–5 maximum to maintain focus and avoid overextension

## Current Holdings
<!-- Update this regularly — never hardcode tickers here as investment advice -->
See positions_cache.json for live positions (Supabase-synced).

## Watchlist
See atlas_db watchlist table / GET /watchlist for live watchlist.

## Risk Capacity
See risk_profile.md

## Notes
- Loop 5 reads atlas_db.fetch_positions_cache_shapes(user_id) for real Supabase UUID
- For test_user_local: returns empty lists (mock)
- For None (CLI): reads positions_cache.json (legacy local file)
