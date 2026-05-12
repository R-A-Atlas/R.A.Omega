"""Portfolio report agent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def build_portfolio_report(positions: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(float(p.get("market_value", 0)) for p in positions)
    rows = []
    for p in positions:
        value = float(p.get("market_value", 0))
        rows.append({**p, "weight": round(value / total, 4) if total else 0})
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "total_value": total, "positions": rows}


def write_portfolio_report(positions: list[dict[str, Any]]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "portfolio_latest.json"
    out.write_text(json.dumps(build_portfolio_report(positions), indent=2) + "\n", encoding="utf-8")
    return out
