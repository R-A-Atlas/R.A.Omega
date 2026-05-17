"""General artifact planning and export dispatch for R.A. Omega."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_export.build_text import REPORTS_DIR, _sections, _slug


@dataclass(frozen=True)
class ArtifactPlan:
    requested_format: str
    canonical_format: str
    endpoint: str
    media_type: str
    label: str


_ALIASES: dict[str, str] = {
    "word": "docx",
    "doc": "docx",
    "docx": "docx",
    "pdf": "pdf",
    "ppt": "pptx",
    "pptx": "pptx",
    "powerpoint": "pptx",
    "slides": "pptx",
    "deck": "pptx",
    "presentation": "pptx",
    "xls": "xlsx",
    "xlsx": "xlsx",
    "excel": "xlsx",
    "spreadsheet": "xlsx",
    "workbook": "xlsx",
    "csv": "csv",
    "markdown": "md",
    "md": "md",
    "txt": "txt",
    "text": "txt",
    "html": "html",
    "json": "json",
    "xml": "xml",
    "yaml": "yaml",
    "yml": "yaml",
}

_FORMAT_META: dict[str, tuple[str, str, str]] = {
    "docx": ("/export/docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Download Word"),
    "pdf": ("/export/pdf", "application/pdf", "Download PDF"),
    "pptx": ("/export/pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "Download Slides"),
    "xlsx": ("/export/xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Download Excel"),
    "csv": ("/export/csv", "text/csv; charset=utf-8", "Download CSV"),
    "md": ("/export/md", "text/markdown; charset=utf-8", "Download Markdown"),
    "txt": ("/export/txt", "text/plain; charset=utf-8", "Download Text"),
    "html": ("/export/html", "text/html; charset=utf-8", "Download HTML"),
    "json": ("/export/json", "application/json", "Download JSON"),
    "xml": ("/export/xml", "application/xml; charset=utf-8", "Download XML"),
    "yaml": ("/export/yaml", "application/x-yaml; charset=utf-8", "Download YAML"),
}

_EXTENSION_RE = re.compile(r"\.([A-Za-z0-9]{1,8})\b")
_ARTIFACT_INTENT_RE = re.compile(
    r"\b(?:make|create|generate|write|build|draft|export|download|save|turn|convert|give)\b"
    r".{0,100}\b(?:file|report|document|artifact|spreadsheet|workbook|deck|presentation|slides?|memo|brief|template|table)\b",
    re.I | re.S,
)


def normalize_artifact_format(value: str | None) -> str | None:
    if not value:
        return None
    fmt = str(value).strip().lower().lstrip(".")
    return _ALIASES.get(fmt, fmt if fmt in _FORMAT_META else None)


def detect_artifact_format(raw_query: str) -> str | None:
    q = raw_query or ""
    for match in _EXTENSION_RE.finditer(q):
        fmt = normalize_artifact_format(match.group(1))
        if fmt:
            return fmt
    ql = q.lower()
    ordered_aliases = sorted(_ALIASES, key=len, reverse=True)
    for alias in ordered_aliases:
        if re.search(rf"\b{re.escape(alias)}\b", ql):
            return _ALIASES[alias]
    if _ARTIFACT_INTENT_RE.search(q):
        return "docx"
    return None


def user_requested_artifact(raw_query: str) -> bool:
    return detect_artifact_format(raw_query) is not None or bool(_ARTIFACT_INTENT_RE.search(raw_query or ""))


def plan_artifact(raw_query: str = "", requested_format: str | None = None) -> ArtifactPlan:
    canonical = normalize_artifact_format(requested_format) or detect_artifact_format(raw_query) or "docx"
    endpoint, media_type, label = _FORMAT_META[canonical]
    return ArtifactPlan(
        requested_format=requested_format or canonical,
        canonical_format=canonical,
        endpoint=endpoint,
        media_type=media_type,
        label=label,
    )


def write_query_envelope_json(envelope: dict[str, Any], dest: Path | None = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = dest or (REPORTS_DIR / f"{_slug(envelope)}.json")
    target.write_text(json.dumps(envelope, indent=2, default=str), encoding="utf-8")
    return target


def write_query_envelope_xml(envelope: dict[str, Any], dest: Path | None = None) -> Path:
    import xml.etree.ElementTree as ET

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = dest or (REPORTS_DIR / f"{_slug(envelope)}.xml")
    root = ET.Element("ra_omega_report")
    for heading, value in _sections(envelope):
        node = ET.SubElement(root, re.sub(r"[^a-zA-Z0-9_]+", "_", heading.lower()).strip("_") or "section")
        node.text = value if isinstance(value, str) else json.dumps(value, default=str)
    tree = ET.ElementTree(root)
    tree.write(target, encoding="utf-8", xml_declaration=True)
    return target


def write_query_envelope_yaml(envelope: dict[str, Any], dest: Path | None = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = dest or (REPORTS_DIR / f"{_slug(envelope)}.yaml")
    lines = ["ra_omega_report:"]
    for heading, value in _sections(envelope):
        key = re.sub(r"[^a-zA-Z0-9_]+", "_", heading.lower()).strip("_") or "section"
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        safe = str(text).replace("\r\n", "\n").replace("\r", "\n")
        lines.append(f"  {key}: |")
        lines.extend(f"    {line}" for line in safe.split("\n"))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def export_artifact(envelope: dict[str, Any], requested_format: str | None = None) -> tuple[Path, ArtifactPlan]:
    plan = plan_artifact(str(envelope.get("query") or ""), requested_format or envelope.get("_requested_doc_type"))
    fmt = plan.canonical_format
    if fmt == "docx":
        from atlas_export.build_docx import write_query_envelope_docx
        return write_query_envelope_docx(envelope), plan
    if fmt == "pdf":
        from atlas_agents.documents.pdf.pdf_agent import generate_pdf
        return generate_pdf(envelope), plan
    if fmt == "pptx":
        from atlas_export.build_deck import write_query_envelope_pptx
        return write_query_envelope_pptx(envelope), plan
    if fmt == "xlsx":
        from atlas_agents.documents.excel.excel_agent import generate_excel
        return generate_excel(envelope), plan
    if fmt == "csv":
        from atlas_export.build_text import write_query_envelope_csv
        return write_query_envelope_csv(envelope), plan
    if fmt in {"md", "txt"}:
        from atlas_export.build_text import write_query_envelope_text
        return write_query_envelope_text(envelope, fmt=fmt), plan
    if fmt == "html":
        from atlas_agents.documents.comparison.html_print_agent import generate_html
        return generate_html(envelope), plan
    if fmt == "json":
        return write_query_envelope_json(envelope), plan
    if fmt == "xml":
        return write_query_envelope_xml(envelope), plan
    if fmt == "yaml":
        return write_query_envelope_yaml(envelope), plan
    raise ValueError(f"Unsupported artifact format: {fmt}")
