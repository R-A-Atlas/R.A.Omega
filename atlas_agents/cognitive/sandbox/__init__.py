"""Execution sandbox validator."""

from __future__ import annotations

import ast
from typing import Any


def validate_python(source: str) -> dict[str, Any]:
    try:
        ast.parse(source)
        return {"status": "APPROVED", "error": None}
    except SyntaxError as exc:
        return {"status": "REJECTED", "error": f"{exc.msg} at line {exc.lineno}"}
