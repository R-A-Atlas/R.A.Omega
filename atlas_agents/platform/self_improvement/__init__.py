"""Self-improvement note writer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTES_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Notes"


def write_improvement_note(title: str, body: str) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = NOTES_DIR / f"improvement_{stamp}.md"
    out.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return out
