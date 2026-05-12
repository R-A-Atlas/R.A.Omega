"""Specialist activation graph for R.A. Omega.

This deterministic layer maps a user query plus the coarse route decision into
the small set of specialist agents that should contribute context. It is the
first production slice of the "neural web" architecture: route to expert
clusters, collect compact packets, then let the synthesizer write the answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from orchestration.router_policy import RouteDecision


@dataclass(frozen=True)
class SpecialistAgent:
    agent_id: str
    name: str
    division: str
    packet_key: str
    cache_file: str | None
    role: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentActivation:
    route: str
    complexity: str
    agents: list[SpecialistAgent]
    reasons: list[str]
    max_parallel: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "complexity": self.complexity,
            "agents": [a.to_dict() for a in self.agents],
            "agent_ids": [a.agent_id for a in self.agents],
            "packet_keys": [a.packet_key for a in self.agents],
            "reasons": list(self.reasons),
            "max_parallel": self.max_parallel,
        }


AGENTS: dict[str, SpecialistAgent] = {
    "D1": SpecialistAgent("D1", "Crypto Hound", "Trading Desk", "crypto", "crypto_top50_latest.json", "crypto market context"),
    "D2": SpecialistAgent("D2", "Equities Scanner", "Trading Desk", "equities", "equities_latest.json", "equity movers and ticker context"),
    "D3": SpecialistAgent("D3", "Options Flow Monitor", "Trading Desk", "options_flow", "options_flow_latest.json", "unusual options activity"),
    "D4": SpecialistAgent("D4", "Insider Tracker", "Trading Desk", "insider_trades", "insider_trades_latest.json", "SEC Form 4 insider activity"),
    "D5": SpecialistAgent("D5", "Earnings Parser", "Trading Desk", "earnings", "earnings_latest.json", "earnings calendar and surprise context"),
    "D6": SpecialistAgent("D6", "Forex Radar", "Trading Desk", "forex", "forex_latest.json", "currency and dollar context"),
    "D7": SpecialistAgent("D7", "Commodities Watch", "Trading Desk", "commodities", "commodities_latest.json", "commodity and inflation-sensitive context"),
    "D8": SpecialistAgent("D8", "Dark Pool Monitor", "Trading Desk", "dark_pool", "dark_pool_latest.json", "large off-exchange equity prints"),
    "D10": SpecialistAgent("D10", "Bond Yield Curve", "Trading Desk", "bond_yields", "bond_yields_latest.json", "rates and yield curve context"),
    "M1": SpecialistAgent("M1", "Fed Rate Probability", "Macro", "fed_watch", "fed_watch_latest.json", "Fed policy expectations"),
    "M7": SpecialistAgent("M7", "Inflation CPI Bot", "Macro", "inflation", "cpi_latest.json", "inflation context"),
    "M8": SpecialistAgent("M8", "Congressional Trade Watcher", "Macro", "congress_trades", "congress_trades_latest.json", "Congressional disclosure context"),
    "M9": SpecialistAgent("M9", "Global Liquidity Monitor", "Macro", "global_liquidity", "global_liquidity_latest.json", "global liquidity context"),
    "IQ1": SpecialistAgent("IQ1", "Cross Asset Correlation", "Intelligence", "correlation", "correlation_latest.json", "cross-asset relationship context"),
    "IQ2": SpecialistAgent("IQ2", "Regime Change Detector", "Intelligence", "regime_change", "regime_change_latest.json", "market regime context"),
    "IQ3": SpecialistAgent("IQ3", "Earnings Season Coordinator", "Intelligence", "earnings_season", "earnings_season_brief_latest.json", "earnings-season context"),
    "IQ4": SpecialistAgent("IQ4", "Sector Rotation Agent", "Intelligence", "sector_rotation", "sector_rotation_latest.json", "sector leadership context"),
    "IQ5": SpecialistAgent("IQ5", "News Catalyst Agent", "Intelligence", "news_catalysts", "news_catalysts_latest.json", "news catalyst context"),
    "IQ8": SpecialistAgent("IQ8", "Risk Budget Agent", "Intelligence", "risk_budget", "risk_budget_latest.json", "position sizing and portfolio risk context"),
    "R1": SpecialistAgent("R1", "Residential Scout", "Real Estate", "residential", "residential_latest.json", "home-buying market context"),
    "R2": SpecialistAgent("R2", "Rental Yield Calculator", "Real Estate", "rental_yield", "rental_yield_latest.json", "rent versus buy yield context"),
    "R7": SpecialistAgent("R7", "Mortgage Rate Tracker", "Real Estate", "mortgage_rates", "mortgage_rates_latest.json", "mortgage-rate context"),
    "W1": SpecialistAgent("W1", "Credit Card Optimizer", "Wealth", "credit_cards", "credit_cards_latest.json", "credit-card payoff and rewards context"),
    "W3": SpecialistAgent("W3", "Student Debt Monitor", "Wealth", "student_debt", "student_debt_latest.json", "student-loan context"),
    "W4": SpecialistAgent("W4", "HYSA Tracker", "Wealth", "hysa", "hysa_latest.json", "cash yield context"),
    "W5": SpecialistAgent("W5", "IRA 401k Limit Bot", "Wealth", "retirement_limits", "retirement_limits_latest.json", "retirement contribution limit context"),
    "W7": SpecialistAgent("W7", "Cost of Living Indexer", "Wealth", "cost_of_living", "col_latest.json", "location cost context"),
    "L1": SpecialistAgent("L1", "Federal Tax Code Bot", "Legal", "federal_tax", "federal_tax_latest.json", "federal tax context"),
    "L2": SpecialistAgent("L2", "State Tax Monitor", "Legal", "state_tax", "state_tax_latest.json", "state tax context"),
    "L4": SpecialistAgent("L4", "SEC EDGAR Bot", "Legal", "sec_filings", "sec_filings_latest.json", "SEC filing context"),
    "B1": SpecialistAgent("B1", "SBA Grant Loan Finder", "Business", "sba", "sba_latest.json", "small-business capital context"),
    "B2": SpecialistAgent("B2", "B2B SaaS Metrics Bot", "Business", "saas_metrics", "saas_metrics_latest.json", "SaaS unit economics context"),
    "B5": SpecialistAgent("B5", "Franchise Evaluator", "Business", "franchise", "franchise_latest.json", "franchise economics context"),
    "P1": SpecialistAgent("P1", "Broker Integration Agent", "Platform", "broker", None, "portfolio/broker position context"),
    "P7": SpecialistAgent("P7", "Compliance Archive Agent", "Platform", "compliance", None, "compliance and audit context"),
}


_TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")
_TRADING_RE = re.compile(r"\b(trade|trading|stock|ticker|shares?|equity|chart|technical|support|resistance|breakout|trend|swing|scalp|day\s+trade)\b", re.I)
_OPTIONS_RE = re.compile(r"\b(options?|calls?|puts?|strike|expiry|expiration|iv|theta|gamma|delta|spread|covered\s+call|cash-secured)\b", re.I)
_EARNINGS_RE = re.compile(r"\b(earnings|guidance|revenue|eps|margin|quarter|10-q|10-k|filing)\b", re.I)
_MACRO_RE = re.compile(r"\b(macro|fed|rates?|inflation|cpi|yield|liquidity|recession|dollar|forex|commodit)\b", re.I)
_CRYPTO_RE = re.compile(r"\b(crypto|bitcoin|btc|ethereum|eth|wallet|stablecoin|defi|coinbase|binance|kraken|metamask)\b", re.I)
_REAL_ESTATE_RE = re.compile(r"\b(home|house|mortgage|rent|rental|airbnb|real\s+estate|property|reit)\b", re.I)
_PERSONAL_FINANCE_RE = re.compile(r"\b(debt|credit\s+card|student\s+loan|hysa|savings|retirement|401k|ira|insurance|budget)\b", re.I)
_TAX_RE = re.compile(r"\b(tax|irs|capital\s+gains|wash\s+sale|deduct|llc|s-corp|state\s+tax)\b", re.I)
_BUSINESS_RE = re.compile(r"\b(business|startup|saas|sba|grant|franchise|runway|pricing|cash\s+flow|llc)\b", re.I)
_PORTFOLIO_RE = re.compile(r"\b(portfolio|position|allocation|rebalance|risk|size|drawdown|correlation|hedge)\b", re.I)
_CONGRESS_RE = re.compile(r"\b(congress|politician|senate|house\s+trade|stock\s+act)\b", re.I)


def activate_specialists(query: str, route_decision: RouteDecision) -> AgentActivation:
    q = query or ""
    selected: list[str] = []
    reasons: list[str] = []

    def add(ids: list[str], reason: str) -> None:
        added = False
        for agent_id in ids:
            if agent_id in AGENTS and agent_id not in selected:
                selected.append(agent_id)
                added = True
        if added and reason not in reasons:
            reasons.append(reason)

    if route_decision.route_band == "quick_chat":
        return AgentActivation("conversation", route_decision.route_band, [], ["quick_chat_no_specialists"], 0)

    tickers = [t for t in _TICKER_RE.findall(q) if t.upper() not in {"I", "A", "THE", "AND", "FOR", "USA", "USD"}]
    if tickers or _TRADING_RE.search(q):
        add(["D2", "IQ4", "IQ8"], "equity_or_trading_context")
    if _OPTIONS_RE.search(q):
        add(["D3", "D8", "IQ8"], "options_or_derivatives_context")
    if _EARNINGS_RE.search(q):
        add(["D5", "IQ3", "L4"], "earnings_or_filing_context")
    if _CRYPTO_RE.search(q):
        add(["D1"], "crypto_context")
        if re.search(r"\b(wallet|stablecoin|coinbase|binance|kraken|metamask)\b", q, re.I):
            add(["L1"], "crypto_tax_transfer_context")
    if _REAL_ESTATE_RE.search(q):
        add(["R1", "R2", "R7", "W7"], "real_estate_context")
    if _MACRO_RE.search(q):
        add(["M1", "M7", "M9", "D10", "IQ2"], "macro_context")
    if _PERSONAL_FINANCE_RE.search(q):
        add(["W1", "W3", "W4", "W5"], "personal_finance_context")
    if _TAX_RE.search(q):
        add(["L1", "L2"], "tax_context")
    if _BUSINESS_RE.search(q):
        add(["B1", "B2", "B5"], "business_context")
    if _PORTFOLIO_RE.search(q):
        add(["P1", "IQ1", "IQ8"], "portfolio_risk_context")
    if _CONGRESS_RE.search(q):
        add(["M8"], "congressional_disclosure_context")
    if route_decision.compliance_flags:
        add(["P7"], "compliance_context")
    if route_decision.route_band == "deep_research":
        add(["IQ2", "IQ5"], "deep_research_context")

    if not selected and route_decision.route_band in {"market_snapshot", "focused_analysis", "deep_research"}:
        add(["D2", "IQ2", "IQ8"], "default_finance_context")

    budget = max(route_decision.tool_budget, 1)
    max_agents = min(max(budget, 3), 8)
    selected = selected[:max_agents]
    route = _route_name(q, selected, route_decision)
    return AgentActivation(
        route=route,
        complexity=route_decision.route_band,
        agents=[AGENTS[agent_id] for agent_id in selected],
        reasons=reasons or ["default"],
        max_parallel=min(len(selected), 5),
    )


def _route_name(query: str, selected: list[str], route_decision: RouteDecision) -> str:
    q = query or ""
    if _OPTIONS_RE.search(q):
        return "options_trade_analysis"
    if _CRYPTO_RE.search(q):
        return "crypto_finance_analysis"
    if _REAL_ESTATE_RE.search(q):
        return "real_estate_finance_analysis"
    if _PERSONAL_FINANCE_RE.search(q):
        return "personal_finance_analysis"
    if _BUSINESS_RE.search(q):
        return "business_finance_analysis"
    if _MACRO_RE.search(q):
        return "macro_market_analysis"
    if selected:
        return "specialist_finance_analysis"
    return route_decision.route_band


__all__ = ["AGENTS", "AgentActivation", "SpecialistAgent", "activate_specialists"]
