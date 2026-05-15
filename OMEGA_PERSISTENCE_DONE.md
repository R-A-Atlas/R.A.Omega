# Omega OS Persistence — DONE

**Date:** 2026-05-15
**Branch:** codex/chat-modes-settings

---

## Files Changed

| File | Change |
|------|--------|
| `omega_persistence.py` | Created — full persistence layer with Supabase + local fallback |
| `api_server.py` | Updated — 4 new `/omega-os/` endpoints |
| `tests/test_omega_persistence.py` | Created — 58 unit tests, all passing |

`.env.example` — Supabase placeholders already present; no change needed.

---

## What Was Built

### omega_persistence.py

**Detection:**
- `is_supabase_configured()` — checks SUPABASE_URL + SUPABASE_KEY for real credentials (not placeholder fragments like `YOUR_`, `YOUR_PROJECT_ID`, `example.com`)

**Write functions:**
- `save_report_metadata(report)` — saves report metadata; tries Supabase, falls back to local JSON
- `save_research_task(task)` — queues a research task; tries Supabase, falls back to local JSON
- `save_omega_event(event)` — always writes to local JSON (events log, no Supabase table assumed)

**Read functions:**
- `get_recent_reports(limit=10)` — newest first; Supabase or local JSON
- `get_research_queue(limit=10)` — queued tasks sorted by priority desc; Supabase or local JSON
- `get_persistence_status()` — returns mode, supabase_configured, counts, runtime_dir path

**Local fallback directory:**
```
omega_os/archives/runtime/
  reports.json         — report metadata records
  research_tasks.json  — queued research tasks
  omega_events.json    — system events log
```
- Auto-created on first write (`_ensure_runtime_dir()`)
- Capped at 500 records per file (`_MAX_LOCAL_RECORDS`)
- Returns `persistence_mode="local_fallback"` on every record

**Supabase delegation:**
- Attempted when `is_supabase_configured()` is True
- Falls back to local JSON on any exception (import error, network error, schema error)
- Returns `persistence_mode="supabase"` when Supabase write succeeds

---

### api_server.py — 4 new endpoints

```
GET  /omega-os/persistence/status   → {persistence_mode, supabase_configured, counts, runtime_dir}
GET  /omega-os/reports/recent       → {reports: [...], limit}
GET  /omega-os/research-queue       → {tasks: [...], limit}
POST /omega-os/research-task        → {task: {...}, status: "queued"}
```

All endpoints:
- Lazy-import `omega_persistence` (no startup cost)
- Return structured JSON
- Raise HTTP 422 for missing required fields, 500 for unexpected errors

---

## Safety Rules Enforced

- No Supabase credentials hardcoded — reads from env at call time only
- `omega_persistence` is never imported in `query_router.py`
- `classify_intent_route()` still takes exactly one parameter
- No broker write/trade actions in this module
- `persistence_mode` field always present in returned records
- Local fallback never triggers if Supabase is healthy

---

## py_compile Results

```
python -m py_compile omega_persistence.py api_server.py omega_connections.py prompt_builder.py
# ALL PASS
```

---

## Test Results

```
tests/test_omega_persistence.py: 58 passed
Full suite (excluding live-server test_omega.py): 1436 passed, 0 failures
```

### Test coverage
- `is_supabase_configured()` — 5 cases (no env, placeholder URL, placeholder key, real credentials, empty)
- `save_report_metadata()` — 10 cases (file save, id/UUID, mode, query stored, optional fields, accumulation, ISO8601 timestamp, sec_filings_used default/set, auto-mkdir)
- `save_research_task()` — 9 cases (file save, queued status, mode, priority default/custom, UUID, accumulation, optional fields)
- `save_omega_event()` — 5 cases (file save, id, severity default/custom, event_type stored)
- `get_recent_reports()` — 6 cases (returns list, empty, records returned, newest-first, limit, cap)
- `get_research_queue()` — 6 cases (returns list, empty, records returned, priority sort, limit, all queued)
- `get_persistence_status()` — 5 cases (dict, required keys, local_fallback mode, counts, runtime_dir string)
- No secrets — 3 cases (forbidden patterns, no real URLs, .env.example has placeholders)
- API endpoints — 6 cases (4 route registrations, JSON-serializable status, task response shape)
- Routing purity — 4 cases (not in query_router, classify_intent_route still 1 param, importable, py_compile)

---

## Remaining / Next Steps

- Research task status update endpoint (`PATCH /omega-os/research-task/{id}`) — not yet built; tasks stay "queued" forever in local fallback
- Supabase `research_tasks` table schema not in `schema.sql` — add if Supabase mode is needed in production
- `save_report_metadata()` in atlas_omega.py / api_server.py company report path — not yet called automatically; manual call from application code required
