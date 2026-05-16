"""
smoke_test.py — R.A. Omega endpoint smoke tester.

Hits every critical HTTP endpoint and verifies status codes and key content.
Assumes the server is already running at http://127.0.0.1:8000.
Run after any server restart or before marking a task done.

Usage:
    python omega_os/skills/smoke_tester/tools/smoke_test.py
    python omega_os/skills/smoke_tester/tools/smoke_test.py --base-url http://127.0.0.1:8000
    python omega_os/skills/smoke_tester/tools/smoke_test.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent

DEFAULT_BASE = "http://127.0.0.1:8000"
TIMEOUT_S    = 8


@dataclass
class SmokeResult:
    endpoint: str
    expected_status: int
    actual_status: int | None
    content_check: str      # substring to verify in body, or ""
    content_ok: bool
    error: str
    duration_ms: float

    @property
    def passed(self) -> bool:
        return (
            self.actual_status == self.expected_status
            and self.content_ok
            and not self.error
        )


# ── Endpoint definitions ───────────────────────────────────────────────────────

def _endpoints(base: str) -> list[tuple[str, str, int, str]]:
    """Return list of (method, url, expected_status, content_check)."""
    B = base.rstrip("/")
    return [
        # Core pages
        ("GET", f"{B}/",               200, ""),
        ("GET", f"{B}/auth",           200, ""),
        ("GET", f"{B}/command-center", 200, "R.A. Omega"),
        ("GET", f"{B}/app",            200, ""),   # may redirect to /auth — both OK
        ("GET", f"{B}/v2",             200, ""),
        ("GET", f"{B}/design_system.css", 200, "--color-accent"),
        ("GET", f"{B}/omega-os/brain-network", 200, "omega"),
        # Health + data APIs
        ("GET", f"{B}/health",         200, ""),
        ("GET", f"{B}/regime",         200, ""),
        ("GET", f"{B}/alerts",         200, ""),
        ("GET", f"{B}/watchlist",      200, ""),
        ("GET", f"{B}/sessions",       200, ""),
        ("GET", f"{B}/omega-os/dashboard", 200, ""),
        ("GET", f"{B}/omega-os/skills", 200, ""),
        ("GET", f"{B}/sandbox/agent-health", 200, ""),
    ]


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _get(url: str) -> tuple[int, str, float]:
    """Return (status_code, body_text, duration_ms)."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OmegaSmokeTest/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            return resp.status, body, (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        body = e.read(512).decode("utf-8", errors="replace")
        return e.code, body, (time.time() - t0) * 1000
    except urllib.error.URLError as e:
        return None, str(e.reason), (time.time() - t0) * 1000
    except Exception as e:
        return None, str(e), (time.time() - t0) * 1000


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_smoke(base_url: str = DEFAULT_BASE) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    for method, url, expected, content_check in _endpoints(base_url):
        status, body, ms = _get(url)
        content_ok = (content_check == "") or (content_check.lower() in body.lower())
        error = "" if status is not None else body
        # /app may redirect (302) to /auth — treat both as pass
        if url.endswith("/app") and status in (200, 302):
            expected = status
        results.append(SmokeResult(
            endpoint=url.replace(base_url, ""),
            expected_status=expected,
            actual_status=status,
            content_check=content_check,
            content_ok=content_ok,
            error=error,
            duration_ms=round(ms, 1),
        ))
    return results


def print_results(results: list[SmokeResult], base_url: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep = "=" * 68
    print(sep)
    print(f"  R.A. OMEGA — SMOKE TEST  ({base_url})")
    print(sep)
    print(f"\n  {'ENDPOINT':<36} {'STATUS':>6}  {'MS':>6}  RESULT")
    print(f"  {'-'*36} {'-'*6}  {'-'*6}  ------")
    for r in results:
        icon   = "[OK]" if r.passed else "[!!]"
        status = str(r.actual_status) if r.actual_status else "ERR"
        note   = ""
        if not r.passed:
            if r.error:
                note = f"  <- {r.error[:40]}"
            elif r.actual_status != r.expected_status:
                note = f"  <- expected {r.expected_status}"
            elif not r.content_ok:
                note = f"  <- body missing '{r.content_check}'"
        print(f"  {r.endpoint:<36} {status:>6}  {r.duration_ms:>5.0f}ms  {icon}{note}")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n{sep}")
    if failed == 0:
        print(f"  RESULT: PASS — {passed}/{len(results)} endpoints OK")
    else:
        print(f"  RESULT: FAIL — {failed} endpoint(s) failing")
        print("  Tip: Is the server running?  uvicorn api_server:app --host 127.0.0.1 --port 8000")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega smoke tester")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--json",     action="store_true")
    args = parser.parse_args()

    results = run_smoke(args.base_url)

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps([
            {
                "endpoint":        r.endpoint,
                "status":          r.actual_status,
                "expected":        r.expected_status,
                "duration_ms":     r.duration_ms,
                "passed":          r.passed,
                "error":           r.error,
            }
            for r in results
        ], indent=2))
    else:
        print_results(results, args.base_url)

    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
