"""
run_supabase_health.py — Safe stub for the supabase_health_agent worker.

Checks local DB presence, health endpoint reachability (if server is up),
and persistence file integrity. No external APIs called directly.
Output is returned as a string and optionally written to atlas_vault/03-Outputs/.

No broker actions. No email sends. No schema mutations.
"""
from __future__ import annotations

import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"

_LOCAL_SERVER = "http://127.0.0.1:8000"

_REQUIRED_LOCAL_FILES = [
    "atlas_memory.db",
    "atlas_tracker.db",
]

_OPTIONAL_LOCAL_FILES = [
    "positions_cache.json",
    "paper_trades.json",
]


@dataclass
class HealthCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class SupabaseHealthResult:
    success: bool
    report: str = ""
    checks: list[HealthCheck] = field(default_factory=list)
    error: str = ""


def _check_local_file(fname: str, required: bool) -> HealthCheck:
    path = ROOT / fname
    exists = path.exists()
    label = "REQUIRED" if required else "OPTIONAL"
    if exists:
        size_kb = path.stat().st_size / 1024
        return HealthCheck(
            name=f"{label}: {fname}",
            passed=True,
            detail=f"Present ({size_kb:.1f} KB)",
        )
    else:
        return HealthCheck(
            name=f"{label}: {fname}",
            passed=not required,
            detail="Missing" if required else "Not present (optional)",
        )


def _check_health_endpoint() -> HealthCheck:
    try:
        req = urllib.request.urlopen(f"{_LOCAL_SERVER}/health", timeout=3)
        body = req.read(512).decode("utf-8", errors="replace")
        return HealthCheck(
            name="GET /health endpoint",
            passed=True,
            detail=f"HTTP {req.status} — {body[:120]}",
        )
    except urllib.error.URLError as exc:
        return HealthCheck(
            name="GET /health endpoint",
            passed=False,
            detail=f"Server not reachable: {exc.reason}",
        )
    except Exception as exc:
        return HealthCheck(
            name="GET /health endpoint",
            passed=False,
            detail=f"Error: {exc}",
        )


def run(write_output: bool = False) -> SupabaseHealthResult:
    """
    Run persistence and health checks.

    Args:
        write_output: If True, writes report to atlas_vault/03-Outputs/supabase_health.md.

    Returns:
        SupabaseHealthResult with .success, .report, .checks.
    """
    try:
        checks: list[HealthCheck] = []

        for fname in _REQUIRED_LOCAL_FILES:
            checks.append(_check_local_file(fname, required=True))

        for fname in _OPTIONAL_LOCAL_FILES:
            checks.append(_check_local_file(fname, required=False))

        checks.append(_check_health_endpoint())

        passed_count = sum(1 for c in checks if c.passed)
        total = len(checks)

        lines = [
            "# Supabase / Persistence Health Report",
            "",
            f"**Result: {passed_count}/{total} checks passed**",
            "",
            "## Checks",
            "",
        ]
        for c in checks:
            icon = "✓" if c.passed else "✗"
            lines.append(f"- [{icon}] **{c.name}**: {c.detail}")

        lines += [
            "",
            "## Manual Steps (if checks fail)",
            "",
            "- `atlas_memory.db` missing → check NEVER DELETE rule in CLAUDE.md Section 14",
            "- `atlas_tracker.db` missing → same; restore from backup if available",
            "- `/health` unreachable → start server: `uvicorn api_server:app --host 127.0.0.1 --port 8000`",
            "- Supabase tables missing → run schema.sql migration in Supabase SQL Editor (Section 9 in CLAUDE.md)",
            "",
            "## Supabase Table Checklist (verify manually)",
            "",
            "- [ ] `queries` table exists with `session_id` column",
            "- [ ] `chat_sessions` table exists",
            "- [ ] `user_watchlist` table exists",
            "- [ ] `positions` table exists",
            "- [ ] Row Level Security enabled on all five tenant tables",
        ]

        report = "\n".join(lines)

        if write_output:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUTS_DIR / "supabase_health.md"
            out_path.write_text(report, encoding="utf-8")

        return SupabaseHealthResult(
            success=True,
            report=report,
            checks=checks,
        )

    except Exception as exc:
        return SupabaseHealthResult(success=False, error=str(exc))


if __name__ == "__main__":
    result = run(write_output=True)
    if result.success:
        print(result.report)
        all_required_passed = all(
            c.passed for c in result.checks if c.name.startswith("REQUIRED")
        )
        raise SystemExit(0 if all_required_passed else 1)
    else:
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
