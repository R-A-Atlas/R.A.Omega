"""
omega_audit.py — Four C audit for the Omega OS layer.

Scores the system across four dimensions (0–25 each, 0–100 total):
  Context      — How well the context files are populated
  Connections  — How many planned connections are active
  Capabilities — How many required skills are built and complete
  Cadence      — How many recurring jobs are planned/scheduled

Run directly:
  python omega_audit.py
"""
from __future__ import annotations

import re
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_ROOT          = Path(__file__).parent
_OMEGA_OS_DIR  = _ROOT / "omega_os"
_SKILLS_DIR    = _OMEGA_OS_DIR / "skills"
_CONTEXT_DIR   = _OMEGA_OS_DIR / "context"
_CONNECTIONS_FILE = _OMEGA_OS_DIR / "connections" / "connections.md"
_AUDITS_FILE   = _OMEGA_OS_DIR / "audits" / "four_c_audits.md"

# ── Expected assets (what a fully-built system should have) ───────────────────
REQUIRED_CONTEXT_FILES = [
    "about_user.md", "about_business.md", "priorities.md", "preferences.md",
    "portfolio_profile.md", "risk_profile.md", "project_roadmap.md",
    "user_goals.md", "brand_guidelines.md", "product_specs.md", "agent_architecture.md",
]

REQUIRED_SKILLS = [
    "onboard", "audit", "level_up", "company_report", "daily_brief",
    "document_generator", "dashboard_generator", "portfolio_review",
    "research_queue", "watchlist_update", "voice_capture_triage", "weekly_product_review",
]

REQUIRED_SKILL_SECTIONS = [
    "name", "description", "when_to_use", "inputs_required",
    "steps", "outputs", "safety_rules", "related_files", "quality_checks",
]

PLANNED_CONNECTIONS = [
    "Google Workspace", "Gmail", "Google Calendar", "Google Drive",
    "Google Docs", "Google Sheets", "GitHub", "Telegram", "ClickUp",
    "Notion", "Slack", "SEC EDGAR", "Alpha Vantage", "Polygon.io",
    "Finnhub", "SendGrid",
]

ACTIVE_CONNECTIONS = [
    "Supabase", "Stripe", "yfinance", "Gemini", "OpenAI Whisper",
    "OpenAI TTS", "ElevenLabs", "Chroma",
]

REQUIRED_CADENCE_JOBS = [
    "daily_market_brief", "daily_priority_brief", "weekly_portfolio_review",
    "weekly_omega_os_audit", "weekly_product_review",
    "monthly_finance_report", "monthly_product_roadmap_review",
]


# ── Four C Scoring ────────────────────────────────────────────────────────────

def _score_context() -> tuple[int, list[str], list[str]]:
    """Score context files: 0–25."""
    strengths: list[str] = []
    gaps: list[str] = []
    score = 0

    if not _CONTEXT_DIR.exists():
        return 0, strengths, [f"omega_os/context/ directory missing"]

    existing = [f.name for f in _CONTEXT_DIR.iterdir() if f.is_file()]
    present = [f for f in REQUIRED_CONTEXT_FILES if f in existing]
    missing = [f for f in REQUIRED_CONTEXT_FILES if f not in existing]

    # Points: 2 per file present (11 files × 2 = 22 max) + 3 for no fill-in placeholders
    score += len(present) * 2
    if len(present) == len(REQUIRED_CONTEXT_FILES):
        strengths.append("All required context files exist")
        # Check for un-filled placeholders
        fill_ins = 0
        for filename in REQUIRED_CONTEXT_FILES:
            content = (_CONTEXT_DIR / filename).read_text(encoding="utf-8", errors="ignore")
            fill_ins += content.count("[fill in]")
        if fill_ins == 0:
            score += 3
            strengths.append("All context files fully populated (no placeholders)")
        else:
            gaps.append(f"{fill_ins} '[fill in]' placeholders remain in context files")
    else:
        gaps.extend([f"Missing context file: {f}" for f in missing])

    return min(score, 25), strengths, gaps


def _score_connections() -> tuple[int, list[str], list[str]]:
    """Score connections: 0–25."""
    strengths: list[str] = []
    gaps: list[str] = []
    score = 0

    # Active connections: 1 point each (8 active = 8 points)
    score += len(ACTIVE_CONNECTIONS)
    if ACTIVE_CONNECTIONS:
        strengths.append(f"{len(ACTIVE_CONNECTIONS)} active connections: {', '.join(ACTIVE_CONNECTIONS[:4])}...")

    # Planned connections that are still only planned (not yet active)
    if _CONNECTIONS_FILE.exists():
        conn_text = _CONNECTIONS_FILE.read_text(encoding="utf-8")
        active_count = conn_text.lower().count("| active")
        configured_count = conn_text.lower().count("| configured")
        if active_count > 0 or configured_count > 0:
            strengths.append(f"Connections registry exists with {active_count} active, {configured_count} configured")
        score += min(configured_count, 5)  # up to 5 points for configured-but-not-yet-active
        gaps.extend([f"Planned connection not yet active: {c}" for c in PLANNED_CONNECTIONS[:4]])
    else:
        gaps.append("connections.md registry not found")

    return min(score, 25), strengths, gaps


def _score_capabilities() -> tuple[int, list[str], list[str]]:
    """Score capabilities (skills): 0–25."""
    strengths: list[str] = []
    gaps: list[str] = []
    score = 0

    if not _SKILLS_DIR.exists():
        return 0, strengths, ["omega_os/skills/ directory missing"]

    existing_skills = [d.name for d in _SKILLS_DIR.iterdir() if d.is_dir()]
    present_skills = [s for s in REQUIRED_SKILLS if s in existing_skills]
    missing_skills = [s for s in REQUIRED_SKILLS if s not in existing_skills]

    # 1.5 points per skill present (12 skills × 1.5 = 18)
    score += int(len(present_skills) * 1.5)

    # +1 per skill with all required sections (up to 7 bonus points)
    complete_count = 0
    incomplete_skills = []
    for skill_name in present_skills:
        skill_file = _SKILLS_DIR / skill_name / "skill.md"
        if skill_file.exists():
            content = skill_file.read_text(encoding="utf-8").lower()
            missing_sections = [s for s in REQUIRED_SKILL_SECTIONS if f"## {s}" not in content]
            if not missing_sections:
                complete_count += 1
            else:
                incomplete_skills.append(f"{skill_name} missing: {missing_sections}")

    score += min(complete_count, 7)

    if present_skills:
        strengths.append(f"{len(present_skills)}/{len(REQUIRED_SKILLS)} required skills built")
    if complete_count == len(present_skills) and present_skills:
        strengths.append("All built skills have complete required sections")
    if missing_skills:
        gaps.extend([f"Missing skill: {s}" for s in missing_skills])
    if incomplete_skills:
        gaps.extend(incomplete_skills[:3])

    return min(score, 25), strengths, gaps


def _score_cadence() -> tuple[int, list[str], list[str]]:
    """Score cadence (scheduled/planned recurring jobs): 0–25."""
    strengths: list[str] = []
    gaps: list[str] = []
    score = 0

    cadence_file = _ROOT / "omega_cadence.py"
    if cadence_file.exists():
        content = cadence_file.read_text(encoding="utf-8")
        found_jobs = [j for j in REQUIRED_CADENCE_JOBS if j in content]
        score += len(found_jobs) * 3  # 3 points per declared job (7 × 3 = 21 max)
        if found_jobs:
            strengths.append(f"{len(found_jobs)}/{len(REQUIRED_CADENCE_JOBS)} cadence jobs declared in omega_cadence.py")
        missing_jobs = [j for j in REQUIRED_CADENCE_JOBS if j not in found_jobs]
        if missing_jobs:
            gaps.extend([f"Missing cadence job: {j}" for j in missing_jobs])
        # Bonus: if any jobs have real scheduler wiring (CronCreate or APScheduler)
        if "CronCreate" in content or "APScheduler" in content or "schedule" in content.lower():
            score += 4
            strengths.append("Cadence jobs have real scheduler wiring")
        else:
            gaps.append("Cadence jobs declared but not yet scheduled (omega_cadence.py is declarations only)")
    else:
        gaps.append("omega_cadence.py not found — no cadence plan exists")
        gaps.extend([f"Missing cadence job: {j}" for j in REQUIRED_CADENCE_JOBS])

    return min(score, 25), strengths, gaps


# ── Phase labels ──────────────────────────────────────────────────────────────

def _phase_label(total: int) -> str:
    if total <= 40:
        return "Foundation — build context and skills"
    if total <= 60:
        return "Development — add connections and cadence"
    if total <= 80:
        return "Operations — automate and scale"
    return "Command Center — fully operational Omega OS"


# ── Next steps recommendation ─────────────────────────────────────────────────

def _recommend_next_steps(
    context_score: int,
    conn_score: int,
    cap_score: int,
    cad_score: int,
    gaps: list[str],
) -> list[str]:
    steps: list[str] = []
    # Fill in lowest-scoring dimension first
    scores = [
        (context_score, "Fill in [fill in] placeholders in omega_os/context/ files"),
        (conn_score, "Add a new active connection (Google Sheets or SEC EDGAR next)"),
        (cap_score, "Build a missing skill SOP (research_queue or voice_capture_triage next)"),
        (cad_score, "Create omega_cadence.py with all 7 required cadence job declarations"),
    ]
    scores.sort(key=lambda x: x[0])
    steps.extend(s for _, s in scores[:3])
    # Add specific gap-based steps
    for gap in gaps[:3]:
        if "Missing context file" in gap:
            filename = gap.split(": ")[-1]
            steps.append(f"Create omega_os/context/{filename}")
            break
    if not any("prompt_builder" in s for s in steps):
        steps.append("Wire omega_os_loader into prompt_builder.py for synthesis-time context injection")
    return steps[:5]


# ── Main audit function ───────────────────────────────────────────────────────

def run_audit() -> dict[str, Any]:
    """Run the full Four C audit and return a result dict."""
    c_score, c_strengths, c_gaps = _score_context()
    co_score, co_strengths, co_gaps = _score_connections()
    ca_score, ca_strengths, ca_gaps = _score_capabilities()
    cd_score, cd_strengths, cd_gaps = _score_cadence()

    total = c_score + co_score + ca_score + cd_score
    all_strengths = c_strengths + co_strengths + ca_strengths + cd_strengths
    all_gaps = c_gaps + co_gaps + ca_gaps + cd_gaps
    next_steps = _recommend_next_steps(c_score, co_score, ca_score, cd_score, all_gaps)

    return {
        "context":      c_score,
        "connections":  co_score,
        "capabilities": ca_score,
        "cadence":      cd_score,
        "total":        total,
        "phase":        _phase_label(total),
        "strengths":    all_strengths,
        "gaps":         all_gaps,
        "next_steps":   next_steps,
        "audited_at":   datetime.now(timezone.utc).isoformat(),
    }


def print_audit(result: dict[str, Any]) -> None:
    """Print a formatted audit report to stdout."""
    sep = "=" * 60
    print("\n" + sep)
    print("  OMEGA OS -- FOUR C AUDIT")
    print(sep)
    print(f"  Context:      {result['context']:>3}/25")
    print(f"  Connections:  {result['connections']:>3}/25")
    print(f"  Capabilities: {result['capabilities']:>3}/25")
    print(f"  Cadence:      {result['cadence']:>3}/25")
    print("  " + "-" * 20)
    print(f"  TOTAL:        {result['total']:>3}/100")
    print(f"  Phase:        {result['phase']}")
    print()

    if result["strengths"]:
        print("  STRENGTHS:")
        for s in result["strengths"]:
            print(f"    [+] {s}")
        print()

    if result["gaps"]:
        print("  GAPS:")
        for g in result["gaps"][:8]:
            print(f"    [-] {g}")
        print()

    print("  NEXT 5 STEPS:")
    for i, step in enumerate(result["next_steps"], 1):
        print(f"    {i}. {step}")
    print(sep + "\n")


if __name__ == "__main__":
    result = run_audit()
    print_audit(result)
    # Optionally append to audit log
    try:
        from omega_os_loader import append_audit_result
        append_audit_result(result)
        print("  Audit result appended to omega_os/audits/four_c_audits.md")
    except Exception as e:
        print(f"  Warning: could not append audit result — {e}")
