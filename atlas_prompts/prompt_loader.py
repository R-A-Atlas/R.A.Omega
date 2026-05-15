"""
atlas_prompts/prompt_loader.py — Agent prompt loading and domain mapping.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_PROMPTS_PATH = Path(__file__).parent / "prompts.json"
_CACHE: Optional[dict] = None

_FALLBACK_FINANCE_PROMPT = (
    "You are a senior financial analyst. Provide rigorous, data-driven analysis "
    "with clear bull/bear cases and actionable recommendations. "
    "Always note that analysis is not personalized investment advice.\n\nUser query: {query}"
)


def _load_prompts() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("atlas_prompts: failed to load prompts.json: %s", exc)
            _CACHE = {"archetypes": {}, "domain_map": {}}
    return _CACHE


def get_agent_prompt(agent_type: str, query: str) -> str:
    """Return the system prompt for the given agent archetype with query injected.

    Falls back to a generic finance prompt if agent_type is not found.
    """
    data = _load_prompts()
    archetypes = data.get("archetypes", {})
    archetype = archetypes.get(agent_type)
    if archetype:
        template = archetype.get("system_prompt", _FALLBACK_FINANCE_PROMPT)
        try:
            return template.format(query=query)
        except (KeyError, IndexError):
            return template
    log.debug("atlas_prompts: unknown agent_type %r — using fallback", agent_type)
    return _FALLBACK_FINANCE_PROMPT.format(query=query)


def get_domain_prompt(domain: str) -> str:
    """Return the system prompt for the given domain string (e.g. 'GENERAL_FINANCE').

    Maps the domain to the appropriate archetype via prompts.json domain_map,
    then returns the archetype's system prompt (without query injected).
    Returns empty string if no mapping found so callers can skip prepending.
    """
    data = _load_prompts()
    domain_map = data.get("domain_map", {})
    archetype_key = domain_map.get(domain)
    if not archetype_key:
        return ""
    archetypes = data.get("archetypes", {})
    archetype = archetypes.get(archetype_key)
    if not archetype:
        return ""
    template = archetype.get("system_prompt", "")
    # Return without query injected — caller appends their own prompt
    return template.replace("\n\nUser query: {query}", "")
