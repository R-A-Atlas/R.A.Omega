"""Build standalone printable HTML reports from POST /query-shaped JSON."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from tools.atlas_pdf_weasyprint import build_html

from atlas_export.pdf_render import REPORTS_DIR, _slug_ticker


def write_query_envelope_html(
    envelope: dict[str, Any],
    dest: Path | None = None,
) -> Path:
    """Render envelope to standalone HTML under atlas_vault/03-Outputs/Reports."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tick_slug = _slug_ticker(envelope)
    target = dest or (REPORTS_DIR / f"{tick_slug}_{date.today().strftime('%Y-%m-%d')}.html")
    target.write_text(build_html(envelope), encoding="utf-8")
    return target


__all__ = ["write_query_envelope_html"]
