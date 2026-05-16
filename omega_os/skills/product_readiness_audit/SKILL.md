# Skill: product_readiness_audit

## Purpose
Audits R.A. Omega's product readiness across 8 categories with a 100-point rubric.
Identifies exactly what is working, what is broken, and what is missing — with
specific fix instructions for each gap.

## Trigger
- Weekly (via audit_runner cadence job)
- Before any deployment to Railway/Render
- After any significant codebase change

## Steps
```
# Full audit
python omega_os/skills/product_readiness_audit/tools/readiness_check.py

# Single category deep-dive
python omega_os/skills/product_readiness_audit/tools/readiness_check.py --category auth
python omega_os/skills/product_readiness_audit/tools/readiness_check.py --category billing

# JSON output
python omega_os/skills/product_readiness_audit/tools/readiness_check.py --json
```

## Categories and max points

| Category | Max Pts | What it checks |
|---|---|---|
| Auth & Security | 20 | Auth route, Supabase JWT, DISABLE_AUTH guard, .env not committed |
| Billing | 10 | Stripe keys, webhook, subscription gate |
| Core AI Quality | 20 | Gemini key, intent router, 10-loop engine, OmegaAgent, envelope |
| UI/UX | 15 | /command-center, /app, sessions sidebar, StructuredResponse cards, mobile |
| Data Layer | 15 | atlas_memory.db, atlas_tracker.db, RAG chunks, vault outputs |
| Infrastructure | 10 | Procfile, /health, railway.json, GEMINI_API_KEY |
| Test Coverage | 5 | Test count ≥ 2000, no HIGH fragile tests |
| Memory & Personalization | 5 | Memory injector wired, Loop 5 personalization, session context |

## Verdict thresholds

| Score | Verdict |
|---|---|
| 90–100 | PRODUCTION READY |
| 75–89 | BETA READY |
| 55–74 | ALPHA / STAGING |
| < 55 | NOT READY |

## Guardrails
- All checks are read-only — never modifies any file
- Does not call external APIs or LLMs
- Auth check reads ATLAS_DISABLE_AUTH from env — run in dev context to test local state
- Production environment check: run on server with prod env vars to get accurate picture
