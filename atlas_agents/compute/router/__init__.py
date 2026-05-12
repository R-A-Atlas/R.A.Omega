"""Compute router."""

from __future__ import annotations


def route_compute(task: str, *, deep_research: bool = False) -> dict[str, str]:
    text = task.lower()
    if deep_research:
        return {"engine": "deep_research", "model_tier": "high"}
    if any(w in text for w in ("hello", "hi", "thanks")) and len(text.split()) <= 4:
        return {"engine": "fast_chat", "model_tier": "low"}
    if any(w in text for w in ("analyze", "research", "compare")):
        return {"engine": "finance_analysis", "model_tier": "medium"}
    return {"engine": "general", "model_tier": "low"}
