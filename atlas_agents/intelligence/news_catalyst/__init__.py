"""News catalyst agent."""

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
    catalysts = [
        {"ticker": "NVDA", "type": "PRODUCT", "impact": "HIGH", "summary": "AI accelerator cycle supports demand."},
        {"ticker": "TSLA", "type": "REGULATORY", "impact": "MEDIUM", "summary": "Autonomy and tariff headlines increase volatility."},
        {"ticker": "JPM", "type": "MACRO", "impact": "MEDIUM", "summary": "Credit quality commentary remains a banking signal."},
        {"ticker": "XLE", "type": "COMMODITY", "impact": "MEDIUM", "summary": "Oil inventory changes affect energy beta."},
    ]
    return {"generated_at": _now(), "record_count": len(catalysts), "catalysts": catalysts}


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "news_catalysts_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
