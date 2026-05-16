"""
export_markdown_report.py — Safe, deterministic markdown report exporter.

No external APIs. No API keys. Fully local and deterministic.
Exports report text to a markdown file under a safe output directory.

Usage:
  python export_markdown_report.py --text "...report text..." --filename report.md
  python export_markdown_report.py --file input.txt --filename output.md
  python export_markdown_report.py --file input.txt  # auto-names output file
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


# Output files go here only — never to arbitrary paths
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[5] / "atlas_vault" / "03-Outputs"

# Characters forbidden in output filenames
_UNSAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


@dataclass
class ExportResult:
    success: bool
    output_path: str = ""
    error: str = ""

    def summary(self) -> str:
        if self.success:
            return f"EXPORTED: {self.output_path}"
        return f"EXPORT FAILED: {self.error}"


def _safe_filename(name: str) -> str:
    """Strip unsafe characters from a filename."""
    safe = _UNSAFE_FILENAME_RE.sub("_", name)
    return safe[:200] or "report"


def export(
    text: str,
    filename: str | None = None,
    output_dir: str | Path | None = None,
) -> ExportResult:
    """
    Export report text to a markdown file.

    Args:
        text: The report text to export.
        filename: Optional output filename. Auto-generated if omitted.
        output_dir: Directory to write to. Defaults to atlas_vault/03-Outputs/.

    Returns:
        ExportResult with .success and .output_path.
    """
    if not isinstance(text, str) or not text.strip():
        return ExportResult(success=False, error="Empty or invalid report text")

    out_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ExportResult(success=False, error=f"Cannot create output directory: {exc}")

    if filename:
        safe_name = _safe_filename(filename)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"report_{ts}.md"

    out_path = out_dir / safe_name

    # Safety check: resolved path must still be inside out_dir
    try:
        out_path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        return ExportResult(success=False, error="Path traversal detected — export refused")

    try:
        out_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return ExportResult(success=False, error=f"Write failed: {exc}")

    return ExportResult(success=True, output_path=str(out_path))


def _parse_args(args: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    i = 0
    while i < len(args):
        if args[i] in ("--text", "--file", "--filename", "--output-dir") and i + 1 < len(args):
            result[args[i].lstrip("-").replace("-", "_")] = args[i + 1]
            i += 2
        else:
            i += 1
    return result


if __name__ == "__main__":
    parsed = _parse_args(sys.argv[1:])
    if not parsed:
        print("Usage: python export_markdown_report.py --text <text> [--filename <name.md>]")
        print("       python export_markdown_report.py --file <input.txt> [--filename <name.md>]")
        sys.exit(0)

    if "file" in parsed:
        try:
            text = Path(parsed["file"]).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        text = parsed.get("text", "")

    result = export(
        text=text,
        filename=parsed.get("filename"),
        output_dir=parsed.get("output_dir"),
    )
    print(result.summary())
    sys.exit(0 if result.success else 1)
