# Portfolio Profile

## Purpose
This file describes the user's portfolio characteristics for personalized analysis.
Loaded by Loop 5 personalization in the query pipeline.

## Portfolio Style
<!-- Fill in -->
- Primary focus: [equity / options / crypto / mixed]
- Holding period: [day trading / swing / long-term / mixed]
- Typical position size: [fill in]
- Max positions at once: [fill in]

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
