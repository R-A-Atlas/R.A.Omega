"""Executable prompt-backed wrapper for this R.A. Omega agent."""

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
