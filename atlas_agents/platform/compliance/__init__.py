"""Compliance archive agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Compliance"


def archive_event(event: dict[str, Any]) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = ARCHIVE_DIR / f"compliance_{stamp}.json"
    out.write_text(json.dumps({"archived_at": stamp, **event}, indent=2) + "\n", encoding="utf-8")
    return out
