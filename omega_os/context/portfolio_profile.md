# Portfolio Profile

## Purpose
This file describes the user's portfolio characteristics for personalized analysis.
Loaded by Loop 5 personalization in the query pipeline.

## Portfolio Style
- Mode: Builder-first, capital-preservation
- No active portfolio right now
- May study options and swing trades for learning purposes
- R.A. Omega should prioritize: paper trading, research, debt reduction, income generation, and business building — in that order — before risking real capital

## Current Holdings
<!-- No live positions — paper trading only. Update this when income/debt situation stabilizes. -->
See positions_cache.json for live positions (Supabase-synced).

## Watchlist
See atlas_db watchlist table / GET /watchlist for live watchlist.

## Risk Capacity
See risk_profile.md

## Notes
- Loop 5 reads atlas_db.fetch_positions_cache_shapes(user_id) for real Supabase UUID
- For test_user_local: returns empty lists (mock)
- For None (CLI): reads positions_cache.json (legacy local file)
