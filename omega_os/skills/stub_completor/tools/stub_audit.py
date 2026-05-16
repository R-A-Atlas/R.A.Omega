"""
stub_audit.py — Audits which Omega OS skills are stubs vs fully implemented.

Reports:
  - Full skills (SKILL.md + tool scripts)
  - Stub skills (SKILL.md only — no tool scripts)
  - Priority build order (based on cadence references + how many skills depend on them)
  - Suggested tool script name and first 5 lines for each stub

Usage:
    python omega_os/skills/stub_completor/tools/stub_audit.py
    python omega_os/skills/stub_completor/tools/stub_audit.py --stubs-only
    python omega_os/skills/stub_completor/tools/stub_audit.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT   = Path(__file__).parent.parent.parent.parent.parent
SKILLS = ROOT / "omega_os" / "skills"
sys.path.insert(0, str(ROOT))


@dataclass
class SkillEntry:
    name: str
    has_skill_md: bool
    has_evals: bool
    has_contract: bool
    tools: list[str]
    cadence_refs: int        # how many cadence jobs reference this skill
    skill_refs: int          # how many OTHER skills require this one
    priority_score: float    # higher = build sooner

    @property
    def is_full(self) -> bool:
        return bool(self.tools)

    @property
    def is_stub(self) -> bool:
        return not self.tools


def _count_cadence_refs(skill_name: str) -> int:
    try:
        text = (ROOT / "omega_cadence.py").read_text(encoding="utf-8", errors="replace")
        return text.count(f'"{skill_name}"') + text.count(f"'{skill_name}'")
    except Exception:
        return 0


def _count_skill_refs(skill_name: str) -> int:
    """Count how many OTHER skills' SKILL.md files reference this skill."""
    count = 0
    for skill_dir in SKILLS.iterdir():
        if not skill_dir.is_dir() or skill_dir.name == skill_name:
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            if skill_name in text:
                count += 1
    return count


def _score(entry: SkillEntry) -> float:
    """Higher score = higher build priority."""
    score = 0.0
    score += entry.cadence_refs * 10   # cadence dependency is urgent
    score += entry.skill_refs   * 5    # referenced by other skills
    if entry.has_skill_md:   score += 2
    if entry.has_evals:      score += 1
    if entry.has_contract:   score += 1
    return score


def _suggest_tool_name(name: str) -> str:
    """Suggest the main tool script name for a stub skill."""
    mapping = {
        "daily_brief":          "run_daily_brief.py",
        "portfolio_review":     "run_portfolio_review.py",
        "watchlist_update":     "run_watchlist_update.py",
        "audit":                "run_audit.py",
        "level_up":             "run_level_up.py",
        "onboard":              "run_onboard.py",
        "research_queue":       "run_research_queue.py",
        "voice_capture_triage": "run_voice_triage.py",
        "weekly_product_review":"run_weekly_review.py",
        "capture_triage":       "run_capture_triage.py",
        "dashboard_generator":  "run_dashboard_generator.py",
        "document_generator":   "run_document_generator.py",
        "general_chat":         "run_general_chat.py",
        "source_verification":  "run_source_verification.py",
        "visual_qa":            "run_visual_qa.py",
    }
    return mapping.get(name, f"run_{name}.py")


def scan_skills() -> list[SkillEntry]:
    entries = []
    for skill_dir in sorted(SKILLS.iterdir()):
        if not skill_dir.is_dir():
            continue
        name         = skill_dir.name
        has_skill_md = (skill_dir / "SKILL.md").exists()
        has_evals    = (skill_dir / "evals.json").exists()
        has_contract = (skill_dir / "contract.json").exists()
        tools        = [t.name for t in (skill_dir / "tools").glob("*.py")] if (skill_dir / "tools").exists() else []
        cadence_refs = _count_cadence_refs(name)
        skill_refs   = _count_skill_refs(name)

        entry = SkillEntry(
            name=name,
            has_skill_md=has_skill_md,
            has_evals=has_evals,
            has_contract=has_contract,
            tools=tools,
            cadence_refs=cadence_refs,
            skill_refs=skill_refs,
            priority_score=0.0,
        )
        entry = SkillEntry(
            name=name,
            has_skill_md=has_skill_md,
            has_evals=has_evals,
            has_contract=has_contract,
            tools=tools,
            cadence_refs=cadence_refs,
            skill_refs=skill_refs,
            priority_score=_score(entry),
        )
        entries.append(entry)

    return sorted(entries, key=lambda e: (-e.priority_score, e.name))


def print_report(entries: list[SkillEntry], stubs_only: bool = False) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sep = "=" * 72
    full  = [e for e in entries if e.is_full]
    stubs = [e for e in entries if e.is_stub]

    print(sep)
    print("  R.A. OMEGA — SKILL INVENTORY & STUB AUDIT")
    print(sep)
    print(f"\n  {len(full)} FULL  |  {len(stubs)} STUBS  |  {len(entries)} total\n")

    if not stubs_only:
        print("  FULL SKILLS")
        print(f"  {'NAME':<32} {'TOOLS'}")
        print(f"  {'-'*32} {'-'*30}")
        for e in full:
            print(f"  {e.name:<32} {', '.join(e.tools)}")

    print(f"\n  STUB SKILLS — BUILD ORDER  (score = cadence_refs*10 + skill_refs*5)")
    print(f"  {'#':<3} {'NAME':<32} {'SCORE':>6}  {'CADENCE':>7}  {'SUGGESTED TOOL'}")
    print(f"  {'-'*3} {'-'*32} {'-'*6}  {'-'*7}  {'-'*28}")
    for i, e in enumerate(stubs, 1):
        suggest = _suggest_tool_name(e.name)
        flags = []
        if e.cadence_refs: flags.append(f"cadence×{e.cadence_refs}")
        if e.skill_refs:   flags.append(f"refs×{e.skill_refs}")
        flag_str = " ".join(flags) if flags else ""
        print(f"  {i:<3} {e.name:<32} {e.priority_score:>6.0f}  {flag_str:>9}  {suggest}")

    print(f"\n  To implement a stub, run:")
    print(f"    mkdir omega_os/skills/<name>/tools")
    print(f"    # Create the tool script — dev_session_guard is a good template")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(description="Omega OS skill stub audit")
    parser.add_argument("--stubs-only", action="store_true", help="Show only stub skills")
    parser.add_argument("--json",       action="store_true", help="Output JSON")
    args = parser.parse_args()

    entries = scan_skills()

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps([
            {
                "name":           e.name,
                "is_full":        e.is_full,
                "tools":          e.tools,
                "cadence_refs":   e.cadence_refs,
                "skill_refs":     e.skill_refs,
                "priority_score": e.priority_score,
                "suggested_tool": _suggest_tool_name(e.name) if e.is_stub else None,
            }
            for e in entries
        ], indent=2))
    else:
        print_report(entries, stubs_only=args.stubs_only)


if __name__ == "__main__":
    main()
