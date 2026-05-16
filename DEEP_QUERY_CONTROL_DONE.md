# DEEP_QUERY_CONTROL_DONE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests before: 1600 passed
Tests after: 1636 passed (+36 new tests)

---

## Summary

Five-phase fix for bad ticker extraction, misfired deep research, stuck polling,
and quality firewall reliability.

---

## PHASE 1 — Stopword Expansion

**File:** `query_router.py`

Added to `QueryParser._STOPWORDS`:
```
ONN, TV, AH, USA, API, PDF, HTML
```

**Effect:** Queries like "ONN is moving — should I buy?" no longer extract ONN as a ticker.
"After hours TSLA up 3%" still extracts TSLA; AH is ignored.

---

## PHASE 2 — Research Mode Gate

**Files:** `query_router.py` (route() method), `api_server.py`

### query_router.py — route() gate
In the `else` branch (non-deep mode), after `classify_intent_route()` returns
`INTENT_MARKET_DEEP_DIVE`, the result is downgraded to `INTENT_GENERAL_FINANCE`
unless `_EXPLICIT_TRADE_RE` matches (user explicitly asks for trade setup/entry/stop).

```python
route_kind = classify_intent_route(raw_q)
# In normal/web mode, only explicit trade requests use the 10-loop engine.
if route_kind == INTENT_MARKET_DEEP_DIVE and not _EXPLICIT_TRADE_RE.search(raw_q):
    route_kind = INTENT_GENERAL_FINANCE
```

### api_server.py — pass research_mode to router.route()
```python
raw = router.route(
    q_store,
    ...
    research_mode=mode,   # ← added
    ...
)
```

**Effect:**
- `research_mode="normal"` + "analyze NVDA" → Omega (fast path, ~2s)
- `research_mode="deep"` + any query → 10-loop engine (forced)
- `research_mode="normal"` + "give me a trade setup for NVDA" → 10-loop (explicit trade preserved)

---

## PHASE 3 — Job Completion State

**Files:** `orchestration/research_jobs.py`, `api_server.py`, `ra_omega_app.html`

### research_jobs.py — activity_from_job()
Added `final_response_available` flag:
```python
"final_response_available": status in {"completed", "failed", "cancelled"},
```

### api_server.py — _build_research_activity_payload()
- Added `"final_response_available": True` to all non-quick_chat activity payloads
- Fixed `"progress_pct": 100` (was erroneously 35 for deep_research completed routes)

### ra_omega_app.html — poll stop condition
Added belt-and-suspenders to polling guard:
```javascript
if (!jobId || !['queued', 'in_progress'].includes(String(activity.status || '')) || activity.final_response_available) return;
```

---

## PHASE 4 — Quality Firewall Safety

No changes required. Existing code already:
- Wraps the entire quality firewall block in `try/except Exception`
- Returns the best available answer with `_quality_firewall: {passed: False, reason: ...}` flag
- Never blocks or freezes on validation failure

---

## PHASE 5 — Tests

**File:** `tests/test_deep_query_control.py` (36 new tests)

| Class | Count | Coverage |
|-------|-------|----------|
| `TestStopwordExpansion` | 15 | All 7 new stopwords + ticker extraction behavior |
| `TestRoutingGate` | 7 | route() param, gate source, api_server wiring, classify behavior |
| `TestJobCompletionState` | 8 | final_response_available for all status values |
| `TestQualityFirewallSafety` | 6 | validate_response safety for all edge cases |

---

## py_compile Results

```
python -m py_compile query_router.py api_server.py orchestration/research_jobs.py quality_firewall.py response_judge.py output_contracts.py output_modes.py
→ COMPILE OK ✅
```

---

## pytest Results

```
pytest tests/ --maxfail=5 --disable-warnings -q
→ 1636 passed, 16 warnings ✅  (+36 new tests)
```

---

## Behavior Matrix After Fix

| Scenario | Before | After |
|----------|--------|-------|
| "ONN is moving" → ticker extraction | ONN extracted | ONN ignored (stopword) |
| "After hours TSLA up 3%" → AH | AH extracted as ticker | AH ignored; TSLA extracted |
| "analyze NVDA" in normal mode | 10-loop engine (~45s) | Omega fast path (~3s) |
| "analyze NVDA" in deep mode | 10-loop engine | 10-loop engine (unchanged) |
| "give me a trade setup for NVDA" in normal mode | 10-loop | 10-loop (explicit trade preserved) |
| research_mode passed to router | Not passed | Passed: research_mode=mode |
| Completed job activity | No final_response_available | final_response_available: True |
| In-progress job activity | No final_response_available | final_response_available: False |
| Frontend poll stop on completed | Status-only check | Status OR final_response_available |
| Quality firewall failure | No change (already safe) | No change (already safe) |

---

## Remaining Issues

- None introduced by this fix.
- Supabase production migration still pending (user-run task).
- Visual QA on /app still recommended after any UI changes.
