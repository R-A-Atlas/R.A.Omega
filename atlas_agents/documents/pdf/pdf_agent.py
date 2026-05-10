"""DOC2 PDF Report Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_export.pdf_render import write_query_envelope_pdf


def generate_pdf(payload: dict[str, Any], dest: Path | None = None) -> Path:
    """Generate a formatted PDF report from an Omega/query JSON payload."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty JSON object")
    return write_query_envelope_pdf(payload, dest)


__all__ = ["generate_pdf"]
