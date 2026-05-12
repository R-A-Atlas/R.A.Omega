"""PowerPoint document agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_export.build_deck import write_query_envelope_pptx


def generate_powerpoint(envelope: dict[str, Any], dest: str | Path | None = None) -> Path:
    return write_query_envelope_pptx(envelope, Path(dest) if dest else None)
