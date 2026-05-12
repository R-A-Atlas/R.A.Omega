"""Earnings season coordinator."""

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
    clusters = [
        {"theme": "AI infrastructure", "tickers": ["NVDA", "AVGO", "AMD", "MSFT"], "watch": "capex guidance"},
        {"theme": "consumer credit", "tickers": ["JPM", "AXP", "COF"], "watch": "charge-offs and delinquencies"},
        {"theme": "advertising demand", "tickers": ["META", "GOOGL", "AMZN"], "watch": "ad pricing and margins"},
    ]
    return {
        "generated_at": _now(),
        "season": "Q1 2026",
        "record_count": len(clusters),
        "clusters": clusters,
        "brief": "Focus on guidance revisions, margin durability, and capex commentary.",
    }


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "earnings_season_brief_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
