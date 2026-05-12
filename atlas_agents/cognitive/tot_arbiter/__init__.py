"""Tree-of-thoughts arbiter."""

from __future__ import annotations

from typing import Any


def arbitrate(bull: dict[str, Any], bear: dict[str, Any]) -> dict[str, Any]:
    bull_score = float(bull.get("confidence", 0.5))
    bear_score = float(bear.get("confidence", 0.5))
    winner = "bull" if bull_score >= bear_score else "bear"
    return {"winner": winner, "bull": bull, "bear": bear, "conclusion": bull.get("thesis") if winner == "bull" else bear.get("thesis")}
