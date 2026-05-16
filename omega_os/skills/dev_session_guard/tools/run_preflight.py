"""
run_preflight.py — R.A. Omega pre-flight and pre-commit guard.

Modes:
  (default)         Full session start check — health, chains, upgrades, brief
  --pre-commit      Strict commit gate — exits 1 on ANY blocker
  --protected-only  Only check protected files (fast)
  --brief           Session brief only (delegates to session_briefing.py)

Usage:
    python omega_os/skills/dev_session_guard/tools/run_preflight.py
    python omega_os/skills/dev_session_guard/tools/run_preflight.py --pre-commit
    python omega_os/skills/dev_session_guard/tools/run_preflight.py --protected-only
"""
from __future__ import annotations

import argparse
import json
import py_compile
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── Constants ─────────────────────────────────────────────────────────────────

PROTECTED_FILES = [
    "deep_research.py",
    "gemini_limiter.py",
]

PROTECTED_DATABASES = [
    "atlas_memory.db",
    "atlas_tracker.db",
]

PROTECTED_DIRS = [
    "atlas_rag",
]

CORE_FILES_TO_COMPILE = [
    "api_server.py",
    "query_router.py",
    "atlas_omega.py",
    "output_modes.py",
    "alerts.py",
    "progress_state.py",
    "omega_connections.py",
    "omega_cadence.py",
]

BASELINE_TEST_COUNT = 1300    # function count baseline (pytest total includes parametrize multiply)
MIN_HEALTH_SCORE    = 75      # below this = warning in pre-commit mode

NEVER_STAGE = [
    ".env",
    "atlas_memory.db",
    "atlas_tracker.db",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git"] + args, cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return ""


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _warn(msg: str) -> None:
    print(f"  [~~]  {msg}")


def _fail(msg: str) -> None:
    print(f"  [!!]  {msg}")


def _section(title: str) -> None:
    print(f"\n  -- {title} --")


# ── Individual checks ─────────────────────────────────────────────────────────

def check_protected_files() -> list[str]:
    """Return list of protected files that have been modified."""
    blockers: list[str] = []
    modified_raw = _git(["diff", "--name-only", "HEAD"])
    modified_files = set(modified_raw.splitlines())
    # Also check unstaged
    unstaged_raw = _git(["diff", "--name-only"])
    modified_files |= set(unstaged_raw.splitlines())

    for fname in PROTECTED_FILES:
        if fname in modified_files:
            _fail(f"PROTECTED FILE MODIFIED: {fname}  ← NEVER touch this")
            blockers.append(f"Protected file modified: {fname}")
        else:
            _ok(f"Protected: {fname} untouched")
    return blockers


def check_protected_databases() -> list[str]:
    """Return blocker if protected databases are missing."""
    blockers: list[str] = []
    for db in PROTECTED_DATABASES:
        path = ROOT / db
        if path.exists():
            _ok(f"Database intact: {db}")
        else:
            _fail(f"DATABASE MISSING: {db}  ← do NOT delete this")
            blockers.append(f"Protected database missing: {db}")
    return blockers


def check_compile(pre_commit: bool = False) -> list[str]:
    """Compile-check all core files. Returns list of failures."""
    blockers: list[str] = []
    for fname in CORE_FILES_TO_COMPILE:
        path = ROOT / fname
        if not path.exists():
            _warn(f"Not found (skipping compile): {fname}")
            continue
        tmp = tempfile.mktemp(suffix=".py")
        try:
            shutil.copy(path, tmp)
            py_compile.compile(tmp, doraise=True)
            _ok(f"Compiles: {fname}")
        except py_compile.PyCompileError as exc:
            msg = str(exc).replace(tmp, fname)
            _fail(f"COMPILE ERROR: {fname} — {msg}")
            blockers.append(f"Compile failure: {fname}")
        finally:
            Path(tmp).unlink(missing_ok=True)
    return blockers


def check_test_count(baseline: int = BASELINE_TEST_COUNT) -> list[str]:
    """Count test functions. Warn (not block) if count drops."""
    import re
    count = 0
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        _warn("tests/ directory not found")
        return []
    for f in tests_dir.glob("test_*.py"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            count += len(re.findall(r"^def test_", text, re.MULTILINE))
        except Exception:
            pass
    if count >= baseline:
        _ok(f"Test functions: {count} (>= baseline {baseline})")
        return []
    else:
        _warn(f"Test count dropped: {count} found, baseline is {baseline}")
        # Warning only — not a hard blocker (tests may have been consolidated)
        return []


def check_staged_forbidden(pre_commit: bool = False) -> list[str]:
    """In pre-commit mode, block if any forbidden files are staged."""
    if not pre_commit:
        return []
    staged = _git(["diff", "--cached", "--name-only"]).splitlines()
    blockers: list[str] = []
    for fname in NEVER_STAGE:
        if any(fname in s for s in staged):
            _fail(f"STAGED FORBIDDEN FILE: {fname}  ← never commit this")
            blockers.append(f"Forbidden file staged: {fname}")
        else:
            _ok(f"Not staged: {fname}")
    return blockers


def check_health_score() -> tuple[int, str, list[str]]:
    """Run health_scorer. Returns (score, rating, warnings)."""
    warnings: list[str] = []
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from health_scorer import score as hs_score
        result = hs_score()
        s, r = result.overall, result.overall_rating
        if s >= 85:
            _ok(f"Architecture health: {s}/100 {r}")
        elif s >= 75:
            _warn(f"Architecture health: {s}/100 {r}")
        else:
            _fail(f"Architecture health LOW: {s}/100 {r}")
            warnings.append(f"Health score low: {s}/100")
        return s, r, warnings
    except Exception as exc:
        _warn(f"health_scorer unavailable: {exc}")
        return 0, "unavailable", []


def check_chain_wires() -> list[str]:
    """Run chain_mapper dead wire scan. Returns blockers on broken chains."""
    blockers: list[str] = []
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from chain_mapper import build_chain_map, scan_dead_wires
        chains = build_chain_map()
        wires = scan_dead_wires(chains)
        # DeadWire is a dataclass with: category, target, severity, detail
        broken  = [w for w in wires if w.category == "broken_chain"]
        unrouted = [w for w in wires if w.category == "unrouted_intent"]
        if broken:
            for b in broken:
                _fail(f"BROKEN CHAIN: {b.target} — {b.detail}")
            blockers.extend([f"Broken chain: {b.target}" for b in broken])
        else:
            _ok("Chain integrity: 0 broken chains")
        if unrouted:
            _warn(f"{len(unrouted)} unrouted intents (expected for OS-layer skills)")
        return blockers
    except Exception as exc:
        _warn(f"chain_mapper unavailable: {exc}")
        return []


def check_critical_upgrades() -> list[str]:
    """Run upgrade_scanner critical-only. Returns top 3 as warnings."""
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from upgrade_scanner import scan, SEVERITY_CRITICAL
        scan_result = scan(ROOT)
        critical = [r for r in scan_result.opportunities if r.severity == SEVERITY_CRITICAL]
        if critical:
            _warn(f"Upgrade scanner: {len(critical)} critical items")
            for r in critical[:3]:
                rel = Path(r.file).name if hasattr(r, "file") else str(r)
                msg = getattr(r, "message", str(r))[:55]
                line = getattr(r, "line", "?")
                _warn(f"  {rel}:{line} {msg}")
        else:
            _ok("Upgrade scanner: 0 critical items")
        return []    # upgrades are warnings, not blockers
    except Exception as exc:
        _warn(f"upgrade_scanner unavailable: {exc}")
        return []


def check_ui_scores(pre_commit: bool = False) -> list[str]:
    """Run ui_audit. Warn if any core page below 65."""
    warnings: list[str] = []
    try:
        sys.path.insert(0, str(ROOT / "omega_os" / "skills" / "improve_system" / "tools"))
        from ui_audit import run_audit
        reports = run_audit()
        low = [r for r in reports if r.exists and r.overall < 65]
        if low:
            for r in low:
                _warn(f"UI score low: {r.filename} {r.overall}/100")
                warnings.append(f"UI score low: {r.filename} {r.overall}/100")
        else:
            scores = ", ".join(f"{r.filename.split('.')[0]}:{r.overall}" for r in reports if r.exists)
            _ok(f"UI audit: {scores}")
        return warnings
    except Exception as exc:
        _warn(f"ui_audit unavailable: {exc}")
        return []


# ── Main modes ────────────────────────────────────────────────────────────────

def run_preflight(pre_commit: bool = False, protected_only: bool = False) -> int:
    """Run all checks. Returns exit code (0=pass, 1=blocked)."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sep = "=" * 64
    mode = "PRE-COMMIT" if pre_commit else "PROTECTED-ONLY" if protected_only else "SESSION START"
    print(sep)
    print(f"  R.A. OMEGA PRE-FLIGHT CHECK  [{mode}]")
    print(sep)

    all_blockers: list[str] = []

    # ── 1. Protected files ──────────────────────────────────────────────────
    _section("Protected Files")
    all_blockers.extend(check_protected_files())
    all_blockers.extend(check_protected_databases())

    if protected_only:
        _print_result(all_blockers, pre_commit=False)
        return 0

    # ── 2. Staged forbidden (pre-commit only) ───────────────────────────────
    if pre_commit:
        _section("Staged File Check")
        all_blockers.extend(check_staged_forbidden(pre_commit=True))

    # ── 3. Compile check ────────────────────────────────────────────────────
    _section("Syntax Check")
    all_blockers.extend(check_compile(pre_commit=pre_commit))

    # ── 4. Test count ───────────────────────────────────────────────────────
    _section("Test Count")
    check_test_count()    # warnings only, no blockers

    # ── 5. Architecture health ──────────────────────────────────────────────
    _section("Architecture Health")
    _score, _rating, health_warns = check_health_score()

    # ── 6. Chain integrity ──────────────────────────────────────────────────
    _section("Chain Integrity")
    all_blockers.extend(check_chain_wires())

    # ── 7. Critical upgrades (session start only) ───────────────────────────
    if not pre_commit:
        _section("Critical Upgrades")
        check_critical_upgrades()

    # ── 8. UI audit ─────────────────────────────────────────────────────────
    _section("UI Audit")
    check_ui_scores(pre_commit=pre_commit)

    # ── 9. Session brief (session start only) ───────────────────────────────
    if not pre_commit:
        _section("Session Context")
        try:
            from session_briefing import brief
            print(brief())
        except Exception as exc:
            _warn(f"session_briefing unavailable: {exc}")

    # ── Result ───────────────────────────────────────────────────────────────
    return _print_result(all_blockers, pre_commit=pre_commit)


def _print_result(blockers: list[str], pre_commit: bool) -> int:
    sep = "=" * 64
    print(f"\n{sep}")
    if not blockers:
        print(f"  RESULT: PASS  — no blockers found")
        if pre_commit:
            print("  Safe to commit.")
        print(sep)
        return 0
    else:
        print(f"  RESULT: FAIL  — {len(blockers)} blocker(s)")
        for i, b in enumerate(blockers, 1):
            print(f"    {i}. {b}")
        if pre_commit:
            print("  Fix all blockers before committing.")
        print(sep)
        return 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="R.A. Omega pre-flight and pre-commit guard"
    )
    parser.add_argument("--pre-commit",     action="store_true",
                        help="Strict commit gate mode — exits 1 on any blocker")
    parser.add_argument("--protected-only", action="store_true",
                        help="Only check protected files (fast, <1s)")
    parser.add_argument("--brief",          action="store_true",
                        help="Print session brief only")
    args = parser.parse_args()

    if args.brief:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from session_briefing import brief
            print(brief())
        except Exception as exc:
            print(f"session_briefing error: {exc}")
        sys.exit(0)

    exit_code = run_preflight(
        pre_commit=args.pre_commit,
        protected_only=args.protected_only,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
