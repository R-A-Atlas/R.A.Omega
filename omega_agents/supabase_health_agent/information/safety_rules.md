# supabase_health_agent — Safety Rules

1. Read-only checks only. Do not write to any database or table.
2. Do not run migrations or schema changes.
3. Do not call external broker or financial APIs.
4. Do not store credentials in logs or output files.
5. If Supabase is unavailable, report DEGRADED — do not attempt to reconnect repeatedly.
6. Do not send health alerts externally (no email, no Slack yet).
7. Output goes to stdout or atlas_vault/03-Outputs/ only.
8. Never delete or truncate any table or file.
