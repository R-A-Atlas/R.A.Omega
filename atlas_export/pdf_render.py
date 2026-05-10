"""POST /query-shaped envelope → PDF via WeasyPrint (see tools/atlas_pdf_weasyprint)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def _slug_ticker(envelope: dict[str, Any]) -> str:
    from tools.atlas_pdf_weasyprint import _ticker

    raw = _ticker(envelope)
    s = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw).strip("_")[:42]
    return s or "report"


def write_query_envelope_pdf(
    envelope: dict[str, Any],
    dest: Path | None = None,
) -> Path:
    """Render envelope to PDF; returns written path."""
    from tools.atlas_pdf_weasyprint import build_html

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tick_slug = _slug_ticker(envelope)
    target = dest or (REPORTS_DIR / f"{tick_slug}_{date.today().strftime('%Y-%m-%d')}.pdf")
    html_src = build_html(envelope)
    try:
        from weasyprint import HTML

        HTML(string=html_src, base_url=str(ROOT.absolute())).write_pdf(str(target.resolve()))
    except Exception:
        _write_basic_pdf(envelope, target)
    return target


def _pdf_text_escape(s: Any) -> str:
    return str(s if s is not None else "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_line(text: str, width: int = 92) -> list[str]:
    words = str(text or "").replace("\r", "").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if len(nxt) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines or [""]


def _pdf_lines(envelope: dict[str, Any]) -> list[str]:
    fr = envelope.get("final_report") if isinstance(envelope.get("final_report"), dict) else {}
    lines = [
        "ATLAS OMEGA REPORT",
        f"Query: {envelope.get('query') or ''}",
        f"Ticker: {_slug_ticker(envelope)}",
        "",
        "TLDR",
    ]
    lines.extend(_wrap_line(envelope.get("tldr") or fr.get("tldr") or fr.get("primary_recommendation") or ""))
    for label, value in (
        ("Executive Summary", fr.get("executive_summary") or fr.get("executive_brief") or ""),
        ("Trader Memo", envelope.get("trader_memo") or fr.get("trader_memo") or ""),
        ("Hedge Fund Brief", envelope.get("hedge_fund_brief") or fr.get("hedge_fund_brief") or ""),
    ):
        if value:
            lines.extend(["", label])
            lines.extend(_wrap_line(str(value)))
    scenarios = envelope.get("scenarios") if isinstance(envelope.get("scenarios"), list) else []
    if scenarios:
        lines.extend(["", "Scenarios"])
        for sc in scenarios[:8]:
            lines.extend(_wrap_line(sc if isinstance(sc, str) else repr(sc), 100))
    return lines[:260]


def _write_basic_pdf(envelope: dict[str, Any], target: Path) -> None:
    """Small PDF fallback for systems without WeasyPrint native libraries."""
    lines = _pdf_lines(envelope)
    pages = [lines[i : i + 42] for i in range(0, len(lines), 42)] or [["ATLAS OMEGA REPORT"]]
    objects: list[bytes] = []

    def add(obj: str | bytes) -> int:
        objects.append(obj.encode("latin-1", "replace") if isinstance(obj, str) else obj)
        return len(objects)

    page_ids: list[int] = []
    content_ids: list[int] = []
    font_id = 0
    pages_id = 0
    catalog_id = add("<< /Type /Catalog /Pages 0 0 R >>")
    pages_id = add("<< /Type /Pages /Kids [] /Count 0 >>")
    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for page in pages:
        y = 760
        content_lines = ["BT", "/F1 10 Tf", "36 760 Td"]
        for idx, line in enumerate(page):
            if idx:
                content_lines.append("0 -16 Td")
            content_lines.append(f"({_pdf_text_escape(line)}) Tj")
            y -= 16
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", "replace")
        content_id = add(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)
        content_ids.append(content_id)
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>"
    ).encode("latin-1")
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("latin-1")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    target.write_bytes(bytes(out))


__all__ = ["write_query_envelope_pdf", "REPORTS_DIR", "_slug_ticker"]
