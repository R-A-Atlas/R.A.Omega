"""Portfolio risk budget agent."""

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
    sleeves = [
        {"sleeve": "US equities", "target_weight": 0.45, "risk_budget": 0.52, "status": "OK"},
        {"sleeve": "International equities", "target_weight": 0.15, "risk_budget": 0.18, "status": "OK"},
        {"sleeve": "Fixed income", "target_weight": 0.25, "risk_budget": 0.16, "status": "UNDERUSED"},
        {"sleeve": "Alternatives", "target_weight": 0.10, "risk_budget": 0.10, "status": "OK"},
        {"sleeve": "Cash", "target_weight": 0.05, "risk_budget": 0.04, "status": "OK"},
    ]
    return {
        "generated_at": _now(),
        "portfolio_risk_score": 63,
        "max_single_sleeve_risk": 0.52,
        "record_count": len(sleeves),
        "sleeves": sleeves,
        "action": "Trim concentrated equity beta before adding leverage.",
    }


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "risk_budget_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
