"""Discord bot message formatter."""

from __future__ import annotations

from typing import Any


def format_discord_message(alert: dict[str, Any]) -> dict[str, Any]:
    title = str(alert.get("title") or "R.A. Omega Alert")
    summary = str(alert.get("summary") or alert.get("message") or "")
    return {"content": f"**{title}**\n{summary}"[:1900], "allowed_mentions": {"parse": []}}
