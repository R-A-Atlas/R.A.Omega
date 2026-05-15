"""
quality_firewall.py — Validates synthesis output against the declared output_mode.
Uses OUTPUT_CONTRACTS to enforce required/forbidden sections.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from output_contracts import OUTPUT_CONTRACTS

log = logging.getLogger(__name__)


@dataclass
class QualityResult:
    passed: bool
    reason: str
    repair_instruction: str = ""

    # Backward-compatible alias so old callers using .passed still work
    @property
    def _compat_passed(self) -> bool:
        return self.passed


# Alias kept for code that imported FirewallResult from the old module
FirewallResult = QualityResult


def validate_response(
    raw_query: str,
    intent: str,
    output_mode: str,
    answer: str,
) -> QualityResult:
    """
    Checks synthesis output against the output_mode contract.
    Returns QualityResult with .passed, .reason, and .repair_instruction.
    """
    contract = OUTPUT_CONTRACTS.get(output_mode)
    if not contract:
        return QualityResult(
            passed=False,
            reason=f"Unknown output_mode: {output_mode}",
            repair_instruction="Regenerate using a valid output mode.",
        )

    text = (answer or "").lower()

    # ── Forbidden phrase check ────────────────────────────────────────────────
    for phrase in contract.forbidden_phrases:
        if phrase.lower() in text:
            log.warning(
                "quality_firewall: forbidden phrase %r in output_mode=%s for %r",
                phrase, output_mode, raw_query[:60],
            )
            return QualityResult(
                passed=False,
                reason=f"Forbidden phrase found for output_mode={output_mode}: {phrase}",
                repair_instruction=(
                    f"Regenerate the answer as output_mode={output_mode}. "
                    f"Remove all trade-plan language including '{phrase}'. "
                    "Answer the user's actual request directly."
                ),
            )

    # ── Required section check ────────────────────────────────────────────────
    missing = [s for s in contract.required_sections if s.lower() not in text]
    if missing and output_mode not in {"chat", "finance_answer"}:
        log.warning(
            "quality_firewall: missing sections %s in output_mode=%s for %r",
            missing, output_mode, raw_query[:60],
        )
        return QualityResult(
            passed=False,
            reason=f"Missing required sections: {missing}",
            repair_instruction=(
                f"Regenerate as output_mode={output_mode}. "
                f"Include these required sections: {', '.join(missing)}."
            ),
        )

    # ── Length check ─────────────────────────────────────────────────────────
    if not answer or len(answer.strip()) < 20:
        return QualityResult(
            passed=False,
            reason="Answer too short or empty.",
            repair_instruction="Regenerate with a complete answer.",
        )

    return QualityResult(passed=True, reason="Passed quality firewall.")
