"""Market regime change detector."""

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
    return {
        "generated_at": _now(),
        "regime": "RISK_ON_WITH_RATE_CAUTION",
        "confidence": 0.72,
        "inputs": {
            "spx_trend": "UP",
            "credit_spreads": "STABLE",
            "vix_level": 17.8,
            "dxy_trend": "FLAT",
            "yield_curve": "INVERTED_BUT_STEEPENING",
        },
        "risk_flags": ["duration_sensitive_assets", "late_cycle_credit"],
        "recommended_posture": "Favor quality growth and cash-flow durability; avoid high leverage.",
    }


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "regime_change_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
