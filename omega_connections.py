"""
omega_connections.py — Connection registry for the Omega OS layer.

Declares all planned and active connections with their auth requirements, permissions,
and safety notes. Does NOT require real credentials — use .env.example placeholders.

Usage:
    from omega_connections import get_registry, get_connection, list_active, list_planned
    registry = get_registry()
    conn = get_connection("gmail")
    active = list_active()
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_ACTIVE      = "active"
STATUS_CONFIGURED  = "configured"   # env vars set, not yet wired in code
STATUS_PLANNED     = "planned"      # registered but no credentials or code yet
STATUS_DEPRECATED  = "deprecated"

# ── Auth method constants ─────────────────────────────────────────────────────
AUTH_NONE      = "none"
AUTH_API_KEY   = "api_key"
AUTH_OAUTH2    = "oauth2"
AUTH_JWT       = "jwt"
AUTH_BOT_TOKEN = "bot_token"
AUTH_SERVICE_ACCOUNT = "service_account"


import os as _os


def _sec_edgar_status() -> str:
    """Return active if SEC_USER_AGENT is configured, else configured."""
    ua = _os.getenv("SEC_USER_AGENT", "").strip()
    if ua and "contact@example.com" not in ua.lower():
        return STATUS_ACTIVE
    return STATUS_CONFIGURED


def _telegram_status() -> str:
    """Return active if TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_IDS are set, configured if token only."""
    _placeholders = ("YOUR_", "your_", "placeholder", "PLACEHOLDER")
    token = _os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or any(p in token for p in _placeholders):
        return STATUS_CONFIGURED
    allowed = _os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not allowed or any(p in allowed for p in _placeholders):
        return STATUS_CONFIGURED
    return STATUS_ACTIVE


def _google_workspace_status() -> str:
    """Return active when GOOGLE_WORKSPACE_ENABLED=true and all credentials present, else planned."""
    enabled = _os.getenv("GOOGLE_WORKSPACE_ENABLED", "false").strip().lower()
    if enabled not in ("true", "1", "yes"):
        return STATUS_PLANNED
    _placeholder = ("YOUR_", "your_")
    for var in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        val = _os.getenv(var, "").strip()
        if not val or any(p in val for p in _placeholder):
            return STATUS_CONFIGURED
    return STATUS_ACTIVE


@dataclass(frozen=True)
class Connection:
    name: str
    slug: str                         # snake_case identifier for lookups
    status: str                       # active | configured | planned | deprecated
    auth_method: str
    env_vars_required: tuple[str, ...] = field(default_factory=tuple)
    permissions_needed: tuple[str, ...] = field(default_factory=tuple)
    can_read: bool = True
    can_write: bool = False
    is_destructive: bool = False      # can delete data or send money
    safety_notes: str = ""
    use_cases: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["env_vars_required"] = list(d["env_vars_required"])
        d["permissions_needed"] = list(d["permissions_needed"])
        d["use_cases"] = list(d["use_cases"])
        return d


# ── Connection registry ───────────────────────────────────────────────────────

_REGISTRY: list[Connection] = [

    # ── Active / production-ready ─────────────────────────────────────────────

    Connection(
        name="Supabase",
        slug="supabase",
        status=STATUS_ACTIVE,
        auth_method=AUTH_JWT,
        env_vars_required=("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY"),
        permissions_needed=("database_read", "database_write", "auth_management"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Service role key has full DB access — never expose in frontend. RLS policies must be applied for multi-tenant data isolation.",
        use_cases=("user auth", "sessions", "watchlist", "positions", "query history"),
    ),

    Connection(
        name="Stripe",
        slug="stripe",
        status=STATUS_CONFIGURED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID_STARTER", "STRIPE_PRICE_ID_PRO"),
        permissions_needed=("charges_read", "charges_write", "webhooks"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Never log Stripe secret keys. Webhook secret must be verified on every inbound event. Confirm production keys in deployment secrets before launch.",
        use_cases=("subscription billing", "checkout sessions", "webhook events"),
    ),

    Connection(
        name="Google Gemini",
        slug="gemini",
        status=STATUS_ACTIVE,
        auth_method=AUTH_API_KEY,
        env_vars_required=("GOOGLE_API_KEY",),
        permissions_needed=("generative_ai"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="gemini_limiter.py handles rate limiting — do not bypass. Use Flash for chat/simple, Pro for deep research and trade plans. Monitor cost via get_stats().",
        use_cases=("synthesis", "analysis", "report generation"),
    ),

    Connection(
        name="OpenAI Whisper",
        slug="openai_whisper",
        status=STATUS_CONFIGURED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("OPENAI_API_KEY",),
        permissions_needed=("audio_transcription"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="Audio files are sent to OpenAI API — do not transcribe sensitive PII. Raw audio is not stored; only the transcription text is logged.",
        use_cases=("POST /voice/query transcription"),
    ),

    Connection(
        name="OpenAI TTS",
        slug="openai_tts",
        status=STATUS_CONFIGURED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("OPENAI_API_KEY", "OPENAI_TTS_VOICE"),
        permissions_needed=("text_to_speech"),
        can_read=False,
        can_write=True,
        is_destructive=False,
        safety_notes="Do not send financial advice or trade recommendations to TTS without user confirmation. Shares OPENAI_API_KEY with Whisper.",
        use_cases=("POST /tts response audio"),
    ),

    Connection(
        name="ElevenLabs",
        slug="elevenlabs",
        status=STATUS_CONFIGURED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"),
        permissions_needed=("text_to_speech"),
        can_read=False,
        can_write=True,
        is_destructive=False,
        safety_notes="Alternative TTS provider. Falls back to OpenAI TTS if not configured.",
        use_cases=("POST /tts alternative voice output"),
    ),

    Connection(
        name="yfinance",
        slug="yfinance",
        status=STATUS_ACTIVE,
        auth_method=AUTH_NONE,
        env_vars_required=(),
        permissions_needed=("public_market_data"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="Free, unauthenticated API — rate-limited at scale. Add Polygon.io or Alpha Vantage as authenticated fallback before production launch with >100 concurrent users.",
        use_cases=("price data", "fundamentals", "options chain", "analyst targets"),
    ),

    Connection(
        name="Chroma (local)",
        slug="chroma",
        status=STATUS_ACTIVE,
        auth_method=AUTH_NONE,
        env_vars_required=(),
        permissions_needed=("local_file_read", "local_file_write"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Local vector DB at atlas_rag/. Do not delete the atlas_rag/ directory — it contains 355 pre-indexed chunks for SOUN, O, and NVDA.",
        use_cases=("RAG semantic search", "SEC filings chunks", "finance knowledge"),
    ),

    # ── Planned connections ───────────────────────────────────────────────────

    Connection(
        name="Gmail",
        slug="gmail",
        status=STATUS_PLANNED,
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN_GMAIL"),
        permissions_needed=("gmail.send", "gmail.readonly"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Requires OAuth2 consent flow. Never send trade recommendations via email without explicit user confirmation. Do not store refresh tokens in source code.",
        use_cases=("daily brief email delivery", "alert notifications", "digest reports"),
    ),

    Connection(
        name="Google Calendar",
        slug="google_calendar",
        status=STATUS_PLANNED,
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN_CALENDAR"),
        permissions_needed=("calendar.readonly", "calendar.events"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Read calendar for earnings and macro events. Write only for auto-scheduling cadence jobs. Never delete user events without explicit confirmation.",
        use_cases=("earnings event tracking", "cadence job scheduling", "macro calendar"),
    ),

    Connection(
        name="Google Drive",
        slug="google_drive",
        status=STATUS_PLANNED,
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN_DRIVE"),
        permissions_needed=("drive.file", "drive.readonly"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Use drive.file scope (not drive scope) — limits access to files created by this app only. Never access user files outside the R.A. Omega folder.",
        use_cases=("auto-save research reports", "PDF export to Drive", "company report archive"),
    ),

    Connection(
        name="Google Docs",
        slug="google_docs",
        status=STATUS_PLANNED,
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN_DRIVE"),
        permissions_needed=("documents.create", "documents.readonly"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Share GOOGLE_REFRESH_TOKEN_DRIVE with Google Drive. Create documents in the R.A. Omega Drive folder only.",
        use_cases=("company report docs", "weekly review documents", "research summaries"),
    ),

    Connection(
        name="Google Sheets",
        slug="google_sheets",
        status=STATUS_PLANNED,
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN_DRIVE"),
        permissions_needed=("spreadsheets.create", "spreadsheets.values.update"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Share token with Drive/Docs. Recommended for portfolio tracking and watchlist sync. Do not auto-overwrite user-modified sheets without version check.",
        use_cases=("portfolio tracking", "watchlist export", "performance log", "options chain export"),
    ),

    Connection(
        name="GitHub",
        slug="github",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("GITHUB_TOKEN",),
        permissions_needed=("repo_read", "repo_write"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Use a fine-grained personal access token scoped to the R.A. Omega repo only. Never push directly to main — use branches. Never include secrets in auto-generated commits.",
        use_cases=("auto-commit research outputs", "skill versioning", "session log commits"),
    ),

    Connection(
        name="Telegram",
        slug="telegram",
        status=_telegram_status(),
        auth_method=AUTH_BOT_TOKEN,
        env_vars_required=("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS"),
        permissions_needed=("receive_messages", "send_messages", "send_documents"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Webhook receiver gated by TELEGRAM_ALLOWED_USER_IDS allowlist — empty list rejects all users. Never forward financial data to public groups. Use private chat or private channel only.",
        use_cases=("capture inbox via chat", "daily brief delivery", "watchlist RED alerts", "research queue notifications"),
    ),

    Connection(
        name="ClickUp",
        slug="clickup",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("CLICKUP_API_KEY", "CLICKUP_LIST_ID"),
        permissions_needed=("task_create", "task_update"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Use a dedicated ClickUp list for R.A. Omega tasks only. Do not write to shared team spaces without explicit authorization.",
        use_cases=("research queue tasks", "sprint planning", "action item tracking"),
    ),

    Connection(
        name="Notion",
        slug="notion",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("NOTION_TOKEN", "NOTION_DATABASE_ID"),
        permissions_needed=("page_create", "database_update"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes="Use a dedicated Notion integration with access limited to the R.A. Omega workspace only. Do not grant access to personal or team-wide Notion accounts.",
        use_cases=("research notes", "company profiles", "weekly review pages"),
    ),

    Connection(
        name="Slack",
        slug="slack",
        status=STATUS_PLANNED,
        auth_method=AUTH_BOT_TOKEN,
        env_vars_required=("SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_CHANNEL_ID"),
        permissions_needed=("chat:write", "files:write"),
        can_read=False,
        can_write=True,
        is_destructive=False,
        safety_notes="Post to a dedicated #ra-omega channel only. Never post trade recommendations to public or shared Slack channels. Verify signing secret on all inbound events.",
        use_cases=("daily brief posts", "watchlist alerts", "weekly review summaries"),
    ),

    Connection(
        name="Alpha Vantage",
        slug="alpha_vantage",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("ALPHA_VANTAGE_KEY",),
        permissions_needed=("market_data_read"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="Use as fallback when yfinance is rate-limited. Free tier: 5 API calls/min, 500/day. Label data source in responses.",
        use_cases=("price fallback", "fundamentals fallback", "forex data"),
    ),

    Connection(
        name="Polygon.io",
        slug="polygon",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("POLYGON_API_KEY",),
        permissions_needed=("stocks_read", "options_read", "aggregates_read"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="Preferred authenticated market data source for production scale. Better rate limits than yfinance. Label data source in responses.",
        use_cases=("production market data", "options chain", "tick data", "aggregates"),
    ),

    Connection(
        name="Finnhub",
        slug="finnhub",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("FINNHUB_API_KEY",),
        permissions_needed=("quote_read", "news_read", "earnings_read"),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes="Good source for earnings calendars and sentiment data. Free tier available. Label data source in responses.",
        use_cases=("earnings calendar", "news sentiment", "insider trading data"),
    ),

    Connection(
        name="SEC EDGAR",
        slug="sec_edgar",
        status=_sec_edgar_status(),  # active when SEC_USER_AGENT is configured
        auth_method=AUTH_NONE,
        env_vars_required=("SEC_USER_AGENT",),
        permissions_needed=("public_api_read",),
        can_read=True,
        can_write=False,
        is_destructive=False,
        safety_notes=(
            "Free public API — no auth required. Respect EDGAR rate limits (10 req/sec max). "
            "SEC_USER_AGENT must identify your app and contact email per EDGAR terms of service. "
            "Format: 'App Name contact@yourdomain.com'. "
            "omega_sec_edgar.py implements rate limiting automatically."
        ),
        use_cases=("10-K/10-Q/8-K filings", "company CIK lookup", "filing dates", "material events"),
    ),

    Connection(
        name="SendGrid",
        slug="sendgrid",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("SENDGRID_API_KEY", "DIGEST_EMAIL", "DIGEST_FROM_EMAIL"),
        permissions_needed=("mail.send"),
        can_read=False,
        can_write=True,
        is_destructive=False,
        safety_notes="Use for digest emails only. Never send user financial data to unverified addresses. Rate-limit digest sends to once per cadence cycle.",
        use_cases=("daily digest email", "weekly report email", "alert notifications"),
    ),

    Connection(
        name="Broker API (generic)",
        slug="broker_api",
        status=STATUS_PLANNED,
        auth_method=AUTH_API_KEY,
        env_vars_required=("BROKER_API_KEY", "BROKER_API_SECRET", "BROKER_BASE_URL"),
        permissions_needed=("account_read", "market_data_read"),
        can_read=True,
        can_write=False,
        is_destructive=True,
        safety_notes="DESTRUCTIVE CAPABILITY — can place real trades with write permissions. Read-only initially. Never enable write/trading permissions without explicit multi-step user confirmation. Always paper trade first. Never auto-execute trades.",
        use_cases=("live positions sync", "real P&L data", "account balance", "paper trading validation"),
    ),

    Connection(
        name="Google Workspace",
        slug="google_workspace",
        status=_google_workspace_status(),
        auth_method=AUTH_OAUTH2,
        env_vars_required=("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN", "GOOGLE_WORKSPACE_ENABLED"),
        permissions_needed=("documents.create", "spreadsheets.create", "drive.file"),
        can_read=True,
        can_write=True,
        is_destructive=False,
        safety_notes=(
            "Set GOOGLE_WORKSPACE_ENABLED=true to activate. Uses drive.file scope only — "
            "limits access to files created by this app. Never access files outside the R.A. Omega "
            "Drive folder. Requires google-auth google-api-python-client packages."
        ),
        use_cases=("company report export to Google Docs", "research data export to Google Sheets", "Drive archive"),
    ),
]


# ── Registry lookup functions ─────────────────────────────────────────────────

def get_registry() -> list[Connection]:
    """Return all connections in the registry."""
    return list(_REGISTRY)


def get_connection(slug: str) -> Connection | None:
    """Look up a connection by its slug."""
    for conn in _REGISTRY:
        if conn.slug == slug:
            return conn
    return None


def list_active() -> list[Connection]:
    """Return connections with status=active."""
    return [c for c in _REGISTRY if c.status == STATUS_ACTIVE]


def list_configured() -> list[Connection]:
    """Return connections with status=configured (env vars set, not yet fully wired)."""
    return [c for c in _REGISTRY if c.status == STATUS_CONFIGURED]


def list_planned() -> list[Connection]:
    """Return connections with status=planned."""
    return [c for c in _REGISTRY if c.status == STATUS_PLANNED]


def list_by_status(status: str) -> list[Connection]:
    """Return connections matching a given status."""
    return [c for c in _REGISTRY if c.status == status]


def list_destructive() -> list[Connection]:
    """Return connections with is_destructive=True — these require extra confirmation before enabling."""
    return [c for c in _REGISTRY if c.is_destructive]


def registry_summary() -> dict:
    """Return a compact summary dict suitable for API responses."""
    return {
        "total": len(_REGISTRY),
        "active": len(list_active()),
        "configured": len(list_configured()),
        "planned": len(list_planned()),
        "connections": [
            {
                "name": c.name,
                "slug": c.slug,
                "status": c.status,
                "auth_method": c.auth_method,
                "can_read": c.can_read,
                "can_write": c.can_write,
                "is_destructive": c.is_destructive,
            }
            for c in _REGISTRY
        ],
    }
