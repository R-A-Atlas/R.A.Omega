"""
run_growth_content.py — Safe stub for the growth_content_agent worker.

Reads DONE files and git log to generate content ideas and a launch-ready
post draft. No external APIs, no social media posting, no LLM calls.
Output is returned as a string and optionally written to atlas_vault/03-Outputs/.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"

_POST_TEMPLATES = [
    (
        "Reddit r/algotrading launch post",
        """\
**[R.A. Omega] Built an institutional-grade finance AI for ~$0.017/query**

I've been building R.A. Omega for the past few months — a finance-first AI platform
that fetches 10+ free data sources in parallel and synthesizes them via Gemini into
institutional-grade analysis.

**What it does:**
- POST /query → deep equity/options analysis (10-loop engine)
- POST /omega → fast cross-domain: debt, mortgages, macro, cars
- Interactive HTML reports (edit + annotate like Power BI)
- ~$0.017/query target cost

**What's shipping:**
{done_count} phases complete. Looking for 50 beta testers.

DM or comment — I'll give you free access.
""",
    ),
    (
        "Twitter/X thread starter",
        """\
🧵 Built a finance AI that costs $0.017/query and gives you hedge-fund-grade analysis.

Here's how it works (1/{done_count} phases shipped):
""",
    ),
    (
        "Product Hunt launch description",
        """\
R.A. Omega — Institutional finance AI for retail traders.

Ask any finance question. Get hedge-fund-grade analysis in under 3 minutes.
10+ data sources. ~$0.017/query. Fully interactive HTML reports.

{done_count} engineering phases shipped. Built solo.
""",
    ),
]


@dataclass
class GrowthContentResult:
    success: bool
    report: str = ""
    done_files: list[str] = field(default_factory=list)
    content_drafts: list[tuple[str, str]] = field(default_factory=list)
    error: str = ""


def _collect_done_files() -> list[str]:
    return sorted(p.name for p in ROOT.glob("*_DONE.md"))


def _recent_git_log() -> str:
    try:
        log = subprocess.run(
            ["git", "-C", str(ROOT), "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=10,
        )
        return log.stdout.strip() if log.returncode == 0 else "(git log unavailable)"
    except Exception as exc:
        return f"(git error: {exc})"


def run(write_output: bool = False) -> GrowthContentResult:
    """
    Generate content ideas and post drafts based on current project state.

    Args:
        write_output: If True, writes report to atlas_vault/03-Outputs/growth_content.md.

    Returns:
        GrowthContentResult with .success, .report, .content_drafts.
    """
    try:
        done_files = _collect_done_files()
        done_count = len(done_files)
        git_log = _recent_git_log()

        drafts = []
        for title, template in _POST_TEMPLATES:
            body = template.format(done_count=done_count)
            drafts.append((title, body))

        lines = [
            "# Growth Content Brief",
            "",
            f"**Phases completed:** {done_count}",
            "",
            "## Recent Commits",
            "",
            "```",
            git_log,
            "```",
            "",
            "## Content Drafts",
            "",
        ]
        for title, body in drafts:
            lines.append(f"### {title}")
            lines.append("")
            lines.append(body)
            lines.append("")

        lines += [
            "## Content Ideas (manual)",
            "",
            "- Screenshot of the interactive HTML report → post on Twitter",
            "- Before/after: 'I used to pay $40 for Bloomberg terminal access. Now I pay $0.017.'",
            "- Post the query cost breakdown in r/personalfinance",
            "- 'What 10 phases of solo engineering looks like' dev diary on dev.to",
            "- Comparison table: Bloomberg vs R.A. Omega vs ChatGPT for finance",
        ]

        report = "\n".join(lines)

        if write_output:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUTS_DIR / "growth_content.md"
            out_path.write_text(report, encoding="utf-8")

        return GrowthContentResult(
            success=True,
            report=report,
            done_files=done_files,
            content_drafts=drafts,
        )

    except Exception as exc:
        return GrowthContentResult(success=False, error=str(exc))


if __name__ == "__main__":
    result = run(write_output=True)
    if result.success:
        print(result.report)
    else:
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
