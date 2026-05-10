"""DOC4 Excel Model Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import date
import re

from atlas_export.build_workbook import _tick, write_query_envelope_xlsx
from atlas_export.pdf_render import REPORTS_DIR


def generate_excel(payload: dict[str, Any], dest: Path | None = None) -> Path:
    """Generate an XLSX workbook from an Omega/query JSON payload."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload must be a non-empty JSON object")
    if dest is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        tk = re.sub(r"[^\w\-]+", "_", _tick(payload))[:32] or "ATLAS"
        dest = REPORTS_DIR / f"{tk}_{date.today().strftime('%Y-%m-%d')}.xlsx"
    return write_query_envelope_xlsx(payload, dest)


__all__ = ["generate_excel"]
