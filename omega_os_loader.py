"""
omega_os_loader.py — Progressive context loader for the Omega OS layer.

Loads only relevant context files for each query/intent/output_mode combination.
Never dumps all omega_os context into every prompt.

Progressive loading:
  Level 1 — skill name and description (always fast)
  Level 2 — full skill.md (loaded when skill is activated)
  Level 3 — extra references (loaded only when the skill requires them)
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_OMEGA_OS_DIR = Path(__file__).parent / "omega_os"
_SKILLS_DIR   = _OMEGA_OS_DIR / "skills"
_CONTEXT_DIR  = _OMEGA_OS_DIR / "context"
_DECISIONS_DIR = _OMEGA_OS_DIR / "decisions"
_AUDITS_FILE  = _OMEGA_OS_DIR / "audits" / "four_c_audits.md"

log = logging.getLogger(__name__)

# ── Required sections every skill.md must have ────────────────────────────────
REQUIRED_SKILL_SECTIONS = (
    "name", "description", "when_to_use", "inputs_required",
    "steps", "outputs", "safety_rules", "related_files", "quality_checks",
)

# ── Skill → intent/output_mode mapping for auto-selection ────────────────────
_SKILL_MATCH: list[dict[str, Any]] = [
    {
        "skill": "company_report",
        "intents": {"COMPANY_RESEARCH", "GENERAL_FINANCE"},
        "output_modes": {"company_report"},
        "keywords": {"company report", "everything on", "research on", "tell me about"},
    },
    {
        "skill": "daily_brief",
        "intents": {"GENERAL_FINANCE", "GENERAL_CHAT"},
        "output_modes": {"finance_answer", "chat"},
        "keywords": {"daily brief", "morning brief", "market update", "what's happening today", "morning market"},
    },
    {
        "skill": "portfolio_review",
        "intents": {"GENERAL_FINANCE"},
        "output_modes": {"finance_answer"},
        "keywords": {"portfolio", "my positions", "rebalance", "risk exposure", "portfolio review"},
    },
    {
        "skill": "document_generator",
        "intents": {"DOCUMENT_GENERATION"},
        "output_modes": {"document"},
        "keywords": {"pdf report", "excel", "powerpoint", "generate a report", "make me a document", "pdf"},
    },
    {
        "skill": "dashboard_generator",
        "intents": {"HTML_ARTIFACT"},
        "output_modes": {"html_artifact"},
        "keywords": {"html dashboard", "interactive", "visual report", "html report", "dashboard"},
    },
    {
        "skill": "audit",
        "intents": set(),
        "output_modes": set(),
        "keywords": {"omega os audit", "four c audit", "run audit", "4c score", "os score"},
    },
    {
        "skill": "level_up",
        "intents": set(),
        "output_modes": set(),
        "keywords": {"level up", "what should i automate", "next skill", "automation opportunity"},
    },
    {
        "skill": "watchlist_update",
        "intents": {"GENERAL_FINANCE"},
        "output_modes": {"finance_answer"},
        "keywords": {"watchlist", "add to watchlist", "remove from watchlist", "update watchlist"},
    },
    {
        "skill": "research_queue",
        "intents": {"MARKET_DEEP_DIVE", "COMPANY_RESEARCH", "GENERAL_FINANCE"},
        "output_modes": set(),
        "keywords": {"research queue", "add to queue", "queue research", "batch research"},
    },
    {
        "skill": "voice_capture_triage",
        "intents": set(),
        "output_modes": set(),
        "keywords": {"voice", "audio", "transcribe"},
    },
    {
        "skill": "weekly_product_review",
        "intents": set(),
        "output_modes": set(),
        "keywords": {"weekly review", "product review", "weekly product", "sprint review"},
    },
    {
        "skill": "onboard",
        "intents": {"GENERAL_CHAT", "CASUAL"},
        "output_modes": {"chat"},
        "keywords": {"get started", "how do i use", "onboard", "help me start", "new user"},
    },
]

# ── Context files loaded per intent ───────────────────────────────────────────
_INTENT_CONTEXT_MAP: dict[str, list[str]] = {
    "COMPANY_RESEARCH":  ["about_business.md", "brand_guidelines.md", "product_specs.md"],
    "MARKET_DEEP_DIVE":  ["about_business.md", "risk_profile.md", "portfolio_profile.md"],
    "GENERAL_FINANCE":   ["about_business.md", "preferences.md"],
    "DOCUMENT_GENERATION": ["brand_guidelines.md", "preferences.md"],
    "HTML_ARTIFACT":     ["brand_guidelines.md", "preferences.md"],
    "GENERAL_CHAT":      ["about_user.md", "preferences.md"],
    "CASUAL":            ["about_user.md"],
    "TRADING_ANALYSIS":  ["risk_profile.md", "portfolio_profile.md"],
}


# ── Public API ────────────────────────────────────────────────────────────────

def list_skills() -> list[dict[str, str]]:
    """Return Level 1 info (name + description) for all available skills."""
    skills = []
    if not _SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "skill.md"
        if skill_dir.is_dir() and skill_file.exists():
            name = skill_dir.name
            desc = _extract_section(skill_file.read_text(encoding="utf-8"), "description")
            skills.append({"skill": name, "description": desc.strip()})
    return skills


def load_skill(skill_name: str) -> str:
    """Return the full skill.md content for Level 2 loading."""
    skill_file = _SKILLS_DIR / skill_name / "skill.md"
    if not skill_file.exists():
        log.warning("omega_os_loader: skill not found: %s", skill_name)
        return ""
    return skill_file.read_text(encoding="utf-8")


def select_skill(raw_query: str, intent: str, output_mode: str) -> str:
    """
    Match raw_query + intent + output_mode to the most relevant skill name.
    Returns the skill name string, or "" if no match.
    Never passes raw_query into routing — this is synthesis-time only.
    """
    q = (raw_query or "").lower()
    best_skill = ""
    best_score = 0

    for entry in _SKILL_MATCH:
        score = 0
        # Keyword match
        for kw in entry["keywords"]:
            if kw in q:
                score += 2
        # Intent match
        if intent and entry["intents"] and intent in entry["intents"]:
            score += 3
        # Output mode match
        if output_mode and entry["output_modes"] and output_mode in entry["output_modes"]:
            score += 2
        if score > best_score:
            best_score = score
            best_skill = entry["skill"]

    return best_skill if best_score > 0 else ""


def load_relevant_context(raw_query: str, intent: str, output_mode: str) -> str:
    """
    Load only the context files relevant to this query.
    Returns a concatenated string ready for prompt injection.
    Does NOT include raw_query in routing — context is for synthesis only.

    Progressive loading:
      Level 1: skill name/description (via list_skills — not included in returned text)
      Level 2: relevant context files for this intent
      Level 3: skill.md if a skill is selected
    """
    parts: list[str] = []

    # Level 2: intent-specific context files
    context_files = _INTENT_CONTEXT_MAP.get(intent, ["preferences.md"])
    for filename in context_files:
        filepath = _CONTEXT_DIR / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"## {filename[:-3].replace('_', ' ').title()}\n{content}")

    # Level 3: skill.md if a skill is matched
    skill_name = select_skill(raw_query, intent, output_mode)
    if skill_name:
        skill_content = load_skill(skill_name)
        if skill_content:
            parts.append(f"## Active Skill: {skill_name}\n{skill_content[:1500]}")  # cap size

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)


def write_decision(title: str, summary: str, source: str = "user") -> None:
    """Append a new architecture or product decision to decisions files."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## {title}\n**Date:** {date}\n**Source:** {source}\n**Summary:** {summary}\n"
    target = _DECISIONS_DIR / "architecture_decisions.md"
    if target.exists():
        with target.open("a", encoding="utf-8") as f:
            f.write(entry)
        log.info("omega_os_loader: decision written: %s", title)
    else:
        log.warning("omega_os_loader: decisions file not found, decision not saved")


def append_audit_result(result: dict[str, Any]) -> None:
    """Append a Four C audit result to the audit log."""
    if not _AUDITS_FILE.exists():
        log.warning("omega_os_loader: audits file not found")
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    score = result.get("total", 0)
    context_score = result.get("context", 0)
    conn_score = result.get("connections", 0)
    cap_score = result.get("capabilities", 0)
    cad_score = result.get("cadence", 0)
    entry = (
        f"\n### Audit {date} — Total: {score}/100\n"
        f"- Context: {context_score}/25\n"
        f"- Connections: {conn_score}/25\n"
        f"- Capabilities: {cap_score}/25\n"
        f"- Cadence: {cad_score}/25\n"
    )
    gaps = result.get("gaps", [])
    if gaps:
        entry += "**Gaps:** " + "; ".join(gaps[:5]) + "\n"
    next_steps = result.get("next_steps", [])
    if next_steps:
        entry += "**Next Steps:**\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(next_steps[:5])) + "\n"
    with _AUDITS_FILE.open("a", encoding="utf-8") as f:
        f.write(entry)
    log.info("omega_os_loader: audit result appended (score=%d)", score)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_section(text: str, section_name: str) -> str:
    """Extract the content under a ## section heading from markdown."""
    pattern = rf"##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""
