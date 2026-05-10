"""
C1 — Code Optimizer Agent  (Cognitive Division)
================================================
Structural job: read Python source files and surface concrete async /
performance upgrade suggestions without executing the code.

Outputs a dict written to data_cache/code_optimizer_latest.json:
  {
    "generated_at": "<ISO-Z>",
    "files_analyzed": 3,
    "total_issues": 12,
    "reports": [
      {
        "file": "atlas_omega.py",
        "issues": [
          {
            "line": 450,
            "rule": "SYNC_IO_IN_HANDLER",
            "severity": "HIGH",
            "snippet": "json.loads(path.read_text(...))",
            "suggestion": "Wrap in asyncio.to_thread() or use aiofiles"
          }, ...
        ]
      }
    ],
    "source": "code_optimizer_static_analysis"
  }

Rules detected
--------------
SYNC_IO_IN_HANDLER      — blocking file read inside a sync def called from async context
SYNC_HTTP_IN_HANDLER    — requests.get/post inside sync def, blocks event loop
MISSING_TIMEOUT         — requests.get/post without timeout= kwarg
THREADPOOL_OVERKILL     — ThreadPoolExecutor spun up inside a hot path per-call
BROAD_EXCEPT            — bare `except Exception` swallowing errors silently
UNTYPED_RETURN          — public function missing return type annotation
MISSING_CACHE_GUARD     — repeated file.read() on same path within one function
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── output ──────────────────────────────────────────────────────────────────
_CACHE_FILE = "code_optimizer_latest.json"


def _data_cache_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data_cache"
        if candidate.is_dir():
            return candidate
    # fallback: create next to project root guess
    root = here.parents[3]
    d = root / "data_cache"
    d.mkdir(exist_ok=True)
    return d


# ── issue model ──────────────────────────────────────────────────────────────
@dataclass
class Issue:
    line: int
    rule: str
    severity: str          # HIGH | MEDIUM | LOW
    snippet: str
    suggestion: str


@dataclass
class FileReport:
    file: str
    issues: list[Issue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"file": self.file, "issues": [asdict(i) for i in self.issues]}


# ── rule detectors (AST + regex) ─────────────────────────────────────────────

_SYNC_IO_PATTERNS = re.compile(
    r"(?:"
    r"\bopen\("                          # open(
    r"|\.read_text\("                    # any_var.read_text(
    r"|\.write_text\("                   # any_var.write_text(
    r"|\.read_bytes\("                   # any_var.read_bytes(
    r"|\.write_bytes\("                  # any_var.write_bytes(
    r"|\.read\(\)"                       # file.read()
    r"|\.write\("                        # file.write(
    r")"
)
_SYNC_HTTP_PATTERNS = re.compile(r"\brequests\.(get|post|put|delete|patch)\b")
_TIMEOUT_ABSENT = re.compile(r"requests\.(get|post|put|delete|patch)\([^)]*\)")
_HAS_TIMEOUT = re.compile(r"timeout\s*=")


def _analyze_source(path: Path) -> FileReport:
    report = FileReport(file=str(path))
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        report.issues.append(Issue(
            line=0, rule="READ_ERROR", severity="HIGH",
            snippet="", suggestion=str(exc),
        ))
        return report

    lines = source.splitlines()

    # ── AST pass ─────────────────────────────────────────────────────────────
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        report.issues.append(Issue(
            line=0, rule="SYNTAX_ERROR", severity="HIGH",
            snippet="", suggestion="File has syntax errors — fix before optimizing.",
        ))
        return report

    _ast_checks(tree, lines, report)

    # ── regex pass ───────────────────────────────────────────────────────────
    _regex_checks(lines, report)

    # dedupe by (line, rule)
    seen: set[tuple[int, str]] = set()
    deduped: list[Issue] = []
    for iss in report.issues:
        key = (iss.line, iss.rule)
        if key not in seen:
            seen.add(key)
            deduped.append(iss)
    report.issues = sorted(deduped, key=lambda i: i.line)
    return report


def _ast_checks(tree: ast.Module, lines: list[str], report: FileReport) -> None:
    """Walk the AST and detect structural anti-patterns."""

    for node in ast.walk(tree):

        # BROAD_EXCEPT — bare `except Exception as e: pass / log only`
        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (
                isinstance(node.type, ast.Name) and node.type.id == "Exception"
            ):
                body_nodes = node.body
                # flag if body is only pass / raise / log
                if all(
                    isinstance(n, (ast.Pass, ast.Raise, ast.Expr)) for n in body_nodes
                ):
                    snippet = _get_line(lines, node.lineno)
                    report.issues.append(Issue(
                        line=node.lineno,
                        rule="BROAD_EXCEPT",
                        severity="LOW",
                        snippet=snippet,
                        suggestion=(
                            "Narrow the exception type (e.g. json.JSONDecodeError, OSError) "
                            "and log the full traceback rather than silently swallowing."
                        ),
                    ))

        # THREADPOOL_OVERKILL — ThreadPoolExecutor inside a function body
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                ctx = item.context_expr
                if (
                    isinstance(ctx, ast.Call)
                    and isinstance(ctx.func, ast.Attribute)
                    and ctx.func.attr == "ThreadPoolExecutor"
                ):
                    snippet = _get_line(lines, node.lineno)
                    report.issues.append(Issue(
                        line=node.lineno,
                        rule="THREADPOOL_OVERKILL",
                        severity="MEDIUM",
                        snippet=snippet,
                        suggestion=(
                            "Creating ThreadPoolExecutor per-call is expensive. "
                            "Hoist to module-level or use asyncio.to_thread() for I/O-bound work."
                        ),
                    ))

        # UNTYPED_RETURN — public functions without return annotation
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_") and node.returns is None:
                snippet = _get_line(lines, node.lineno)
                report.issues.append(Issue(
                    line=node.lineno,
                    rule="UNTYPED_RETURN",
                    severity="LOW",
                    snippet=snippet,
                    suggestion=(
                        f"Add a return type annotation to `{node.name}()` "
                        "to improve IDE support and catch type errors early."
                    ),
                ))


def _regex_checks(lines: list[str], report: FileReport) -> None:
    """Line-by-line regex checks."""
    path_reads_seen: dict[str, int] = {}

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # SYNC_IO_IN_HANDLER
        if _SYNC_IO_PATTERNS.search(stripped):
            report.issues.append(Issue(
                line=i, rule="SYNC_IO_IN_HANDLER", severity="HIGH",
                snippet=stripped[:120],
                suggestion=(
                    "Blocking file I/O inside a sync function called from FastAPI blocks the "
                    "event loop. Wrap with `asyncio.to_thread(lambda: ...)` or use `aiofiles`."
                ),
            ))

        # SYNC_HTTP_IN_HANDLER + MISSING_TIMEOUT
        if _SYNC_HTTP_PATTERNS.search(stripped):
            report.issues.append(Issue(
                line=i, rule="SYNC_HTTP_IN_HANDLER", severity="HIGH",
                snippet=stripped[:120],
                suggestion=(
                    "requests.* is blocking. Replace with `httpx.AsyncClient` or move "
                    "to a background thread via `asyncio.to_thread()`."
                ),
            ))
            # also check for missing timeout
            m = _TIMEOUT_ABSENT.search(stripped)
            if m and not _HAS_TIMEOUT.search(stripped):
                report.issues.append(Issue(
                    line=i, rule="MISSING_TIMEOUT", severity="MEDIUM",
                    snippet=stripped[:120],
                    suggestion="Add timeout=10 (seconds) to prevent indefinite hangs.",
                ))

        # MISSING_CACHE_GUARD — same read_text call on same variable twice
        m2 = re.search(r"(\w+)\.read_text\(", stripped)
        if m2:
            var = m2.group(1)
            if var in path_reads_seen:
                report.issues.append(Issue(
                    line=i, rule="MISSING_CACHE_GUARD", severity="MEDIUM",
                    snippet=stripped[:120],
                    suggestion=(
                        f"`{var}.read_text()` called more than once in this scope. "
                        "Read once into a variable and reuse."
                    ),
                ))
            else:
                path_reads_seen[var] = i


def _get_line(lines: list[str], lineno: int) -> str:
    try:
        return lines[lineno - 1].strip()[:120]
    except IndexError:
        return ""


# ── public API ───────────────────────────────────────────────────────────────

def analyze_files(paths: list[Path]) -> dict:
    """
    Analyze a list of Python files and return a structured report dict.
    Also writes data_cache/code_optimizer_latest.json.
    """
    reports: list[FileReport] = []
    for p in paths:
        if p.suffix != ".py":
            continue
        reports.append(_analyze_source(p))

    total_issues = sum(len(r.issues) for r in reports)
    high = sum(
        1 for r in reports for iss in r.issues if iss.severity == "HIGH"
    )
    medium = sum(
        1 for r in reports for iss in r.issues if iss.severity == "MEDIUM"
    )
    low = sum(
        1 for r in reports for iss in r.issues if iss.severity == "LOW"
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files_analyzed": len(reports),
        "total_issues": total_issues,
        "severity_summary": {"HIGH": high, "MEDIUM": medium, "LOW": low},
        "reports": [r.to_dict() for r in reports],
        "source": "code_optimizer_static_analysis",
    }

    out = _data_cache_root() / _CACHE_FILE
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def analyze_project_root(root: Optional[Path] = None, max_files: int = 20) -> dict:
    """
    Convenience: scan the top-level *.py files of the project root.
    Skips __pycache__, .venv, node_modules.
    """
    if root is None:
        here = Path(__file__).resolve()
        root = here.parents[3]  # atlas_agents/../../../  → project root

    skip = {"__pycache__", ".venv", "venv", "node_modules", ".git"}
    py_files: list[Path] = []
    for p in sorted(root.glob("*.py")):
        if p.stem not in skip:
            py_files.append(p)
        if len(py_files) >= max_files:
            break

    return analyze_files(py_files)


if __name__ == "__main__":
    result = analyze_project_root()
    print(
        f"Analyzed {result['files_analyzed']} files — "
        f"{result['total_issues']} issues "
        f"(HIGH={result['severity_summary']['HIGH']}, "
        f"MEDIUM={result['severity_summary']['MEDIUM']}, "
        f"LOW={result['severity_summary']['LOW']})"
    )
    print(f"Report → data_cache/{_CACHE_FILE}")
