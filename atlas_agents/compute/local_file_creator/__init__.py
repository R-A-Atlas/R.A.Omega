"""Local file creator."""

from __future__ import annotations

from pathlib import Path


def create_text_file(path: str | Path, content: str, *, overwrite: bool = False) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(str(target))
    target.write_text(content, encoding="utf-8")
    return target
