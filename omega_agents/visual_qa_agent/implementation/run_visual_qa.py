"""
run_visual_qa.py — Safe stub for the visual_qa_agent worker.

Scans known UI files and produces a structured visual QA report listing
what to check manually. Does not open browsers or take screenshots.
Output is returned as a string and optionally written to atlas_vault/03-Outputs/.

No external APIs. No API keys. No broker actions. No email sends.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"

_UI_FILES = [
    "ra_omega_app.html",
    "auth.html",
    "index_1778228972988.html",
    "atlas_dashboard_v4.html",
]

_CHECKLIST = [
    "StructuredResponse cards render on agent rows",
    "ExportBar shows Copy JSON + Listen (TTS) buttons",
    "Sessions sidebar: New chat, list, rename, archive, delete",
    "Live market regime chip loads (not hardcoded BULL MARKET)",
    "QuickStatsStrip RYG meters appear on query response",
    "Sign Out button visible in /option1 header",
    "Auth guard: /option1 redirects to /auth when no token",
    "POST /query returns final_report with all required keys",
    "POST /omega returns correct envelope shape",
    "Mobile layout: no horizontal overflow on /app",
]


@dataclass
class VisualQAResult:
    success: bool
    report: str = ""
    ui_files_found: list[str] = field(default_factory=list)
    ui_files_missing: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    error: str = ""


def run(write_output: bool = False) -> VisualQAResult:
    """
    Produce a visual QA checklist report.

    Args:
        write_output: If True, writes report to atlas_vault/03-Outputs/visual_qa_report.md.

    Returns:
        VisualQAResult with .success, .report, .ui_files_found, .ui_files_missing.
    """
    try:
        found = []
        missing = []
        for fname in _UI_FILES:
            path = ROOT / fname
            if path.exists():
                found.append(fname)
            else:
                missing.append(fname)

        lines = [
            "# Visual QA Report",
            "",
            "## UI Files",
            "",
        ]
        if found:
            lines.append("**Present:**")
            for f in found:
                lines.append(f"- ✓ {f}")
        if missing:
            lines.append("")
            lines.append("**Missing:**")
            for f in missing:
                lines.append(f"- ✗ {f}")

        lines += [
            "",
            "## Manual Checklist",
            "",
            "Start server: `uvicorn api_server:app --host 127.0.0.1 --port 8000`",
            "Then verify each item manually:",
            "",
        ]
        for item in _CHECKLIST:
            lines.append(f"- [ ] {item}")

        lines += [
            "",
            "## Instructions",
            "",
            "1. Start the server (see Section 4 in CLAUDE.md).",
            "2. Open http://127.0.0.1:8000/app in browser.",
            "3. Run: `Analyze NVDA — current setup and trade plan`",
            "4. Tick each checklist item above.",
            "5. Screenshot and save to atlas_vault/01-Raw/Screenshots/.",
        ]

        report = "\n".join(lines)

        if write_output:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUTS_DIR / "visual_qa_report.md"
            out_path.write_text(report, encoding="utf-8")

        return VisualQAResult(
            success=True,
            report=report,
            ui_files_found=found,
            ui_files_missing=missing,
            checklist=_CHECKLIST,
        )

    except Exception as exc:
        return VisualQAResult(success=False, error=str(exc))


if __name__ == "__main__":
    result = run(write_output=True)
    if result.success:
        print(result.report)
    else:
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
