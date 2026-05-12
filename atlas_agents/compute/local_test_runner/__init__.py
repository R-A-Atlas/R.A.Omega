"""Local test runner command builder."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def build_pytest_command(paths: list[str] | None = None) -> list[str]:
    return ["python", "-m", "pytest", *(paths or ["tests/"]), "-q"]


def write_test_result(result: dict[str, Any]) -> Path:
    out = REPO_ROOT / f"test_results_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return out
