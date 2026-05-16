"""
run_report_qa.py — Safe stub for the report_qa_agent worker.

Runs deterministic quality checks on three canonical sample outputs:
  1. Company report (BlackRock)
  2. Trade plan (TSLA)
  3. General chat (apple pie recipe — no finance bleed expected)

Uses the existing omega_os skill verifiers. No external APIs. No LLM calls.
Output is returned as a string and optionally written to atlas_vault/03-Outputs/.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "atlas_vault" / "03-Outputs"

# ── Minimal sample outputs for deterministic checks ───────────────────────────

_SAMPLE_COMPANY_REPORT = """\
## Executive Summary
BlackRock is the world's largest asset manager with $10.5T AUM.

## Company Overview
Founded in 1988, headquartered in New York City.

## What They Do
Investment management, risk management, advisory services.

## Business Model
Fee-based asset management across equities, fixed income, and alternatives.

## Financial Snapshot
AUM: $10.5T | Revenue: $17.9B | Net Income: $5.5B

## Key Executives
Larry Fink (CEO), Rob Kapito (President).

## Recent News
BlackRock acquired Global Infrastructure Partners in Q1 2024.

## Competitive Position
Dominant via iShares ETF franchise.

## Key Risks
Fee compression, regulatory pressure.

## Sources
SEC EDGAR 10-K 2023.

## Bottom Line
Global leader in asset management.
"""

_SAMPLE_TRADE_PLAN = """\
## Setup
TSLA consolidating above $200 support with decreasing volume.

## Entry
Entry: $205 on break above $202 resistance.
Stop Loss: $197 (risk: 4%)

## Invalidation
Position invalidated if TSLA closes below $195 on volume.

## Risk
Risk per share: $8. Position size: 100 shares. Total risk: $800.
Risk/Reward: 1:2.5

## Scenarios
Bull: TSLA reaches $225 within 2 weeks.
Bear: Break below $195 triggers stop.
"""

_SAMPLE_CHAT = "You need flour, sugar, and apples. Mix and bake at 375 degrees for 45 minutes."


@dataclass
class ReportQAEntry:
    name: str
    output_mode: str
    passed: bool
    reason: str


@dataclass
class ReportQAResult:
    success: bool
    report: str = ""
    entries: list[ReportQAEntry] = field(default_factory=list)
    error: str = ""


def _check_company_report() -> ReportQAEntry:
    try:
        sys.path.insert(0, str(ROOT))
        from omega_os.skills.company_report.tools.verify_company_report import verify
        result = verify(_SAMPLE_COMPANY_REPORT)
        return ReportQAEntry(
            name="BlackRock company report",
            output_mode="company_report",
            passed=result.passed,
            reason=result.summary(),
        )
    except Exception as exc:
        return ReportQAEntry(
            name="BlackRock company report",
            output_mode="company_report",
            passed=False,
            reason=f"Verifier unavailable: {exc}",
        )


def _check_trade_plan() -> ReportQAEntry:
    try:
        sys.path.insert(0, str(ROOT))
        from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
        result = verify(_SAMPLE_TRADE_PLAN)
        return ReportQAEntry(
            name="TSLA trade plan",
            output_mode="trade_plan",
            passed=result.passed,
            reason=result.summary(),
        )
    except Exception as exc:
        return ReportQAEntry(
            name="TSLA trade plan",
            output_mode="trade_plan",
            passed=False,
            reason=f"Verifier unavailable: {exc}",
        )


def _check_chat_no_bleed() -> ReportQAEntry:
    trade_terms = ("entry price", "stop loss", "the setup", "take profit", "naked call")
    found = [t for t in trade_terms if t in _SAMPLE_CHAT.lower()]
    passed = len(found) == 0
    reason = "PASS: no trade bleed in chat response." if passed else f"FAIL: trade terms found: {found}"
    return ReportQAEntry(
        name="Apple pie chat (no finance bleed)",
        output_mode="chat",
        passed=passed,
        reason=reason,
    )


def run(write_output: bool = False) -> ReportQAResult:
    """
    Run QA checks on canonical sample outputs.

    Args:
        write_output: If True, writes report to atlas_vault/03-Outputs/report_qa.md.

    Returns:
        ReportQAResult with .success, .report, .entries.
    """
    try:
        entries = [
            _check_company_report(),
            _check_trade_plan(),
            _check_chat_no_bleed(),
        ]

        passed_count = sum(1 for e in entries if e.passed)
        total = len(entries)

        lines = [
            "# Report QA",
            "",
            f"**Result: {passed_count}/{total} passed**",
            "",
            "## Checks",
            "",
        ]
        for e in entries:
            status = "PASS" if e.passed else "FAIL"
            lines.append(f"### [{status}] {e.name} (`{e.output_mode}`)")
            lines.append("")
            lines.append(e.reason)
            lines.append("")

        report = "\n".join(lines)

        if write_output:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = OUTPUTS_DIR / "report_qa.md"
            out_path.write_text(report, encoding="utf-8")

        return ReportQAResult(
            success=True,
            report=report,
            entries=entries,
        )

    except Exception as exc:
        return ReportQAResult(success=False, error=str(exc))


if __name__ == "__main__":
    result = run(write_output=True)
    if result.success:
        print(result.report)
        all_passed = all(e.passed for e in result.entries)
        raise SystemExit(0 if all_passed else 1)
    else:
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
