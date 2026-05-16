# supabase_health_agent — Plan

## Current Plan (v1)
1. Check local databases (atlas_memory.db, atlas_tracker.db) — file exists + readable
2. Check GET /health endpoint (if server is running locally)
3. Check GET /sessions endpoint (Supabase availability)
4. Check atlas_vault/03-Outputs/ is writable
5. Report HEALTHY / DEGRADED / DOWN

## Known Degraded States
- ATLAS_DISABLE_AUTH=true → Supabase not configured → /sessions returns 503 → WARN (expected in dev)
- No server running → /health unreachable → WARN (expected when server not started)

## Future Enhancements
- Monitor query count trends (queries table row count over time)
- Alert when atlas_memory.db exceeds 500MB
- Add Modal cron trigger for automated daily health check
