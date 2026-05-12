"""Comparison report document agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .html_print_agent import generate_html


def generate_comparison(envelope: dict[str, Any], dest: str | Path | None = None) -> Path:
    return generate_html(envelope, Path(dest) if dest else None)
