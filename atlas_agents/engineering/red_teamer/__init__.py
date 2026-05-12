"""Red team prompt scanner."""

from __future__ import annotations

RISK_TERMS = ("ignore previous", "exfiltrate", "api key", "bypass")


def scan_prompt(text: str) -> dict[str, object]:
    hits = [t for t in RISK_TERMS if t in text.lower()]
    return {"risk": "HIGH" if hits else "LOW", "hits": hits}
