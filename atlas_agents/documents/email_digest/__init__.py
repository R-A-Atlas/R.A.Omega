"""Email digest document agent."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def build_digest(items: list[dict[str, Any]]) -> str:
    rows = "\n".join(f"- {i.get('title', 'Update')}: {i.get('summary', '')}" for i in items)
    return f"R.A. Omega Daily Digest\nGenerated: {datetime.now(timezone.utc).isoformat()}\n\n{rows}\n"


def write_digest(items: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "email_digest_latest.txt"
    out.write_text(build_digest(items), encoding="utf-8")
    return out
