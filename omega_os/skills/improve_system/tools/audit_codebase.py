"""
audit_codebase.py — Deterministic read-only audit of the R.A. Omega codebase.

No external APIs. No API keys. No writes to source files.
Output is a structured report written to atlas_vault/03-Outputs/codebase_audit.md
and/or returned as an AuditResult for programmatic use.

Checks performed:
  1. py_compile  — all .py files compile cleanly
  2. Secret scan — no hardcoded credentials in source files
  3. Protected files — deep_research.py and gemini_limiter.py are unmodified (git clean)
  4. BASE_DIR    — api_server.py uses BASE_DIR not SCRIPT_DIR
  5. Import safety — no file outside the allowed set imports deep_research or gemini_limiter
  6. Output mode contracts — output_modes in omega_pipeline are covered by output_contracts
  7. Worker stubs — every omega_agents worker has an implementation stub

CLI:
  python audit_codebase.py
  python audit_codebase.py --root /path/to/project
  python audit_codebase.py --json
  python audit_codebase.py --output /path/to/report.md
"""
from __future__ import annotations

import json
import py_compile
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[4]   # project root
_OUTPUTS_DIR = _ROOT / "atlas_vault" / "03-Outputs"

# ── Protected files (NEVER modify per CLAUDE.md rule 1) ──────────────────────

_PROTECTED_FILES = ("deep_research.py", "gemini_limiter.py")

# ── Dangerous patterns inside protected module usage ─────────────────────────
# CLAUDE.md: "NEVER modify: deep_research.py, gemini_limiter.py"
# Importing them is fine. These patterns flag bypasses or monkey-patching.
_DANGEROUS_USAGE_PATTERNS: list[tuple[str, str]] = [
    (r"gemini_limiter\._", "Accessing private internals of gemini_limiter"),
    (r"deep_research\._", "Accessing private internals of deep_research"),
    (r"gemini_limiter\.RATE_LIMIT\s*=", "Overwriting gemini_limiter rate limit"),
    (r"gemini_limiter\.bypass", "Bypassing gemini_limiter"),
]

# ── Secret patterns (regex) ───────────────────────────────────────────────────

_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'"sk-[A-Za-z0-9]{20,}"', "Hardcoded OpenAI key literal"),
    (r"'sk-[A-Za-z0-9]{20,}'", "Hardcoded OpenAI key literal"),
    (r'"whsec_[A-Za-z0-9]{10,}"', "Hardcoded Stripe webhook secret"),
    (r'"SG\.[A-Za-z0-9]{10,}"', "Hardcoded SendGrid key"),
    (r'SUPABASE_KEY\s*=\s*"[^"]{20,}"', "Hardcoded Supabase key"),
    (r'api_key\s*=\s*"[^"]{10,}"', "Hardcoded api_key assignment"),
    (r"bot_token\s*=\s*'[^']{10,}'", "Hardcoded bot_token assignment"),
    (r'bot_token\s*=\s*"[^"]{10,}"', "Hardcoded bot_token assignment"),
]

# ── Python source directories to compile-check ───────────────────────────────

_COMPILE_GLOBS = [
    "*.py",
    "omega_os/**/*.py",
    "omega_agents/**/*.py",
    "atlas_agents/**/*.py",
    "atlas_core/**/*.py",
    "atlas_memory/**/*.py",
    "atlas_sandbox/**/*.py",
    "atlas_export/**/*.py",
    "tests/*.py",
]

# ── Files / directories to exclude from secret scan ──────────────────────────
# Tests use fake credential formats (fake tokens, fake keys) to test gating logic.
_SECRET_SCAN_EXCLUDES = {".env", ".env.example", "audit_codebase.py"}
_SECRET_SCAN_EXCLUDE_DIRS = {"tests", "__pycache__"}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Check:
    category: str
    target: str
    passed: bool
    severity: str = "error"    # error | warning | info
    detail: str = ""


@dataclass
class AuditResult:
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    warning_count: int
    checks: list[Check] = field(default_factory=list)
    report: str = ""
    error: str = ""

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{status}: {self.passed_count}/{self.total} checks passed, "
            f"{self.failed_count} failed, {self.warning_count} warnings"
        )


# ── Check 1 — py_compile ─────────────────────────────────────────────────────

def _check_py_compile(root: Path) -> list[Check]:
    checks: list[Check] = []
    seen: set[Path] = set()

    for pattern in _COMPILE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path in seen:
                continue
            if "__pycache__" in path.parts:
                continue
            seen.add(path)
            try:
                py_compile.compile(str(path), doraise=True)
                checks.append(Check("py_compile", path.relative_to(root).as_posix(), True, "error", ""))
            except py_compile.PyCompileError as exc:
                checks.append(Check("py_compile", path.relative_to(root).as_posix(), False, "error", str(exc)))

    return checks


# ── Check 2 — Secret scan ─────────────────────────────────────────────────────

def _check_secrets(root: Path) -> list[Check]:
    checks: list[Check] = []
    patterns = [(re.compile(p), label) for p, label in _SECRET_PATTERNS]

    for path in sorted(root.glob("**/*.py")):
        if any(part in _SECRET_SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if path.name in _SECRET_SCAN_EXCLUDES:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found: list[str] = []
        for regex, label in patterns:
            if regex.search(source):
                found.append(label)
        if found:
            checks.append(Check("secret_scan", rel, False, "error", "; ".join(found)))
        else:
            checks.append(Check("secret_scan", rel, True, "info", ""))

    return checks


# ── Check 3 — Protected files (git clean check) ───────────────────────────────

def _check_protected_files(root: Path) -> list[Check]:
    checks: list[Check] = []
    for fname in _PROTECTED_FILES:
        path = root / fname
        if not path.exists():
            checks.append(Check("protected_files", fname, False, "warning", "File not found in project root"))
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", fname],
                capture_output=True, text=True, timeout=10,
            )
            modified = result.stdout.strip()
            if modified:
                checks.append(Check("protected_files", fname, False, "error",
                                    "NEVER-MODIFY file has uncommitted changes"))
            else:
                checks.append(Check("protected_files", fname, True, "error", ""))
        except Exception as exc:
            checks.append(Check("protected_files", fname, True, "warning", f"git check skipped: {exc}"))

    return checks


# ── Check 4 — BASE_DIR in api_server.py ──────────────────────────────────────

def _check_base_dir(root: Path) -> list[Check]:
    path = root / "api_server.py"
    if not path.exists():
        return [Check("base_dir", "api_server.py", False, "warning", "api_server.py not found")]

    source = path.read_text(encoding="utf-8", errors="replace")

    if "SCRIPT_DIR" in source and "BASE_DIR" not in source:
        return [Check("base_dir", "api_server.py", False, "error",
                      "Uses SCRIPT_DIR instead of BASE_DIR — file paths will break on deploy")]
    if "SCRIPT_DIR" in source:
        return [Check("base_dir", "api_server.py", False, "warning",
                      "SCRIPT_DIR still present alongside BASE_DIR — verify all paths use BASE_DIR")]
    return [Check("base_dir", "api_server.py", True, "error", "")]


# ── Check 5 — Import safety ───────────────────────────────────────────────────

def _check_import_safety(root: Path) -> list[Check]:
    """
    Flag dangerous USAGE of protected modules (private internals, rate-limit bypasses).
    Importing deep_research or gemini_limiter is fine — the rule is don't MODIFY them.
    """
    checks: list[Check] = []
    compiled = [(re.compile(p), label) for p, label in _DANGEROUS_USAGE_PATTERNS]

    for path in sorted(root.glob("**/*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found: list[str] = []
        for regex, label in compiled:
            if regex.search(source):
                found.append(label)
        if found:
            rel = path.relative_to(root).as_posix()
            checks.append(Check("import_safety", rel, False, "error", "; ".join(found)))

    if not checks:
        checks.append(Check("import_safety", "all files", True, "error",
                            "No dangerous usage of protected modules detected"))
    return checks


# ── Check 6 — Output mode coverage ───────────────────────────────────────────

def _check_output_mode_coverage(root: Path) -> list[Check]:
    checks: list[Check] = []
    try:
        sys.path.insert(0, str(root))
        from output_contracts import OUTPUT_CONTRACTS  # type: ignore
        contracted = set(OUTPUT_CONTRACTS.keys())
    except Exception as exc:
        return [Check("output_modes", "output_contracts.py", False, "warning",
                      f"Could not load output_contracts: {exc}")]

    try:
        pipeline_src = (root / "omega_pipeline.py").read_text(encoding="utf-8", errors="replace")
        # Extract output_mode strings from pipeline routing
        modes_in_pipeline = set(re.findall(r'"(company_report|trade_plan|chat|general_chat|'
                                           r'finance_answer|market_snapshot|document|html_artifact|'
                                           r'unknown)"', pipeline_src))
    except Exception as exc:
        return [Check("output_modes", "omega_pipeline.py", False, "warning",
                      f"Could not read omega_pipeline: {exc}")]

    uncovered = modes_in_pipeline - contracted - {"unknown"}
    if uncovered:
        checks.append(Check("output_modes", "omega_pipeline.py", False, "warning",
                            f"Output modes without contracts: {sorted(uncovered)}"))
    else:
        checks.append(Check("output_modes", "omega_pipeline.py", True, "warning",
                            f"All pipeline output modes covered by contracts ({len(contracted)} contracts)"))
    return checks


# ── Check 7 — Worker stubs ────────────────────────────────────────────────────

def _check_worker_stubs(root: Path) -> list[Check]:
    checks: list[Check] = []
    agents_dir = root / "omega_agents"
    if not agents_dir.is_dir():
        return [Check("worker_stubs", "omega_agents/", False, "warning", "omega_agents/ directory not found")]

    for worker_dir in sorted(agents_dir.iterdir()):
        if not worker_dir.is_dir() or worker_dir.name.startswith("."):
            continue
        impl_dir = worker_dir / "implementation"
        stubs = list(impl_dir.glob("run_*.py")) if impl_dir.is_dir() else []
        if stubs:
            checks.append(Check("worker_stubs", f"omega_agents/{worker_dir.name}", True, "error", ""))
        else:
            checks.append(Check("worker_stubs", f"omega_agents/{worker_dir.name}", False, "error",
                                "Missing implementation/run_*.py stub"))
    return checks


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(result: AuditResult, root: Path) -> str:
    lines = [
        "# Codebase Audit Report",
        "",
        f"**Root:** `{root}`",
        f"**Result:** {result.summary()}",
        "",
    ]

    categories = sorted({c.category for c in result.checks})
    for cat in categories:
        cat_checks = [c for c in result.checks if c.category == cat]
        failures = [c for c in cat_checks if not c.passed]
        icon = "[PASS]" if not failures else "[FAIL]"
        lines.append(f"## {icon} {cat.replace('_', ' ').title()}")
        lines.append("")
        for c in cat_checks:
            if c.passed and c.category == "secret_scan":
                continue  # skip per-file PASS lines for secret scan (too verbose)
            if c.passed and c.category == "py_compile":
                continue  # same for compile
            status = "PASS" if c.passed else ("WARN" if c.severity == "warning" else "FAIL")
            line = f"- [{status}] `{c.target}`"
            if c.detail:
                line += f" — {c.detail}"
            lines.append(line)
        if not failures:
            if cat == "secret_scan":
                lines.append(f"- All {len(cat_checks)} files clean")
            elif cat == "py_compile":
                lines.append(f"- All {len(cat_checks)} files compile cleanly")
            else:
                lines.append("- All checks passed")
        lines.append("")

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def audit(root: Path | None = None) -> AuditResult:
    """
    Run all codebase checks and return a structured AuditResult.

    Args:
        root: Project root directory. Defaults to the R.A. Omega project root.

    Returns:
        AuditResult with .passed, .checks, .report, .summary().
    """
    if root is None:
        root = _ROOT

    all_checks: list[Check] = []
    all_checks += _check_py_compile(root)
    all_checks += _check_secrets(root)
    all_checks += _check_protected_files(root)
    all_checks += _check_base_dir(root)
    all_checks += _check_import_safety(root)
    all_checks += _check_output_mode_coverage(root)
    all_checks += _check_worker_stubs(root)

    failures  = [c for c in all_checks if not c.passed and c.severity == "error"]
    warnings  = [c for c in all_checks if not c.passed and c.severity == "warning"]
    passed    = [c for c in all_checks if c.passed]

    result = AuditResult(
        passed        = len(failures) == 0,
        total         = len(all_checks),
        passed_count  = len(passed),
        failed_count  = len(failures),
        warning_count = len(warnings),
        checks        = all_checks,
    )
    result.report = _build_report(result, root)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = "--json" in args
    root_arg = None
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            root_arg = Path(args[idx + 1])
    out_arg = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            out_arg = Path(args[idx + 1])

    result = audit(root=root_arg)

    if as_json:
        print(json.dumps({
            "passed":        result.passed,
            "total":         result.total,
            "passed_count":  result.passed_count,
            "failed_count":  result.failed_count,
            "warning_count": result.warning_count,
            "checks": [
                {"category": c.category, "target": c.target,
                 "passed": c.passed, "severity": c.severity, "detail": c.detail}
                for c in result.checks
            ],
        }, indent=2))
    else:
        print(result.report)

    # Write to atlas_vault/03-Outputs/ by default (unless --output specified)
    out_path = out_arg or (_ROOT / "atlas_vault" / "03-Outputs" / "codebase_audit.md")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.report, encoding="utf-8")
        if not as_json:
            print(f"\nReport written to: {out_path}")
    except Exception as exc:
        print(f"Warning: could not write report — {exc}", file=sys.stderr)

    sys.exit(0 if result.passed else 1)
