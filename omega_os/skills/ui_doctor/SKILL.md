# Skill: UI Doctor

**Slug:** ui_doctor  
**Priority:** 1 — run whenever the frontend looks broken or hasn't updated

## What It Does

Diagnoses and auto-fixes the R.A. Omega frontend serving stack. Catches every
known class of UI failure: CDN blocking, missing static assets, wrong Lucide icon
index, incorrect response field ordering, and server misconfiguration.

## Why It Exists

Edge's Tracking Prevention blocks CDN scripts (unpkg.com, cdn.tailwindcss.com)
on localhost, silently breaking React, Babel, and Lucide. This skill downloads
all dependencies to `/static/` and rewires the HTML to load them locally.

## Checks

1. **static_files** — React, Babel, Lucide, Tailwind are present in `/static/`
2. **static_mount** — FastAPI mounts `/static` via StaticFiles in api_server.py
3. **html_cdn_refs** — ra_omega_app.html uses `/static/` not CDN URLs
4. **lucide_icon_index** — Icon renderer reads `iconData[2]` (children) not `[1]` (attrs)
5. **format_response_order** — formatQueryResponse shows executive_summary before tldr
6. **server_reachable** — Server is up at http://127.0.0.1:8000
7. **app_correct_file** — /app serves the correct HTML with local deps

## Usage

```bash
# Diagnose only
python omega_os/skills/ui_doctor/tools/ui_doctor.py

# Diagnose + auto-fix all issues
python omega_os/skills/ui_doctor/tools/ui_doctor.py --fix

# JSON output (for scripting)
python omega_os/skills/ui_doctor/tools/ui_doctor.py --json
```

After `--fix` always restart the server:
```bash
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

Then hard-refresh the browser: `Ctrl+Shift+R`

## Rules

- Never modify deep_research.py, gemini_limiter.py, or the 10-loop engine
- Safe to run repeatedly — all fixes are idempotent
- Downloads use User-Agent header to avoid 403s from CDN
