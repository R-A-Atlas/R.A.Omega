"""
quality_firewall.py — Validates synthesis output against the declared output_mode.
Uses OUTPUT_CONTRACTS to enforce required/forbidden sections.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from output_contracts import OUTPUT_CONTRACTS, CHAT_TRADE_FORBIDDEN

log = logging.getLogger(__name__)

# Trade bleed: section headers that belong only in trade_plan output
_COMPANY_REPORT_BLEED_HEADERS: tuple[str, ...] = (
    "the setup",
    "your rules",
    "what breaks this",
    "how this plays out",
    "hold period",
    "action: buy",
    "action: sell",
    "action: avoid",
    "action: short",
    "rating: buy",
    "rating: sell",
    "rating: hold",
    "rating: avoid",
    "entry price",
    "stop loss",
    "take profit",
    "execution rules",
    "risk/reward",
    "position size",
    "position sizing",
    "trade rating",
    "tripwire",
    "hedge fund brief",
    "best contract",
    "best options contract",
)

_CHAT_REPAIR = (
    "The response contains trade-plan section headers that do not belong in a chat or finance answer. "
    "Rewrite as a plain, conversational answer. "
    "Remove THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT, "
    "Action: buy/sell/avoid, Rating: buy/sell/hold, Stop Loss, Take Profit, "
    "Hedge Fund Brief, Intelligence Brief/Memo, and all trade-plan language. "
    "Answer the user's actual question directly in plain text."
)

_COMPANY_REPORT_REPAIR = (
    "The response contains trade-plan sections that do not belong in a company intelligence report. "
    "Rewrite as a company_report with these sections only: "
    "Executive Summary, Company Overview, What They Do, Business Model, Financial Snapshot, "
    "Key Executives, Recent News / Catalysts, Competitive Position, Key Risks, Sources / Data Notes, Bottom Line. "
    "Remove THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT, Entry, Stop Loss, Take Profit, "
    "Action: buy/sell/avoid, Rating: buy/sell/hold, Tripwire, Trade Rating, and all position-sizing language."
)

_EVASIVE_OPINION_PHRASES: tuple[str, ...] = (
    "as an ai",
    "as a language model",
    "i don't have personal opinions",
    "i do not have personal opinions",
    "i don't have opinions",
    "i do not have opinions",
)

_FINANCE_OPINION_REPAIR = (
    "Regenerate as a grounded finance answer. Give a direct data-backed take using "
    "'My read is' or 'My view is', cite the relevant evidence or missing data, and avoid "
    "personalized investment advice. Do not say you lack personal opinions."
)


@dataclass
class QualityResult:
    passed: bool
    reason: str
    repair_instruction: str = ""
    bleed_detected: bool = False

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
    Returns QualityResult with .passed, .reason, .repair_instruction, and .bleed_detected.
    Never raises — on any internal error returns passed=False with an error reason.
    """
    try:
        return _validate(raw_query, intent, output_mode, answer)
    except Exception as exc:
        log.warning("quality_firewall: internal error — %s", exc, exc_info=True)
        return QualityResult(
            passed=False,
            reason=f"Quality check error: {exc}",
            repair_instruction="Regenerate with a complete answer.",
        )


def _validate(
    raw_query: str,
    intent: str,
    output_mode: str,
    answer: str,
) -> QualityResult:
    contract = OUTPUT_CONTRACTS.get(output_mode)
    if not contract:
        return QualityResult(
            passed=False,
            reason=f"Unknown output_mode: {output_mode}",
            repair_instruction="Regenerate using a valid output mode.",
        )

    text = (answer or "").lower()

    if output_mode == "finance_answer":
        try:
            from output_modes import user_asked_finance_opinion
            is_finance_opinion = user_asked_finance_opinion(raw_query)
        except Exception:
            is_finance_opinion = False
        if is_finance_opinion:
            for phrase in _EVASIVE_OPINION_PHRASES:
                if phrase in text:
                    return QualityResult(
                        passed=False,
                        reason=f"Evasive finance-opinion phrase found: {phrase}",
                        repair_instruction=_FINANCE_OPINION_REPAIR,
                    )

    # ── chat / finance_answer / general_chat trade bleed check ───────────────
    if output_mode in {"chat", "finance_answer", "general_chat"}:
        for phrase in CHAT_TRADE_FORBIDDEN:
            if phrase in text:
                log.warning(
                    "quality_firewall: trade bleed %r detected in %s for %r",
                    phrase, output_mode, (raw_query or "")[:60],
                )
                return QualityResult(
                    passed=False,
                    reason=f"Trade bleed in {output_mode}: forbidden phrase '{phrase}'",
                    repair_instruction=_CHAT_REPAIR,
                    bleed_detected=True,
                )

    # ── company_report trade bleed check (runs before generic forbidden check) ──
    if output_mode == "company_report":
        for phrase in _COMPANY_REPORT_BLEED_HEADERS:
            if phrase in text:
                log.warning(
                    "quality_firewall: trade bleed %r detected in company_report for %r",
                    phrase, raw_query[:60],
                )
                return QualityResult(
                    passed=False,
                    reason=f"Trade bleed in company_report: forbidden phrase '{phrase}'",
                    repair_instruction=_COMPANY_REPORT_REPAIR,
                    bleed_detected=True,
                )

    # ── Forbidden phrase check ────────────────────────────────────────────────
    for phrase in contract.forbidden_phrases:
        if phrase.lower() in text:
            log.warning(
                "quality_firewall: forbidden phrase %r in output_mode=%s for %r",
                phrase, output_mode, raw_query[:60],
            )
            bleed = output_mode == "company_report"
            return QualityResult(
                passed=False,
                reason=f"Forbidden phrase found for output_mode={output_mode}: {phrase}",
                repair_instruction=(
                    _COMPANY_REPORT_REPAIR if bleed else (
                        f"Regenerate the answer as output_mode={output_mode}. "
                        f"Remove all trade-plan language including '{phrase}'. "
                        "Answer the user's actual request directly."
                    )
                ),
                bleed_detected=bleed,
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

    # ── Deterministic verifier — company_report ───────────────────────────────
    if output_mode == "company_report":
        try:
            from omega_os.skills.company_report.tools.verify_company_report import verify as _vcr
            _vr = _vcr(answer)
            if not _vr.passed:
                if _vr.forbidden_found:
                    return QualityResult(
                        passed=False,
                        reason=f"Verifier: trade bleed in company_report: {_vr.forbidden_found}",
                        repair_instruction=_COMPANY_REPORT_REPAIR,
                        bleed_detected=True,
                    )
                if _vr.missing_sections:
                    return QualityResult(
                        passed=False,
                        reason=f"Verifier: missing required sections: {_vr.missing_sections}",
                        repair_instruction=(
                            f"Regenerate as company_report. Include these required sections: "
                            f"{', '.join(_vr.missing_sections)}."
                        ),
                    )
        except Exception:
            pass  # verifier unavailable — degrade gracefully

    # ── Deterministic verifier — trade_plan ──────────────────────────────────
    if output_mode == "trade_plan":
        try:
            from omega_os.skills.trade_plan.tools.verify_trade_plan import verify as _vtp
            _vr = _vtp(answer)
            if not _vr.passed:
                if _vr.forbidden_found:
                    return QualityResult(
                        passed=False,
                        reason=f"Verifier: forbidden pattern in trade_plan: {_vr.forbidden_found}",
                        repair_instruction=(
                            "Regenerate as trade_plan. Remove naked options. "
                            "Always include a stop loss."
                        ),
                    )
                if _vr.missing_sections:
                    return QualityResult(
                        passed=False,
                        reason=f"Verifier: missing required sections in trade_plan: {_vr.missing_sections}",
                        repair_instruction=(
                            f"Regenerate as trade_plan. Include: {', '.join(_vr.missing_sections)}. "
                            "A stop loss is required."
                        ),
                    )
        except Exception:
            pass  # verifier unavailable — degrade gracefully

    return QualityResult(passed=True, reason="Passed quality firewall.")


_INLINE_SECTION_RE = re.compile(r'^[A-Z][A-Za-z ]{2,30}:\s')


def _strip_trade_sections(text: str) -> str:
    """
    Best-effort removal of trade-plan section headers and their content from text.
    A 'section' starts at a line whose lowercased content contains a forbidden phrase
    AND whose line looks like a header (starts with #, all-caps, or ends with ':').
    Skipping stops when a new non-forbidden header is found.
    """
    forbidden = set(_COMPANY_REPORT_BLEED_HEADERS)
    lines = text.split('\n')
    out: list[str] = []
    skipping = False
    for line in lines:
        ll = line.lower().strip()
        is_forbidden = any(f in ll for f in forbidden)
        looks_like_header = (
            line.startswith('#')
            or ll.endswith(':')
            or (ll == ll.upper() and len(ll) > 2)
        )
        if is_forbidden and looks_like_header:
            skipping = True
            continue
        if skipping:
            new_section = (
                line.startswith('#')
                or (line.strip().endswith(':') and line.strip() and line.strip()[0].isupper() and len(line.strip()) < 80)
                or bool(_INLINE_SECTION_RE.match(line.strip()))
            )
            if new_section and not is_forbidden:
                skipping = False
            else:
                continue
        out.append(line)
    return '\n'.join(out).strip()


def repair_response(answer: str, output_mode: str) -> tuple[str, bool]:
    """
    Attempt one text-based repair pass for a bleed violation.
    Returns (repaired_text, repaired_successfully: bool).
    One pass maximum — never recurses or calls external services.
    Never raises.
    """
    try:
        if output_mode != "company_report" or not answer:
            return answer or "", False
        repaired = _strip_trade_sections(answer)
        success = bool(repaired) and len(repaired) >= 30
        if success:
            log.info("quality_firewall: repair_response removed trade sections from company_report")
        else:
            log.warning("quality_firewall: repair_response produced insufficient output — returning original with warning")
        return repaired if success else answer, success
    except Exception as exc:
        log.warning("quality_firewall: repair_response error — %s", exc)
        return answer or "", False
