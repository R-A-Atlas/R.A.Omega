# Connections Registry

Status legend: planned | configured | active | deprecated

## Current Connections

| Name | Status | Auth Method | Notes |
|------|--------|-------------|-------|
| Supabase | active | JWT + service role key | Auth, sessions, watchlist, positions |
| Stripe | configured | API key + webhook secret | Billing routes exist; prod verification pending |
| yfinance | active | none (free) | Market data, fundamentals, options chain |
| Gemini (Google AI) | active | API key | Primary LLM — Flash for simple, Pro for deep |
| OpenAI Whisper | configured | API key | POST /voice/query |
| OpenAI TTS | configured | API key | POST /tts |
| ElevenLabs | configured | API key | TTS alternative |
| Chroma (local) | active | none (local file) | RAG vector DB — atlas_rag/ |

## Planned Connections

| Name | Status | Auth Method | Env Vars Needed | Read | Write | Destructive |
|------|--------|-------------|-----------------|------|-------|-------------|
| Google Workspace | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| Gmail | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| Google Calendar | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| Google Drive | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| Google Docs | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| Google Sheets | planned | OAuth2 | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | yes | no |
| GitHub | planned | Personal access token | GITHUB_TOKEN | yes | yes | no |
| Telegram | planned | Bot token | TELEGRAM_BOT_TOKEN | yes | yes | no |
| ClickUp | planned | API key | CLICKUP_API_KEY | yes | yes | no |
| Notion | planned | Integration token | NOTION_TOKEN | yes | yes | no |
| Slack | planned | Bot token + signing secret | SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET | yes | yes | no |
| Broker API (generic) | planned | API key + secret | BROKER_API_KEY, BROKER_API_SECRET | yes | no | no |
| SEC EDGAR | planned | none (free API) | none | yes | no | no |
| Alpha Vantage | planned | API key | ALPHA_VANTAGE_KEY | yes | no | no |
| Polygon.io | planned | API key | POLYGON_API_KEY | yes | no | no |
| Finnhub | planned | API key | FINNHUB_API_KEY | yes | no | no |
| SendGrid | planned | API key | SENDGRID_API_KEY | no | yes | no |
| Railway | planned | API token | RAILWAY_TOKEN | yes | yes | no |

## Safety Rules
- Never hardcode API keys or secrets in source files
- All secrets must be in .env (gitignored) with placeholders in .env.example
- Destructive operations require explicit user confirmation before execution
- OAuth flows are interactive — suggest `! gcloud auth login` pattern for CLI
