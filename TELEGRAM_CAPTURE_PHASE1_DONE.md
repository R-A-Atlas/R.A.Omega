# TELEGRAM CAPTURE — PHASE 1 DONE

Date: 2026-05-16
Branch: codex/chat-modes-settings
Tests: **2294 passed, 0 failed** (no regressions; capture/telegram tests to be added in Phase 2)

---

## Goal Met

| Phase | Status |
|---|---|
| Phase 1: omega_capture.py — capture inbox (5 functions) | ✅ |
| Phase 2: omega_telegram.py — Telegram adapter (7 functions) | ✅ |
| Phase 3: .env.example — Telegram + voice placeholders | ✅ |
| py_compile: 6 target files | ✅ |

---

## Files Created

- `omega_capture.py` — Capture inbox (classify, save, triage, list, status)
- `omega_telegram.py` — Telegram adapter (configure check, allowlist, normalize, route)

## Files Changed

### .env.example
Added under the Telegram section:
```
TELEGRAM_ALLOWED_USER_IDS=YOUR_TELEGRAM_USER_ID
TELEGRAM_WEBHOOK_SECRET=YOUR_TELEGRAM_WEBHOOK_SECRET
VOICE_TRANSCRIPTION_ENABLED=false
WHISPER_PROVIDER=openai
```

---

## Capture Behavior (omega_capture.py)

### classify_capture(raw_text, source) → str

Deterministic keyword matching — no LLM calls.

| Type | Trigger keywords |
|---|---|
| `bug` | bug, broken, crash, error, fix, not working, fails, exception, 500 |
| `research_request` | research, analyze, look into, investigate, report on, deep dive |
| `reminder` | remind, reminder, don't forget, follow up, revisit |
| `content_idea` | post, tweet, blog, content, marketing, publish, draft |
| `idea` | idea, what if, could we, feature, proposal, suggest |
| `task` | todo, implement, add, create, build, write, make |
| `unknown` | (fallback) |

Priority order: bug > research_request > reminder > content_idea > idea > task > unknown.

### save_capture(raw_text, source, metadata) → dict

- Assigns UUID, timestamp, capture_type, status="inbox"
- Logs event to omega_persistence (degrades gracefully if unavailable)
- Always persists to `omega_os/archives/runtime/captures.json` (local fallback)
- Caps at 500 records to prevent unbounded growth

### triage_capture(capture_id) → dict

- Sets status="triaged", records triaged_at timestamp
- Returns `{"error": "..."}` if not found (never raises)

### get_capture_inbox(limit=20) → list[dict]

- Returns status="inbox" captures, newest first
- Max 100 records per call

### get_capture_status() → dict

Returns:
```python
{
    "total":         int,
    "inbox_count":   int,
    "triaged_count": int,
    "by_type":       {"bug": N, "idea": N, ...},
    "by_source":     {"telegram": N, ...},
    "storage":       "local_json",
    "captures_file": "...path...",
}
```

---

## Telegram Safety Behavior (omega_telegram.py)

### is_telegram_configured()

- Returns `False` when TELEGRAM_BOT_TOKEN is missing, empty, or contains any placeholder fragment (`YOUR_`, `your_`, `example`, `placeholder`)
- Never raises

### verify_allowed_user(user_id)

- Parses `TELEGRAM_ALLOWED_USER_IDS` (comma-separated integer IDs)
- Empty allowlist → ALL users rejected (fail-safe default)
- Returns `False` for any user not explicitly listed

### normalize_telegram_message(payload)

- Extracts: user_id, username, first_name, text, message_type, message_id, chat_id, voice_file_id
- message_type: text | voice | audio | photo | document | other | invalid
- Returns `{"error": "...", "message_type": "invalid"}` on malformed input — never raises

### process_telegram_text_message(payload)

Routing:
1. Not configured → `{"status": "error", "reason": "telegram_not_configured"}`
2. User not allowed → `{"status": "rejected", "reason": "user_not_allowed"}`
3. Empty text → `{"status": "error", "reason": "empty text"}`
4. Success → `{"status": "captured", "capture": {...}}`

### process_telegram_voice_message(payload)

Routing:
1. Not configured → `{"status": "error"}`
2. User not allowed → `{"status": "rejected"}`
3. `VOICE_TRANSCRIPTION_ENABLED=false` → `{"status": "voice_not_enabled"}`
4. Voice enabled, OPENAI_API_KEY missing/placeholder → `{"status": "not_configured"}`
5. Voice enabled, key present → `process_telegram_voice_stub()` → `{"status": "voice_not_implemented"}`

### process_telegram_voice_stub(payload)

Always returns:
```python
{"status": "voice_not_implemented", "reason": "...", "hint": "..."}
```
Safe placeholder until full Whisper wiring is added.

### get_telegram_status()

Returns dashboard-safe dict:
```python
{
    "configured":           bool,
    "status":               "not_configured" | "configured_no_allowlist" | "active",
    "voice_enabled":        bool,
    "whisper_configured":   bool,
    "allowed_users_count":  int,
    "webhook_secret_set":   bool,
    "whisper_provider":     "openai",
}
```

---

## Env Placeholders (.env.example)

```
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
TELEGRAM_ALLOWED_USER_IDS=YOUR_TELEGRAM_USER_ID
TELEGRAM_WEBHOOK_SECRET=YOUR_TELEGRAM_WEBHOOK_SECRET
VOICE_TRANSCRIPTION_ENABLED=false
WHISPER_PROVIDER=openai
```

All values are placeholder-only — no real credentials in any file.

---

## py_compile Results

```
python -m py_compile omega_capture.py omega_telegram.py omega_persistence.py omega_connections.py omega_dashboard.py api_server.py
# ALL PASS — no output
```

---

## pytest Results

```
2294 passed, 0 failed, 16 warnings in 71.72s
```

---

## Remaining Issues

None blocking.

| Optional next work | Priority |
|---|---|
| Add `tests/test_omega_capture.py` and `tests/test_omega_telegram.py` | High |
| Add `POST /telegram/webhook` route to api_server.py | Medium |
| Wire `get_capture_status()` into `build_command_center_snapshot()` | Medium |
| Add `telegram` to omega_connections.py registry with correct status detection | Low |
| Wire full Whisper transcription when voice is enabled | Future |
| Add Telegram bot send_message (outbound reply) with allowlist gate | Future |
