"""
tests/test_telegram_capture.py

Tests for the Telegram capture foundation:
- omega_capture: classify, save, triage, inbox, status
- omega_telegram: configure check, allowlist, normalize, route, voice gating
- API endpoints: capture CRUD + Telegram webhook
- Dashboard: capture/telegram fields present
- Security: no hardcoded secrets
"""
from __future__ import annotations

import os
import json
from pathlib import Path

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── omega_capture — classify ──────────────────────────────────────────────────

def test_classify_capture_importable():
    from omega_capture import classify_capture  # noqa: F401


def test_classify_bug():
    from omega_capture import classify_capture
    assert classify_capture("Bug: dashboard crashes on refresh") == "bug"


def test_classify_research_request():
    from omega_capture import classify_capture
    assert classify_capture("Research NVDA earnings in detail") == "research_request"


def test_classify_reminder():
    from omega_capture import classify_capture
    assert classify_capture("Remind me to follow up on the TSLA trade") == "reminder"


def test_classify_content_idea():
    from omega_capture import classify_capture
    assert classify_capture("Post this on Twitter tomorrow") == "content_idea"


def test_classify_idea():
    from omega_capture import classify_capture
    assert classify_capture("Idea: what if we added a dark mode toggle?") == "idea"


def test_classify_task():
    from omega_capture import classify_capture
    assert classify_capture("Todo: implement the export button") == "task"


def test_classify_unknown():
    from omega_capture import classify_capture
    assert classify_capture("Hello world") == "unknown"


def test_classify_empty_string_returns_unknown():
    from omega_capture import classify_capture
    assert classify_capture("") == "unknown"


def test_classify_non_string_returns_unknown():
    from omega_capture import classify_capture
    assert classify_capture(None) == "unknown"  # type: ignore


# ── omega_capture — save / inbox / triage / status ────────────────────────────

def test_save_capture_returns_dict():
    from omega_capture import save_capture
    result = save_capture("Test capture — bug in login flow", source="test")
    assert isinstance(result, dict)


def test_save_capture_has_required_fields():
    from omega_capture import save_capture
    result = save_capture("Idea: add export button", source="test")
    for key in ("id", "saved_at", "source", "raw_text", "capture_type", "status"):
        assert key in result, f"save_capture result missing: {key}"


def test_save_capture_source_stored():
    from omega_capture import save_capture
    result = save_capture("Research BlackRock", source="telegram")
    assert result["source"] == "telegram"


def test_save_capture_status_is_inbox():
    from omega_capture import save_capture
    result = save_capture("Task: write tests", source="test")
    assert result["status"] == "inbox"


def test_save_capture_classification_correct():
    from omega_capture import save_capture
    result = save_capture("Todo: implement dark mode", source="test")
    assert result["capture_type"] == "task"


def test_save_capture_with_metadata():
    from omega_capture import save_capture
    meta = {"user_id": 12345, "message_id": 99}
    result = save_capture("Reminder: check positions", source="telegram", metadata=meta)
    assert result["metadata"]["user_id"] == 12345


def test_get_capture_inbox_returns_list():
    from omega_capture import get_capture_inbox
    inbox = get_capture_inbox(limit=5)
    assert isinstance(inbox, list)


def test_get_capture_inbox_newest_first():
    from omega_capture import save_capture, get_capture_inbox
    a = save_capture("First capture", source="test")
    b = save_capture("Second capture", source="test")
    inbox = get_capture_inbox(limit=10)
    ids = [c["id"] for c in inbox]
    # b should appear before a (newest first)
    assert ids.index(b["id"]) < ids.index(a["id"])


def test_triage_capture_returns_updated_record():
    from omega_capture import save_capture, triage_capture
    saved = save_capture("Bug: login fails", source="test")
    result = triage_capture(saved["id"])
    assert result["status"] == "triaged"
    assert result["triaged_at"] is not None


def test_triage_capture_unknown_id_returns_error():
    from omega_capture import triage_capture
    result = triage_capture("nonexistent-id-xyz")
    assert "error" in result


def test_get_capture_status_returns_dict():
    from omega_capture import get_capture_status
    status = get_capture_status()
    assert isinstance(status, dict)


def test_get_capture_status_has_required_fields():
    from omega_capture import get_capture_status
    status = get_capture_status()
    for key in ("total", "inbox_count", "triaged_count", "by_type", "by_source"):
        assert key in status, f"get_capture_status missing: {key}"


def test_get_capture_status_counts_are_ints():
    from omega_capture import get_capture_status
    status = get_capture_status()
    assert isinstance(status["inbox_count"], int)
    assert isinstance(status["triaged_count"], int)


# ── omega_telegram — configuration ───────────────────────────────────────────

def test_telegram_importable():
    import omega_telegram  # noqa: F401


def test_is_telegram_configured_false_when_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from omega_telegram import is_telegram_configured
    assert not is_telegram_configured()


def test_is_telegram_configured_false_with_placeholder(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
    from omega_telegram import is_telegram_configured
    assert not is_telegram_configured()


def test_is_telegram_configured_true_with_real_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ")
    from omega_telegram import is_telegram_configured
    assert is_telegram_configured()


# ── omega_telegram — allowlist ────────────────────────────────────────────────

def test_verify_allowed_user_false_when_no_allowlist(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    from omega_telegram import verify_allowed_user
    assert not verify_allowed_user(12345)


def test_verify_allowed_user_false_when_placeholder(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "YOUR_TELEGRAM_USER_ID")
    from omega_telegram import verify_allowed_user
    assert not verify_allowed_user(12345)


def test_verify_allowed_user_true_when_in_list(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345,67890")
    from omega_telegram import verify_allowed_user
    assert verify_allowed_user(12345)
    assert verify_allowed_user("67890")


def test_verify_allowed_user_false_when_not_in_list(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    from omega_telegram import verify_allowed_user
    assert not verify_allowed_user(99999)


# ── omega_telegram — normalize ────────────────────────────────────────────────

def _make_text_payload(user_id=12345, text="Hello"):
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": user_id, "username": "testuser", "first_name": "Test"},
            "chat": {"id": user_id},
            "text": text,
        }
    }


def _make_voice_payload(user_id=12345):
    return {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "from": {"id": user_id, "username": "testuser", "first_name": "Test"},
            "chat": {"id": user_id},
            "voice": {"file_id": "abc123", "duration": 5},
        }
    }


def test_normalize_text_message():
    from omega_telegram import normalize_telegram_message
    msg = normalize_telegram_message(_make_text_payload(text="Research NVDA"))
    assert msg["message_type"] == "text"
    assert msg["text"] == "Research NVDA"
    assert msg["user_id"] == 12345


def test_normalize_voice_message():
    from omega_telegram import normalize_telegram_message
    msg = normalize_telegram_message(_make_voice_payload())
    assert msg["message_type"] == "voice"
    assert msg["voice_file_id"] == "abc123"


def test_normalize_malformed_payload_does_not_crash():
    from omega_telegram import normalize_telegram_message
    result = normalize_telegram_message(None)
    assert "error" in result
    assert result["message_type"] == "invalid"


def test_normalize_empty_dict_does_not_crash():
    from omega_telegram import normalize_telegram_message
    result = normalize_telegram_message({})
    assert "error" in result


def test_normalize_no_from_field():
    from omega_telegram import normalize_telegram_message
    payload = {"update_id": 1, "message": {"text": "hi", "message_id": 1, "chat": {"id": 1}}}
    result = normalize_telegram_message(payload)
    assert result["user_id"] is None


# ── omega_telegram — process text ─────────────────────────────────────────────

def test_process_text_not_configured_returns_error(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from omega_telegram import process_telegram_text_message
    result = process_telegram_text_message(_make_text_payload())
    assert result["status"] == "error"
    assert "not_configured" in result["reason"]


def test_process_text_unauthorized_user_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "99999")
    from omega_telegram import process_telegram_text_message
    result = process_telegram_text_message(_make_text_payload(user_id=12345))
    assert result["status"] == "rejected"
    assert result["reason"] == "user_not_allowed"


def test_process_text_allowed_user_captured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    from omega_telegram import process_telegram_text_message
    result = process_telegram_text_message(_make_text_payload(text="Research BlackRock earnings"))
    assert result["status"] == "captured"
    assert "capture" in result
    assert result["capture"]["source"] == "telegram"


def test_process_text_malformed_payload_does_not_crash(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    from omega_telegram import process_telegram_text_message
    result = process_telegram_text_message("not a dict at all")
    assert result["status"] == "error"


# ── omega_telegram — voice gating ─────────────────────────────────────────────

def test_process_voice_not_configured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message(_make_voice_payload())
    assert result["status"] == "error"


def test_process_voice_disabled_returns_voice_not_enabled(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_ENABLED", "false")
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message(_make_voice_payload(user_id=12345))
    assert result["status"] == "voice_not_enabled"


def test_process_voice_enabled_no_key_returns_not_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message(_make_voice_payload(user_id=12345))
    assert result["status"] == "not_configured"


def test_process_voice_enabled_with_key_returns_stub(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-realkey123")
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message(_make_voice_payload(user_id=12345))
    assert result["status"] == "voice_not_implemented"


def test_process_voice_unauthorized_user_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "99999")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_ENABLED", "true")
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message(_make_voice_payload(user_id=12345))
    assert result["status"] == "rejected"


def test_process_voice_stub_never_raises():
    from omega_telegram import process_telegram_voice_stub
    result = process_telegram_voice_stub(None)
    assert result["status"] == "voice_not_implemented"


def test_process_voice_malformed_does_not_crash(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    from omega_telegram import process_telegram_voice_message
    result = process_telegram_voice_message({"bad": "payload"})
    assert isinstance(result, dict)
    assert "status" in result


# ── omega_telegram — get_telegram_status ─────────────────────────────────────

def test_get_telegram_status_returns_dict():
    from omega_telegram import get_telegram_status
    status = get_telegram_status()
    assert isinstance(status, dict)


def test_get_telegram_status_has_required_fields():
    from omega_telegram import get_telegram_status
    status = get_telegram_status()
    for key in ("configured", "status", "voice_enabled", "whisper_configured"):
        assert key in status, f"get_telegram_status missing: {key}"


def test_get_telegram_status_not_configured_when_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from omega_telegram import get_telegram_status
    status = get_telegram_status()
    assert status["status"] == "not_configured"
    assert not status["configured"]


# ── API endpoints ─────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api_server import app
    return TestClient(app)


def test_capture_status_endpoint(client):
    resp = client.get("/omega-os/capture/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "inbox_count" in data


def test_capture_inbox_endpoint(client):
    resp = client.get("/omega-os/capture/inbox")
    assert resp.status_code == 200
    data = resp.json()
    assert "captures" in data
    assert isinstance(data["captures"], list)


def test_capture_save_endpoint(client):
    resp = client.post("/omega-os/capture", json={"text": "Bug: test endpoint fails on edge case", "source": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "captured"
    assert "capture" in data


def test_capture_save_endpoint_missing_text(client):
    resp = client.post("/omega-os/capture", json={"source": "test"})
    assert resp.status_code == 400


def test_capture_triage_endpoint(client):
    # Save first
    saved = client.post("/omega-os/capture", json={"text": "Task: triage this", "source": "test"}).json()
    capture_id = saved["capture"]["id"]
    # Then triage
    resp = client.post(f"/omega-os/capture/{capture_id}/triage")
    assert resp.status_code == 200
    assert resp.json()["status"] == "triaged"


def test_capture_triage_unknown_id(client):
    resp = client.post("/omega-os/capture/nonexistent-id-xyz/triage")
    assert resp.status_code == 404


def test_telegram_status_endpoint(client):
    resp = client.get("/omega-os/telegram/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "status" in data


def test_telegram_webhook_not_configured(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    resp = client.post("/omega-os/telegram/webhook", json={"update_id": 1})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_telegram_webhook_rejects_unauthorized_user(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "99999")
    payload = _make_text_payload(user_id=12345, text="Research NVDA")
    resp = client.post("/omega-os/telegram/webhook", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert result["result"]["status"] == "rejected"


def test_telegram_webhook_captures_allowed_user(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    payload = _make_text_payload(user_id=12345, text="Research BlackRock for me")
    resp = client.post("/omega-os/telegram/webhook", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert result["ok"] is True
    assert result["result"]["status"] == "captured"


def test_telegram_webhook_malformed_payload_returns_200(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    # Malformed but sends valid JSON
    resp = client.post("/omega-os/telegram/webhook", json={"garbage": True})
    assert resp.status_code == 200


def test_telegram_webhook_voice_disabled(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:realtoken")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "12345")
    monkeypatch.setenv("VOICE_TRANSCRIPTION_ENABLED", "false")
    payload = _make_voice_payload(user_id=12345)
    resp = client.post("/omega-os/telegram/webhook", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert result["result"]["status"] == "voice_not_enabled"


# ── Dashboard fields ──────────────────────────────────────────────────────────

def test_dashboard_includes_capture_inbox_count(client):
    resp = client.get("/omega-os/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "capture_inbox_count" in data


def test_dashboard_includes_latest_captures(client):
    resp = client.get("/omega-os/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "latest_captures" in data
    assert isinstance(data["latest_captures"], list)


def test_dashboard_includes_telegram_status(client):
    resp = client.get("/omega-os/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "telegram_status" in data
    assert isinstance(data["telegram_status"], dict)


def test_dashboard_includes_voice_capture_status(client):
    resp = client.get("/omega-os/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "voice_capture_status" in data
    assert data["voice_capture_status"] in ("enabled", "disabled")


# ── Security ──────────────────────────────────────────────────────────────────

def test_no_hardcoded_secrets_in_omega_capture():
    source = (ROOT / "omega_capture.py").read_text(encoding="utf-8")
    for pattern in ("sk-", "Bearer ", "api_key =", "bot_token ="):
        assert pattern not in source, f"omega_capture.py must not contain: {pattern!r}"


def test_no_hardcoded_secrets_in_omega_telegram():
    import re
    source = (ROOT / "omega_telegram.py").read_text(encoding="utf-8")
    # Look for string literals that look like real secrets (long alphanumeric after sk-)
    # "startswith("sk-")" is allowed (key format check), "sk-abc123..." is not
    assert not re.search(r'"sk-[A-Za-z0-9]{10,}"', source), \
        "omega_telegram.py must not contain hardcoded OpenAI key literal"
    for pattern in ("Bearer ", "bot_token =", "api_key ="):
        assert pattern not in source, f"omega_telegram.py must not contain: {pattern!r}"


def test_telegram_module_has_no_hardcoded_user_ids():
    source = (ROOT / "omega_telegram.py").read_text(encoding="utf-8")
    # Should not have numeric IDs hardcoded (only reads from env)
    import re
    hardcoded_ids = re.findall(r'(?<!["\'])(?<!\w)\d{6,}(?!\w)(?!["\'])', source)
    assert not hardcoded_ids, f"omega_telegram.py has hardcoded numeric IDs: {hardcoded_ids}"
