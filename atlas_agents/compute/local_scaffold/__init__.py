"""Local scaffold helper."""

from __future__ import annotations

from pathlib import Path


def scaffold_package(root: str | Path, name: str) -> list[Path]:
    base = Path(root) / name
    base.mkdir(parents=True, exist_ok=True)
    init = base / "__init__.py"
    prompt = base / "AGENT_PROMPT.md"
    if not init.exists():
        init.write_text('"""Generated package."""\n', encoding="utf-8")
    if not prompt.exists():
        prompt.write_text(f"# {name}\n", encoding="utf-8")
    return [init, prompt]
