"""Build lightweight text artifacts from POST /query-shaped analysis JSON."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def _txt(value: Any, limit: int = 12000) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            value = json.dumps(value, indent=2, default=str)
        except (TypeError, ValueError):
            value = str(value)
    return str(value).strip()[:limit]


def _slug(envelope: dict[str, Any]) -> str:
    raw = envelope.get("query") or "ra_omega_report"
    slug = re.sub(r"[^\w\-]+", "_", str(raw).strip())[:48].strip("_")
    return slug or "ra_omega_report"


def _sections(envelope: dict[str, Any]) -> list[tuple[str, Any]]:
    fr = envelope.get("final_report") if isinstance(envelope.get("final_report"), dict) else {}
    return [
        ("Request", envelope.get("query")),
        ("Bottom Line", envelope.get("tldr") or fr.get("tldr") or fr.get("bottom_line")),
        ("Executive Summary", fr.get("executive_summary") or fr.get("executive_brief")),
        ("Overview", fr.get("company_overview") or fr.get("overview") or fr.get("situation_analysis")),
        ("Key Insight", fr.get("key_insight")),
        ("Recommendation", fr.get("primary_recommendation")),
        ("Scenarios", envelope.get("scenarios") or fr.get("scenarios")),
        ("Risks", fr.get("key_risks") or fr.get("risks_and_tripwires")),
        ("Action Plan", fr.get("action_plan") or envelope.get("execution_rules")),
        ("Sources", fr.get("named_resources") or fr.get("sources") or fr.get("data_notes")),
    ]


def write_query_envelope_text(
    envelope: dict[str, Any],
    dest: Path | None = None,
    *,
    fmt: str = "txt",
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fmt = (fmt or "txt").lower().lstrip(".")
    if fmt not in {"txt", "md"}:
        raise ValueError("fmt must be txt or md")
    target = dest or (REPORTS_DIR / f"{_slug(envelope)}_{date.today().strftime('%Y-%m-%d')}.{fmt}")

    lines: list[str] = []
    title = "R.A. Omega Intelligence Report"
    lines.append(f"# {title}" if fmt == "md" else title)
    lines.append("")
    lines.append(f"Generated: {date.today().isoformat()}")
    lines.append("")
    for heading, value in _sections(envelope):
        text = _txt(value)
        if not text:
            continue
        lines.append(f"## {heading}" if fmt == "md" else heading.upper())
        lines.append(text)
        lines.append("")
    lines.append(
        "R.A. Omega synthesizes available data for research purposes. This is not personalized investment advice."
    )
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


def write_query_envelope_csv(
    envelope: dict[str, Any],
    dest: Path | None = None,
) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = dest or (REPORTS_DIR / f"{_slug(envelope)}_{date.today().strftime('%Y-%m-%d')}.csv")
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["section", "content"])
        for heading, value in _sections(envelope):
            text = _txt(value, 30000)
            if text:
                writer.writerow([heading, text])
    return target
