"""
run_daily_build_brief.py — Safe stub for the daily_build_brief worker.

Reads DONE files and git state from the project root, then produces a
structured daily engineering brief as a Markdown string.

No external APIs. No API keys. No broker actions. No email sends.
Output is returned as a string and optionally written to atlas_vault/03-Outputs/.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"


@dataclass
class DailyBriefResult:
    success: bool
    report: str = ""
    done_files: list[str] = field(default_factory=list)
    git_summary: str = ""
    error: str = ""


def _collect_done_files() -> list[str]:
    return sorted(p.name for p in ROOT.glob("*_DONE.md"))


def _git_summary() -> str:
    try:
        log = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--oneline", "-10"],
            capture_output=True, text=True, timeout=10,
        )
        return log.stdout.strip() if log.returncode == 0 else "(git log unavailable)"
    except Exception as exc:
        return f"(git error: {exc})"


def _git_status() -> str:
    try:
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--short"],
            capture_output=True, text=True, timeout=10,
        )
        return status.stdout.strip() if status.returncode == 0 else "(git status unavailable)"
    except Exception as exc:
        return f"(git status error: {exc})"


def run(write_output: bool = False) -> DailyBriefResult:
    """
    Produce a daily engineering brief.

    Args:
        write_output: If True, writes brief to atlas_vault/03-Outputs/daily_build_brief.md.

    Returns:
        DailyBriefResult with .success, .brief, .done_files, .git_summary.
    """
    try:
        done_files = _collect_done_files()
        git_log = _git_summary()
        git_status = _git_status()

        lines = [
            "# Daily Build Brief",
            "",
            "## Completed Phases",
            "",
        ]
        if done_files:
            for f in done_files:
                lines.append(f"- {f}")
        else:
            lines.append("- (none found)")

        lines += [
            "",
            "## Recent Git Log (last 10)",
            "",
            "```",
            git_log,
            "```",
            "",
            "## Git Status (uncommitted changes)",
            "",
            "```",
            git_status if git_status else "(clean)",
            "```",
        ]

        brief = "\n".join(lines)

        if write_output:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUTS_DIR / "daily_build_brief.md"
            out_path.write_text(brief, encoding="utf-8")

        return DailyBriefResult(
            success=True,
            report=brief,
            done_files=done_files,
            git_summary=git_log,
        )

    except Exception as exc:
        return DailyBriefResult(success=False, error=str(exc))


if __name__ == "__main__":
    result = run(write_output=True)
    if result.success:
        print(result.report)
    else:
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
