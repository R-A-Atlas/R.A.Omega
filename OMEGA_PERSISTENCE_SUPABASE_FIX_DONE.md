# OMEGA_PERSISTENCE_SUPABASE_FIX_DONE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests before: 1591 passed
Tests after: 1600 passed (+9 new tests)

---

## Root Cause

`omega_persistence.py` had 4 locations doing:
```python
from atlas_db import supabase as _sb
```

But `atlas_db.py` does not export a module-level `supabase` symbol. The correct pattern is:
```python
get_supabase_client()  # lazy singleton, returns None if unconfigured
```

This caused a `cannot import name 'supabase' from 'atlas_db'` ImportError every time
Supabase was configured, which was swallowed by the `except Exception` block and
silently forced the local fallback — even when Supabase was available.

---

## Files Changed

| File | Change |
|------|--------|
| `omega_persistence.py` | Fixed all 4 bad imports → use `get_supabase_client()` |
| `tests/test_omega_persistence.py` | Added 9 new tests covering Supabase path and fix regression |

---

## Diff Summary

### omega_persistence.py (4 hunks, identical pattern)

```diff
- from atlas_db import supabase as _sb
- if _sb:
+ from atlas_db import get_supabase_client as _get_sb
+ _sb = _get_sb()
+ if _sb:
```

Applied to:
1. `save_report_metadata()` — queries table insert
2. `save_research_task()` — research_tasks table insert
3. `get_recent_reports()` — queries table select
4. `get_research_queue()` — research_tasks table select

### tests/test_omega_persistence.py (9 new tests)

**TestRoutingPurity (1 new):**
- `test_uses_get_supabase_client_not_bare_symbol` — asserts source never imports bare `supabase` from atlas_db; asserts `get_supabase_client` is present

**TestSupabasePath (5 new):**
- `test_save_report_uses_supabase_when_configured` — mocks `get_supabase_client`, confirms `persistence_mode == "supabase"`
- `test_get_recent_reports_uses_supabase_when_configured` — mocks client, confirms list returned
- `test_get_research_queue_uses_supabase_when_configured` — mocks client, confirms list returned
- `test_falls_back_to_local_when_client_is_none` — client returns None → local fallback
- `test_falls_back_to_local_on_supabase_exception` — client raises → local fallback

**TestApiResponses (3 new):**
- `test_research_queue_endpoint_returns_list` — no crash when Supabase not configured
- `test_dashboard_endpoint_registered` — /omega-os/dashboard route exists
- `test_dashboard_snapshot_is_json_serializable` — full snapshot serializes to JSON

---

## py_compile Results

```
python -m py_compile atlas_db.py omega_persistence.py api_server.py omega_dashboard.py
→ COMPILE OK ✅
```

---

## pytest Results

```
pytest tests/ --maxfail=5 --disable-warnings -q
→ 1600 passed, 16 warnings ✅  (+9 new tests)
```

---

## Behavior After Fix

| Scenario | Before | After |
|----------|--------|-------|
| Supabase configured, real creds | ImportError → silent fallback to local | `get_supabase_client()` called → Supabase path executes correctly |
| Supabase configured, client returns None | ImportError → fallback | None check → fallback (correct) |
| Supabase configured, client raises | ImportError → fallback | Exception caught → fallback (correct) |
| Supabase not configured | Env check short-circuits before import | Same — no change |

---

## Remaining Issues

- None introduced by this fix.
- The missing import warning is now gone.
- Local fallback continues to work correctly when Supabase is not configured.
- Supabase path now correctly delegates to `atlas_db.get_supabase_client()`.
