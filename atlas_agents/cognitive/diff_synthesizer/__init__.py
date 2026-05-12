"""Diff synthesizer."""

from __future__ import annotations

import difflib


def synthesize_diff(before: str, after: str, filename: str = "file.txt") -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )
