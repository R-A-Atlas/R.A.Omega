"""Watchlist alert report agent."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def build_alert_card(alert: dict[str, Any]) -> str:
    ticker = html.escape(str(alert.get("ticker") or "WATCH"))
    message = html.escape(str(alert.get("message") or alert.get("summary") or "Alert triggered."))
    level = html.escape(str(alert.get("level") or "INFO"))
    return f"<article><h1>{ticker}</h1><strong>{level}</strong><p>{message}</p></article>"


def write_alert_card(alert: dict[str, Any]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "watchlist_alert_latest.html"
    out.write_text(build_alert_card(alert), encoding="utf-8")
    return out
