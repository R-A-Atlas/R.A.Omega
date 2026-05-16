# Skill: cadence_wirer

## Purpose
Wires omega_cadence.py job declarations to APScheduler for automated background
execution. Jobs with real tool scripts run on schedule; stubs log a notice and
are skipped until implemented.

## Trigger
- On server startup (when OMEGA_CADENCE_ENABLED=true)
- When adding a new cadence job to omega_cadence.py
- When a stub skill is promoted to full implementation (add its runner to RUNNERS)

## Steps

### Dry-run (development — no scheduling)
```
python omega_os/skills/cadence_wirer/tools/start_cadence.py --dry-run
```
Shows which jobs have real runners vs stubs and their UTC cron schedules.

### Production activation
```bash
OMEGA_CADENCE_ENABLED=true python omega_os/skills/cadence_wirer/tools/start_cadence.py
```

### Wiring from api_server.py startup
```python
from omega_os.skills.cadence_wirer.tools.start_cadence import start_cadence_if_enabled
# call at end of startup event handler:
start_cadence_if_enabled()
```

## Cadence job schedule (UTC)

| Slug | Schedule | Runner |
|---|---|---|
| daily_market_brief | Mon-Fri 11:00 UTC (7 AM ET) | REAL → session_briefing.py |
| daily_priority_brief | Mon-Fri 12:30 UTC (8:30 AM ET) | STUB |
| weekly_portfolio_review | Sun 22:00 UTC (6 PM ET) | STUB |
| weekly_omega_os_audit | Mon 13:00 UTC (9 AM ET) | REAL → route_audit.py |
| weekly_product_review | Mon 14:00 UTC (10 AM ET) | STUB |
| monthly_finance_report | 1st of month 12:00 UTC (8 AM ET) | STUB |
| monthly_product_roadmap_review | Last Fri 19:00 UTC (3 PM ET) | STUB |

## Adding a new real runner
1. Write the tool script under `omega_os/skills/<name>/tools/`
2. Add a `_run_<name>()` function to `start_cadence.py`
3. Add the slug → function mapping to `RUNNERS` dict
4. Add the cron schedule to `SCHEDULES` dict if not already present
5. Run `--dry-run` to verify REAL shows for the new slug

## Guardrails
- `start_cadence_if_enabled()` is safe to import unconditionally — no side effects unless env var is set
- Only OMEGA_CADENCE_ENABLED=true activates the scheduler
- Stub runners never call external APIs — they log and return
- Do not remove the misfire_grace_time=300 safety window

## Dependencies
```
pip install apscheduler
```
(Already in requirements if present; APScheduler missing → warning log, not crash)
