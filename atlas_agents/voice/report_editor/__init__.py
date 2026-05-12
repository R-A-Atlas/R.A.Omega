"""Natural-language report editor."""

from __future__ import annotations

from pathlib import Path


def apply_instruction(html_text: str, instruction: str) -> str:
    note = f"\n<!-- edit: {instruction.strip()} -->\n" if instruction.strip() else ""
    return html_text.rstrip() + note


def edit_report(path: str | Path, instruction: str) -> Path:
    report_path = Path(path)
    text = report_path.read_text(encoding="utf-8")
    report_path.write_text(apply_instruction(text, instruction), encoding="utf-8")
    return report_path
