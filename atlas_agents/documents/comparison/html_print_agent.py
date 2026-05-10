"""Printable HTML report agent for Omega/query JSON payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_export.html_report import write_query_envelope_html


def generate_html(payload: dict[str, Any], dest: Path | None = None) -> Path:
    """Generate a standalone printable HTML report."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty JSON object")
    return write_query_envelope_html(payload, dest)


__all__ = ["generate_html"]
