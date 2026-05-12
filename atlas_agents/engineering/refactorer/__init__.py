"""Refactor planning helper."""

from __future__ import annotations


def propose_extraction(symbol: str, files: list[str]) -> dict[str, object]:
    return {"symbol": symbol, "files": files, "action": "extract_shared_helper" if len(files) > 1 else "keep_local"}
