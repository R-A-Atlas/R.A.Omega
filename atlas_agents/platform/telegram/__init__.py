"""Telegram alert formatter."""

from __future__ import annotations

from typing import Any


def format_telegram_message(alert: dict[str, Any]) -> str:
    title = str(alert.get("title") or "R.A. Omega Alert")
    summary = str(alert.get("summary") or alert.get("message") or "")
    return f"{title}\n\n{summary}"[:3900]
