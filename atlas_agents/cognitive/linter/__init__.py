"""Static linter security scanner."""

from __future__ import annotations

from pathlib import Path

DANGEROUS_PATTERNS = ("eval(", "exec(", "subprocess.Popen", "shell=True")


def scan_text(text: str) -> list[str]:
    return [p for p in DANGEROUS_PATTERNS if p in text]


def scan_file(path: str | Path) -> dict[str, object]:
    p = Path(path)
    violations = scan_text(p.read_text(encoding="utf-8", errors="ignore"))
    return {"path": str(p), "status": "CLEAN" if not violations else "VIOLATIONS", "violations": violations}
