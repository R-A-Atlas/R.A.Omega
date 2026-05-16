# Skill: deployment_checklist

## Purpose
Pre-deployment gate that validates every requirement before pushing to Railway/Render.
Exits 1 if any hard blocker is found. Use as a final manual check or CI gate.

## Trigger
- Before any `git push` to the deploy branch
- Before merging a PR that changes api_server.py, auth.html, or env var usage
- As part of a monthly "are we still deployable?" audit

## Steps
1. Set prod-like env vars (or review what is and isn't set)
2. Run: `python omega_os/skills/deployment_checklist/tools/deploy_check.py`
3. Fix all [!!] blockers before pushing
4. Review [~~] warnings — non-blocking but should be addressed before launch

## Blockers (hard failures — do NOT deploy if any fail)
- ATLAS_DISABLE_AUTH must NOT be "true" in prod
- auth.html must redirect to /command-center (not /option1 or /app)
- SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY must be set
- .env must NOT be staged in git
- All required HTML and Python files must exist on disk
- api_server.py must compile clean
- atlas_memory.db and atlas_tracker.db must exist
- Procfile must exist and reference uvicorn + api_server

## Warnings (review before deploying)
- STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET not set → billing won't work
- TELEGRAM_BOT_TOKEN not set → Telegram delivery won't work
- OPENAI_API_KEY not set → voice transcription won't work
- atlas_memory.db < 1KB → may be empty

## Guardrails
- ATLAS_DISABLE_AUTH=true is local dev only — NEVER deploy with it true
- Never commit .env to git (this checker enforces it)
- Do not remove required file checks without updating CLAUDE.md Section 8

## Output
```
  [OK]  ATLAS_DISABLE_AUTH=(not set) — auth guard active
  [!!]  SUPABASE_URL not set — Supabase project URL
  [~~]  STRIPE_SECRET_KEY not set — Stripe billing (revenue blocked without this)
...
RESULT: FAIL — 1 blocker(s)
```
