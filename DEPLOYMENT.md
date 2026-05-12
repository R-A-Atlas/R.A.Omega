# R.A. Omega Deployment Runbook

This is the production path for R.A. Omega on Railway or Render. Local development can use `ATLAS_DISABLE_AUTH=true`; hosted production must not.

## Required Services

- GitHub repository: `https://github.com/R-A-Atlas/R.A.Omega`
- Python 3.11 or newer
- Supabase project for auth, sessions, history, preferences, watchlist, and billing tier state
- Stripe account for subscriptions
- Gemini API key for finance synthesis
- Optional OpenAI API key for voice transcription and TTS

## Production Environment Variables

Set these in Railway or Render:

```dotenv
ATLAS_DISABLE_AUTH=false
ATLAS_CORS_ORIGINS=https://your-domain.com

GOOGLE_API_KEY=your_gemini_key
GEMINI_API_KEY=your_gemini_key

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key

STRIPE_SECRET_KEY=sk_live_or_test_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRICE_STARTER=price_optional_starter
STRIPE_PRICE_PRO=price_pro
STRIPE_PRICE_BUSINESS=price_business
STRIPE_PRICE_ENTERPRISE=price_enterprise

ATLAS_DEV_API_KEY=long_random_key_for_developer_api
```

Optional:

```dotenv
OPENAI_API_KEY=
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_VOICE=alloy
TRADIER_TOKEN=
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_PAPER=True
```

## Supabase

1. Open the Supabase SQL Editor.
2. Run `schema.sql`.
3. Confirm these objects exist:
   - `chat_sessions`
   - `queries`
   - `research_jobs`
   - `user_preferences`
   - `user_watchlist`
   - `positions`
4. Confirm RLS policies are enabled and user-scoped.
5. Confirm `user_preferences` includes:
   - `subscription_tier`
   - `subscription_status`
   - `report_depth`
   - `card_density`
   - `voice_dictation`
   - `citation_preference`
   - `compliance_level`

## Stripe

Create recurring prices for:

- Pro: `$49/month`
- Business: `$149/month`
- Optional Enterprise/custom plan

Set webhook endpoint:

```text
https://your-domain.com/billing/webhook
```

Events to send:

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

## Railway

`railway.toml` is included. Railway should run:

```bash
python -m uvicorn api_server:app --host 0.0.0.0 --port $PORT
```

Health check:

```text
/health
```

## Render

Use these settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python -m uvicorn api_server:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

## Post-Deploy Smoke Test

Open:

```text
https://your-domain.com/
https://your-domain.com/app
https://your-domain.com/dashboard
https://your-domain.com/pricing
https://your-domain.com/health
```

Expected:

- `/` shows R.A. Omega auth/landing.
- `/app` redirects to `/auth` if not signed in.
- `/dashboard` returns HTML.
- `/pricing` shows Free, Pro, Business, Developer tiers.
- `/health` returns JSON with `status: ok`.

## Local Health Command

Use this before pushing or after a Cursor Cloud agent finishes:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\omega_health.ps1
```

For full verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\omega_health.ps1 -Full
```

## Production Guardrails

- Never deploy with `ATLAS_DISABLE_AUTH=true`.
- Never commit `.env`.
- Never put service role keys in browser-exposed config.
- Keep `SUPABASE_ANON_KEY` for browser auth only.
- Keep `SUPABASE_KEY` server-side only.
- Keep Stripe webhook signature verification enabled in production.
