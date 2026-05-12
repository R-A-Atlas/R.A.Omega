"""Codebase mapper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def build_repo_map(root: str | Path = REPO_ROOT) -> dict[str, Any]:
    base = Path(root)
    files = [str(p.relative_to(base)).replace("\\", "/") for p in base.rglob("*.py") if ".git" not in p.parts and "__pycache__" not in p.parts]
    return {"root": str(base), "python_file_count": len(files), "sample_files": files[:200]}


def write_repo_map(root: str | Path = REPO_ROOT) -> Path:
    out = REPO_ROOT / "atlas_agents" / "cognitive" / "codebase_mapper" / "repo_map.json"
    out.write_text(json.dumps(build_repo_map(root), indent=2) + "\n", encoding="utf-8")
    return out
