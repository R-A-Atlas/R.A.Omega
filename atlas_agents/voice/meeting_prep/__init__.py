"""Meeting prep report generator."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def build_meeting_prep(meeting: dict[str, Any]) -> str:
    title = html.escape(str(meeting.get("title") or "Meeting Prep"))
    attendees = ", ".join(html.escape(str(a)) for a in meeting.get("attendees", []))
    agenda = "".join(f"<li>{html.escape(str(x))}</li>" for x in meeting.get("agenda", []))
    return f"<html><body><h1>{title}</h1><p>{attendees}</p><ul>{agenda}</ul></body></html>"


def write_meeting_prep(meeting: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"meeting_prep_{stamp}.html"
    out.write_text(build_meeting_prep(meeting), encoding="utf-8")
    return out
