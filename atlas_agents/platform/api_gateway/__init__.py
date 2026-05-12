"""API gateway request normalizer."""

from __future__ import annotations

from typing import Any


def normalize_query_request(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or payload.get("message") or "").strip()
    return {
        "query": query,
        "research_mode": payload.get("research_mode", "normal"),
        "web_search": bool(payload.get("web_search", False)),
        "session_id": payload.get("session_id"),
    }
