"""
atlas_prompts/generate_prompts.py — Generate prompt configs from AGENT_REGISTRY.md.

Reads the AGENT_REGISTRY.md file, extracts agent entries, and generates
structured prompt entries in prompts.json using Jinja2 templates.

Division prefixes → archetypes:
  D (Trading Data)  → finance_analyst
  M (Macro)         → finance_analyst
  R (Real Estate)   → finance_analyst
  W (Wealth/Debt)   → finance_analyst
  L (Tax/Legal)     → finance_analyst
  B (Business)      → finance_analyst
  A (Alternative)   → finance_analyst
  G (Growth/Mktg)   → data_retriever
  IQ (Intelligence) → finance_analyst

Usage:
  python atlas_prompts/generate_prompts.py              # writes to prompts.json
  python atlas_prompts/generate_prompts.py --dry-run    # print only, no write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jinja2 import Template

_ROOT = Path(__file__).parent.parent
_REGISTRY_PATH = _ROOT / "AGENT_REGISTRY.md"
_PROMPTS_PATH = Path(__file__).parent / "prompts.json"

# Maps division letter prefix to archetype key in prompts.json
_DIVISION_ARCHETYPE: dict[str, str] = {
    "D": "finance_analyst",
    "M": "finance_analyst",
    "R": "finance_analyst",
    "W": "finance_analyst",
    "L": "finance_analyst",
    "B": "finance_analyst",
    "A": "finance_analyst",
    "G": "data_retriever",
    "IQ": "finance_analyst",
}

# Jinja2 template for each generated agent system prompt
_PROMPT_TEMPLATE = Template(
    "You are {{ agent_name }}, a specialized financial intelligence agent in the ATLAS system. "
    "{{ role_description }} "
    "Your intent is {{ intent }}. "
    "Return structured JSON with headline, executive_brief, key_insight, and action_plan. "
    "Use only data provided; do not hallucinate. "
    "User query: {query}"
)

_ROW_RE = re.compile(
    r"^\|\s*((?:IQ|[A-Z])\d*)\s+([^|]+?)\s*\|"   # division+name
    r"\s*([A-Z_]+(?:_SCAN|_SYNTHESIS|_DIVE)?)\s*\|"  # intent
    r"\s*([^|]+?)\s*\|",  # cache file
    re.MULTILINE,
)

# Fallback: rows with only agent name and cache file (no intent column)
_ROW_NO_INTENT_RE = re.compile(
    r"^\|\s*((?:IQ|[A-Z])\d*)\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)


def _division_prefix(code: str) -> str:
    if code.upper().startswith("IQ"):
        return "IQ"
    return re.match(r"[A-Z]+", code).group(0) if re.match(r"[A-Z]+", code) else "D"


def parse_registry(text: str) -> list[dict]:
    agents: list[dict] = []
    seen: set[str] = set()
    for m in _ROW_RE.finditer(text):
        code, name, intent, cache = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
        if not intent or intent.lower() in ("intent", "cache file"):
            continue
        key = intent
        if key in seen:
            continue
        seen.add(key)
        div = _division_prefix(code)
        archetype = _DIVISION_ARCHETYPE.get(div, "finance_analyst")
        role_desc = f"You specialize in {name.lower().rstrip('✅').strip()} analysis and intelligence."
        prompt_text = _PROMPT_TEMPLATE.render(
            agent_name=name.strip("✅ "),
            role_description=role_desc,
            intent=intent,
        )
        agents.append(
            {
                "code": code,
                "name": name.strip("✅ "),
                "intent": intent,
                "cache_file": cache,
                "archetype": archetype,
                "system_prompt": prompt_text,
            }
        )
    return agents


def generate(dry_run: bool = False) -> None:
    if not _REGISTRY_PATH.exists():
        print(f"ERROR: {_REGISTRY_PATH} not found", file=sys.stderr)
        sys.exit(1)

    registry_text = _REGISTRY_PATH.read_text(encoding="utf-8")
    agents = parse_registry(registry_text)

    if not agents:
        print("WARNING: no agents parsed from AGENT_REGISTRY.md — check regex or file format")
        return

    # Load existing prompts.json
    existing: dict = {}
    if _PROMPTS_PATH.exists():
        try:
            existing = json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"WARNING: could not load existing prompts.json: {exc}")

    domain_map: dict = existing.get("domain_map", {})
    generated_section: dict = existing.get("generated_agents", {})

    for agent in agents:
        intent = agent["intent"]
        archetype = agent["archetype"]
        domain_map.setdefault(intent, archetype)
        generated_section[intent] = {
            "code": agent["code"],
            "name": agent["name"],
            "archetype": archetype,
            "cache_file": agent["cache_file"],
            "system_prompt": agent["system_prompt"],
        }

    existing["domain_map"] = domain_map
    existing["generated_agents"] = generated_section

    output = json.dumps(existing, indent=2, ensure_ascii=False)

    if dry_run:
        print(f"[dry-run] Would write {len(output)} bytes to {_PROMPTS_PATH}")
        print(f"[dry-run] Parsed {len(agents)} agents:")
        for a in agents:
            print(f"  {a['code']:4s}  {a['intent']:40s}  archetype={a['archetype']}")
    else:
        _PROMPTS_PATH.write_text(output, encoding="utf-8")
        print(f"Written {len(agents)} agent prompt entries to {_PROMPTS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate prompt configs from AGENT_REGISTRY.md")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    args = parser.parse_args()
    generate(dry_run=args.dry_run)
