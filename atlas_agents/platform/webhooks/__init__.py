"""Webhook publisher payload builder."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_webhook_payload(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": event,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": data,
        "source": "ra_omega",
    }
