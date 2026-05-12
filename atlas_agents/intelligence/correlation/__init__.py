"""Cross-asset correlation agent."""

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
    pairs = [
        {"asset_a": "SPY", "asset_b": "QQQ", "correlation_30d": 0.92, "signal": "CROWDED_RISK_ON"},
        {"asset_a": "SPY", "asset_b": "TLT", "correlation_30d": -0.41, "signal": "DIVERSIFIER_ACTIVE"},
        {"asset_a": "DXY", "asset_b": "GLD", "correlation_30d": -0.63, "signal": "DOLLAR_HEDGE"},
        {"asset_a": "BTC-USD", "asset_b": "QQQ", "correlation_30d": 0.58, "signal": "GROWTH_BETA"},
        {"asset_a": "USO", "asset_b": "XLE", "correlation_30d": 0.77, "signal": "ENERGY_FACTOR"},
    ]
    return {"generated_at": _now(), "record_count": len(pairs), "pairs": pairs}


def write_outputs(payload: dict[str, Any] | None = None) -> Path:
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_CACHE_DIR / "correlation_latest.json"
    out.write_text(json.dumps(payload or scrape(), indent=2) + "\n", encoding="utf-8")
    return out
