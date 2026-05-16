"""
omega_telegram.py — Safe Telegram adapter for R.A. Omega capture inbox.

Receives Telegram webhook payloads, verifies user allowlist, and routes
messages to the capture inbox (omega_capture). Voice messages require
VOICE_TRANSCRIPTION_ENABLED=true and a valid Whisper/OpenAI key.

No real credentials are required to import this module — all functions
degrade gracefully when TELEGRAM_BOT_TOKEN is missing.

Safety rules:
- Only TELEGRAM_ALLOWED_USER_IDS may send messages; all others are rejected.
- TELEGRAM_BOT_TOKEN must be present and non-placeholder to be considered configured.
- Voice transcription only fires when VOICE_TRANSCRIPTION_ENABLED=true AND
  OPENAI_API_KEY is present and non-placeholder.
- Never crashes on malformed payloads.
- Never sends messages, only receives.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# ── Placeholder detection ─────────────────────────────────────────────────────

_PLACEHOLDER_FRAGMENTS = ("YOUR_", "your_", "example", "placeholder")


def _is_real_value(val: str) -> bool:
    """Return True if val looks like a real credential (not a placeholder)."""
    if not val or not val.strip():
        return False
    for frag in _PLACEHOLDER_FRAGMENTS:
        if frag in val:
            return False
    return True


# ── Configuration checks ──────────────────────────────────────────────────────

def is_telegram_configured() -> bool:
    """Return True when TELEGRAM_BOT_TOKEN is present and non-placeholder."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    return _is_real_value(token)


def _get_allowed_user_ids() -> set[str]:
    """
    Parse TELEGRAM_ALLOWED_USER_IDS env var.

    Format: comma-separated list of Telegram user IDs (integers as strings).
    Returns empty set when not configured — this means ALL users are rejected.
    """
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not raw or not _is_real_value(raw):
        return set()
    return {uid.strip() for uid in raw.split(",") if uid.strip()}


def _is_voice_enabled() -> bool:
    """Return True when VOICE_TRANSCRIPTION_ENABLED=true."""
    val = os.getenv("VOICE_TRANSCRIPTION_ENABLED", "false").strip().lower()
    return val in ("true", "1", "yes")


def _is_whisper_configured() -> bool:
    """Return True when a real OPENAI_API_KEY is present."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return _is_real_value(key) and key.startswith("sk-")


# ── Public API ────────────────────────────────────────────────────────────────

def get_telegram_status() -> dict[str, Any]:
    """
    Return Telegram adapter status for dashboard/health consumption.

    Returns dict with: configured, voice_enabled, whisper_configured,
    allowed_users_count, status, webhook_secret_set.
    """
    configured = is_telegram_configured()
    voice      = _is_voice_enabled()
    whisper    = _is_whisper_configured()
    allowed    = _get_allowed_user_ids()
    webhook_secret = _is_real_value(os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip())

    if not configured:
        status = "not_configured"
    elif not allowed:
        status = "configured_no_allowlist"
    else:
        status = "active"

    return {
        "configured":           configured,
        "status":               status,
        "voice_enabled":        voice,
        "whisper_configured":   whisper,
        "allowed_users_count":  len(allowed),
        "webhook_secret_set":   webhook_secret,
        "whisper_provider":     os.getenv("WHISPER_PROVIDER", "openai"),
    }


def verify_allowed_user(user_id: int | str) -> bool:
    """
    Return True if user_id is in TELEGRAM_ALLOWED_USER_IDS.

    An empty allowlist means NO users are allowed (fail-safe default).
    """
    allowed = _get_allowed_user_ids()
    if not allowed:
        return False
    return str(user_id) in allowed


def normalize_telegram_message(payload: Any) -> dict[str, Any]:
    """
    Extract fields from a Telegram Update payload.

    Returns a normalized dict with:
        user_id, username, text, message_type, message_id, chat_id,
        voice_file_id, raw_payload_summary.

    Never raises — returns {"error": "..."} on malformed input.
    """
    try:
        if not isinstance(payload, dict):
            return {"error": "payload must be a dict", "message_type": "invalid"}

        message = payload.get("message") or payload.get("edited_message") or {}
        if not message:
            return {"error": "no message in payload", "message_type": "invalid"}

        user    = message.get("from") or {}
        user_id = user.get("id")
        chat    = message.get("chat") or {}

        # Determine message type
        if message.get("text"):
            message_type = "text"
        elif message.get("voice"):
            message_type = "voice"
        elif message.get("audio"):
            message_type = "audio"
        elif message.get("photo"):
            message_type = "photo"
        elif message.get("document"):
            message_type = "document"
        else:
            message_type = "other"

        voice = message.get("voice") or {}

        return {
            "user_id":             user_id,
            "username":            user.get("username", ""),
            "first_name":          user.get("first_name", ""),
            "text":                message.get("text", ""),
            "message_type":        message_type,
            "message_id":          message.get("message_id"),
            "chat_id":             chat.get("id"),
            "voice_file_id":       voice.get("file_id"),
            "voice_duration_secs": voice.get("duration"),
            "raw_payload_summary": f"update_id={payload.get('update_id')} type={message_type}",
        }
    except Exception as exc:
        log.warning("normalize_telegram_message: %s", exc)
        return {"error": str(exc), "message_type": "invalid"}


def process_telegram_text_message(payload: Any) -> dict[str, Any]:
    """
    Process a Telegram text message — save to capture inbox.

    Args:
        payload: Raw Telegram Update dict.

    Returns:
        {"status": "captured", "capture": {...}} on success.
        {"status": "rejected", "reason": "..."} when user not allowed.
        {"status": "error",    "reason": "..."} on any failure.
    """
    try:
        if not is_telegram_configured():
            return {"status": "error", "reason": "telegram_not_configured"}

        msg = normalize_telegram_message(payload)
        if msg.get("error"):
            return {"status": "error", "reason": msg["error"]}
        if msg.get("message_type") != "text":
            return {"status": "error", "reason": f"expected text message, got {msg.get('message_type')}"}

        user_id = msg.get("user_id")
        if not verify_allowed_user(user_id):
            log.warning("omega_telegram: rejected user_id=%s (not in allowlist)", user_id)
            return {"status": "rejected", "reason": "user_not_allowed"}

        text = msg.get("text", "").strip()
        if not text:
            return {"status": "error", "reason": "empty text"}

        from omega_capture import save_capture as _save
        capture = _save(
            raw_text=text,
            source="telegram",
            metadata={
                "user_id":    user_id,
                "username":   msg.get("username"),
                "message_id": msg.get("message_id"),
                "chat_id":    msg.get("chat_id"),
            },
        )

        return {"status": "captured", "capture": capture}

    except Exception as exc:
        log.warning("process_telegram_text_message: %s", exc)
        return {"status": "error", "reason": str(exc)}


def process_telegram_voice_stub(payload: Any) -> dict[str, Any]:
    """
    Placeholder for future voice transcription.

    Always returns {"status": "voice_not_implemented"} until Whisper is wired.
    Safe to call — never crashes.
    """
    return {
        "status":  "voice_not_implemented",
        "reason":  "Voice transcription not yet wired. Set VOICE_TRANSCRIPTION_ENABLED=true and configure OPENAI_API_KEY to enable.",
        "hint":    "See docs/architecture/ALWAYS_ON_AGENT_HOSTING.md for Whisper setup.",
    }


def process_telegram_voice_message(payload: Any) -> dict[str, Any]:
    """
    Process a Telegram voice message.

    Routing:
      - VOICE_TRANSCRIPTION_ENABLED=false → voice_not_enabled
      - VOICE_TRANSCRIPTION_ENABLED=true, no OPENAI_API_KEY → not_configured
      - VOICE_TRANSCRIPTION_ENABLED=true, key present → process_telegram_voice_stub
        (stub returns voice_not_implemented until full Whisper wiring is done)

    Args:
        payload: Raw Telegram Update dict.

    Returns:
        Status dict — never raises.
    """
    try:
        if not is_telegram_configured():
            return {"status": "error", "reason": "telegram_not_configured"}

        msg = normalize_telegram_message(payload)
        if msg.get("error"):
            return {"status": "error", "reason": msg["error"]}

        user_id = msg.get("user_id")
        if not verify_allowed_user(user_id):
            log.warning("omega_telegram: rejected voice from user_id=%s", user_id)
            return {"status": "rejected", "reason": "user_not_allowed"}

        if not _is_voice_enabled():
            return {
                "status": "voice_not_enabled",
                "reason": "Set VOICE_TRANSCRIPTION_ENABLED=true to enable voice capture.",
            }

        if not _is_whisper_configured():
            return {
                "status": "not_configured",
                "reason": "OPENAI_API_KEY is missing or placeholder. Configure it to enable Whisper transcription.",
            }

        # Voice is enabled and key is configured — hand off to stub
        return process_telegram_voice_stub(payload)

    except Exception as exc:
        log.warning("process_telegram_voice_message: %s", exc)
        return {"status": "error", "reason": str(exc)}
