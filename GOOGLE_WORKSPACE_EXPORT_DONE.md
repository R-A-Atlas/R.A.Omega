# Google Workspace Export Adapter — DONE

**Date:** 2026-05-15
**Branch:** codex/chat-modes-settings

---

## Files Changed

| File | Change |
|------|--------|
| `omega_google_workspace.py` | Created — full Google Workspace export adapter |
| `omega_connections.py` | Updated — `_google_workspace_status()` + "Google Workspace" registry entry |
| `.env.example` | Updated — added `GOOGLE_WORKSPACE_ENABLED`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_DRIVE_REPORTS_FOLDER_ID` |
| `api_server.py` | Updated — `GET /omega-os/google-workspace/status` + `POST /omega-os/export-report` |
| `tests/test_omega_google_workspace.py` | Created — 49 unit tests, all passing |

---

## What Was Built

### omega_google_workspace.py

**Detection:**
- `is_google_workspace_configured()` — True when `GOOGLE_WORKSPACE_ENABLED=true` AND all three credentials present and non-placeholder
- `get_google_workspace_status()` — full status dict: configured, enabled, missing_vars, available_operations, message, scopes, folder_id

**Export functions:**
- `create_report_doc(title, markdown_content, folder_id=None)` — creates Google Doc from report content; moves to Drive folder if configured
- `create_research_sheet(title, rows, folder_id=None)` — creates Google Sheet from tabular data
- `export_report_bundle(report_id, formats=["doc","sheet"])` — high-level export: loads metadata from omega_persistence, calls create_report_doc and/or create_research_sheet

**Not-configured path (safe without credentials):**
- All functions return `{"success": False, "status": "not_configured", "configured": False, ...}`
- Never crash — no exception propagates to caller
- `doc_id`, `doc_url`, `sheet_id`, `sheet_url` are None when not configured
- `exports: {}` when not configured

**Error path:**
- Google API errors caught and returned as `{"success": False, "status": "error", "error": "..."}`

**Credential flow (when configured):**
- `_build_credentials()` — uses `google.oauth2.credentials.Credentials` + refresh
- `googleapiclient.discovery.build()` — lazy import inside each function (not at module level)
- Scopes: `documents`, `spreadsheets`, `drive.file` (narrowest possible scope)

### omega_connections.py

Added `_google_workspace_status()`:
- `STATUS_PLANNED` when `GOOGLE_WORKSPACE_ENABLED=false`
- `STATUS_CONFIGURED` when enabled but credentials missing/placeholder
- `STATUS_ACTIVE` when fully configured

Added "Google Workspace" connection entry (slug: `google_workspace`) with `can_write=True`, `is_destructive=False`.

### .env.example

New section after existing Google OAuth2 block:
```
GOOGLE_WORKSPACE_ENABLED=false
GOOGLE_REFRESH_TOKEN=YOUR_GOOGLE_REFRESH_TOKEN
GOOGLE_DRIVE_REPORTS_FOLDER_ID=YOUR_FOLDER_ID
```

### api_server.py — 2 new endpoints

```
GET  /omega-os/google-workspace/status  → {configured, enabled, missing_vars, available_operations, message}
POST /omega-os/export-report            → {success, status, report_id, exports, configured}
```
POST endpoint:
- Requires `report_id` in body (422 if missing)
- Accepts optional `formats: ["doc","sheet"]`
- Returns `not_configured` when credentials absent — never crashes

---

## Safety Rules Enforced

- No Google credentials hardcoded — all reads from env at call time
- `omega_google_workspace` never imported in `query_router.py` or `prompt_builder.py`
- `classify_intent_route()` still takes exactly one parameter
- All functions return structured dicts, never raise uncaught exceptions
- Trading content (`stop_loss`, `entry_price`, `take_profit`) never appears in export responses
- `GOOGLE_WORKSPACE_ENABLED=false` is the default (opt-in, not opt-out)
- `drive.file` scope only — cannot access existing user files

---

## py_compile Results

```
python -m py_compile omega_google_workspace.py omega_connections.py omega_persistence.py api_server.py prompt_builder.py atlas_omega.py
# ALL PASS
```

---

## Test Results

```
tests/test_omega_google_workspace.py: 49 passed
Full suite (excluding live-server test_omega.py): 1517 passed, 0 failures
```

### Test coverage
- `is_google_workspace_configured()` — 6 cases (disabled, not set, enabled+missing, placeholder, real creds, "yes" variant)
- `get_google_workspace_status()` — 6 cases (returns dict, required keys, not_configured, configured+real, missing_vars listed, JSON-serializable)
- `create_report_doc()` not_configured — 6 cases (not_configured status, no crash, title in response, doc_id None, doc_url None, configured=False)
- `create_research_sheet()` not_configured — 4 cases (not_configured, no crash on empty rows, sheet_id None, rows_written=0)
- `export_report_bundle()` not_configured — 7 cases (not_configured, no crash, report_id in response, exports empty, configured=False, custom formats, default formats)
- omega_connections Google Workspace status — 6 cases (entry exists, planned when disabled, configured when enabled+missing, active when fully configured, can_write=True, not destructive)
- API endpoints — 4 cases (both routes registered, status returns structured JSON, export returns not_configured)
- No secrets — 3 cases (no secret patterns in source, .env.example uses placeholders, all required vars present)
- Routing purity — 4 cases (not in query_router, classify_intent_route 1 param, not in prompt_builder, importable)
- Trading format quarantine — 3 cases (company_report forbids trade phrases, export bundle no trading content, py_compile)

---

## Remaining / Next Steps

- `_build_credentials()` requires `google-auth google-api-python-client` — add to requirements.txt when activating
- `create_report_doc()` converts Markdown to plain text naively (strips `**`, `*`, `#`) — a proper converter (e.g. `markdown2` + HTML-to-text) is needed for production quality
- `export_report_bundle()` populates doc content only from persistence metadata; full report JSON content is not yet passed to the Doc — that wiring is the next step
- No Drive folder auto-creation — `GOOGLE_DRIVE_REPORTS_FOLDER_ID` must be created manually in Google Drive before first use
