# supabase_health_agent — Instructions

## What This Worker Does
Checks the health of the R.A. Omega persistence layer: Supabase table availability,
recent report counts, session state, research queue, and local SQLite databases.
Reports health status without modifying any data.

## When to Run
- Daily, before the build session starts
- After any schema migration or deployment
- When users report persistence errors

## Skills Used
- `source_verification` — verify data sources are accessible
- `improve_system` — analyze failures and suggest fixes

## Checks Performed (read-only)
1. Local SQLite: atlas_memory.db exists and is readable
2. Local SQLite: atlas_tracker.db exists and is readable
3. Supabase: GET /sessions returns 200 or expected error (503 if not configured)
4. Supabase: GET /health returns 200
5. File system: atlas_vault/03-Outputs/ is writable
6. File system: recent DONE files exist (project is active)

## Output
- Health status report: each check as PASS / FAIL / WARN
- Overall status: HEALTHY / DEGRADED / DOWN
- Saved to stdout or atlas_vault/03-Outputs/health_<date>.md

## Error Recording
On any check failure, append to `past_errors.md` with check name, error, and timestamp.

## How to Improve
After each run, append one line to `memory.md`: date, overall status, notable issues.
