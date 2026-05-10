# R.A. Omega

R.A. Omega is a finance-focused AI assistant and trading intelligence platform. The current app combines a FastAPI backend, a ChatGPT-style web chat surface, financial research agents, portfolio/watchlist endpoints, voice/TTS support, Supabase-backed history, and a large test suite for the agent modules.

The main local product surface is:

- API server: `api_server.py`
- Primary chat UI: `http://127.0.0.1:8000/option1`
- Optional dashboard: `http://127.0.0.1:8000/v4`

## Current Status

- Sprint 8 and Sprint 9 installers have been audited and run locally.
- Sprint 9 C0 code optimizer tests pass.
- Full test suite passes locally with expected skips and Supabase dependency warnings.
- Generated caches, local databases, reports, secrets, and large document exports are ignored by Git.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with any keys you want to enable. For local UI development without Supabase auth, keep:

```dotenv
ATLAS_DISABLE_AUTH=true
```

Start the app:

```powershell
.\start_ra_omega.ps1
```

Or run directly:

```powershell
python api_server.py
```

Then open:

```text
http://127.0.0.1:8000/option1
```

## Verification

Run the focused Sprint 9 optimizer test:

```powershell
python -m pytest tests/test_c0_code_optimizer.py -v
```

Run the full suite:

```powershell
python -m pytest tests/ -q
```

Known local result from the current source:

```text
878 passed, 55 skipped, 2 warnings
```

The warnings are Supabase package deprecation warnings for `timeout` and `verify`. The skips are intentional for optional external dependencies, slow checks, future scraper placeholders, and Windows-specific export runtime conditions.

## Environment

Start from `.env.example`. Important variables:

- `ATLAS_DISABLE_AUTH=true` for local development without Supabase JWTs.
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` for Gemini-backed finance analysis.
- `OPENAI_API_KEY` for Whisper voice input and OpenAI TTS.
- `SUPABASE_URL`, `SUPABASE_KEY`, and `SUPABASE_ANON_KEY` for hosted auth, history, sessions, positions, and watchlists.
- `TRADIER_TOKEN`, `ALPACA_API_KEY`, and `ALPACA_SECRET_KEY` for broker/data integrations.
- `SENDGRID_API_KEY` or SMTP variables for digest email.

Never commit `.env`, keys, local cache folders, database files, generated reports, or exports.

## Main Files

- `api_server.py` - FastAPI app, API endpoints, auth dependency, UI routes.
- `index_1778227564596.html` - primary R.A. Omega chat UI.
- `atlas_omega.py` - core Omega financial assistant logic.
- `query_router.py` - routing layer for finance queries.
- `atlas_agents/` - agent prompts and modules by domain.
- `atlas_vault/02-Wiki/Skills/` - tracked skill definitions required by the tests.
- `schema.sql` - Supabase table shape and migration reference.
- `tests/` - regression, endpoint, security, export, and agent tests.

## Next Product Work

1. Consolidate the primary UI into a stable filename, such as `ra_omega_app.html`, and keep old dashboards as archive references only if still needed.
2. Add a single app config layer for model/provider settings instead of spreading provider behavior across scripts.
3. Complete voice input UX: recording state, transcript preview, send/cancel behavior, and graceful errors when `OPENAI_API_KEY` is missing.
4. Tighten hosted auth/session flow with Supabase and keep `ATLAS_DISABLE_AUTH=true` local-only.
5. Add deployment instructions once the hosting target is chosen.
