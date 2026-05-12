"""Eval scorer helper."""

from __future__ import annotations

from typing import Any


def score_eval(results: list[dict[str, Any]]) -> dict[str, float | int]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {"total": total, "passed": passed, "score": round(passed / total, 3) if total else 0.0}
