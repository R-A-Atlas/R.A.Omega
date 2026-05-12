"""Content repurposer for social and blog outlines."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Content"


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repurpose(source: str) -> dict[str, Any]:
    thread = [
        "Finance AI is shifting from chat-only answers to verified workflows.",
        "The key product gap is not more text. It is better routing.",
        "Normal questions should stay fast and conversational.",
        "Deep research should activate only when the user asks for depth.",
        "The best finance agents combine data feeds, memory, and guardrails.",
        "Every report should show source quality and confidence.",
        "Automation matters, but paper testing comes before live money.",
        "The winning UI feels simple while the system underneath is rigorous.",
    ]
    outline = [
        "Why finance chat needs workflow routing",
        "Normal chat vs deep research",
        "Data validation and source confidence",
        "Agent memory and personalization",
        "Paper trading before live execution",
    ]
    return {
        "generated_at": iso_now_z(),
        "title": "Finance-first AI agents need verified workflows",
        "date": "2026-05-11",
        "source": source,
        "twitter_thread": thread,
        "blog_outline": outline,
    }


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "content_repurpose_latest.json"
    import json
    out.write_text(json.dumps(payload or repurpose("manual"), indent=2) + "\n", encoding="utf-8")
    return out
