"""Central runtime configuration helpers for R.A. Omega.

This module keeps environment-variable parsing in one place for hosted auth,
billing, AI providers, and browser-exposed public config. It intentionally
returns strings/booleans instead of a long-lived singleton so tests can safely
monkeypatch environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def env_text(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_csv(name: str) -> list[str]:
    return [part.strip() for part in env_text(name).split(",") if part.strip()]


def google_api_key() -> str:
    return env_text("GOOGLE_API_KEY") or env_text("GEMINI_API_KEY")


def gemini_model() -> str:
    return env_text("GEMINI_MODEL", "gemini-2.5-flash")


def openai_api_key() -> str:
    return env_text("OPENAI_API_KEY")


def openai_whisper_model() -> str:
    return env_text("OPENAI_WHISPER_MODEL", "whisper-1")


def openai_tts_model() -> str:
    return env_text("OPENAI_TTS_MODEL", "tts-1")


def openai_tts_voice(override: str | None = None) -> str:
    return (override or env_text("OPENAI_TTS_VOICE") or "alloy").strip()


def elevenlabs_api_key() -> str:
    return env_text("ELEVENLABS_API_KEY")


def elevenlabs_voice_id(override: str | None = None) -> str:
    return (override or env_text("ELEVENLABS_VOICE_ID")).strip()


def auth_disabled() -> bool:
    return env_bool("ATLAS_DISABLE_AUTH")


def allow_unsigned_stripe_webhook() -> bool:
    return env_bool("ATLAS_ALLOW_UNSIGNED_STRIPE_WEBHOOK")


def cors_origins() -> list[str]:
    return env_csv("ATLAS_CORS_ORIGINS")


def developer_api_keys() -> list[str]:
    raw = env_text("ATLAS_DEV_API_KEYS") or env_text("ATLAS_DEV_API_KEY")
    return [key.strip() for key in raw.split(",") if key.strip()]


def default_subscription_tier() -> str:
    return env_text("ATLAS_DEFAULT_SUBSCRIPTION_TIER", "free").lower() or "free"


def tier_daily_limit(tier: str, default: int) -> int:
    raw = env_text(f"ATLAS_TIER_{str(tier or '').upper()}_DAILY_QUERIES")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def stripe_secret_key() -> str:
    return env_text("STRIPE_SECRET_KEY")


def stripe_webhook_secret() -> str:
    return env_text("STRIPE_WEBHOOK_SECRET")


def stripe_price_for_plan(plan: str) -> str:
    name = str(plan or "").upper()
    return env_text(f"STRIPE_PRICE_{name}") or env_text(f"STRIPE_PRICE_ID_{name}")


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_key: str
    anon_key: str

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_key)

    @property
    def public(self) -> dict[str, str]:
        return {"url": self.url, "anonKey": self.anon_key}


def supabase_config() -> SupabaseConfig:
    anon = env_text("SUPABASE_ANON_KEY") or env_text("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    return SupabaseConfig(
        url=env_text("SUPABASE_URL"),
        service_key=env_text("SUPABASE_KEY"),
        anon_key=anon,
    )


__all__ = [
    "SupabaseConfig",
    "allow_unsigned_stripe_webhook",
    "auth_disabled",
    "cors_origins",
    "default_subscription_tier",
    "developer_api_keys",
    "elevenlabs_api_key",
    "elevenlabs_voice_id",
    "env_bool",
    "env_csv",
    "env_text",
    "gemini_model",
    "google_api_key",
    "openai_api_key",
    "openai_tts_model",
    "openai_tts_voice",
    "openai_whisper_model",
    "stripe_price_for_plan",
    "stripe_secret_key",
    "stripe_webhook_secret",
    "supabase_config",
    "tier_daily_limit",
]
