"""Reflection correction engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTES_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Notes"


def build_correction(issue: str, correction: str) -> str:
    return f"# Correction\n\nIssue: {issue}\n\nCorrection: {correction}\n"


def write_correction(issue: str, correction: str) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = NOTES_DIR / f"corrections_{stamp}.md"
    out.write_text(build_correction(issue, correction), encoding="utf-8")
    return out
