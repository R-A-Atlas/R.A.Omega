"""Shared runtime for prompt-backed R.A. Omega agents.

This does not pretend a prompt-only agent has a live data scraper. It gives
every agent package executable, deterministic behavior: load its contract,
extract the useful sections, and return a structured specialist packet that the
router/synthesizer can consume or a developer can inspect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_agent_prompt(agent_dir: str | Path) -> str:
    path = Path(agent_dir) / "AGENT_PROMPT.md"
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_prompt_sections(prompt: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip().lower().replace(" ", "_")
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.rstrip())
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _first_header(prompt: str, fallback: str) -> str:
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback.replace("_", " ").replace("-", " ").title()


def _extract_metadata(prompt: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in prompt.splitlines()[:12]:
        stripped = line.strip()
        if stripped.startswith("# ID:"):
            meta["id"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("# Status:"):
            meta["source_status"] = stripped.split(":", 1)[1].strip()
    return meta


def _query_terms(query: str) -> set[str]:
    return {
        word.strip(".,:;!?()[]{}\"'").lower()
        for word in query.split()
        if len(word.strip(".,:;!?()[]{}\"'")) >= 4
    }


def relevance_score(prompt: str, query: str) -> float:
    terms = _query_terms(query)
    if not terms:
        return 0.0
    body = prompt.lower()
    hits = sum(1 for term in terms if term in body)
    return round(min(1.0, hits / max(3, len(terms))), 3)


def run_prompt_backed_agent(
    agent_dir: str | Path,
    query: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a compact specialist packet for one prompt-backed agent."""
    directory = Path(agent_dir)
    prompt = read_agent_prompt(directory)
    sections = parse_prompt_sections(prompt)
    title = _first_header(prompt, directory.name)
    metadata = _extract_metadata(prompt)
    output_contract = sections.get("output", "")
    rules = sections.get("rules", "")
    job = sections.get("your_job", "")
    identity = sections.get("identity", "")

    return {
        "ok": True,
        "agent": {
            "name": title,
            "id": metadata.get("id", ""),
            "path": directory.as_posix(),
            "source_status": metadata.get("source_status", ""),
        },
        "query": query,
        "relevance": relevance_score(prompt, query),
        "context_keys": sorted((context or {}).keys()),
        "specialist_packet": {
            "identity": identity,
            "job": job,
            "output_contract": output_contract,
            "operating_rules": rules,
        },
        "limitations": [
            "Prompt-backed runtime only; no live external scraper is attached in this module.",
            "Use domain-specific scraper modules when fresh market data is required.",
        ],
    }


__all__ = ["parse_prompt_sections", "read_agent_prompt", "relevance_score", "run_prompt_backed_agent"]

