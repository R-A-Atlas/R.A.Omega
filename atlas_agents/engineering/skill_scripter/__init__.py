"""Skill scripter utility."""

from __future__ import annotations

from pathlib import Path


def write_skill(path: str | Path, name: str, description: str) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    out = target / "SKILL.md"
    out.write_text(f"# {name}\n\n{description}\n", encoding="utf-8")
    return out
