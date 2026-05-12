"""Conversational memory extraction for finance preferences."""

from __future__ import annotations

from typing import Any


def extract_preferences(messages: list[dict[str, Any]]) -> dict[str, Any]:
    joined = " ".join(str(m.get("content", "")) for m in messages).lower()
    risk = "aggressive" if any(w in joined for w in ("options", "leverage", "growth")) else "balanced"
    horizon = "short_term" if any(w in joined for w in ("today", "swing", "day trade")) else "long_term"
    return {
        "risk_profile": risk,
        "time_horizon": horizon,
        "preferred_style": "concise",
        "finance_focus": any(w in joined for w in ("stock", "debt", "tax", "real estate", "crypto")),
    }


def update_memory(existing: dict[str, Any] | None, messages: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(existing or {})
    out.update(extract_preferences(messages))
    out["message_count"] = len(messages)
    return out
