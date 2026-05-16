"""
verify_contracts.py — Validates internal tool APIs haven't drifted.

Checks that every internal improve_system tool exports the functions and
return-type attributes that callers depend on. Prevents the DeadWire/.get()
and run_scan/scan() class of runtime crashes that bit us in dev_session_guard.

Usage:
    python omega_os/skills/api_contract_guard/tools/verify_contracts.py
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
TOOLS = ROOT / "omega_os" / "skills" / "improve_system" / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TOOLS))

@dataclass
class ContractResult:
    tool: str
    passed: bool
    failures: list[str]


def _ok(msg: str) -> None:  print(f"  [OK]  {msg}")
def _fail(msg: str) -> None: print(f"  [!!]  {msg}")
def _warn(msg: str) -> None: print(f"  [~~]  {msg}")


# ── Contract definitions ───────────────────────────────────────────────────────

def check_health_scorer() -> ContractResult:
    failures = []
    try:
        from health_scorer import score, HealthResult
        result = score()
        # Must have .overall (numeric) and .overall_rating (str)
        if not hasattr(result, "overall"):
            failures.append("HealthResult missing .overall attribute")
        elif not isinstance(result.overall, (int, float)):
            failures.append(f".overall must be numeric, got {type(result.overall)}")
        if not hasattr(result, "overall_rating"):
            failures.append("HealthResult missing .overall_rating attribute")
        # overall must be safely castable to int (caught float*str bug)
        try:
            _ = int(result.overall)
        except (TypeError, ValueError) as e:
            failures.append(f"int(result.overall) failed: {e}")
        if not failures:
            _ok(f"health_scorer: score()={result.overall}/100 ({result.overall_rating})")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("health_scorer", not failures, failures)


def check_upgrade_scanner() -> ContractResult:
    failures = []
    try:
        from upgrade_scanner import scan, SEVERITY_CRITICAL
        # Public API is scan(root) → ScanResult with .opportunities list
        result = scan(ROOT)
        if not hasattr(result, "opportunities"):
            failures.append("ScanResult missing .opportunities attribute")
        elif not isinstance(result.opportunities, list):
            failures.append(f".opportunities must be list, got {type(result.opportunities)}")
        # Verify SEVERITY_CRITICAL is a string constant
        if not isinstance(SEVERITY_CRITICAL, str):
            failures.append(f"SEVERITY_CRITICAL must be str, got {type(SEVERITY_CRITICAL)}")
        if not failures:
            _ok(f"upgrade_scanner: scan() returned {len(result.opportunities)} opportunities")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("upgrade_scanner", not failures, failures)


def check_chain_mapper() -> ContractResult:
    failures = []
    try:
        from chain_mapper import build_chain_map, scan_dead_wires
        chains = build_chain_map()
        wires  = scan_dead_wires(chains)
        # DeadWire must be a dataclass/namedtuple with .category, .target, .detail, .severity
        if wires:
            w = wires[0]
            for attr in ("category", "target", "detail", "severity"):
                if not hasattr(w, attr):
                    failures.append(f"DeadWire missing .{attr} — do NOT use .get()")
            # Confirm it's NOT a dict (the bug we hit)
            if isinstance(w, dict):
                failures.append("DeadWire is a dict — contract expects dataclass with attrs")
        if not failures:
            _ok(f"chain_mapper: build_chain_map()={len(chains)} chains, {len(wires)} dead wires")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("chain_mapper", not failures, failures)


def check_ui_audit() -> ContractResult:
    failures = []
    try:
        from ui_audit import run_audit, FileReport
        reports = run_audit()
        if not isinstance(reports, list):
            failures.append(f"run_audit() must return list, got {type(reports)}")
        elif reports:
            r = reports[0]
            for attr in ("filename", "overall", "exists"):
                if not hasattr(r, attr):
                    failures.append(f"FileReport missing .{attr}")
            if not failures:
                scores = ", ".join(f"{r.filename.split('.')[0]}:{r.overall}" for r in reports if r.exists)
                _ok(f"ui_audit: run_audit()=[{scores}]")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("ui_audit", not failures, failures)


def check_session_briefing() -> ContractResult:
    failures = []
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "dev_session_guard" / "tools"))
        from session_briefing import brief
        output = brief()
        if not isinstance(output, str):
            failures.append(f"brief() must return str, got {type(output)}")
        if "Branch" not in output:
            failures.append("brief() output missing 'Branch' section")
        if "Health" not in output:
            failures.append("brief() output missing 'Health' section")
        lines = output.splitlines()
        if len(lines) > 40:
            failures.append(f"brief() is {len(lines)} lines — must be <=40 for one screen")
        if not failures:
            _ok(f"session_briefing: brief() returns {len(lines)}-line summary")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("session_briefing", not failures, failures)


def check_route_audit() -> ContractResult:
    failures = []
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "route_map" / "tools"))
        from route_audit import run_audit, AuditReport
        report = run_audit()
        if not isinstance(report, AuditReport):
            failures.append(f"run_audit() must return AuditReport, got {type(report)}")
        if not hasattr(report, "routes"):
            failures.append("AuditReport missing .routes")
        if not hasattr(report, "auth_redirect_ok"):
            failures.append("AuditReport missing .auth_redirect_ok")
        if not report.auth_redirect_ok:
            failures.append(f"Auth redirect is broken: points to {report.auth_redirect_target}")
        if not failures:
            _ok(f"route_audit: run_audit()={len(report.routes)} routes, auth_ok={report.auth_redirect_ok}")
    except Exception as e:
        failures.append(f"import/call failed: {e}")
    return ContractResult("route_audit", not failures, failures)


# ── Runner ─────────────────────────────────────────────────────────────────────

CHECKS = [
    check_health_scorer,
    check_upgrade_scanner,
    check_chain_mapper,
    check_ui_audit,
    check_session_briefing,
    check_route_audit,
]

def run_all() -> list[ContractResult]:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep = "=" * 64
    print(sep)
    print("  R.A. OMEGA — INTERNAL API CONTRACT GUARD")
    print(sep)

    results = []
    for check in CHECKS:
        tool_name = check.__name__.replace("check_", "")
        print(f"\n  -- {tool_name} --")
        try:
            r = check()
        except Exception as e:
            _fail(f"Checker itself crashed: {e}")
            r = ContractResult(tool_name, False, [str(e)])
        if r.failures:
            for f in r.failures:
                _fail(f)
        results.append(r)

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n{sep}")
    print(f"  RESULT: {passed}/{len(results)} contracts PASS — {failed} FAIL")
    if failed:
        print("  Fix the failing contracts before adding new callers of these tools.")
    print(sep)
    return results


def main() -> None:
    import argparse, json
    parser = argparse.ArgumentParser(description="R.A. Omega internal API contract guard")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.json:
        import io
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        results = []
        for check in CHECKS:
            # Suppress human-readable output during JSON mode
            _old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                r = check()
            except Exception as e:
                tool_name = check.__name__.replace("check_", "")
                r = ContractResult(tool_name, False, [str(e)])
            finally:
                sys.stdout = _old_stdout
            results.append(r)
        print(json.dumps([
            {"check": r.tool, "passed": r.passed, "failures": r.failures}
            for r in results
        ], indent=2))
        sys.exit(0 if all(r.passed for r in results) else 1)
    else:
        results = run_all()
        sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
