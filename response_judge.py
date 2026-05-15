"""
response_judge.py — Final strict judge before answer reaches the frontend.
Deterministic now; later can call an LLM judge.
"""
from __future__ import annotations

from dataclasses import dataclass

from quality_firewall import validate_response


@dataclass
class JudgeResult:
    verdict: str          # "PASS" or "FAIL"
    reason: str
    repair_instruction: str = ""


def judge_response(
    raw_query: str,
    intent: str,
    output_mode: str,
    answer: str,
) -> JudgeResult:
    """
    Runs quality_firewall and wraps in a JudgeResult.
    Returns PASS or FAIL with repair_instruction.
    """
    quality = validate_response(raw_query, intent, output_mode, answer)
    if not quality.passed:
        return JudgeResult(
            verdict="FAIL",
            reason=quality.reason,
            repair_instruction=quality.repair_instruction,
        )

    return JudgeResult(
        verdict="PASS",
        reason="Answer satisfies output contract.",
        repair_instruction="",
    )
