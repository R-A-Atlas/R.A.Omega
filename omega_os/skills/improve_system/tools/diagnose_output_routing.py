"""
diagnose_output_routing.py — Trace and fix output mode routing for any query.

Given a query, shows exactly:
  1. What intent was classified
  2. Which routing rule fired and why
  3. What output_mode / renderer was chosen
  4. Whether the result looks wrong
  5. The root cause (which keyword or intent triggered the wrong branch)
  6. Suggested fixes (rewrite query OR patch output_modes.py)

No external APIs. No LLM calls. Fully deterministic.

CLI:
  python diagnose_output_routing.py "give me a company report on BlackRock"
  python diagnose_output_routing.py "TSLA trade setup" --expected company_report
  python diagnose_output_routing.py --fix "give me a report on Apple"
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_ROOT))


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class RoutingStep:
    step: str
    value: str
    triggered_by: str = ""
    is_problem: bool = False


@dataclass
class DiagnosisResult:
    query: str
    intent: str
    output_mode: str
    renderer_type: str
    skill_name: str
    steps: list[RoutingStep] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    rephrased_query: str = ""
    report: str = ""

    @property
    def has_problems(self) -> bool:
        return bool(self.problems)


# ── Intent classification trace ───────────────────────────────────────────────

def _get_intent(query: str) -> tuple[str, str]:
    """Return (intent, triggered_by). Never raises."""
    try:
        from query_router import classify_intent_route
        intent = classify_intent_route(query)
        return intent, "classify_intent_route()"
    except Exception as exc:
        return "GENERAL_FINANCE", f"fallback (classify_intent_route error: {exc})"


# ── Trade trigger trace ───────────────────────────────────────────────────────

def _find_trade_triggers(query: str) -> list[str]:
    """Return list of trade trigger words found in query."""
    try:
        from output_modes import TRADE_TRIGGER_WORDS, _OPTIONS_TRADE_RE
        q = query.lower()
        found = [w for w in TRADE_TRIGGER_WORDS if w in q]
        if _OPTIONS_TRADE_RE.search(query):
            found.append("(options/trading regex pattern)")
        return found
    except Exception:
        return []


def _find_document_triggers(query: str) -> list[str]:
    """Return list of document trigger words found in query."""
    try:
        from output_modes import DOCUMENT_TRIGGER_WORDS
        q = query.lower()
        return [w for w in DOCUMENT_TRIGGER_WORDS if w in q]
    except Exception:
        return []


def _find_html_triggers(query: str) -> list[str]:
    """Return list of HTML trigger words found in query."""
    try:
        from output_modes import HTML_TRIGGER_WORDS
        q = query.lower()
        return [w for w in HTML_TRIGGER_WORDS if w in q]
    except Exception:
        return []


# ── Full routing trace ────────────────────────────────────────────────────────

def _trace_resolve_output_mode(query: str, intent: str) -> tuple[str, list[RoutingStep]]:
    """
    Manually trace resolve_output_mode() step by step.
    Returns (actual_output_mode, steps_list).
    """
    steps: list[RoutingStep] = []
    q = query

    html_triggers = _find_html_triggers(q)
    if html_triggers:
        steps.append(RoutingStep(
            step="HTML trigger words",
            value="html_artifact",
            triggered_by=f"words: {html_triggers}",
        ))
        return "html_artifact", steps
    steps.append(RoutingStep("HTML trigger words", "no match", ""))

    if intent == "HTML_ARTIFACT":
        steps.append(RoutingStep("intent == HTML_ARTIFACT", "html_artifact", "intent"))
        return "html_artifact", steps
    steps.append(RoutingStep("intent == HTML_ARTIFACT", "no match", ""))

    # Intent-confirmed company research wins over any keyword triggers (matches output_modes.py fix)
    if intent == "COMPANY_RESEARCH":
        steps.append(RoutingStep("intent == COMPANY_RESEARCH", "company_report", "intent"))
        return "company_report", steps
    steps.append(RoutingStep("intent == COMPANY_RESEARCH", "no match", ""))

    doc_triggers = _find_document_triggers(q)
    if intent == "DOCUMENT_GENERATION" or doc_triggers:
        triggered_by = f"intent={intent}" if intent == "DOCUMENT_GENERATION" else f"words: {doc_triggers}"
        steps.append(RoutingStep(
            step="Document trigger",
            value="document",
            triggered_by=triggered_by,
            is_problem=False,
        ))
        return "document", steps
    steps.append(RoutingStep("Document trigger", "no match", ""))

    trade_triggers = _find_trade_triggers(q)
    if intent in ("TRADING_ANALYSIS", "MARKET_DEEP_DIVE") or trade_triggers:
        triggered_by = f"intent={intent}" if intent in ("TRADING_ANALYSIS", "MARKET_DEEP_DIVE") \
                       else f"words: {trade_triggers}"
        steps.append(RoutingStep(
            step="Trade trigger",
            value="trade_plan",
            triggered_by=triggered_by,
            is_problem=False,
        ))
        return "trade_plan", steps
    steps.append(RoutingStep("Trade trigger", "no match", ""))

    if intent == "GENERAL_FINANCE":
        try:
            from query_router import detect_company_name as _detect
            company = _detect(q)
            if company:
                steps.append(RoutingStep(
                    "GENERAL_FINANCE + company name detected",
                    "company_report",
                    f"company detected: {company}",
                ))
                return "company_report", steps
        except Exception:
            pass
        steps.append(RoutingStep("GENERAL_FINANCE -> finance_answer", "finance_answer", "intent"))
        return "finance_answer", steps

    if intent == "MARKET_DATA":
        steps.append(RoutingStep("intent == MARKET_DATA", "market_snapshot", "intent"))
        return "market_snapshot", steps

    steps.append(RoutingStep("fallback", "chat", "no other rule matched"))
    return "chat", steps


# ── Problem detector ──────────────────────────────────────────────────────────

def _detect_problems(
    query: str,
    intent: str,
    output_mode: str,
    steps: list[RoutingStep],
    expected: str | None,
) -> list[str]:
    problems: list[str] = []

    # User-specified expected mode
    if expected and output_mode != expected:
        problems.append(
            f"Expected output_mode='{expected}' but got '{output_mode}'"
        )

    # Trade plan with no trade signals — intent classifier misfire
    if output_mode == "trade_plan" and not _find_trade_triggers(query) and intent == "COMPANY_RESEARCH":
        problems.append(
            f"Output is trade_plan but query has no trade keywords and intent=COMPANY_RESEARCH. "
            f"Intent classifier may be misidentifying this query as TRADING_ANALYSIS."
        )

    return problems


# ── Fix suggester ─────────────────────────────────────────────────────────────

def _suggest_fixes(
    query: str,
    intent: str,
    output_mode: str,
    problems: list[str],
    expected: str | None,
) -> tuple[list[str], str]:
    fixes: list[str] = []
    rephrased = ""

    doc_triggers = _find_document_triggers(query)
    trade_triggers = _find_trade_triggers(query)

    # Only generate targeted fixes when the user told us what they expected
    target = expected

    # Fix 1: document keywords intercepted a non-document query
    if doc_triggers and output_mode == "document" and target and target != "document":
        clean = query
        for w in doc_triggers:
            clean = re.sub(re.escape(w), "", clean, flags=re.I).strip()
        rephrased = f"Give me everything on {clean}" if clean else query
        fixes.append(
            f"Rephrase query — remove document trigger words {doc_triggers}. "
            f"Try: \"{rephrased}\""
        )
        fixes.append(
            f"OR: remove '{doc_triggers}' from DOCUMENT_TRIGGER_WORDS in output_modes.py "
            f"(line ~37) since these words are ambiguous for non-document queries."
        )

    # Fix 2: intent classifier thinks it's a trade request but user expected company research
    if intent in ("TRADING_ANALYSIS", "MARKET_DEEP_DIVE") and target == "company_report":
        fixes.append(
            f"Intent classifier returned '{intent}' — it thinks this is a trade request. "
            f"Fix: use a query that makes company research explicit, e.g. "
            f"'Tell me everything about [company]' or 'Company profile: [company]'."
        )

    # Fix 3: force override via request_controls
    if problems and target:
        fixes.append(
            f"Force output mode via request_controls: pass "
            f"{{\"output_mode_override\": \"{target}\"}} with your query to bypass routing."
        )

    return fixes, rephrased


# ── Main entry point ──────────────────────────────────────────────────────────

def diagnose(query: str, expected: str | None = None) -> DiagnosisResult:
    """
    Trace routing for a query and return a DiagnosisResult.

    Args:
        query:    The raw query to diagnose.
        expected: Optional expected output_mode to check against.

    Returns:
        DiagnosisResult with .problems, .fixes, .report, .rephrased_query.
    """
    intent, intent_source = _get_intent(query)
    output_mode, steps = _trace_resolve_output_mode(query, intent)

    # Get renderer and skill from pipeline
    renderer_type = "unknown"
    skill_name = ""
    try:
        from omega_pipeline import select_renderer_type
        renderer_type = select_renderer_type(output_mode, "")
    except Exception:
        pass
    try:
        from omega_skill_registry import get_skill_for_output_mode
        skill_name = get_skill_for_output_mode(output_mode) or ""
    except Exception:
        pass

    problems = _detect_problems(query, intent, output_mode, steps, expected)
    fixes, rephrased = _suggest_fixes(query, intent, output_mode, problems, expected)

    result = DiagnosisResult(
        query=query,
        intent=intent,
        output_mode=output_mode,
        renderer_type=renderer_type,
        skill_name=skill_name,
        steps=steps,
        problems=problems,
        fixes=fixes,
        rephrased_query=rephrased,
    )
    result.report = _build_report(result, intent_source, expected)
    return result


def _build_report(result: DiagnosisResult, intent_source: str, expected: str | None) -> str:
    lines = [
        "# Output Routing Diagnosis",
        "",
        f"**Query:** `{result.query}`",
        f"**Intent:** `{result.intent}` (via {intent_source})",
        f"**Output mode:** `{result.output_mode}`",
        f"**Renderer:** `{result.renderer_type}`",
        f"**Skill:** `{result.skill_name or '(none)'}`",
    ]
    if expected:
        match = "OK" if result.output_mode == expected else "MISMATCH"
        lines.append(f"**Expected:** `{expected}` — [{match}]")
    lines += ["", "## Routing Trace", ""]
    for i, s in enumerate(result.steps, 1):
        icon = "[FAIL]" if s.is_problem else "[pass]"
        line = f"{i}. {icon} **{s.step}** -> `{s.value}`"
        if s.triggered_by:
            line += f" (triggered by: {s.triggered_by})"
        lines.append(line)

    if result.problems:
        lines += ["", "## Problems Found", ""]
        for p in result.problems:
            lines.append(f"- {p}")
    else:
        lines += ["", "## No Problems Found", "", "- Routing looks correct."]

    if result.fixes:
        lines += ["", "## Suggested Fixes", ""]
        for i, f in enumerate(result.fixes, 1):
            lines.append(f"{i}. {f}")

    if result.rephrased_query:
        lines += ["", "## Rephrased Query (avoids trigger words)", "",
                  f'> "{result.rephrased_query}"']

    return "\n".join(lines)


# ── Patch helper (optional --fix mode) ───────────────────────────────────────

def remove_word_from_trigger_list(word: str, list_name: str = "DOCUMENT_TRIGGER_WORDS") -> str:
    """
    Return a diff-style suggestion for removing `word` from the named trigger list
    in output_modes.py. Does NOT write to the file.
    """
    path = _ROOT / "output_modes.py"
    try:
        source = path.read_text(encoding="utf-8")
        if f'"{word}"' in source:
            return (
                f"In output_modes.py, remove:\n"
                f'    "{word}",\n'
                f"from {list_name}.\n"
                f"This stops '{word}' from triggering {list_name} routing."
            )
        return f"'{word}' not found in output_modes.py."
    except Exception as exc:
        return f"Could not read output_modes.py: {exc}"


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python diagnose_output_routing.py <query> [--expected <mode>] [--fix <word>]")
        print("Modes: company_report | trade_plan | chat | document | html_artifact | finance_answer")
        sys.exit(0)

    expected = None
    fix_word = None
    query_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--expected" and i + 1 < len(args):
            expected = args[i + 1]
            i += 2
        elif args[i] == "--fix" and i + 1 < len(args):
            fix_word = args[i + 1]
            i += 2
        else:
            query_parts.append(args[i])
            i += 1

    query = " ".join(query_parts)
    result = diagnose(query, expected=expected)
    print(result.report)

    if fix_word:
        print()
        print("## Patch Suggestion")
        print()
        print(remove_word_from_trigger_list(fix_word))

    sys.exit(0 if not result.has_problems else 1)
