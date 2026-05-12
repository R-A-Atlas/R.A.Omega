"""API integration helper."""

from __future__ import annotations

from typing import Any


def build_endpoint_spec(method: str, path: str, request_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"method": method.upper(), "path": path, "request_schema": request_schema or {}, "auth_required": True}
