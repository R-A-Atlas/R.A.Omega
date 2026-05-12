"""Alert voice notifier payload builder."""

from __future__ import annotations

from typing import Any


def build_call_script(alert: dict[str, Any]) -> str:
    title = str(alert.get("title") or "R.A. Omega alert")
    summary = str(alert.get("summary") or alert.get("message") or "A watched condition changed.")
    return f"{title}. {summary}"


def build_twilio_payload(to_number: str, alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "to": to_number,
        "script": build_call_script(alert),
        "status": "QUEUED",
        "provider": "twilio",
    }
