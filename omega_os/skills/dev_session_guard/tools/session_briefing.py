"""
session_briefing.py — R.A. Omega session state brief.

Reads the live state of the project and prints a one-screen summary:
  - Current branch + last 3 commits
  - Health score (from health_scorer)
  - Next priority (from CLAUDE.md Section 9)
  - Active warnings (from upgrade_scanner critical items)

Run at the start of every Claude Code session.

Usage:
    python omega_os/skills/dev_session_guard/tools/session_briefing.py
"""
from __future__ import annotations

import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git"] + args, cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return ""


def _get_branch() -> str:
    return _git(["branch", "--show-current"]) or "unknown"


def _get_recent_commits(n: int = 3) -> list[str]:
    raw = _git(["log", f"--oneline", f"-{n}"])
    return raw.splitlines() if raw else []


def _get_health_score() -> tuple[int, str]:
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from health_scorer import score as hs_score
        result = hs_score()
        return result.overall, result.overall_rating
    except Exception as exc:
        return 0, f"unavailable ({exc})"


def _get_next_priority() -> str:
    """Extract PRIORITY BUILD LIST from CLAUDE.md — first non-done item."""
    claude_md = ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return "CLAUDE.md not found"
    text = claude_md.read_text(encoding="utf-8", errors="replace")
    # Find Section 9
    m = re.search(r"## 9\. PRIORITY BUILD LIST(.*?)(?=\n## \d+\.)", text, re.DOTALL)
    if not m:
        return "Section 9 not found in CLAUDE.md"
    section = m.group(1)
    # Find first non-DONE priority
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("### PRIORITY") and "DONE" not in stripped:
            return stripped.replace("### ", "")
    # All priorities done — find the last one
    priorities = [l.strip() for l in section.splitlines() if l.strip().startswith("### PRIORITY")]
    return priorities[-1] if priorities else "All priorities complete"


def _get_test_count() -> int:
    """Fast count of test functions without running pytest."""
    count = 0
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return 0
    for f in tests_dir.glob("test_*.py"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            count += len(re.findall(r"^def test_", text, re.MULTILINE))
        except Exception:
            pass
    return count


def _get_critical_upgrade_items() -> list[str]:
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from upgrade_scanner import run_scan, Severity
        results = run_scan(critical_only=True)
        return [f"{r.file}:{r.line} {r.message[:60]}" for r in results[:5]]
    except Exception:
        return []


def _get_modified_files() -> list[str]:
    raw = _git(["status", "--short"])
    return [l.strip() for l in raw.splitlines() if l.strip()][:8]


def brief() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    branch = _get_branch()
    commits = _get_recent_commits(3)
    health_score, health_rating = _get_health_score()
    next_priority = _get_next_priority()
    test_count = _get_test_count()
    modified = _get_modified_files()

    lines: list[str] = []
    sep = "=" * 64

    lines.append(sep)
    lines.append("  R.A. OMEGA — SESSION BRIEF")
    lines.append(f"  {now}")
    lines.append(sep)
    lines.append("")

    # Branch
    lines.append(f"  Branch    {branch}")
    lines.append(f"  Tests     {test_count} functions detected")
    hs_int = int(health_score) if health_score else 0
    score_bar = "[" + "#" * (hs_int // 10) + "." * (10 - hs_int // 10) + "]"
    lines.append(f"  Health    {health_score}/100 {score_bar} {health_rating}")
    lines.append("")

    # Recent commits
    lines.append("  Recent commits:")
    for c in commits:
        lines.append(f"    {c}")
    lines.append("")

    # Modified files
    if modified:
        lines.append("  Uncommitted changes:")
        for f in modified:
            lines.append(f"    {f}")
        lines.append("")

    # Next priority
    lines.append("  Next priority:")
    lines.append(f"    {next_priority}")
    lines.append("")

    lines.append(sep)
    lines.append("  Run:  python omega_os/skills/dev_session_guard/tools/run_preflight.py")
    lines.append("  Docs: CLAUDE.md Section 9 for full priority list")
    lines.append(sep)

    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(brief())


if __name__ == "__main__":
    main()
