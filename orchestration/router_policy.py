"""Adaptive route scoring for the R.A. Omega chat surface.

This layer is intentionally deterministic. It gives the app a stable product
contract before any LLM/router work happens: quick chat, market snapshot,
focused analysis, deep research, or compliance escalation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal


RouteBand = Literal[
    "quick_chat",
    "market_snapshot",
    "focused_analysis",
    "deep_research",
    "compliance_escalation",
]


@dataclass(frozen=True)
class RouteDecision:
    route_band: RouteBand
    deep_score: float
    tool_budget: int
    max_steps: int
    background_ok: bool
    target_model_tier: str
    output_shape: str
    reasons: list[str]
    compliance_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["deep_score"] = round(float(self.deep_score), 2)
        return out


_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|sup|thanks?|thank\s+you|ok+|okay|cool|nice|bye)\b[!.?\s]*$",
    re.I,
)
_DEEP_RE = re.compile(
    r"\b(deep\s+research|full\s+due\s+diligence|full\s+dd|decision[-\s]?grade|rank\s+(?:the\s+)?best|best\s+\d+|build\s+(?:me\s+)?(?:a\s+)?portfolio|investment\s+committee|ic\s+memo)\b",
    re.I,
)
_SNAPSHOT_RE = re.compile(
    r"\b(today|right\s+now|now|snapshot|overview|market\s+look|market\s+today|quick\s+look|chart|spy|qqq|vix|breadth)\b",
    re.I,
)
_FOCUSED_RE = re.compile(
    r"\b(analy[sz]e|compare|valuation|earnings|options?|flow|support|resistance|price\s+target|catalyst|risk|macro|rates?|inflation|crypto|stock|ticker|shares?)\b",
    re.I,
)
_ACTION_RE = re.compile(
    r"\b(should\s+i|buy|sell|hold|allocate|rebalance|trade|position|recommend|pick|best)\b",
    re.I,
)
_COMPLIANCE_RE = re.compile(
    r"\b(guarantee|risk[-\s]?free|insider\s+tip|nonpublic|sure\s+thing|make\s+me\s+rich|what\s+should\s+i\s+buy|tell\s+me\s+to\s+buy)\b",
    re.I,
)
_REGULATORY_RE = re.compile(r"\b(tax|legal|sec|finra|regulatory|compliance|fiduciary)\b", re.I)
_TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")


def decide_route(
    query: str,
    *,
    forced_mode: str = "normal",
    web_search: bool = False,
    cache_coverage: float | None = None,
) -> RouteDecision:
    q = (query or "").strip()
    ql = q.lower()
    reasons: list[str] = []
    flags: list[str] = []
    score = 0.0

    if not q:
        return _decision("quick_chat", 0.0, ["empty_query"], flags)

    if forced_mode == "deep":
        reasons.append("user_selected_deep_research")
        if _COMPLIANCE_RE.search(q):
            flags.append("advice_or_prohibited_claim_risk")
        return _decision("deep_research", 0.82, reasons, flags)

    if _GREETING_RE.match(q):
        score -= 0.35
        reasons.append("low_information_chat")

    if forced_mode == "web" or web_search:
        score += 0.18
        reasons.append("user_selected_web_search")

    if _DEEP_RE.search(q):
        score += 0.45
        reasons.append("explicit_deep_or_ranking_language")
    if _ACTION_RE.search(q):
        score += 0.2
        reasons.append("portfolio_or_trade_action_language")
    if _REGULATORY_RE.search(q):
        score += 0.15
        reasons.append("legal_tax_or_regulatory_context")
        flags.append("regulated_finance_context")
    if _SNAPSHOT_RE.search(q):
        score += 0.12
        reasons.append("fresh_market_snapshot_requested")
    if _FOCUSED_RE.search(q):
        score += 0.2
        reasons.append("finance_analysis_terms")

    tickers = [t for t in _TICKER_RE.findall(q) if t.upper() not in {"I", "A", "THE", "AND", "FOR"}]
    if len(tickers) >= 3:
        score += 0.15
        reasons.append("multi_entity_comparison")
    elif tickers:
        score += 0.08
        reasons.append("market_entity_detected")

    if cache_coverage is not None and cache_coverage >= 0.8:
        score -= 0.2
        reasons.append("high_cache_coverage")

    if _COMPLIANCE_RE.search(q):
        flags.append("advice_or_prohibited_claim_risk")
        if _ACTION_RE.search(q) or "guarantee" in ql or "risk-free" in ql:
            return _decision(
                "compliance_escalation",
                max(score, 0.74),
                reasons + ["compliance_escalation_trigger"],
                flags,
            )

    score = max(0.0, min(1.0, score))
    if score >= 0.72:
        return _decision("deep_research", score, reasons, flags)
    if score >= 0.45:
        return _decision("focused_analysis", score, reasons, flags)
    if _SNAPSHOT_RE.search(q) or (forced_mode == "web" or web_search):
        return _decision("market_snapshot", max(score, 0.28), reasons, flags)
    if _FOCUSED_RE.search(q):
        return _decision("focused_analysis", max(score, 0.45), reasons, flags)
    return _decision("quick_chat", score, reasons or ["default_quick_chat"], flags)


def _decision(
    route_band: RouteBand,
    score: float,
    reasons: list[str],
    flags: list[str],
) -> RouteDecision:
    config = {
        "quick_chat": (0, 1, False, "fast", "plain_text"),
        "market_snapshot": (2, 3, False, "fast_finance", "short_answer_plus_optional_chart"),
        "focused_analysis": (5, 6, False, "finance_reasoning", "structured_memo"),
        "deep_research": (10, 10, True, "deep_research", "cited_report_with_activity"),
        "compliance_escalation": (2, 3, False, "policy_review", "safe_research_or_refusal"),
    }[route_band]
    return RouteDecision(
        route_band=route_band,
        deep_score=score,
        tool_budget=config[0],
        max_steps=config[1],
        background_ok=config[2],
        target_model_tier=config[3],
        output_shape=config[4],
        reasons=reasons,
        compliance_flags=flags,
    )
