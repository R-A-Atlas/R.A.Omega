"""
pipeline_planner.py — R.A. Omega Pipeline Planner

Selects the optimal agent team for each query, creates a structured
execution plan, and returns it to the API for display in the UI.

Usage:
    from pipeline_planner import plan_pipeline
    plan = plan_pipeline(query="Analyze NVDA", intent="MARKET_DEEP_DIVE")
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── Agent pool definitions ────────────────────────────────────────────────────

AGENT_POOL = {
    # Core
    "QueryRouter":       {"domain": "core",    "cost": 0,    "desc": "Route query to correct engine"},
    "IntentClassifier":  {"domain": "core",    "cost": 0,    "desc": "Classify intent and output mode"},
    "SynthesisAgent":    {"domain": "core",    "cost": 1,    "desc": "Gemini LLM synthesis call"},
    "QualityFirewall":   {"domain": "core",    "cost": 0,    "desc": "Validate output against contracts"},
    "PromptArchitect":   {"domain": "core",    "cost": 0,    "desc": "Build optimized synthesis prompt"},
    "MemoryInjector":    {"domain": "memory",  "cost": 0,    "desc": "Inject long-term memory context"},
    "VaultWriter":       {"domain": "memory",  "cost": 0,    "desc": "Persist session memory to vault"},
    # Market
    "EquityScraper":     {"domain": "market",  "cost": 0,    "desc": "Pull price, volume, technicals"},
    "OptionsScraper":    {"domain": "market",  "cost": 0,    "desc": "Options chain and flow data"},
    "NewsScanner":       {"domain": "market",  "cost": 0,    "desc": "Real-time news signals"},
    "SentimentAgent":    {"domain": "market",  "cost": 0,    "desc": "Social + analyst sentiment"},
    "RegimeDetector":    {"domain": "market",  "cost": 0,    "desc": "Market regime classification"},
    "SECFilingAgent":    {"domain": "market",  "cost": 0,    "desc": "SEC filings and EDGAR data"},
    "DarkPoolScanner":   {"domain": "market",  "cost": 0,    "desc": "Dark pool and block trade data"},
    "MacroScanner":      {"domain": "market",  "cost": 0,    "desc": "Macro economic indicators"},
    "BacktestEngine":    {"domain": "market",  "cost": 0,    "desc": "Historical scenario backtesting"},
    "CryptoAgent":       {"domain": "market",  "cost": 0,    "desc": "Crypto market data"},
    # Personal finance
    "WealthScanAgent":   {"domain": "finance", "cost": 0,    "desc": "Savings and wealth scan"},
    "MortgageAgent":     {"domain": "finance", "cost": 0,    "desc": "Mortgage and real estate rates"},
    "DebtOptimizer":     {"domain": "finance", "cost": 0,    "desc": "Debt payoff strategy"},
    "TaxAgent":          {"domain": "finance", "cost": 0,    "desc": "Tax optimization signals"},
    "RealEstateAgent":   {"domain": "finance", "cost": 0,    "desc": "Real estate market data"},
    # Portfolio
    "PortfolioAgent":    {"domain": "portfolio","cost": 0,   "desc": "Portfolio-aware analysis"},
    "RiskBudgetAgent":   {"domain": "portfolio","cost": 0,   "desc": "Risk budget and sizing"},
    "WatchlistAgent":    {"domain": "portfolio","cost": 0,   "desc": "Watchlist monitoring"},
    # Research
    "DeepResearchAgent": {"domain": "research","cost": 0,    "desc": "10-loop deep research run"},
    "RAGEngine":         {"domain": "research","cost": 0,    "desc": "Vector similarity retrieval"},
    "DataCache":         {"domain": "research","cost": 0,    "desc": "Cached knowledge retrieval"},
}

# ── Intent → agent team mapping ───────────────────────────────────────────────

INTENT_AGENT_MAP: dict[str, list[str]] = {
    "MARKET_DEEP_DIVE": [
        "QueryRouter", "IntentClassifier", "EquityScraper", "OptionsScraper",
        "NewsScanner", "SentimentAgent", "RegimeDetector", "MemoryInjector",
        "PortfolioAgent", "PromptArchitect", "SynthesisAgent", "QualityFirewall", "VaultWriter",
    ],
    "TRADING_ANALYSIS": [
        "QueryRouter", "IntentClassifier", "EquityScraper", "OptionsScraper",
        "DarkPoolScanner", "BacktestEngine", "RiskBudgetAgent", "PortfolioAgent",
        "PromptArchitect", "SynthesisAgent", "QualityFirewall", "VaultWriter",
    ],
    "COMPANY_RESEARCH": [
        "QueryRouter", "IntentClassifier", "EquityScraper", "NewsScanner",
        "SECFilingAgent", "SentimentAgent", "MemoryInjector", "RAGEngine",
        "PromptArchitect", "SynthesisAgent", "QualityFirewall", "VaultWriter",
    ],
    "GENERAL_FINANCE": [
        "QueryRouter", "IntentClassifier", "WealthScanAgent", "DataCache",
        "MemoryInjector", "PromptArchitect", "SynthesisAgent", "QualityFirewall",
    ],
    "GENERAL_CHAT": [
        "QueryRouter", "IntentClassifier", "SynthesisAgent", "QualityFirewall",
    ],
    "MACRO_RISK_SCAN": [
        "QueryRouter", "IntentClassifier", "MacroScanner", "RegimeDetector",
        "NewsScanner", "EquityScraper", "MemoryInjector",
        "PromptArchitect", "SynthesisAgent", "QualityFirewall",
    ],
    "REAL_ESTATE_SCAN": [
        "QueryRouter", "IntentClassifier", "RealEstateAgent", "MortgageAgent",
        "DataCache", "PromptArchitect", "SynthesisAgent", "QualityFirewall",
    ],
    "PERSONAL_WEALTH_SCAN": [
        "QueryRouter", "IntentClassifier", "WealthScanAgent", "DebtOptimizer",
        "TaxAgent", "MemoryInjector", "PromptArchitect", "SynthesisAgent", "QualityFirewall",
    ],
    "DEEP_RESEARCH": [
        "QueryRouter", "IntentClassifier", "DeepResearchAgent", "EquityScraper",
        "NewsScanner", "SECFilingAgent", "RAGEngine", "MemoryInjector",
        "PortfolioAgent", "PromptArchitect", "SynthesisAgent", "QualityFirewall", "VaultWriter",
    ],
    "CONVERSATION": [
        "QueryRouter", "SynthesisAgent",
    ],
}

DEFAULT_AGENTS = INTENT_AGENT_MAP["GENERAL_FINANCE"]


# ── Plan dataclass ────────────────────────────────────────────────────────────

@dataclass
class AgentPlan:
    intent: str
    output_mode: str
    agents: list[str]
    agent_count: int
    estimated_loops: int
    estimated_ms: int
    plan_steps: list[dict]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Core planner ─────────────────────────────────────────────────────────────

def plan_pipeline(
    query: str,
    intent: str = "GENERAL_FINANCE",
    output_mode: str = "chat",
    research_mode: str = "normal",
    *,
    user_id: Optional[str] = None,
) -> AgentPlan:
    """
    Select the optimal agent team and create a structured execution plan.

    Args:
        query:         The user's raw query string.
        intent:        Classified intent (e.g. MARKET_DEEP_DIVE).
        output_mode:   Expected output mode (trade_plan, company_report, chat, etc.).
        research_mode: "normal" | "deep" — affects loop count.
        user_id:       Optional user ID for portfolio-aware planning.

    Returns:
        AgentPlan with selected agents and execution steps.
    """
    t0 = time.monotonic()

    # Deep research always uses the full deep team
    if research_mode == "deep":
        intent = "DEEP_RESEARCH"

    agents = list(INTENT_AGENT_MAP.get(intent, DEFAULT_AGENTS))

    # Add portfolio agent for authenticated users
    if user_id and user_id != "test_user_local" and "PortfolioAgent" not in agents:
        agents.insert(-2, "PortfolioAgent")

    # Estimate loop count
    loop_map = {
        "DEEP_RESEARCH": 10, "MARKET_DEEP_DIVE": 10, "TRADING_ANALYSIS": 8,
        "COMPANY_RESEARCH": 7, "MACRO_RISK_SCAN": 6, "REAL_ESTATE_SCAN": 5,
        "PERSONAL_WEALTH_SCAN": 5, "GENERAL_FINANCE": 4, "GENERAL_CHAT": 2,
        "CONVERSATION": 1,
    }
    loops = loop_map.get(intent, 4)

    # Estimate wall-clock time (ms)
    base_ms = {1: 800, 2: 1200, 4: 2500, 5: 4000, 6: 6000, 7: 8000, 8: 10000, 10: 14000}
    est_ms = base_ms.get(loops, loops * 1400)

    # Build ordered plan steps
    steps = _build_steps(agents, intent, loops)

    elapsed_us = int((time.monotonic() - t0) * 1_000_000)

    return AgentPlan(
        intent=intent,
        output_mode=output_mode,
        agents=agents,
        agent_count=len(agents),
        estimated_loops=loops,
        estimated_ms=est_ms,
        plan_steps=steps,
        metadata={
            "query_preview": query[:80],
            "research_mode": research_mode,
            "user_id": user_id,
            "plan_generated_us": elapsed_us,
        },
    )


def _build_steps(agents: list[str], intent: str, loops: int) -> list[dict]:
    """Build human-readable ordered step list from agent team."""
    steps = []

    phase_map = {
        "QueryRouter": ("Intake", 1),
        "IntentClassifier": ("Classify", 1),
        "DeepResearchAgent": ("Deep Research", 2),
        "EquityScraper": ("Data Collection", 3),
        "OptionsScraper": ("Data Collection", 3),
        "NewsScanner": ("Data Collection", 3),
        "SentimentAgent": ("Data Collection", 3),
        "SECFilingAgent": ("Data Collection", 3),
        "MacroScanner": ("Data Collection", 3),
        "DarkPoolScanner": ("Data Collection", 3),
        "BacktestEngine": ("Data Collection", 3),
        "CryptoAgent": ("Data Collection", 3),
        "WealthScanAgent": ("Data Collection", 3),
        "MortgageAgent": ("Data Collection", 3),
        "DebtOptimizer": ("Data Collection", 3),
        "TaxAgent": ("Data Collection", 3),
        "RealEstateAgent": ("Data Collection", 3),
        "RAGEngine": ("Memory Retrieval", 4),
        "MemoryInjector": ("Memory Retrieval", 4),
        "DataCache": ("Memory Retrieval", 4),
        "PortfolioAgent": ("Personalization", 5),
        "RiskBudgetAgent": ("Personalization", 5),
        "WatchlistAgent": ("Personalization", 5),
        "RegimeDetector": ("Context", 5),
        "PromptArchitect": ("Synthesis Prep", 6),
        "SynthesisAgent": ("Synthesis", 7),
        "QualityFirewall": ("Quality Control", 8),
        "VaultWriter": ("Learning", 9),
    }

    seen_phases: set[str] = set()
    for agent in agents:
        meta = AGENT_POOL.get(agent, {})
        phase, order = phase_map.get(agent, ("Execute", 6))
        steps.append({
            "order": order,
            "phase": phase,
            "agent": agent,
            "action": meta.get("desc", "Processing"),
        })

    steps.sort(key=lambda s: (s["order"], s["agent"]))
    return steps
