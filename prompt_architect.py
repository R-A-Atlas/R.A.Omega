"""
prompt_architect.py — R.A. Omega Prompt Architect

Turns messy user queries into structured goal lists, key questions,
and a PromptBlueprint that makes it visible what the system understood
before the analysis arrives.

No LLM calls — deterministic, sub-millisecond.

Usage:
    from prompt_architect import build_blueprint
    bp = build_blueprint(query="Analyze NVDA and tell me if I should buy calls before earnings", intent="MARKET_DEEP_DIVE")
    shaped["_prompt_blueprint"] = bp.to_dict()
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── Goal templates per intent ─────────────────────────────────────────────────

_INTENT_GOALS: dict[str, list[str]] = {
    "MARKET_DEEP_DIVE": [
        "Analyze current technical setup and price action",
        "Evaluate options flow and institutional positioning",
        "Scan news feed and sentiment signals",
        "Assess market regime and macro backdrop",
        "Identify key price levels, catalysts, and risk tripwires",
    ],
    "TRADING_ANALYSIS": [
        "Map entry, stop, and target levels",
        "Analyze dark pool prints and block trade flow",
        "Evaluate risk/reward and position sizing",
        "Run backtesting on similar historical setups",
        "Define execution rules and failure modes",
    ],
    "COMPANY_RESEARCH": [
        "Research business model and competitive position",
        "Review recent SEC filings and insider transactions",
        "Analyze financial health and key metrics",
        "Assess growth catalysts and downside risks",
        "Summarize analyst consensus and valuation",
    ],
    "DEEP_RESEARCH": [
        "Run 10-loop deep research with iterative refinement",
        "Cross-reference SEC filings with news and sentiment",
        "Build comprehensive risk/reward framework",
        "Identify non-consensus insights and asymmetric opportunities",
        "Synthesize all sources into actionable intelligence",
    ],
    "MACRO_RISK_SCAN": [
        "Classify current market regime and trend strength",
        "Track Fed policy signals and yield curve dynamics",
        "Assess inflation, employment, and GDP trajectory",
        "Map sector rotation patterns and global liquidity",
        "Identify systemic risks and contagion pathways",
    ],
    "REAL_ESTATE_SCAN": [
        "Pull current mortgage rates and affordability metrics",
        "Analyze inventory levels and median price trends",
        "Evaluate rental yields and cap rates",
        "Assess zoning, local market conditions, and risks",
        "Compare rent vs buy scenarios for the query context",
    ],
    "PERSONAL_WEALTH_SCAN": [
        "Scan high-yield savings rates and cash positioning",
        "Model debt payoff strategies (avalanche vs snowball)",
        "Identify tax optimization and contribution opportunities",
        "Assess insurance gaps and emergency fund adequacy",
        "Build personalized wealth acceleration roadmap",
    ],
    "GENERAL_FINANCE": [
        "Research the financial topic from authoritative sources",
        "Apply relevant data and benchmarks to the question",
        "Identify actionable insights and next steps",
        "Highlight key risks and considerations",
    ],
    "GENERAL_CHAT": [
        "Answer the question directly and clearly",
    ],
    "CONVERSATION": [
        "Respond conversationally",
    ],
}

_INTENT_KEY_QUESTIONS: dict[str, list[str]] = {
    "MARKET_DEEP_DIVE": [
        "What is the current technical setup and momentum?",
        "What are the key support and resistance levels?",
        "What does options flow and dark pool activity signal?",
        "What is the bull thesis vs the bear thesis?",
        "What are the trade rules, risk levels, and catalysts?",
    ],
    "TRADING_ANALYSIS": [
        "Where is the optimal entry and what is the risk/reward?",
        "What does institutional flow suggest about direction?",
        "How has this setup played out historically?",
        "What are the failure modes and tripwires?",
        "What is the correct position size given current risk budget?",
    ],
    "COMPANY_RESEARCH": [
        "What does this company actually do and how does it make money?",
        "What do the most recent financials and filings reveal?",
        "Who are the main competitors and what is the moat?",
        "What are the biggest growth catalysts and risk factors?",
        "What is the analyst consensus and is there a valuation disconnect?",
    ],
    "DEEP_RESEARCH": [
        "What does the data say that consensus is missing?",
        "What are the non-obvious risks?",
        "What is the asymmetric opportunity if it exists?",
        "What do the SEC filings reveal beyond the headlines?",
        "What is the highest-conviction actionable conclusion?",
    ],
    "MACRO_RISK_SCAN": [
        "What regime are we in and is it changing?",
        "What is the Fed likely to do next and why?",
        "Where is the systemic risk concentrated?",
        "Which sectors benefit and which suffer from current conditions?",
        "What is the playbook given this macro environment?",
    ],
    "REAL_ESTATE_SCAN": [
        "Are current mortgage rates favorable for buying or waiting?",
        "Is this market supply-constrained or demand-driven?",
        "What are realistic rental yields in this area?",
        "Does rent vs buy math favor ownership at this price point?",
        "What are the local market risks to be aware of?",
    ],
    "PERSONAL_WEALTH_SCAN": [
        "Am I optimizing my cash for the current rate environment?",
        "What is the fastest path to eliminating high-interest debt?",
        "What tax-advantaged opportunities am I leaving on the table?",
        "Is my emergency fund sized correctly for my risk profile?",
        "What is the single highest-leverage action I should take first?",
    ],
    "GENERAL_FINANCE": [
        "What is the direct answer to the question?",
        "What context or data supports this?",
        "What are the key caveats or risks?",
        "What should the user do next?",
    ],
    "GENERAL_CHAT": ["What is the user actually asking?"],
    "CONVERSATION": ["How can I be most helpful?"],
}

_INTENT_OUTPUT_SECTIONS: dict[str, list[str]] = {
    "MARKET_DEEP_DIVE": ["Bottom Line", "Executive Summary", "Bull Thesis", "The Setup", "How This Plays Out", "What Breaks This", "Execution Rules", "Intelligence Brief"],
    "TRADING_ANALYSIS": ["Bottom Line", "Entry & Levels", "Risk/Reward", "Execution Rules", "Historical Context", "Failure Modes"],
    "COMPANY_RESEARCH": ["Bottom Line", "Executive Summary", "Business Model", "Financial Snapshot", "Key Catalysts", "Risk Factors", "Analyst Consensus"],
    "DEEP_RESEARCH": ["Bottom Line", "Executive Summary", "Deep Analysis", "Key Findings", "Scenarios", "Risk Framework", "Intelligence Memo"],
    "MACRO_RISK_SCAN": ["Bottom Line", "Regime Assessment", "Fed Watch", "Sector Impact", "Risk Map", "Playbook"],
    "REAL_ESTATE_SCAN": ["Bottom Line", "Market Snapshot", "Rate Environment", "Rent vs Buy", "Risk Factors", "Next Steps"],
    "PERSONAL_WEALTH_SCAN": ["Bottom Line", "Wealth Overview", "Debt Strategy", "Tax Opportunities", "Savings Optimization", "Action Plan"],
    "GENERAL_FINANCE": ["Bottom Line", "Analysis", "Key Points", "Risks", "Next Steps"],
    "GENERAL_CHAT": ["Response"],
    "CONVERSATION": ["Response"],
}

_COMPLEXITY_BY_INTENT: dict[str, int] = {
    "DEEP_RESEARCH": 10, "MARKET_DEEP_DIVE": 8, "TRADING_ANALYSIS": 8,
    "COMPANY_RESEARCH": 7, "MACRO_RISK_SCAN": 6, "REAL_ESTATE_SCAN": 5,
    "PERSONAL_WEALTH_SCAN": 5, "GENERAL_FINANCE": 4, "GENERAL_CHAT": 2,
    "CONVERSATION": 1,
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ParsedGoal:
    id: int
    goal: str
    data_needed: list[str]
    priority: int = 1          # 1 = highest

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromptBlueprint:
    blueprint_id: str
    raw_query: str
    enriched_query: str        # cleaned, clarified version
    intent: str
    output_mode: str
    parsed_goals: list[ParsedGoal]
    key_questions: list[str]
    output_sections: list[str]
    data_requirements: list[str]
    tickers: list[str]
    complexity_score: int      # 1-10
    estimated_sections: int
    query_type: str            # "single_focus" | "multi_goal" | "comparison" | "conversational"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["parsed_goals"] = [g.to_dict() for g in self.parsed_goals]
        return d


# ── Query parsing helpers ─────────────────────────────────────────────────────

_SPLIT_SIGNALS = re.compile(
    r'\b(and also|and then|additionally|also|furthermore|plus|as well as|on top of that|'
    r'can you also|tell me also|i also want|while you\'re at it)\b',
    re.IGNORECASE,
)

_COMPARISON_SIGNALS = re.compile(
    r'\b(vs|versus|compare|compared to|better than|or|which is better|difference between)\b',
    re.IGNORECASE,
)

_RECOMMENDATION_SIGNALS = re.compile(
    r'\b(should i|would you|recommend|suggest|what do you think|opinion|your take|good idea|bad idea)\b',
    re.IGNORECASE,
)

_TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')
_TICKER_STOP = {
    "I", "A", "AI", "TO", "OR", "AND", "THE", "FOR", "IN", "OF", "MY",
    "DO", "IS", "AT", "BE", "ON", "ME", "US", "ETF", "SPY", "QQQ", "IWM",
    "DIA", "VIX", "GDP", "CPI", "PCE", "FED", "SEC", "CEO", "CFO", "IPO",
    "ATH", "ATL", "YTD", "EOD", "EPS", "TTM", "EV", "PE", "PB", "ROE",
    "RSI", "MACD", "IV", "OI", "PUT", "CALL", "ITM", "OTM", "ATM",
}


def _extract_tickers(query: str) -> list[str]:
    return [t for t in _TICKER_RE.findall(query) if t not in _TICKER_STOP][:5]


def _detect_query_type(query: str) -> str:
    lower = query.lower()
    if _COMPARISON_SIGNALS.search(lower):
        return "comparison"
    if _SPLIT_SIGNALS.search(lower):
        return "multi_goal"
    if any(w in lower for w in ["what is", "what are", "how does", "explain", "tell me about"]):
        return "single_focus"
    if _RECOMMENDATION_SIGNALS.search(lower):
        return "single_focus"
    if len(query.split()) <= 8:
        return "single_focus"
    return "single_focus"


def _build_goals(query: str, intent: str, tickers: list[str]) -> list[ParsedGoal]:
    """Build structured goals from the query and intent."""
    base_goals = _INTENT_GOALS.get(intent, _INTENT_GOALS["GENERAL_FINANCE"])
    lower = query.lower()

    # Detect user-specified sub-requests
    extra_goals: list[str] = []
    if "options" in lower or "calls" in lower or "puts" in lower:
        extra_goals.append("Evaluate options strategy and best contract for the setup")
    if "earnings" in lower:
        extra_goals.append("Assess earnings catalyst timing and expected move")
    if "compare" in lower or " vs " in lower:
        extra_goals.append("Run side-by-side comparison across the specified subjects")
    if "portfolio" in lower or "position" in lower or "my" in lower:
        extra_goals.append("Calibrate analysis to your current portfolio and positions")
    if "short" in lower or "short sell" in lower:
        extra_goals.append("Evaluate short thesis, borrow availability, and downside targets")
    if "crypto" in lower or "bitcoin" in lower or "btc" in lower:
        extra_goals.append("Pull on-chain metrics, funding rates, and exchange flows")
    if "tax" in lower:
        extra_goals.append("Identify tax implications and optimization opportunities")
    if "mortgage" in lower or "rate" in lower and "real estate" in lower:
        extra_goals.append("Pull current mortgage rates and affordability metrics")

    # Combine: base goals + query-specific extras, dedup, cap at 6
    all_goals = list(dict.fromkeys(base_goals[:4] + extra_goals))[:6]

    # Data needed per goal
    data_map = {
        "technical": ["price", "volume", "RSI", "MACD", "Bollinger Bands"],
        "options": ["options chain", "IV", "OI", "put/call ratio", "unusual flow"],
        "news": ["news feed", "catalyst events", "sentiment score"],
        "SEC": ["10-K", "10-Q", "8-K", "insider transactions"],
        "macro": ["CPI", "PCE", "yield curve", "Fed funds rate"],
        "portfolio": ["positions", "cost basis", "P&L", "watchlist"],
        "real estate": ["mortgage rates", "median price", "cap rate", "inventory"],
        "debt": ["APR", "balance", "minimum payment", "payoff timeline"],
        "crypto": ["price", "dominance", "funding rate", "on-chain flows"],
    }

    goals = []
    for i, goal_text in enumerate(all_goals):
        gl = goal_text.lower()
        needed = []
        if any(w in gl for w in ["technical", "price", "setup", "levels"]):
            needed.extend(data_map["technical"])
        if any(w in gl for w in ["option", "call", "put", "flow"]):
            needed.extend(data_map["options"])
        if any(w in gl for w in ["news", "sentiment", "catalyst"]):
            needed.extend(data_map["news"])
        if any(w in gl for w in ["sec", "filing", "insider"]):
            needed.extend(data_map["SEC"])
        if any(w in gl for w in ["macro", "fed", "inflation", "regime"]):
            needed.extend(data_map["macro"])
        if any(w in gl for w in ["portfolio", "position", "calibrate"]):
            needed.extend(data_map["portfolio"])
        if not needed:
            needed = ["domain knowledge", "data cache"]
        goals.append(ParsedGoal(
            id=i + 1,
            goal=goal_text,
            data_needed=list(dict.fromkeys(needed))[:4],
            priority=1 if i == 0 else (2 if i < 3 else 3),
        ))
    return goals


def _build_data_requirements(goals: list[ParsedGoal], intent: str) -> list[str]:
    all_data: list[str] = []
    for g in goals:
        all_data.extend(g.data_needed)
    return list(dict.fromkeys(all_data))[:10]


def _enrich_query(query: str, intent: str, tickers: list[str]) -> str:
    """Return a cleaned, clarified version of the raw query."""
    q = query.strip()
    # Remove filler
    q = re.sub(r'\b(um|uh|like|you know|basically|just|please|can you|could you)\b', '', q, flags=re.IGNORECASE)
    q = re.sub(r'\s{2,}', ' ', q).strip()
    # Prefix tickers if referenced implicitly
    if tickers and not any(t in q for t in tickers):
        q = f"{', '.join(tickers)}: {q}"
    return q or query


# ── Public API ────────────────────────────────────────────────────────────────

def build_blueprint(
    query: str,
    intent: str = "GENERAL_FINANCE",
    output_mode: str = "chat",
    *,
    plan: Optional[dict] = None,
    user_id: Optional[str] = None,
) -> PromptBlueprint:
    """
    Parse a user query into a structured PromptBlueprint.

    Args:
        query:       Raw user query.
        intent:      Classified intent from the router.
        output_mode: Expected output mode (trade_plan, company_report, etc.).
        plan:        Optional AgentPlan.to_dict() for context.
        user_id:     Optional user ID (personalizes portfolio goals).

    Returns:
        PromptBlueprint with goals, questions, sections, and complexity score.
    """
    tickers = _extract_tickers(query)
    query_type = _detect_query_type(query)
    enriched = _enrich_query(query, intent, tickers)

    parsed_goals = _build_goals(query, intent, tickers)
    key_questions = _INTENT_KEY_QUESTIONS.get(intent, _INTENT_KEY_QUESTIONS["GENERAL_FINANCE"])
    output_sections = _INTENT_OUTPUT_SECTIONS.get(intent, _INTENT_OUTPUT_SECTIONS["GENERAL_FINANCE"])
    data_requirements = _build_data_requirements(parsed_goals, intent)

    # Bump complexity if deep mode or multi-ticker
    base_complexity = _COMPLEXITY_BY_INTENT.get(intent, 4)
    if plan and plan.get("research_mode") == "deep":
        base_complexity = min(10, base_complexity + 1)
    if len(tickers) > 1:
        base_complexity = min(10, base_complexity + 1)

    return PromptBlueprint(
        blueprint_id=str(uuid.uuid4())[:8],
        raw_query=query[:300],
        enriched_query=enriched[:300],
        intent=intent,
        output_mode=output_mode,
        parsed_goals=parsed_goals,
        key_questions=key_questions[:5],
        output_sections=output_sections,
        data_requirements=data_requirements,
        tickers=tickers,
        complexity_score=base_complexity,
        estimated_sections=len(output_sections),
        query_type=query_type,
    )
