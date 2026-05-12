"""Sentiment divergence agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrape() -> dict[str, Any]:
    divergences = [
        {"ticker": "AAPL", "price_trend": "UP", "sentiment_trend": "DOWN", "signal": "NEGATIVE_DIVERGENCE"},
        {"ticker": "NVDA", "price_trend": "UP", "sentiment_trend": "UP", "signal": "CONFIRMED_MOMENTUM"},
        {"ticker": "DIS", "price_trend": "DOWN", "sentiment_trend": "UP", "signal": "POTENTIAL_REVERSAL"},
        {"ticker": "XLF", "price_trend": "FLAT", "sentiment_trend": "DOWN", "signal": "WATCHLIST"},
    ]
    return {"generated_at": _now(), "record_count": len(divergences), "divergences": divergences}


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "sentiment_divergence_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
