"""Architecture planner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTES_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Notes"


def make_plan(goal: str, steps: list[str]) -> str:
    return "# Architecture Plan\n\nGoal: " + goal + "\n\n" + "\n".join(f"- {s}" for s in steps) + "\n"


def write_plan(goal: str, steps: list[str]) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = NOTES_DIR / f"plan_{stamp}.md"
    out.write_text(make_plan(goal, steps), encoding="utf-8")
    return out
