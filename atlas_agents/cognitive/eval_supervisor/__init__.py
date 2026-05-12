"""Evals benchmarking supervisor."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTES_DIR = REPO_ROOT / "atlas_vault" / "04-Projects" / "ATLAS" / "Notes"


def summarize_eval(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {"total": total, "passed": passed, "pass_rate": round(passed / total, 3) if total else 0}


def write_eval_summary(results: list[dict[str, Any]]) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    summary = summarize_eval(results)
    out = NOTES_DIR / f"nightly_eval_{stamp}.md"
    out.write_text(f"# Nightly Eval\n\n{summary}\n", encoding="utf-8")
    return out
