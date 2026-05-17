"""
output_modes.py — Output mode resolver.
Separates final answer format from intent.
"""
from __future__ import annotations

import re

# ── Constants ────────────────────────────────────────────────────────────────
OUTPUT_CHAT            = "chat"
OUTPUT_GENERAL_CHAT    = "general_chat"
OUTPUT_FINANCE_ANSWER  = "finance_answer"
OUTPUT_COMPANY_REPORT  = "company_report"
OUTPUT_DOCUMENT        = "document"
OUTPUT_HTML_ARTIFACT   = "html_artifact"
OUTPUT_MARKET_SNAPSHOT = "market_snapshot"
OUTPUT_TRADE_PLAN      = "trade_plan"

NON_TRADE_MODES: frozenset[str] = frozenset({
    OUTPUT_CHAT,
    OUTPUT_GENERAL_CHAT,
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
    "document", "word document", "docx", "pdf", "deck", "proposal", "memo",
    "presentation", "spreadsheet", "workbook", "excel", "xlsx", "csv",
    "markdown", "md file", "text file", "txt", "powerpoint", "slides",
}

HTML_TRIGGER_WORDS: set[str] = {
    "html", "dashboard", "chart", "landing page", "website", "interactive", "reactive",
    "visual", "ui component", "html report",
}

# Regex for options / stock trading requests (phrase-level; supplements TRADE_TRIGGER_WORDS)
_OPTIONS_TRADE_RE = re.compile(
    r"\b(?:buy|sell|trade|short|long)\b.{0,50}\b(?:options?|calls?|puts?)\b"
    r"|\b(?:options?|calls?|puts?)\b.{0,50}\b(?:buy|sell|trade)\b"
    r"|\bstop[\s-]loss\b|\btake[\s-]profit\b|\bentry\s+(?:point|price|level)\b",
    re.I | re.S,
)

_EXPLICIT_DOCUMENT_RE = re.compile(
    r"\b(?:in|as|into|to|make|create|generate|write|export|download|save)\b"
    r".{0,80}\b(?:word\s+document|docx|pdf|pdf\s+report|document|deck|presentation|"
    r"powerpoint|slides?|spreadsheet|workbook|excel|xlsx|csv|markdown|md\s+file|text\s+file|txt)\b"
    r"|\b(?:word\s+document|docx|pdf\s+report|powerpoint|slide\s+deck|excel\s+file|csv\s+file|markdown\s+file|text\s+file)\b",
    re.I | re.S,
)

_FINANCE_OPINION_RE = re.compile(
    r"\b(?:what\s+do\s+you\s+think|your\s+(?:personal\s+)?opinion|"
    r"in\s+your\s+(?:personal\s+)?opinion|your\s+view|my\s+view|my\s+read|"
    r"how\s+do\s+you\s+see|what(?:'s|\s+is)\s+your\s+take)\b",
    re.I,
)

_FINANCE_SUBJECT_RE = re.compile(
    r"\b(?:stock|stocks|ticker|market|markets|share|shares|equity|equities|"
    r"crypto|coin|bitcoin|ethereum|option|options|calls?|puts?|earnings|"
    r"valuation|portfolio|finance|financial|invest|investment|nvda|aapl|tsla|"
    r"msft|googl|meta|amzn|blk|blackrock|vanguard|jpm|goldman)\b",
    re.I,
)
_UPPERCASE_TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")


def _has_any(q: str, words: set[str]) -> bool:
    ql = q.lower()
    return any(w in ql for w in words)


def user_explicitly_requested_trade(raw_query: str) -> bool:
    return _has_any(raw_query, TRADE_TRIGGER_WORDS) or bool(_OPTIONS_TRADE_RE.search(raw_query))


def user_explicitly_requested_document(raw_query: str) -> bool:
    return bool(_EXPLICIT_DOCUMENT_RE.search(raw_query or ""))


def detect_requested_document_format(raw_query: str) -> str | None:
    """Return the concrete artifact format requested in natural language."""
    q = (raw_query or "").lower()
    if re.search(r"\bword\s+document\b|\bdocx\b|\b\.docx\b", q):
        return "docx"
    if re.search(r"\bpdf\b|\bpdf\s+report\b|\b\.pdf\b", q):
        return "pdf"
    if re.search(r"\bpowerpoint\b|\bpptx\b|\bslide\s+deck\b|\bslides?\b|\bpresentation\b|\b\.pptx\b", q):
        return "pptx"
    if re.search(r"\bexcel\b|\bxlsx\b|\bspreadsheet\b|\bworkbook\b|\b\.xlsx\b", q):
        return "xlsx"
    if re.search(r"\bcsv\b|\b\.csv\b", q):
        return "csv"
    if re.search(r"\bmarkdown\b|\bmd\s+file\b|\b\.md\b", q):
        return "md"
    if re.search(r"\btext\s+file\b|\btxt\b|\b\.txt\b", q):
        return "txt"
    if re.search(r"\bhtml\s+report\b|\bhtml\s+file\b|\b\.html\b", q):
        return "html"
    if user_explicitly_requested_document(q):
        return "docx"
    return None


def user_asked_finance_opinion(raw_query: str) -> bool:
    q = raw_query or ""
    return bool(
        _FINANCE_OPINION_RE.search(q)
        and (_FINANCE_SUBJECT_RE.search(q) or _UPPERCASE_TICKER_RE.search(q))
    )


def resolve_output_mode(raw_query: str, intent: str) -> str:
    """Return the correct output mode for this query/intent pair."""
    q = raw_query or ""

    if _has_any(q, HTML_TRIGGER_WORDS):
        return OUTPUT_HTML_ARTIFACT

    if intent == "HTML_ARTIFACT":
        return OUTPUT_HTML_ARTIFACT

    if intent == "DOCUMENT_GENERATION" or user_explicitly_requested_document(q):
        return OUTPUT_DOCUMENT

    if user_asked_finance_opinion(q):
        return OUTPUT_FINANCE_ANSWER

    # Intent-confirmed company research wins over any keyword triggers
    if intent == "COMPANY_RESEARCH":
        return OUTPUT_COMPANY_REPORT

    if _has_any(q, DOCUMENT_TRIGGER_WORDS):
        return OUTPUT_DOCUMENT

    if intent in ("TRADING_ANALYSIS", "MARKET_DEEP_DIVE") or user_explicitly_requested_trade(q):
        return OUTPUT_TRADE_PLAN

    if intent in ("GENERAL_FINANCE", "GENERAL_CHAT"):
        # Check if query mentions a known company/ticker → treat as company_report
        try:
            from query_router import detect_company_name as _detect_co
            if _detect_co(q):
                return OUTPUT_COMPANY_REPORT
        except ImportError:
            pass
        return OUTPUT_FINANCE_ANSWER if intent == "GENERAL_FINANCE" else OUTPUT_CHAT

    if intent == "MARKET_DATA":
        return OUTPUT_MARKET_SNAPSHOT

    return OUTPUT_CHAT
