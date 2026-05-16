"""
test_fragility_scan.py — Detects fragile test assertions in the test suite.

A fragile test asserts implementation details that break when the code is
correctly refactored. Common patterns we've been burned by:

  - Asserting exact hex colors ("#18C6C8") instead of CSS variable names
  - Asserting exact line counts that change with formatting
  - Asserting exact string literals that are intentionally migrated
  - Tests that read .html files and check for presentation-layer strings

This scanner finds these patterns and reports them with context and a
semantic alternative suggestion.

Usage:
    python omega_os/skills/test_contract_guard/tools/test_fragility_scan.py
    python omega_os/skills/test_contract_guard/tools/test_fragility_scan.py --fix-hints
    python omega_os/skills/test_contract_guard/tools/test_fragility_scan.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT  = Path(__file__).parent.parent.parent.parent.parent
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT))


@dataclass
class FragileMatch:
    file: str
    line: int
    pattern_name: str
    matched_text: str
    suggestion: str
    severity: str   # "high" | "medium" | "low"


# ── Fragile pattern definitions ───────────────────────────────────────────────

PATTERNS: list[tuple[str, str, str, str]] = [
    # (pattern_name, regex, severity, suggestion)
    (
        "hex_color_assertion",
        r'["\']#[0-9A-Fa-f]{6}["\'].*\bin\b.*\b(read_text|html|text|content|auth)\b',
        "high",
        "Use a CSS variable name or brand comment token: "
        "'var(--color-accent)' or '/* Brand accent: #18C6C8 */' — "
        "hex colors move when the design system is updated.",
    ),
    (
        "hardcoded_line_count",
        r'assert\s+len\(.*\.splitlines\(\)\)\s*[<>=!]=?\s*\d+',
        "medium",
        "Line count assertions break on any formatting change. "
        "Assert semantic content ('Branch' in output) instead of exact line count.",
    ),
    (
        "exact_version_string",
        r'assert\s+["\'][\d\.]+["\']',
        "low",
        "Version string assertions break on every release. "
        "Assert the key is present or use >= comparison.",
    ),
    (
        "magic_number_test_count",
        r'assert\s+\w*count\w*\s*[><=!]=?\s*[2-9]\d{2,}',
        "medium",
        "Hard-coded test count baselines (e.g. >= 1397) drift every time a "
        "test is added or removed. Use a relative check or the BASELINE constant "
        "from dev_session_guard/contract.json.",
    ),
    (
        "implementation_detail_string",
        r'assert\s+["\'](?:option1|/option1)["\'].*\bin\b',
        "high",
        "'/option1' is a legacy redirect alias. Assert the semantic destination "
        "('/command-center') instead of the intermediate redirect.",
    ),
    (
        "raw_css_property_assertion",
        r'assert\s+["\'](?:background|color|border|font-size|padding):\s*[^;]+;["\'].*\bin\b',
        "medium",
        "Asserting raw CSS property strings breaks when styles are refactored. "
        "Assert the CSS variable name instead (e.g. 'var(--color-accent)').",
    ),
]


# ── Scanner ───────────────────────────────────────────────────────────────────

def scan_tests() -> list[FragileMatch]:
    matches: list[FragileMatch] = []
    if not TESTS.exists():
        return matches

    compiled = [(name, re.compile(pat, re.IGNORECASE), sev, sug)
                for name, pat, sev, sug in PATTERNS]

    for test_file in sorted(TESTS.glob("test_*.py")):
        try:
            lines = test_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for name, pat, severity, suggestion in compiled:
                if pat.search(stripped):
                    matches.append(FragileMatch(
                        file=test_file.name,
                        line=lineno,
                        pattern_name=name,
                        matched_text=stripped[:100],
                        suggestion=suggestion,
                        severity=severity,
                    ))

    return matches


def print_report(matches: list[FragileMatch], fix_hints: bool = False) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep = "=" * 72

    by_file: dict[str, list[FragileMatch]] = {}
    for m in matches:
        by_file.setdefault(m.file, []).append(m)

    high   = [m for m in matches if m.severity == "high"]
    medium = [m for m in matches if m.severity == "medium"]
    low    = [m for m in matches if m.severity == "low"]

    print(sep)
    print("  R.A. OMEGA — TEST FRAGILITY SCAN")
    print(sep)
    print(f"\n  {len(matches)} fragile patterns detected  "
          f"({len(high)} high  {len(medium)} medium  {len(low)} low)")
    print(f"  across {len(by_file)} test files\n")

    severity_order = {"high": 0, "medium": 1, "low": 2}
    for fname, file_matches in sorted(by_file.items()):
        file_matches.sort(key=lambda m: (severity_order[m.severity], m.line))
        print(f"  {fname}")
        for m in file_matches:
            icon = "[HI]" if m.severity == "high" else "[MD]" if m.severity == "medium" else "[LO]"
            print(f"    {icon}  line {m.line:>4}  {m.pattern_name}")
            print(f"           {m.matched_text[:80]}")
            if fix_hints:
                print(f"           FIX: {m.suggestion[:90]}")
        print()

    print(sep)
    if not matches:
        print("  RESULT: PASS — no fragile test patterns detected")
    elif high:
        print(f"  RESULT: {len(high)} high-severity fragile tests — address before next release")
    else:
        print(f"  RESULT: {len(medium)} medium + {len(low)} low — review when refactoring those areas")
    print("  Run with --fix-hints to see suggested fixes for each pattern.")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(description="Omega OS test fragility scanner")
    parser.add_argument("--fix-hints",  action="store_true", help="Print fix suggestions")
    parser.add_argument("--json",       action="store_true", help="Output JSON")
    parser.add_argument("--high-only",  action="store_true", help="Report high severity only")
    args = parser.parse_args()

    matches = scan_tests()
    if args.high_only:
        matches = [m for m in matches if m.severity == "high"]

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps([
            {
                "file":         m.file,
                "line":         m.line,
                "pattern":      m.pattern_name,
                "severity":     m.severity,
                "matched_text": m.matched_text,
                "suggestion":   m.suggestion,
            }
            for m in matches
        ], indent=2))
    else:
        print_report(matches, fix_hints=args.fix_hints)


if __name__ == "__main__":
    main()
