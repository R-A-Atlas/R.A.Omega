"""
output_contracts.py — Required and forbidden sections per output mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COMMON_TRADE_FORBIDDEN: list[str] = [
    "trade plan",
    "entry price",
    "stop loss",
    "take profit",
    "execution rules",
    "risk/reward",
    "risk reward",
    "position size",
    "invalidation level",
    "options play",
]


@dataclass(frozen=True)
class OutputContract:
    required_sections: tuple[str, ...] = field(default_factory=tuple)
    forbidden_phrases: tuple[str, ...] = field(default_factory=tuple)
    tone: str = "clear and helpful"
    requires_sources: bool = False


OUTPUT_CONTRACTS: dict[str, OutputContract] = {
    "chat": OutputContract(
        required_sections=(),
        forbidden_phrases=tuple(COMMON_TRADE_FORBIDDEN),
        tone="casual, direct, helpful",
        requires_sources=False,
    ),

    "finance_answer": OutputContract(
        required_sections=(),
        forbidden_phrases=tuple(COMMON_TRADE_FORBIDDEN),
        tone="professional but readable",
        requires_sources=False,
    ),

    "company_report": OutputContract(
        required_sections=(
            "Overview",
            "Business Model",
            "Financial Snapshot",
            "Leadership",
            "Recent News",
            "Risks",
            "Competitive Position",
        ),
        forbidden_phrases=tuple(COMMON_TRADE_FORBIDDEN),
        tone="professional, structured, data-driven",
        requires_sources=True,
    ),

    "document": OutputContract(
        required_sections=(),
        forbidden_phrases=tuple(COMMON_TRADE_FORBIDDEN),
        tone="polished, professional, publication-ready",
        requires_sources=False,
    ),

    "html_artifact": OutputContract(
        required_sections=("<!DOCTYPE html", "<html"),
        forbidden_phrases=(),
        tone="high-visual, polished, interactive where appropriate",
        requires_sources=False,
    ),

    "market_snapshot": OutputContract(
        required_sections=(),
        forbidden_phrases=("guaranteed profit", "risk-free"),
        tone="concise, data-driven, market-aware",
        requires_sources=True,
    ),

    "trade_plan": OutputContract(
        required_sections=("Setup", "Entry", "Invalidation", "Risk", "Scenarios"),
        forbidden_phrases=("guaranteed profit", "risk-free"),
        tone="precise, risk-aware, educational",
        requires_sources=True,
    ),
}
