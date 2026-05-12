"""Local documentation writer."""

from __future__ import annotations

from pathlib import Path


def write_readme(path: str | Path, title: str, body: str) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    out = target / "README.md"
    out.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return out
