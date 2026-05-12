"""White-label branding helper."""

from __future__ import annotations

from typing import Any


def apply_branding(config: dict[str, Any], html_text: str) -> str:
    brand = str(config.get("brand_name") or "R.A. Omega")
    accent = str(config.get("accent_color") or "#3b82f6")
    return html_text.replace("R.A. Omega", brand).replace("--accent:#3b82f6", f"--accent:{accent}")
