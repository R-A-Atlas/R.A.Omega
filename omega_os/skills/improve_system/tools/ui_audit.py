"""
ui_audit.py — ATLAS UI/UX Audit Scanner

Scans all HTML files for common UI problems and scores each file across
5 axes. Produces a ranked report with actionable fixes.

Axes (each 0-100):
  1. design_system_compliance  — CSS token usage, design_system.css import
  2. accessibility             — alt text, labels, ARIA, contrast hints
  3. performance               — render-blocking scripts, large inlines, no defer
  4. responsiveness            — mobile viewport meta, media queries
  5. code_quality              — inline style density, hardcoded colors, TODO count

Usage:
    python ui_audit.py [--html-dir PATH] [--json] [--output PATH] [--min-score N]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ── Config ────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.parent.parent.parent  # project root

_HTML_FILES = [
    "ra_omega_app.html",
    "auth.html",
    "index_1778228972988.html",
    "atlas_dashboard_v4.html",
    "omega_brain_network.html",
]

_DESIGN_TOKEN_PROPS = [
    "--color-", "--font-", "--space-", "--radius-", "--shadow-",
    "--node-", "--anim-", "--ease-",
]

_HARDCODED_COLOR_RE = re.compile(
    r"(?:background|color|border|fill|stroke)\s*[:=]\s*"
    r"(?:#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\))",
    re.IGNORECASE,
)

_INLINE_STYLE_RE    = re.compile(r'\bstyle=["\'][^"\']*["\']', re.IGNORECASE)
_TODO_RE            = re.compile(r"TODO|FIXME|HACK|XXX", re.IGNORECASE)
_IMG_NO_ALT_RE      = re.compile(r'<img(?![^>]*\balt\s*=)[^>]*>', re.IGNORECASE)
_INPUT_NO_LABEL_RE  = re.compile(r'<input(?![^>]*(?:aria-label|aria-labelledby|id\s*=))[^>]*>', re.IGNORECASE)
_MEDIA_QUERY_RE     = re.compile(r'@media\s*\([^)]+\)', re.IGNORECASE)
_VIEWPORT_META_RE   = re.compile(r'<meta[^>]+name=["\']viewport["\'][^>]*>', re.IGNORECASE)
_RENDER_BLOCK_RE    = re.compile(r'<script[^>]+src=["\'][^"\']+["\'](?![^>]*(?:defer|async))[^>]*>', re.IGNORECASE)
_LARGE_INLINE_STYLE_RE = re.compile(r'<style[^>]*>([\s\S]*?)</style>', re.IGNORECASE)

_AXIS_WEIGHTS = {
    "design_system_compliance": 0.30,
    "accessibility":            0.20,
    "performance":              0.20,
    "responsiveness":           0.15,
    "code_quality":             0.15,
}


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    axis: str
    severity: str           # "critical" | "warning" | "info"
    message: str
    suggestion: str
    line: int = 0


@dataclass
class FileReport:
    filename: str
    exists: bool
    scores: dict[str, int] = field(default_factory=dict)
    overall: int = 0
    findings: list[Finding] = field(default_factory=list)
    lines: int = 0


# ── Axis scorers ──────────────────────────────────────────────────────────────

def _score_design_system(html: str, filename: str, findings: list[Finding]) -> int:
    score = 50
    has_import = "/design_system.css" in html
    if has_import:
        score += 25
    else:
        findings.append(Finding(
            axis="design_system_compliance", severity="critical",
            message="design_system.css not imported",
            suggestion='Add <link rel="stylesheet" href="/design_system.css"> in <head>',
        ))

    # Count token usages
    token_uses = sum(html.count(tok) for tok in _DESIGN_TOKEN_PROPS)
    if token_uses > 30:
        score += 25
    elif token_uses > 10:
        score += 15
    elif token_uses > 0:
        score += 5
    else:
        findings.append(Finding(
            axis="design_system_compliance", severity="warning",
            message="No CSS token usage detected",
            suggestion="Replace hardcoded hex colors with var(--color-*) tokens from design_system.css",
        ))

    # Duplicate font imports (loaded via design_system.css already)
    if has_import and "fonts.googleapis.com" in html:
        findings.append(Finding(
            axis="design_system_compliance", severity="info",
            message="Duplicate Google Fonts import (already loaded via design_system.css)",
            suggestion="Remove the redundant <link> to fonts.googleapis.com",
        ))
        score = max(score - 5, 0)

    return min(score, 100)


def _score_accessibility(html: str, filename: str, findings: list[Finding]) -> int:
    score = 100
    deductions = 0

    imgs_no_alt = _IMG_NO_ALT_RE.findall(html)
    if imgs_no_alt:
        penalty = min(len(imgs_no_alt) * 8, 30)
        deductions += penalty
        findings.append(Finding(
            axis="accessibility", severity="warning",
            message=f"{len(imgs_no_alt)} <img> elements missing alt attribute",
            suggestion="Add alt='description' or alt='' for decorative images",
        ))

    inputs_no_label = _INPUT_NO_LABEL_RE.findall(html)
    # Filter: skip hidden/submit/button types
    real_inputs = [i for i in inputs_no_label
                   if 'type="hidden"' not in i and "type='hidden'" not in i
                   and 'type="submit"' not in i and 'type="button"' not in i]
    if real_inputs:
        penalty = min(len(real_inputs) * 6, 24)
        deductions += penalty
        findings.append(Finding(
            axis="accessibility", severity="warning",
            message=f"{len(real_inputs)} <input> fields missing label/aria-label",
            suggestion="Add <label for='id'> or aria-label='...' to every form field",
        ))

    # Check for role attributes (positive signal)
    if 'role="' in html or "role='" in html:
        deductions = max(deductions - 5, 0)

    # lang on <html>
    if '<html' in html and 'lang="' not in html and "lang='" not in html:
        deductions += 5
        findings.append(Finding(
            axis="accessibility", severity="info",
            message="<html> element missing lang attribute",
            suggestion='Add lang="en" to <html>',
        ))

    return max(score - deductions, 0)


def _score_performance(html: str, filename: str, findings: list[Finding]) -> int:
    score = 100
    deductions = 0

    blocking = _RENDER_BLOCK_RE.findall(html)
    if blocking:
        penalty = min(len(blocking) * 10, 40)
        deductions += penalty
        findings.append(Finding(
            axis="performance", severity="critical" if len(blocking) > 2 else "warning",
            message=f"{len(blocking)} render-blocking <script src=> without defer/async",
            suggestion="Add defer or async to external script tags that are not needed before DOMContentLoaded",
        ))

    # Detect large inline style blocks
    style_blocks = _LARGE_INLINE_STYLE_RE.findall(html)
    large_blocks = [s for s in style_blocks if len(s) > 8000]
    if large_blocks:
        total_kb = sum(len(s) for s in large_blocks) / 1024
        findings.append(Finding(
            axis="performance", severity="info",
            message=f"{len(large_blocks)} inline <style> blocks totaling {total_kb:.0f} KB",
            suggestion="Consider moving large style blocks to external CSS files for caching",
        ))
        deductions += min(len(large_blocks) * 5, 15)

    # Unbundled CDN scripts
    cdn_scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\']', html)
    if len(cdn_scripts) > 5:
        findings.append(Finding(
            axis="performance", severity="info",
            message=f"{len(cdn_scripts)} external CDN scripts loaded",
            suggestion="Bundle frequently-used libraries to reduce network round trips",
        ))
        deductions += 5

    return max(score - deductions, 0)


def _score_responsiveness(html: str, filename: str, findings: list[Finding]) -> int:
    score = 0

    has_viewport = bool(_VIEWPORT_META_RE.search(html))
    if has_viewport:
        score += 50
    else:
        findings.append(Finding(
            axis="responsiveness", severity="critical",
            message="Missing <meta name='viewport'> tag",
            suggestion='Add <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        ))

    media_queries = len(_MEDIA_QUERY_RE.findall(html))
    if media_queries >= 3:
        score += 40
    elif media_queries >= 1:
        score += 25
        findings.append(Finding(
            axis="responsiveness", severity="info",
            message=f"Only {media_queries} media query/queries found",
            suggestion="Add breakpoints for at least mobile (≤640px), tablet (≤900px), and desktop",
        ))
    else:
        score += 0
        findings.append(Finding(
            axis="responsiveness", severity="warning",
            message="No @media queries found",
            suggestion="Add responsive breakpoints — layout may break on small screens",
        ))

    # Tailwind or flex/grid signals
    responsive_signals = sum([
        "flex" in html, "grid" in html, "sm:" in html, "md:" in html,
        "lg:" in html, "max-w-" in html,
    ])
    if responsive_signals >= 3:
        score += 10

    return min(score, 100)


def _score_code_quality(html: str, filename: str, findings: list[Finding]) -> int:
    score = 100
    deductions = 0

    # Hardcoded colors in style attributes
    hardcoded = _HARDCODED_COLOR_RE.findall(html)
    if hardcoded:
        penalty = min(len(hardcoded) * 2, 30)
        deductions += penalty
        findings.append(Finding(
            axis="code_quality", severity="warning",
            message=f"{len(hardcoded)} hardcoded color values found",
            suggestion="Replace with CSS custom properties from design_system.css",
        ))

    # Inline styles
    inline_styles = len(_INLINE_STYLE_RE.findall(html))
    if inline_styles > 50:
        penalty = min((inline_styles - 50) // 10 * 3, 20)
        deductions += penalty
        findings.append(Finding(
            axis="code_quality", severity="info",
            message=f"{inline_styles} inline style= attributes (high density)",
            suggestion="Extract repeated inline styles into CSS classes",
        ))

    # TODOs
    todos = len(_TODO_RE.findall(html))
    if todos:
        deductions += min(todos * 3, 15)
        findings.append(Finding(
            axis="code_quality", severity="info",
            message=f"{todos} TODO/FIXME comments",
            suggestion="Resolve or track these in the issue tracker",
        ))

    # Duplicate IDs (basic check)
    ids = re.findall(r'\bid=["\']([^"\']+)["\']', html)
    seen_ids: set[str] = set()
    dupes: set[str] = set()
    for id_val in ids:
        if id_val in seen_ids:
            dupes.add(id_val)
        seen_ids.add(id_val)
    if dupes:
        deductions += min(len(dupes) * 5, 20)
        findings.append(Finding(
            axis="code_quality", severity="critical",
            message=f"Duplicate IDs: {', '.join(sorted(dupes)[:5])}{'…' if len(dupes) > 5 else ''}",
            suggestion="IDs must be unique per document",
        ))

    return max(score - deductions, 0)


# ── Per-file audit ─────────────────────────────────────────────────────────────

def audit_file(filepath: Path) -> FileReport:
    report = FileReport(filename=filepath.name, exists=filepath.is_file())
    if not report.exists:
        report.findings.append(Finding(
            axis="code_quality", severity="critical",
            message=f"{filepath.name} does not exist",
            suggestion="Create the file or remove the reference from the audit list",
        ))
        report.overall = 0
        return report

    html = filepath.read_text(encoding="utf-8", errors="replace")
    report.lines = html.count("\n") + 1
    findings: list[Finding] = []

    scores = {
        "design_system_compliance": _score_design_system(html, filepath.name, findings),
        "accessibility":            _score_accessibility(html, filepath.name, findings),
        "performance":              _score_performance(html, filepath.name, findings),
        "responsiveness":           _score_responsiveness(html, filepath.name, findings),
        "code_quality":             _score_code_quality(html, filepath.name, findings),
    }

    overall = int(sum(scores[ax] * w for ax, w in _AXIS_WEIGHTS.items()))
    report.scores  = scores
    report.overall = overall
    report.findings = sorted(findings, key=lambda f: {"critical": 0, "warning": 1, "info": 2}[f.severity])
    return report


# ── Aggregator ────────────────────────────────────────────────────────────────

def run_audit(html_dir: Path | None = None) -> list[FileReport]:
    base = html_dir or _ROOT
    files = [base / f for f in _HTML_FILES]
    return [audit_file(f) for f in files]


# ── Report formatting ──────────────────────────────────────────────────────────

_GRADE = {range(90, 101): "A", range(80, 90): "B", range(70, 80): "C",
          range(60, 70): "D", range(0, 60): "F"}

def _grade(score: int) -> str:
    for r, g in _GRADE.items():
        if score in r:
            return g
    return "F"


_SEV_ICON = {"critical": "[!]", "warning": "[~]", "info": "[i]"}
_SEV_LINE = {"critical": "CRITICAL", "warning": "WARNING ", "info": "INFO    "}


def format_report(reports: list[FileReport], min_score: int = 0) -> str:
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  ATLAS UI/UX AUDIT REPORT")
    lines.append("=" * 72)
    lines.append("")

    filtered = [r for r in reports if r.overall >= min_score or not r.exists]

    # Summary table
    lines.append(f"  {'File':<36} {'Score':>5} {'Grade':>5}  {'Issues':>6}")
    lines.append(f"  {'-'*36} {'-'*5} {'-'*5}  {'-'*6}")
    for r in sorted(filtered, key=lambda x: x.overall, reverse=True):
        issues = len([f for f in r.findings if f.severity in ("critical", "warning")])
        exists_mark = "" if r.exists else " (missing)"
        lines.append(f"  {r.filename + exists_mark:<36} {r.overall:>5}  {_grade(r.overall):>4}   {issues:>5}")

    # Axis breakdown
    lines.append("")
    lines.append("  Axis Scores")
    lines.append(f"  {'File':<28} {'DS':>5} {'A11y':>5} {'Perf':>5} {'Resp':>5} {'Code':>5}")
    lines.append(f"  {'-'*28} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
    for r in sorted(filtered, key=lambda x: x.overall, reverse=True):
        if not r.exists:
            continue
        s = r.scores
        lines.append(
            f"  {r.filename:<28}"
            f" {s.get('design_system_compliance', 0):>5}"
            f" {s.get('accessibility', 0):>5}"
            f" {s.get('performance', 0):>5}"
            f" {s.get('responsiveness', 0):>5}"
            f" {s.get('code_quality', 0):>5}"
        )

    lines.append("")
    lines.append("  DS=DesignSystem A11y=Accessibility Perf=Performance Resp=Responsiveness Code=Quality")

    # Per-file findings
    for r in sorted(filtered, key=lambda x: x.overall):
        if not r.findings:
            continue
        lines.append("")
        lines.append(f"  -- {r.filename}  [{r.overall}/100 {_grade(r.overall)}] --")
        for f in r.findings:
            lines.append(f"    {_SEV_LINE[f.severity]}  {f.message}")
            lines.append(f"             Fix: {f.suggestion}")

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="ATLAS UI/UX Audit Scanner")
    parser.add_argument("--html-dir", type=Path, default=None,
                        help="Root directory containing HTML files (default: project root)")
    parser.add_argument("--json",      action="store_true", help="Output JSON instead of text")
    parser.add_argument("--output",    type=Path, default=None, help="Write report to file")
    parser.add_argument("--min-score", type=int,  default=0,
                        help="Only show files with score < N (0 = show all)")
    args = parser.parse_args()

    reports = run_audit(args.html_dir)

    if args.json:
        payload = [
            {
                "filename":  r.filename,
                "exists":    r.exists,
                "overall":   r.overall,
                "grade":     _grade(r.overall),
                "lines":     r.lines,
                "scores":    r.scores,
                "findings":  [asdict(f) for f in r.findings],
            }
            for r in reports
        ]
        out = json.dumps(payload, indent=2)
    else:
        out = format_report(reports, min_score=args.min_score)

    print(out)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"\n  Report saved -> {args.output}")


if __name__ == "__main__":
    main()
