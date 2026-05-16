"""
omega_skill_registry.py — Progressive-disclosure registry for R.A. Omega skills.

Level 1: list_skills()               — name + description (always fast)
Level 2: load_skill_instructions()   — full SKILL.md text
Level 3: get_skill_contract()        — contract.json dict
Level 4: get_skill_tools()           — list of tool script paths

Never load all skills at once into a prompt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SKILLS_DIR = Path(__file__).parent / "omega_os" / "skills"

# Canonical map from output_mode → primary skill name
_OUTPUT_MODE_TO_SKILL: dict[str, str] = {
    "company_report": "company_report",
    "trade_plan": "trade_plan",
    "chat": "general_chat",
    "general_chat": "general_chat",
    "finance_answer": "general_chat",
    "market_snapshot": "general_chat",
    "document": "document_generator",
    "html_artifact": "dashboard_generator",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _skill_dir(skill_name: str) -> Path:
    return _SKILLS_DIR / skill_name


def _require_skill(skill_name: str) -> Path:
    d = _skill_dir(skill_name)
    if not d.is_dir():
        raise ValueError(f"Unknown skill: {skill_name!r}")
    return d


# ---------------------------------------------------------------------------
# Level 1 — fast listing
# ---------------------------------------------------------------------------

def list_skills() -> list[dict[str, str]]:
    """Return name + description for every installed skill (Level 1)."""
    result: list[dict[str, str]] = []
    if not _SKILLS_DIR.is_dir():
        return result
    for entry in sorted(_SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        contract_path = entry / "contract.json"
        name = entry.name
        description = ""
        if contract_path.exists():
            try:
                with open(contract_path, encoding="utf-8") as f:
                    data = json.load(f)
                description = data.get("description", "")
            except Exception:
                pass
        result.append({"name": name, "description": description})
    return result


# ---------------------------------------------------------------------------
# Level 1 — metadata only (name + output_mode + renderer_type)
# ---------------------------------------------------------------------------

def load_skill_metadata(skill_name: str) -> dict[str, Any]:
    """Return lightweight metadata dict without loading full SKILL.md."""
    d = _require_skill(skill_name)
    contract_path = d / "contract.json"
    if not contract_path.exists():
        return {"name": skill_name}
    with open(contract_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Level 2 — full instructions
# ---------------------------------------------------------------------------

def load_skill_instructions(skill_name: str) -> str:
    """Return full SKILL.md text for the named skill (Level 2)."""
    d = _require_skill(skill_name)
    skill_md = d / "skill.md"
    if not skill_md.exists():
        skill_md = d / "SKILL.md"
    if not skill_md.exists():
        return f"# {skill_name}\n\n(No skill.md found)"
    return skill_md.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Level 3 — contract
# ---------------------------------------------------------------------------

def get_skill_contract(skill_name: str) -> dict[str, Any]:
    """Return parsed contract.json for the named skill (Level 3)."""
    d = _require_skill(skill_name)
    contract_path = d / "contract.json"
    if not contract_path.exists():
        raise FileNotFoundError(f"No contract.json for skill {skill_name!r}")
    with open(contract_path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Level 4 — tool scripts
# ---------------------------------------------------------------------------

def get_skill_tools(skill_name: str) -> list[str]:
    """Return list of absolute paths to tool scripts for the named skill (Level 4)."""
    d = _require_skill(skill_name)
    tools_dir = d / "tools"
    if not tools_dir.is_dir():
        return []
    return sorted(str(p) for p in tools_dir.iterdir() if p.suffix == ".py")


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def get_skill_for_output_mode(output_mode: str) -> str | None:
    """Return the primary skill name for a given output_mode, or None."""
    return _OUTPUT_MODE_TO_SKILL.get(output_mode)


def get_related_skills(skill_name: str) -> list[str]:
    """Return related skill names listed in contract.json, filtered to installed skills."""
    try:
        contract = get_skill_contract(skill_name)
    except (ValueError, FileNotFoundError):
        return []
    installed = {e["name"] for e in list_skills()}
    related_raw: list[str] = contract.get("related_skills", [])
    return [s for s in related_raw if s in installed]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED_CONTRACT_KEYS = {
    "name", "description", "output_mode", "renderer_type",
    "auto_invocable", "user_invocable", "requires_confirmation", "destructive",
    "required_sections", "forbidden_sections", "related_tools",
}

_REQUIRED_SKILL_MD_SECTIONS = {
    "## name", "## description", "## when_to_use",
    "## inputs_required", "## steps", "## outputs",
    "## safety_rules", "## quality_checks",
    "## examples", "## repair_strategy", "## related_files",
}


def validate_skill_structure(skill_name: str) -> dict[str, Any]:
    """
    Validate that a skill has all required files and contract fields.
    Returns {"valid": bool, "errors": list[str]}.
    """
    errors: list[str] = []
    try:
        d = _require_skill(skill_name)
    except ValueError as exc:
        return {"valid": False, "errors": [str(exc)]}

    # Check required files
    for fname in ("SKILL.md", "contract.json", "examples.md", "CHANGELOG.md"):
        if not (d / fname).exists():
            errors.append(f"Missing file: {fname}")

    # Check contract fields
    contract_path = d / "contract.json"
    if contract_path.exists():
        try:
            with open(contract_path, encoding="utf-8") as f:
                contract = json.load(f)
            missing_keys = _REQUIRED_CONTRACT_KEYS - set(contract.keys())
            for k in sorted(missing_keys):
                errors.append(f"contract.json missing field: {k}")
            # Safety invariant: destructive=true AND auto_invocable=true is forbidden
            if contract.get("destructive") and contract.get("auto_invocable"):
                errors.append("SAFETY VIOLATION: destructive=true and auto_invocable=true simultaneously")
        except json.JSONDecodeError as exc:
            errors.append(f"contract.json parse error: {exc}")

    # Check skill.md sections (falls back to SKILL.md)
    skill_md_path = d / "skill.md"
    if not skill_md_path.exists():
        skill_md_path = d / "SKILL.md"
    if skill_md_path.exists():
        content = skill_md_path.read_text(encoding="utf-8")
        for section in _REQUIRED_SKILL_MD_SECTIONS:
            if section not in content:
                errors.append(f"SKILL.md missing section: {section}")

    return {"valid": len(errors) == 0, "errors": errors}


def audit_all_skills() -> dict[str, dict[str, Any]]:
    """Run validate_skill_structure on every installed skill."""
    return {
        entry["name"]: validate_skill_structure(entry["name"])
        for entry in list_skills()
    }
