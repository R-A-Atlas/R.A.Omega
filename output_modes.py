"""
output_modes.py — Output mode resolver.
Separates final answer format from intent.
"""
from __future__ import annotations

import re

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUT_CHAT            = "chat"
OUTPUT_FINANCE_ANSWER  = "finance_answer"
OUTPUT_COMPANY_REPORT  = "company_report"
OUTPUT_DOCUMENT        = "document"
OUTPUT_HTML_ARTIFACT   = "html_artifact"
OUTPUT_MARKET_SNAPSHOT = "market_snapshot"
OUTPUT_TRADE_PLAN      = "trade_plan"

NON_TRADE_MODES: frozenset[str] = frozenset({
    OUTPUT_CHAT,
    OUTPUT_FINANCE_ANSWER,
    OUTPUT_COMPANY_REPORT,
    OUTPUT_DOCUMENT,
    OUTPUT_HTML_ARTIFACT,
    OUTPUT_MARKET_SNAPSHOT,
})

TRADE_TRIGGER_WORDS: set[str] = {
    "trade setup", "entry price", "stop loss", "take profit", "risk reward",
    "risk/reward", "scalp", "swing trade", "day trade", "options play",
    "buy calls", "buy puts", "trade plan", "execution rules",
    "position size", "invalidation level",
}

DOCUMENT_TRIGGER_WORDS: set[str] = {
    "report", "document", "pdf", "brief", "deck", "proposal", "memo",
    "presentation", "spreadsheet", "workbook",
}

HTML_TRIGGER_WORDS: set[str] = {
    "html", "dashboard", "landing page", "website", "interactive", "reactive",
    "visual", "ui component", "html report",
}

# Regex for options / stock trading requests (phrase-level; supplements TRADE_TRIGGER_WORDS)
_OPTIONS_TRADE_RE = re.compile(
    r"\b(?:buy|sell|trade|short|long)\b.{0,50}\b(?:options?|calls?|puts?)\b"
    r"|\b(?:options?|calls?|puts?)\b.{0,50}\b(?:buy|sell|trade)\b"
    r"|\bstop[\s-]loss\b|\btake[\s-]profit\b|\bentry\s+(?:point|price|level)\b",
    re.I | re.S,
)


def _has_any(q: str, words: set[str]) -> bool:
    ql = q.lower()
    return any(w in ql for w in words)


def user_explicitly_requested_trade(raw_query: str) -> bool:
    return _has_any(raw_query, TRADE_TRIGGER_WORDS) or bool(_OPTIONS_TRADE_RE.search(raw_query))


def resolve_output_mode(raw_query: str, intent: str) -> str:
    """Return the correct output mode for this query/intent pair."""
    q = raw_query or ""

    if _has_any(q, HTML_TRIGGER_WORDS):
        return OUTPUT_HTML_ARTIFACT

    if intent == "HTML_ARTIFACT":
        return OUTPUT_HTML_ARTIFACT

    if intent == "DOCUMENT_GENERATION" or _has_any(q, DOCUMENT_TRIGGER_WORDS):
        return OUTPUT_DOCUMENT

    if intent in ("TRADING_ANALYSIS", "MARKET_DEEP_DIVE") or user_explicitly_requested_trade(q):
        return OUTPUT_TRADE_PLAN

    if intent == "COMPANY_RESEARCH":
        return OUTPUT_COMPANY_REPORT

    if intent == "GENERAL_FINANCE":
        # Check if query mentions a known company → treat as company_report
        try:
            from query_router import detect_company_name as _detect_co
            if _detect_co(q):
                return OUTPUT_COMPANY_REPORT
        except ImportError:
            pass
        return OUTPUT_FINANCE_ANSWER

    if intent == "MARKET_DATA":
        return OUTPUT_MARKET_SNAPSHOT

    return OUTPUT_CHAT
