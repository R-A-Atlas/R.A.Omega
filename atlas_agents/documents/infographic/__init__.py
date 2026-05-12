"""Infographic generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
CHART_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Charts"


def build_svg(title: str, metrics: dict[str, Any]) -> str:
    rows = "".join(
        f'<text x="32" y="{92 + i * 34}" fill="#dbeafe" font-size="18">{k}: {v}</text>'
        for i, (k, v) in enumerate(metrics.items())
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520">'
        '<rect width="900" height="520" fill="#08111f"/>'
        f'<text x="32" y="54" fill="#ffffff" font-size="32" font-family="Arial">{title}</text>'
        f"{rows}</svg>"
    )


def write_infographic(title: str, metrics: dict[str, Any], filename: str = "infographic_latest.svg") -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out = CHART_DIR / filename
    out.write_text(build_svg(title, metrics), encoding="utf-8")
    return out
