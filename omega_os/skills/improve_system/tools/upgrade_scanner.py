"""
upgrade_scanner.py — Upgrade opportunity scanner (Option D).

Reads all source files and flags concrete, actionable upgrade opportunities.
Fully deterministic — no LLM, no external APIs, no writes to source files.

Categories scanned:
  CRITICAL  Silent failures     -- except blocks that swallow errors silently
  HIGH      Deprecated APIs     -- datetime.utcnow(), bare asyncio.get_event_loop()
  MEDIUM    TODO/FIXME markers  -- explicit unresolved tech debt in comments
  MEDIUM    Long functions      -- AST-based, functions over 80 lines
  LOW       Hardcoded timeouts  -- timeout/limit/retry literals that should be configurable
  LOW       Missing logging     -- except blocks that capture but never log the error

Output written to atlas_vault/03-Outputs/upgrade_opportunities.md by default.

CLI:
  python upgrade_scanner.py
  python upgrade_scanner.py --json
  python upgrade_scanner.py --critical-only
  python upgrade_scanner.py --output /path/to/report.md
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_ROOT))

# ── Scan scope ────────────────────────────────────────────────────────────────

# Files excluded from scanning — protected (never modify) or IGNORE-listed in CLAUDE.md
_EXCLUDED_FILES = {
    "deep_research.py", "gemini_limiter.py",       # NEVER MODIFY
    "dashboard_server.py", "auto_bot.py",           # IGNORE-listed in CLAUDE.md
    "START_ATLAS.py", "build_audit_docx.py",
    "generate_project_inventory.py", "self_coder.py",
}

_SCAN_GLOBS = [
    "*.py",
    "omega_os/**/*.py",
    "atlas_core/**/*.py",
    "atlas_agents/**/*.py",
    "atlas_export/**/*.py",
    "atlas_memory/**/*.py",
    "atlas_sandbox/**/*.py",
    "omega_agents/**/*.py",
    "tests/*.py",
]

_SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules"}
# Exclude the diagnostic tools themselves — they contain pattern strings that match their own rules
_SKIP_SELF_DIR = Path(__file__).resolve().parent

# Tests are scanned for TODOs only — not for silent failures, long functions, etc.
_TESTS_ONLY_CATEGORIES = {"todo_fixme"}


# ── Severity ──────────────────────────────────────────────────────────────────

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH     = "HIGH"
SEVERITY_MEDIUM   = "MEDIUM"
SEVERITY_LOW      = "LOW"

_SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 3}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Opportunity:
    category: str
    severity: str
    file: str        # relative path
    line: int
    detail: str
    suggestion: str


@dataclass
class ScanResult:
    opportunities: list[Opportunity] = field(default_factory=list)
    files_scanned: int = 0
    report: str = ""

    def by_severity(self, severity: str) -> list[Opportunity]:
        return [o for o in self.opportunities if o.severity == severity]

    def by_category(self, category: str) -> list[Opportunity]:
        return [o for o in self.opportunities if o.category == category]

    def summary(self) -> str:
        c = len(self.by_severity(SEVERITY_CRITICAL))
        h = len(self.by_severity(SEVERITY_HIGH))
        m = len(self.by_severity(SEVERITY_MEDIUM))
        l = len(self.by_severity(SEVERITY_LOW))
        total = len(self.opportunities)
        return (
            f"{total} opportunities across {self.files_scanned} files: "
            f"{c} critical, {h} high, {m} medium, {l} low"
        )


# ── File collector ────────────────────────────────────────────────────────────

def _collect_files() -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for pattern in _SCAN_GLOBS:
        for path in sorted(_ROOT.glob(pattern)):
            if path in seen:
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.name in _EXCLUDED_FILES:
                continue
            if path.resolve().parent == _SKIP_SELF_DIR:
                continue   # skip diagnostic tools — they contain pattern strings
            seen.add(path)
            result.append(path)
    return result


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _is_test_file(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_")


# ── Category 1: Silent failures ───────────────────────────────────────────────
# except blocks with only `pass` — swallow errors completely

_SILENT_EXCEPT_RE = re.compile(
    r"^( *)except\b[^:]*:\s*\n\1    pass\s*$",
    re.MULTILINE,
)
_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)


def _scan_silent_failures(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    lines = source.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # bare except:
        if re.match(r"^except\s*:\s*$", stripped):
            ops.append(Opportunity(
                "silent_failure", SEVERITY_CRITICAL, rel, i,
                "Bare `except:` catches everything including KeyboardInterrupt and SystemExit",
                "Replace with `except Exception as exc:` and log the error",
            ))
            continue
        # except SomeError: pass (single-line)
        if re.match(r"^except\b.*:\s*pass\s*$", stripped):
            ops.append(Opportunity(
                "silent_failure", SEVERITY_CRITICAL, rel, i,
                f"`{stripped}` — error silently swallowed",
                "Log the exception or re-raise: `log.warning('...', exc_info=True)`",
            ))
            continue

    # Multi-line: except ...: \n    pass
    for m in _SILENT_EXCEPT_RE.finditer(source):
        lineno = source[: m.start()].count("\n") + 1
        ops.append(Opportunity(
            "silent_failure", SEVERITY_CRITICAL, rel, lineno,
            f"except block at line {lineno} silently passes — error discarded",
            "Log or re-raise the exception",
        ))

    # Deduplicate by (file, line)
    seen: set[tuple[str, int]] = set()
    unique: list[Opportunity] = []
    for o in ops:
        key = (o.file, o.line)
        if key not in seen:
            seen.add(key)
            unique.append(o)
    return unique


# ── Category 2: Deprecated APIs ───────────────────────────────────────────────

_DEPRECATED_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    (
        re.compile(r"\bdatetime\.utcnow\(\)"),
        "deprecated_api", SEVERITY_HIGH,
        "datetime.utcnow() is deprecated (Python 3.12+) — use datetime.now(datetime.UTC)",
    ),
    (
        re.compile(r"\basyncio\.get_event_loop\(\)"),
        "deprecated_api", SEVERITY_HIGH,
        "asyncio.get_event_loop() is deprecated — use asyncio.get_running_loop() inside async code",
    ),
    (
        re.compile(r"from\s+typing\s+import\b.*\bOptional\b"),
        "deprecated_api", SEVERITY_LOW,
        "typing.Optional[X] is legacy — prefer X | None (Python 3.10+)",
    ),
    (
        re.compile(r"from\s+typing\s+import\b.*\bDict\b"),
        "deprecated_api", SEVERITY_LOW,
        "typing.Dict is legacy — prefer dict[K, V] (Python 3.9+)",
    ),
    (
        re.compile(r"from\s+typing\s+import\b.*\bList\b"),
        "deprecated_api", SEVERITY_LOW,
        "typing.List is legacy — prefer list[T] (Python 3.9+)",
    ),
    (
        re.compile(r"from\s+typing\s+import\b.*\bTuple\b"),
        "deprecated_api", SEVERITY_LOW,
        "typing.Tuple is legacy — prefer tuple[T, ...] (Python 3.9+)",
    ),
]


def _scan_deprecated_apis(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    lines = source.splitlines()
    for i, line in enumerate(lines, 1):
        for pattern, category, severity, detail in _DEPRECATED_PATTERNS:
            if pattern.search(line):
                suggestion = detail.split(" — ", 1)[1] if " — " in detail else "Upgrade to modern equivalent"
                ops.append(Opportunity(
                    category, severity, rel, i,
                    detail.split(" — ", 1)[0],
                    suggestion,
                ))
    return ops


# ── Category 3: TODO/FIXME markers ───────────────────────────────────────────

_TODO_RE = re.compile(r"#.*\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)", re.I)


def _scan_todo_fixme(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    for i, line in enumerate(source.splitlines(), 1):
        m = _TODO_RE.search(line)
        if m:
            tag = m.group(1).upper()
            note = m.group(2).strip()
            severity = SEVERITY_CRITICAL if tag in ("BUG", "FIXME") else SEVERITY_MEDIUM
            ops.append(Opportunity(
                "todo_fixme", severity, rel, i,
                f"{tag}: {note}" if note else tag,
                "Resolve or create a tracked task for this item",
            ))
    return ops


# ── Category 4: Long functions ────────────────────────────────────────────────

_LONG_FUNCTION_THRESHOLD = 80   # lines


def _scan_long_functions(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = node.end_lineno or start
        length = end - start + 1
        if length > _LONG_FUNCTION_THRESHOLD:
            ops.append(Opportunity(
                "long_function", SEVERITY_MEDIUM, rel, start,
                f"`{node.name}()` is {length} lines (threshold: {_LONG_FUNCTION_THRESHOLD})",
                "Break into smaller focused functions — aim for under 50 lines per function",
            ))
    return ops


# ── Category 5: Hardcoded timeouts / magic limits ────────────────────────────

_HARDCODED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\btimeout\s*=\s*(\d{2,})\b"), "hardcoded timeout value"),
    (re.compile(r"\bmax_retries\s*=\s*\d+\b"), "hardcoded retry count"),
    (re.compile(r"\btime\.sleep\(\d+\)"), "hardcoded sleep duration"),
    (re.compile(r"\blimit\s*=\s*([1-9]\d{2,})\b"), "hardcoded large limit (consider env var)"),
]


def _scan_hardcoded_values(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern, label in _HARDCODED_PATTERNS:
            if pattern.search(line):
                ops.append(Opportunity(
                    "hardcoded_value", SEVERITY_LOW, rel, i,
                    f"{label}: `{stripped[:80]}`",
                    "Extract to a named constant or environment variable",
                ))
                break   # one finding per line
    return ops


# ── Category 6: Missing logging in except blocks ──────────────────────────────
# except SomeError as e: ... but 'e' / 'exc' never used (captured but discarded)

_EXCEPT_AS_RE = re.compile(r"^\s*except\b.*\bas\s+(\w+)\s*:", re.MULTILINE)


def _scan_missing_logging(path: Path, source: str) -> list[Opportunity]:
    ops: list[Opportunity] = []
    rel = _rel(path)
    lines = source.splitlines()

    for m in _EXCEPT_AS_RE.finditer(source):
        var = m.group(1)
        lineno = source[: m.start()].count("\n") + 1

        # Collect the except block body (next lines until dedent)
        indent_match = re.match(r"^(\s*)", lines[lineno - 1])
        base_indent = len(indent_match.group(1)) if indent_match else 0
        block_lines: list[str] = []
        for j in range(lineno, min(lineno + 10, len(lines))):
            l = lines[j]
            if l.strip() == "":
                continue
            line_indent = len(l) - len(l.lstrip())
            if line_indent <= base_indent and l.strip():
                break
            block_lines.append(l)

        block_text = "\n".join(block_lines)
        # If the variable is never referenced in the block body
        if var not in block_text and block_text.strip() not in ("", "pass"):
            ops.append(Opportunity(
                "missing_logging", SEVERITY_LOW, rel, lineno,
                f"Exception captured as `{var}` but never logged or used in except block",
                f"Add `log.warning('...', exc_info=True)` or reference `{var}` in the handler",
            ))
    return ops


# ── Scanner orchestrator ──────────────────────────────────────────────────────

_SCANNERS = [
    ("silent_failure",  _scan_silent_failures,  False),   # (name, fn, tests_only)
    ("deprecated_api",  _scan_deprecated_apis,  False),
    ("todo_fixme",      _scan_todo_fixme,        False),   # runs on test files too
    ("long_function",   _scan_long_functions,    False),
    ("hardcoded_value", _scan_hardcoded_values,  False),
    ("missing_logging", _scan_missing_logging,   False),
]


def scan(critical_only: bool = False) -> ScanResult:
    """
    Scan the codebase for upgrade opportunities.

    Args:
        critical_only: If True, only return CRITICAL and HIGH severity findings.

    Returns:
        ScanResult with .opportunities, .files_scanned, .report, .summary().
    """
    files = _collect_files()
    all_ops: list[Opportunity] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        is_test = _is_test_file(path)

        for cat_name, scanner_fn, _ in _SCANNERS:
            # Skip non-todo scans on test files (different standards apply)
            if is_test and cat_name not in _TESTS_ONLY_CATEGORIES:
                if cat_name != "todo_fixme":
                    continue
            ops = scanner_fn(path, source)
            all_ops.extend(ops)

    if critical_only:
        all_ops = [o for o in all_ops if o.severity in (SEVERITY_CRITICAL, SEVERITY_HIGH)]

    # Sort: severity first, then file, then line
    all_ops.sort(key=lambda o: (_SEVERITY_ORDER[o.severity], o.file, o.line))

    result = ScanResult(opportunities=all_ops, files_scanned=len(files))
    result.report = _build_report(result, critical_only)
    return result


# ── Report builder ────────────────────────────────────────────────────────────

_CATEGORY_META: dict[str, tuple[str, str]] = {
    "silent_failure":  ("Silent Failures",          "Errors swallowed silently — hide bugs in production"),
    "deprecated_api":  ("Deprecated APIs",           "Will break or warn in future Python versions"),
    "todo_fixme":      ("TODO / FIXME Markers",      "Explicit unresolved tech debt"),
    "long_function":   ("Long Functions",            "Functions over 80 lines — hard to test and maintain"),
    "hardcoded_value": ("Hardcoded Values",          "Magic numbers/timeouts that should be configurable"),
    "missing_logging": ("Missing Exception Logging", "Captured exceptions never logged or used"),
}

_SEVERITY_ICON = {
    SEVERITY_CRITICAL: "[CRITICAL]",
    SEVERITY_HIGH:     "[HIGH]",
    SEVERITY_MEDIUM:   "[MEDIUM]",
    SEVERITY_LOW:      "[LOW]",
}


def _build_report(result: ScanResult, critical_only: bool) -> str:
    lines = [
        "# Upgrade Opportunity Scanner",
        "",
        f"**{result.summary()}**",
        "",
    ]

    if critical_only:
        lines.append("_Showing CRITICAL and HIGH only (`--critical-only` flag active)_")
        lines.append("")

    # Summary table
    lines += ["## Summary by Category", "", f"{'Category':<30} {'Count':>6}  Severity", "-" * 55]
    categories_seen = sorted({o.category for o in result.opportunities},
                             key=lambda c: min(_SEVERITY_ORDER[o.severity]
                                               for o in result.opportunities if o.category == c))
    for cat in categories_seen:
        items = [o for o in result.opportunities if o.category == cat]
        worst = min(items, key=lambda o: _SEVERITY_ORDER[o.severity]).severity
        label = _CATEGORY_META.get(cat, (cat, ""))[0]
        lines.append(f"{label:<30} {len(items):>6}  {worst}")
    lines.append("")

    # Detail sections
    lines.append("---")
    lines.append("")

    for cat in categories_seen:
        items = [o for o in result.opportunities if o.category == cat]
        if not items:
            continue
        label, description = _CATEGORY_META.get(cat, (cat, ""))
        worst = min(items, key=lambda o: _SEVERITY_ORDER[o.severity]).severity
        icon = _SEVERITY_ICON[worst]
        lines += [f"## {icon} {label} ({len(items)})", "", f"_{description}_", ""]
        for o in items:
            sev = _SEVERITY_ICON[o.severity]
            lines.append(f"- {sev} `{o.file}:{o.line}` — {o.detail}")
            lines.append(f"  - Fix: {o.suggestion}")
        lines.append("")

    if not result.opportunities:
        lines += ["## No Opportunities Found", "", "Codebase is clean across all scanned categories.", ""]

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Force UTF-8 stdout on Windows to avoid cp1252 encoding errors in source snippets
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    as_json      = "--json"          in args
    critical_only = "--critical-only" in args
    out_arg = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            out_arg = Path(args[idx + 1])

    result = scan(critical_only=critical_only)

    if as_json:
        print(json.dumps({
            "files_scanned": result.files_scanned,
            "summary":       result.summary(),
            "opportunities": [
                {
                    "category":   o.category,
                    "severity":   o.severity,
                    "file":       o.file,
                    "line":       o.line,
                    "detail":     o.detail,
                    "suggestion": o.suggestion,
                }
                for o in result.opportunities
            ],
        }, indent=2))
    else:
        print(result.report)

    out_path = out_arg or (_ROOT / "atlas_vault" / "03-Outputs" / "upgrade_opportunities.md")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.report, encoding="utf-8")
        if not as_json:
            print(f"\nReport written to: {out_path}")
    except Exception as exc:
        print(f"Warning: could not write report -- {exc}", file=sys.stderr)

    sys.exit(0)
