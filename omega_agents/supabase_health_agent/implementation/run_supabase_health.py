"""
run_supabase_health.py - Safe smoke checks for the Supabase/persistence layer.

Checks local DB files, optional live Supabase schema reachability, the local
/health endpoint, and optional authenticated session/watchlist endpoints.

No broker actions. No email sends. No schema mutations. The only optional write
is a test watchlist ticker when --auth-roundtrip is explicitly provided.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    return HealthCheck(
        name=f"{label}: {fname}",
        passed=not required,
        detail="Missing" if required else "Not present (optional)",
    )


def _request_json(
    path: str,
    *,
    bearer_token: str = "",
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, str]:
    data = None
    headers = {"Accept": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{_LOCAL_SERVER}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            text = resp.read(1200).decode("utf-8", errors="replace")
            return int(resp.status), text
    except urllib.error.HTTPError as exc:
        text = exc.read(1200).decode("utf-8", errors="replace")
        return int(exc.code), text
    except Exception as exc:
        return 0, str(exc)


def _check_health_endpoint() -> HealthCheck:
    status, text = _request_json("/health")
    return HealthCheck(
        name="GET /health endpoint",
        passed=status == 200,
        detail=f"HTTP {status} - {text[:180]}",
    )


def _check_supabase_schema(*, live: bool = False) -> HealthCheck:
    try:
        import atlas_db

        if not atlas_db.is_configured():
            return HealthCheck(
                name="Supabase schema probe",
                passed=False,
                detail="SUPABASE_URL/SUPABASE_KEY are not configured",
            )
        if not live:
            return HealthCheck(
                name="Supabase schema probe",
                passed=True,
                detail="Configured; live probe skipped. Re-run with --live-supabase for table checks.",
            )
        status = atlas_db.supabase_schema_status()
        required = (
            "chat_sessions_reachable",
            "user_watchlist_reachable",
            "research_jobs_reachable",
            "user_preferences_reachable",
            "queries_has_session_id_column",
        )
        missing = [key for key in required if status.get(key) is not True]
        return HealthCheck(
            name="Supabase schema probe",
            passed=not missing,
            detail=json.dumps(status, sort_keys=True)[:900],
        )
    except Exception as exc:
        return HealthCheck(
            name="Supabase schema probe",
            passed=False,
            detail=f"Error: {exc}",
        )


def _check_authenticated_endpoint(path: str, *, bearer_token: str) -> HealthCheck:
    if not bearer_token:
        return HealthCheck(
            name=f"Authenticated GET {path}",
            passed=True,
            detail="Skipped; set SUPABASE_AUTH_TOKEN or pass --bearer-token.",
        )
    status, text = _request_json(path, bearer_token=bearer_token)
    return HealthCheck(
        name=f"Authenticated GET {path}",
        passed=status == 200,
        detail=f"HTTP {status} - {text[:180]}",
    )


def _check_watchlist_roundtrip(*, bearer_token: str) -> HealthCheck:
    if not bearer_token:
        return HealthCheck(
            name="Authenticated watchlist roundtrip",
            passed=True,
            detail="Skipped; set SUPABASE_AUTH_TOKEN or pass --bearer-token.",
        )
    ticker = "OMEGATEST"
    add_status, add_text = _request_json(
        "/watchlist",
        bearer_token=bearer_token,
        method="POST",
        body={"ticker": ticker},
    )
    get_status, get_text = _request_json("/watchlist", bearer_token=bearer_token)
    del_status, del_text = _request_json(
        f"/watchlist/{ticker}",
        bearer_token=bearer_token,
        method="DELETE",
    )
    passed = add_status == 200 and get_status == 200 and del_status == 200
    detail = f"add={add_status} get={get_status} delete={del_status} - {(add_text + ' ' + get_text + ' ' + del_text)[:260]}"
    return HealthCheck(
        name="Authenticated watchlist roundtrip",
        passed=passed,
        detail=detail,
    )


def run(
    write_output: bool = False,
    *,
    live_supabase: bool = False,
    bearer_token: str = "",
    auth_roundtrip: bool = False,
) -> SupabaseHealthResult:
    """
    Run persistence and health checks.

    Args:
        write_output: If True, writes atlas_vault/03-Outputs/supabase_health.md.
        live_supabase: If True, runs read-only live schema probes through atlas_db.
        bearer_token: Optional Supabase JWT for authenticated endpoint checks.
        auth_roundtrip: If True and bearer_token is set, add/delete a test watchlist ticker.
    """
    try:
        checks: list[HealthCheck] = []

        for fname in _REQUIRED_LOCAL_FILES:
            checks.append(_check_local_file(fname, required=True))
        for fname in _OPTIONAL_LOCAL_FILES:
            checks.append(_check_local_file(fname, required=False))

        checks.append(_check_supabase_schema(live=live_supabase))
        checks.append(_check_health_endpoint())
        checks.append(_check_authenticated_endpoint("/sessions", bearer_token=bearer_token))
        checks.append(_check_authenticated_endpoint("/watchlist", bearer_token=bearer_token))
        if auth_roundtrip:
            checks.append(_check_watchlist_roundtrip(bearer_token=bearer_token))

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
        for check in checks:
            icon = "OK" if check.passed else "FAIL"
            lines.append(f"- [{icon}] **{check.name}**: {check.detail}")

        lines += [
            "",
            "## Manual Steps If Checks Fail",
            "",
            "- Missing local DB files: restore from backup before deleting or recreating data.",
            "- /health unreachable: start server with `uvicorn api_server:app --host 127.0.0.1 --port 8000`.",
            "- Supabase tables missing: run `schema.sql` in the Supabase SQL Editor.",
            "- Auth checks skipped: set `SUPABASE_AUTH_TOKEN` to a browser session access token.",
            "- Watchlist roundtrip skipped: run `--auth-roundtrip` only with a test account token.",
            "",
            "## Production Auth Flow Checklist",
            "",
            "- [ ] Sign up or sign in from `/auth`.",
            "- [ ] `/sessions` returns saved chat sessions with the browser token.",
            "- [ ] `/watchlist` persists a ticker after refresh.",
            "- [ ] `/history/reports` returns saved reports after a query.",
            "- [ ] `/health` includes `supabase_schema` with all required booleans true.",
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


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run R.A. Omega Supabase/persistence smoke checks.")
    parser.add_argument("--write-output", action="store_true", default=True)
    parser.add_argument("--live-supabase", action="store_true", help="Run read-only live Supabase schema probes.")
    parser.add_argument("--bearer-token", default=os.getenv("SUPABASE_AUTH_TOKEN", ""))
    parser.add_argument("--auth-roundtrip", action="store_true", help="Add/delete a test watchlist ticker using the bearer token.")
    args = parser.parse_args()

    result = run(
        write_output=args.write_output,
        live_supabase=args.live_supabase,
        bearer_token=args.bearer_token,
        auth_roundtrip=args.auth_roundtrip,
    )
    if not result.success:
        print(f"ERROR: {result.error}")
        return 1
    print(result.report)
    required_ok = all(
        check.passed
        for check in result.checks
        if check.name.startswith("REQUIRED") or check.name == "Supabase schema probe"
    )
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())
