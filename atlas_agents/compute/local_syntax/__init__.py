"""Local syntax checker."""

from __future__ import annotations

import py_compile
from pathlib import Path
from typing import Any


def check_python_file(path: str | Path) -> dict[str, Any]:
    try:
        py_compile.compile(str(path), doraise=True)
        return {"path": str(path), "status": "CLEAN", "errors": []}
    except py_compile.PyCompileError as exc:
        return {"path": str(path), "status": "ERROR", "errors": [str(exc)]}
