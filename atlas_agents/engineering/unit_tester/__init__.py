"""Unit test scaffolding helper."""

from __future__ import annotations


def build_smoke_test(module: str) -> str:
    return f"def test_{module.replace('.', '_')}_imports():\n    import {module}\n"
