"""Dependency watcher helper."""

from __future__ import annotations

from pathlib import Path


def parse_requirements(path: str | Path) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
