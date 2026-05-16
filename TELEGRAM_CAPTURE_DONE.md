# TELEGRAM CAPTURE — DONE

Date: 2026-05-16
Branch: codex/chat-modes-settings
Tests: **2363 passed, 0 failed** (+69 new tests since Phase 1)

---

## Goal Met

| Phase | Status |
|---|---|
| Phase 1 (prior): omega_capture.py + omega_telegram.py | ✅ |
| Phase 2: API endpoints (6 routes) | ✅ |
| Phase 3: Dashboard fields (4 new fields) | ✅ |
| Phase 4: tests/test_telegram_capture.py (69 tests) | ✅ |
| py_compile: 6 target files | ✅ |

---

## Files Changed

### api_server.py
Added 6 routes (before dev entry point):

| Route | Method | Description |
|---|---|---|
| `/omega-os/capture/status` | GET | Capture inbox counts by type/source |
| `/omega-os/capture/inbox` | GET | Recent unprocessed captures (newest first) |
| `/omega-os/capture` | POST | Manually save a text capture |
| `/omega-os/capture/{capture_id}/triage` | POST | Mark capture as triaged |
| `/omega-os/telegram/status` | GET | Telegram adapter + voice config status |
| `/omega-os/telegram/webhook` | POST | Receive Telegram webhook updates |

### omega_dashboard.py
Added two helper functions (`_get_capture_status()`, `_get_telegram_status()`) and four new fields to `build_command_center_snapshot()`:
- `capture_inbox_count` (int)
- `latest_captures` (list, last 5)
- `telegram_status` (dict)
- `voice_capture_status` ("enabled" | "disabled")

### tests/test_telegram_capture.py (NEW — 69 tests)

---

## Endpoints — Behavior

### POST /omega-os/capture
```json
Request: {"text": "Bug: login fails", "source": "web", "metadata": {...}}
Response: {"status": "captured", "capture": {id, saved_at, capture_type, ...}}
Error 400: text field missing
```

### POST /omega-os/telegram/webhook

Routing logic:
1. `TELEGRAM_BOT_TOKEN` missing → `{"ok": false, "status": "not_configured"}` (HTTP 200)
2. Malformed payload → `{"ok": false, "status": "invalid_payload"}` (HTTP 200)
3. Text message, unauthorized user → `{"ok": true, "result": {"status": "rejected"}}`
4. Text message, allowed user → `{"ok": true, "result": {"status": "captured", "capture": {...}}}`
5. Voice message, `VOICE_TRANSCRIPTION_ENABLED=false` → `{"status": "voice_not_enabled"}`
6. Voice + enabled + no key → `{"status": "not_configured"}`
7. Voice + enabled + key → `{"status": "voice_not_implemented"}`
8. Unknown message type → `{"status": "ignored"}`

**Always returns HTTP 200** — Telegram retries on non-200, which would create infinite loops on config errors.

---

## Dashboard Fields

`GET /omega-os/dashboard` now includes:

```python
{
    "capture_inbox_count":  int,          # unprocessed captures
    "latest_captures":      list[dict],   # last 5 inbox captures
    "telegram_status": {
        "configured":           bool,
        "status":               "not_configured" | "configured_no_allowlist" | "active",
        "voice_enabled":        bool,
        "whisper_configured":   bool,
        "allowed_users_count":  int,
        "webhook_secret_set":   bool,
    },
    "voice_capture_status": "enabled" | "disabled",
}
```

No Telegram credentials required to load the dashboard — all fields degrade gracefully.

---

## Tests (69 new)

| Category | Tests |
|---|---|
| classify_capture — all 7 types + edge cases | 9 |
| save_capture — fields, source, status, metadata | 7 |
| get_capture_inbox — returns list, ordering | 2 |
| triage_capture — success + unknown ID | 2 |
| get_capture_status — fields, types | 3 |
| is_telegram_configured — missing/placeholder/real | 3 |
| verify_allowed_user — empty/placeholder/in/not-in | 4 |
| normalize_telegram_message — text/voice/malformed/empty | 5 |
| process_telegram_text_message — not_configured/rejected/captured/malformed | 4 |
| process_telegram_voice_message — 5 gate states + stub | 6 |
| get_telegram_status — fields + not_configured | 3 |
| API: capture CRUD endpoints | 6 |
| API: Telegram webhook (not_configured/rejected/captured/malformed/voice_disabled) | 5 |
| Dashboard: 4 new fields present + types | 4 |
| Security: no hardcoded secrets in capture/telegram files | 3 |

---

## py_compile Results

```
python -m py_compile omega_capture.py omega_telegram.py omega_persistence.py omega_connections.py omega_dashboard.py api_server.py
# ALL PASS — no output
```

---

## pytest Results

```
2363 passed, 0 failed, 16 warnings in 63.70s
```

---

## Remaining Issues

None blocking.

| Optional next work | Priority |
|---|---|
| Add `telegram` to omega_connections.py registry with `_telegram_status()` detection | Medium |
| Wire Telegram webhook secret verification (HMAC check on X-Telegram-Bot-Api-Secret-Token) | Medium |
| Full Whisper transcription wiring (when voice enabled + key present) | Future |
| Telegram outbound reply (send_message) with allowlist gate | Future |
| Hermes operator routing — route captures to correct skill/worker | Future |
