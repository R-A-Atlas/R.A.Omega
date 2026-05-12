"""Agent registry audit utilities for R.A. Omega.

The audit is intentionally filesystem-based. An agent is a directory with an
AGENT_PROMPT.md file; real implementation means at least one Python file beyond
__init__.py with non-trivial content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = ROOT / "atlas_agents"
TESTS_ROOT = ROOT / "tests"


@dataclass(frozen=True)
class AgentAuditRow:
    division: str
    agent: str
    path: str
    prompt_bytes: int
    logic_files: list[str]
    test_references: int

    @property
    def has_logic(self) -> bool:
        return bool(self.logic_files)

    @property
    def has_tests(self) -> bool:
        return self.test_references > 0

    @property
    def status(self) -> str:
        if self.has_logic and self.has_tests:
            return "built_verified"
        if self.has_logic:
            return "built_unverified"
        return "prompt_only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "division": self.division,
            "agent": self.agent,
            "path": self.path,
            "prompt_bytes": self.prompt_bytes,
            "logic_files": self.logic_files,
            "logic_file_count": len(self.logic_files),
            "test_references": self.test_references,
            "has_logic": self.has_logic,
            "has_tests": self.has_tests,
            "status": self.status,
        }


def _read_test_index(tests_root: Path = TESTS_ROOT) -> str:
    if not tests_root.exists():
        return ""
    chunks: list[str] = []
    for path in tests_root.rglob("test_*.py"):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(chunks).lower()


def _is_real_logic_file(path: Path) -> bool:
    if path.name == "__init__.py":
        return False
    if "__pycache__" in path.parts:
        return False
    if path.suffix != ".py":
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return False
    if len(text) < 80:
        return False
    return True


def _test_reference_count(agent_dir: Path, test_index: str) -> int:
    try:
        rel_path = agent_dir.relative_to(ROOT)
    except ValueError:
        rel_path = agent_dir
    rel = rel_path.as_posix().lower()
    module = ".".join(rel_path.parts).lower()
    slash_hits = test_index.count(rel)
    module_hits = test_index.count(module)
    return slash_hits + module_hits


def collect_agent_audit(
    agents_root: Path = AGENTS_ROOT,
    tests_root: Path = TESTS_ROOT,
) -> dict[str, Any]:
    """Return a deterministic audit of all agent prompt directories."""
    test_index = _read_test_index(tests_root)
    rows: list[AgentAuditRow] = []

    if not agents_root.exists():
        return {
            "ok": False,
            "error": f"missing agents root: {agents_root}",
            "summary": {},
            "divisions": {},
            "agents": [],
        }

    for prompt in sorted(agents_root.rglob("AGENT_PROMPT.md")):
        agent_dir = prompt.parent
        rel_parts = agent_dir.relative_to(agents_root).parts
        if not rel_parts:
            continue
        division = rel_parts[0]
        agent = "/".join(rel_parts[1:]) if len(rel_parts) > 1 else rel_parts[0]
        logic_files = [
            p.relative_to(agent_dir).as_posix()
            for p in sorted(agent_dir.rglob("*.py"))
            if _is_real_logic_file(p)
        ]
        rows.append(
            AgentAuditRow(
                division=division,
                agent=agent,
                path=Path(agents_root.name, *rel_parts).as_posix(),
                prompt_bytes=prompt.stat().st_size,
                logic_files=logic_files,
                test_references=_test_reference_count(agent_dir, test_index),
            )
        )

    summary = {
        "total_agents": len(rows),
        "built_verified": sum(1 for row in rows if row.status == "built_verified"),
        "built_unverified": sum(1 for row in rows if row.status == "built_unverified"),
        "prompt_only": sum(1 for row in rows if row.status == "prompt_only"),
        "with_logic": sum(1 for row in rows if row.has_logic),
        "with_tests": sum(1 for row in rows if row.has_tests),
    }

    divisions: dict[str, dict[str, int]] = {}
    for row in rows:
        div = divisions.setdefault(
            row.division,
            {
                "total_agents": 0,
                "built_verified": 0,
                "built_unverified": 0,
                "prompt_only": 0,
                "with_logic": 0,
            },
        )
        div["total_agents"] += 1
        div[row.status] += 1
        if row.has_logic:
            div["with_logic"] += 1

    return {
        "ok": True,
        "summary": summary,
        "divisions": dict(sorted(divisions.items())),
        "agents": [row.as_dict() for row in rows],
    }


__all__ = ["collect_agent_audit"]
