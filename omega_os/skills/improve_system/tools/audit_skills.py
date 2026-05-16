"""
audit_skills.py — Deterministic audit of the omega_os/skills directory.

No external APIs. No API keys. Fully local and deterministic.

Checks for:
- Missing required files (skill.md, contract.json, examples.md, CHANGELOG.md)
- Missing required skill.md sections
- Unsafe safety metadata (destructive=true AND auto_invocable=true)
- Duplicate skill names
- Skills without tools/ or tests/ directories

Usage:
  python audit_skills.py
  python audit_skills.py --skills-dir /path/to/skills
  python audit_skills.py --json
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[2]  # omega_os/skills/

REQUIRED_FILES = ("skill.md", "contract.json", "examples.md", "CHANGELOG.md")

REQUIRED_SKILL_MD_SECTIONS = (
    "## name",
    "## description",
    "## when_to_use",
    "## inputs_required",
    "## steps",
    "## outputs",
    "## safety_rules",
    "## quality_checks",
    "## examples",
    "## repair_strategy",
    "## related_files",
)

REQUIRED_CONTRACT_FIELDS = (
    "name",
    "description",
    "output_mode",
    "renderer_type",
    "auto_invocable",
    "user_invocable",
    "requires_confirmation",
    "destructive",
    "required_sections",
    "forbidden_sections",
    "related_tools",
)


@dataclass
class SkillAuditEntry:
    name: str
    valid: bool = True
    missing_files: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    missing_contract_fields: list[str] = field(default_factory=list)
    safety_violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def all_issues(self) -> list[str]:
        return (
            [f"Missing file: {f}" for f in self.missing_files]
            + [f"Missing section: {s}" for s in self.missing_sections]
            + [f"Missing contract field: {k}" for k in self.missing_contract_fields]
            + [f"SAFETY VIOLATION: {v}" for v in self.safety_violations]
            + [f"Warning: {w}" for w in self.warnings]
        )


@dataclass
class AuditResult:
    skills_dir: str
    total_skills: int
    valid_count: int
    invalid_count: int
    entries: list[SkillAuditEntry] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Skills dir: {self.skills_dir}",
            f"Total skills: {self.total_skills}",
            f"Valid: {self.valid_count}  Invalid: {self.invalid_count}",
        ]
        if self.duplicates:
            lines.append(f"Duplicate names: {self.duplicates}")
        for entry in self.entries:
            issues = entry.all_issues()
            status = "PASS" if entry.valid else "FAIL"
            lines.append(f"  [{status}] {entry.name}")
            for issue in issues:
                lines.append(f"        {issue}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "skills_dir": self.skills_dir,
            "total_skills": self.total_skills,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "duplicates": self.duplicates,
            "entries": [
                {
                    "name": e.name,
                    "valid": e.valid,
                    "issues": e.all_issues(),
                }
                for e in self.entries
            ],
        }


def audit(skills_dir: str | Path | None = None) -> AuditResult:
    """
    Audit all skill directories found under skills_dir.
    Returns AuditResult with per-skill entries and aggregate counts.
    """
    base = Path(skills_dir) if skills_dir else _DEFAULT_SKILLS_DIR
    entries: list[SkillAuditEntry] = []
    seen_names: list[str] = []
    duplicates: list[str] = []

    if not base.is_dir():
        return AuditResult(
            skills_dir=str(base),
            total_skills=0,
            valid_count=0,
            invalid_count=0,
            entries=[],
            duplicates=[],
        )

    skill_dirs = sorted(d for d in base.iterdir() if d.is_dir())

    for skill_dir in skill_dirs:
        name = skill_dir.name
        if name in seen_names:
            duplicates.append(name)
        seen_names.append(name)

        entry = SkillAuditEntry(name=name)

        # Check required files
        for fname in REQUIRED_FILES:
            fpath = skill_dir / fname
            if not fpath.exists():
                # Accept SKILL.md as alias for skill.md
                if fname == "skill.md" and (skill_dir / "SKILL.md").exists():
                    continue
                entry.missing_files.append(fname)

        # Check skill.md sections
        skill_md = skill_dir / "skill.md"
        if not skill_md.exists():
            skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8").lower()
            for section in REQUIRED_SKILL_MD_SECTIONS:
                if section.lower() not in content:
                    entry.missing_sections.append(section)

        # Check contract.json
        contract_path = skill_dir / "contract.json"
        if contract_path.exists():
            try:
                with open(contract_path, encoding="utf-8") as f:
                    contract = json.load(f)
                for k in REQUIRED_CONTRACT_FIELDS:
                    if k not in contract:
                        entry.missing_contract_fields.append(k)
                # Safety invariant
                if contract.get("destructive") and contract.get("auto_invocable"):
                    entry.safety_violations.append(
                        "destructive=true AND auto_invocable=true (forbidden combination)"
                    )
            except json.JSONDecodeError as exc:
                entry.warnings.append(f"contract.json parse error: {exc}")

        # Check tools/ and tests/ directories exist
        if not (skill_dir / "tools").is_dir():
            entry.warnings.append("Missing tools/ directory")
        if not (skill_dir / "tests").is_dir():
            entry.warnings.append("Missing tests/ directory")

        # Check CHANGELOG.md is non-empty (stale detection)
        changelog = skill_dir / "CHANGELOG.md"
        if changelog.exists() and changelog.stat().st_size < 10:
            entry.warnings.append("CHANGELOG.md appears empty (possibly stale)")

        entry.valid = (
            not entry.missing_files
            and not entry.missing_sections
            and not entry.missing_contract_fields
            and not entry.safety_violations
        )
        entries.append(entry)

    valid_count = sum(1 for e in entries if e.valid)
    return AuditResult(
        skills_dir=str(base),
        total_skills=len(entries),
        valid_count=valid_count,
        invalid_count=len(entries) - valid_count,
        entries=entries,
        duplicates=duplicates,
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    use_json = "--json" in args
    skills_dir = None
    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 < len(args):
            skills_dir = args[idx + 1]

    result = audit(skills_dir)

    if use_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary())

    sys.exit(0 if result.invalid_count == 0 else 1)
