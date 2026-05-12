"""Data validator helper."""

from __future__ import annotations

from typing import Any


def validate_required_fields(payload: dict[str, Any], fields: list[str]) -> dict[str, object]:
    missing = [f for f in fields if f not in payload]
    return {"status": "PASS" if not missing else "FAIL", "missing": missing}
