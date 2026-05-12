"""Materialize prompt-only agent folders into executable prompt-backed modules."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_audit import AGENTS_ROOT, collect_agent_audit


TEMPLATE = '''"""Executable prompt-backed wrapper for this R.A. Omega agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_agents.agent_runtime import run_prompt_backed_agent


AGENT_DIR = Path(__file__).resolve().parent


def run(query: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return this agent's structured specialist packet."""
    return run_prompt_backed_agent(AGENT_DIR, query=query, context=context)


def describe() -> dict[str, Any]:
    """Return this agent's metadata and operating contract."""
    return run(query="", context={})


__all__ = ["describe", "run"]
'''


def main() -> int:
    report = collect_agent_audit()
    created: list[str] = []
    for agent in report["agents"]:
        if agent["status"] != "prompt_only":
            continue
        agent_dir = AGENTS_ROOT.parent / agent["path"]
        target = agent_dir / "agent.py"
        if target.exists():
            continue
        target.write_text(TEMPLATE, encoding="utf-8", newline="\n")
        created.append(target.relative_to(AGENTS_ROOT.parent).as_posix())
    print(f"created={len(created)}")
    for path in created:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
