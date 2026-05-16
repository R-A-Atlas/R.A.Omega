"""
tests/test_skill_architecture_phase2.py

Tests for Skill Architecture Phase 2:
- 10 core skills have required files and metadata
- Deterministic verifier tools work correctly
- Safety metadata is valid (no destructive+auto_invocable)
- omega_skill_registry routing works
- audit_skills tool correctly audits the skills directory
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest

ROOT = Path(__file__).parent.parent
SKILLS_DIR = ROOT / "omega_os" / "skills"

CORE_10_SKILLS = [
    "company_report",
    "trade_plan",
    "general_chat",
    "document_generator",
    "dashboard_generator",
    "source_verification",
    "report_export",
    "capture_triage",
    "visual_qa",
    "improve_system",
]

REQUIRED_FILES = ["skill.md", "contract.json", "examples.md", "CHANGELOG.md"]

REQUIRED_SECTIONS = [
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
]

REQUIRED_CONTRACT_FIELDS = [
    "name", "description", "output_mode", "renderer_type",
    "auto_invocable", "user_invocable", "requires_confirmation", "destructive",
    "required_sections", "forbidden_sections", "related_tools",
]


# ── Registry listing ──────────────────────────────────────────────────────────

def test_registry_lists_10_core_skills():
    from omega_skill_registry import list_skills
    skills = list_skills()
    names = {s["name"] for s in skills}
    for skill in CORE_10_SKILLS:
        assert skill in names, f"Core skill '{skill}' not found in registry listing"


def test_registry_listing_has_descriptions():
    from omega_skill_registry import list_skills
    skills = list_skills()
    by_name = {s["name"]: s for s in skills}
    for skill in CORE_10_SKILLS:
        assert by_name[skill]["description"], f"Skill '{skill}' has empty description"


# ── File structure ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_skill_md(skill_name):
    skill_md = SKILLS_DIR / skill_name / "skill.md"
    assert skill_md.exists(), f"{skill_name}/skill.md missing"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_contract_json(skill_name):
    assert (SKILLS_DIR / skill_name / "contract.json").exists(), f"{skill_name}/contract.json missing"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_examples_md(skill_name):
    assert (SKILLS_DIR / skill_name / "examples.md").exists(), f"{skill_name}/examples.md missing"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_changelog_md(skill_name):
    assert (SKILLS_DIR / skill_name / "CHANGELOG.md").exists(), f"{skill_name}/CHANGELOG.md missing"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_tools_dir(skill_name):
    assert (SKILLS_DIR / skill_name / "tools").is_dir(), f"{skill_name}/tools/ missing"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_skill_has_tests_dir(skill_name):
    assert (SKILLS_DIR / skill_name / "tests").is_dir(), f"{skill_name}/tests/ missing"


# ── Metadata loading ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_metadata_loads_without_instructions(skill_name):
    from omega_skill_registry import load_skill_metadata, load_skill_instructions
    meta = load_skill_metadata(skill_name)
    assert "name" in meta or "description" in meta, f"Metadata empty for {skill_name}"
    # Metadata must be fast — it should NOT include the full skill.md text
    meta_str = json.dumps(meta)
    # Full instructions are much longer; metadata should be compact
    assert len(meta_str) < 2000, f"Metadata for {skill_name} looks too large — may be loading full instructions"


# ── Safety metadata ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_contract_has_required_fields(skill_name):
    contract_path = SKILLS_DIR / skill_name / "contract.json"
    with open(contract_path, encoding="utf-8") as f:
        contract = json.load(f)
    for field in REQUIRED_CONTRACT_FIELDS:
        assert field in contract, f"{skill_name}/contract.json missing field: {field}"


@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_no_skill_is_destructive_and_auto_invocable(skill_name):
    contract_path = SKILLS_DIR / skill_name / "contract.json"
    with open(contract_path, encoding="utf-8") as f:
        contract = json.load(f)
    if contract.get("destructive") and contract.get("auto_invocable"):
        pytest.fail(
            f"SAFETY VIOLATION: {skill_name} has destructive=true AND auto_invocable=true"
        )


def test_all_core_skills_are_non_destructive():
    """All 10 current core skills must have destructive=false."""
    for skill_name in CORE_10_SKILLS:
        contract_path = SKILLS_DIR / skill_name / "contract.json"
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        assert not contract.get("destructive"), f"{skill_name} should have destructive=false"


# ── Output mode routing ───────────────────────────────────────────────────────

def test_company_report_mode_maps_to_company_report_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("company_report") == "company_report"


def test_trade_plan_mode_maps_to_trade_plan_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("trade_plan") == "trade_plan"


def test_chat_mode_maps_to_general_chat_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("chat") == "general_chat"


def test_general_chat_mode_maps_to_general_chat_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("general_chat") == "general_chat"


def test_document_mode_maps_to_document_generator_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("document") == "document_generator"


def test_html_artifact_mode_maps_to_dashboard_generator_skill():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("html_artifact") == "dashboard_generator"


def test_unknown_mode_maps_to_none():
    from omega_skill_registry import get_skill_for_output_mode
    assert get_skill_for_output_mode("nonexistent_mode_xyz") is None


# ── company_report verifier ───────────────────────────────────────────────────

VALID_COMPANY_REPORT = """
## Executive Summary
BlackRock is the world's largest asset manager with $10.5T AUM.

## Bull Thesis
Strong fee income, institutional client stickiness, AUM growth.

## Bear Thesis
Fee compression from passive fund competition, regulatory headwinds.

## Key Risks
Regulatory changes, market downturn reducing AUM-linked fees.
"""

COMPANY_REPORT_WITH_TRADE_BLEED = """
## Executive Summary
BlackRock overview.

## Bull Thesis
Strong growth.

## Bear Thesis
Competition rising.

## Key Risks
Regulation.

THE SETUP: Entry price at 85, Stop Loss at 80, Take Profit at 95.
"""

COMPANY_REPORT_MISSING_SECTIONS = """
Some overview of a company without the required sections.
"""


def test_company_report_verifier_passes_valid():
    from omega_os.skills.company_report.tools.verify_company_report import verify
    result = verify(VALID_COMPANY_REPORT)
    assert result.passed, f"Expected PASS, got: {result.summary()}"
    assert not result.missing_sections
    assert not result.forbidden_found


def test_company_report_verifier_catches_trade_bleed():
    from omega_os.skills.company_report.tools.verify_company_report import verify
    result = verify(COMPANY_REPORT_WITH_TRADE_BLEED)
    assert not result.passed, "Expected FAIL for trade bleed"
    assert result.forbidden_found, "Should have detected forbidden trade terms"


def test_company_report_verifier_catches_missing_sections():
    from omega_os.skills.company_report.tools.verify_company_report import verify
    result = verify(COMPANY_REPORT_MISSING_SECTIONS)
    assert not result.passed, "Expected FAIL for missing sections"
    assert result.missing_sections, "Should have detected missing sections"
    assert "executive summary" in result.missing_sections


def test_company_report_verifier_rejects_non_string():
    from omega_os.skills.company_report.tools.verify_company_report import verify
    result = verify(None)  # type: ignore[arg-type]
    assert not result.passed
    assert result.errors


def test_company_report_verifier_entry_price_is_forbidden():
    from omega_os.skills.company_report.tools.verify_company_report import verify
    text = VALID_COMPANY_REPORT + "\nEntry price: $85.50"
    result = verify(text)
    assert not result.passed
    assert "entry price" in result.forbidden_found


# ── trade_plan verifier ───────────────────────────────────────────────────────

VALID_TRADE_PLAN = "Entry: 85.50  Stop Loss: 82.00  Risk: defined at 4%. Target: 95."

TRADE_PLAN_MISSING_STOP = "Entry: 85.50  Target: 95  Risk management: TBD."

TRADE_PLAN_MISSING_ENTRY = "Stop Loss: 82.00  Risk: 4%. Target: 95."

TRADE_PLAN_NAKED_OPTIONS = "Entry: 85  Stop Loss: 82  Risk: 4%. Sell naked call for premium."


def test_trade_plan_verifier_passes_valid():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(VALID_TRADE_PLAN)
    assert result.passed, f"Expected PASS, got: {result.summary()}"
    assert not result.missing_sections
    assert not result.forbidden_found


def test_trade_plan_verifier_catches_missing_stop_loss():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(TRADE_PLAN_MISSING_STOP)
    assert not result.passed
    assert "stop loss" in result.missing_sections


def test_trade_plan_verifier_catches_missing_entry():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(TRADE_PLAN_MISSING_ENTRY)
    assert not result.passed
    assert "entry" in result.missing_sections


def test_trade_plan_verifier_catches_naked_options():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(TRADE_PLAN_NAKED_OPTIONS)
    assert not result.passed
    assert result.forbidden_found
    assert "naked call" in result.forbidden_found


def test_trade_plan_verifier_rejects_non_string():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(42)  # type: ignore[arg-type]
    assert not result.passed
    assert result.errors


def test_trade_plan_verifier_notes_missing_recommended():
    from omega_os.skills.trade_plan.tools.verify_trade_plan import verify
    result = verify(VALID_TRADE_PLAN)
    # The valid plan above lacks risk/reward and options play — should note them
    assert result.missing_recommended, "Should note missing recommended sections"


# ── export_markdown_report tool ───────────────────────────────────────────────

def test_export_markdown_report_returns_success(tmp_path):
    from omega_os.skills.report_export.tools.export_markdown_report import export
    result = export("# My Report\n\nContent here.", output_dir=tmp_path)
    assert result.success, f"Expected success, got: {result.error}"
    assert result.output_path
    assert Path(result.output_path).exists()


def test_export_markdown_report_custom_filename(tmp_path):
    from omega_os.skills.report_export.tools.export_markdown_report import export
    result = export("# Report", filename="custom.md", output_dir=tmp_path)
    assert result.success
    assert result.output_path.endswith("custom.md")


def test_export_markdown_report_rejects_empty_text(tmp_path):
    from omega_os.skills.report_export.tools.export_markdown_report import export
    result = export("", output_dir=tmp_path)
    assert not result.success


def test_export_markdown_report_no_path_traversal(tmp_path):
    from omega_os.skills.report_export.tools.export_markdown_report import export
    result = export("content", filename="../../etc/passwd", output_dir=tmp_path)
    # Either succeeds safely (traversal stripped) or fails with error
    if result.success:
        # Must still be inside tmp_path
        assert str(tmp_path.resolve()) in result.output_path or result.output_path.startswith(str(tmp_path))
    # If it fails, that's also acceptable (path traversal detected)


# ── audit_skills tool ─────────────────────────────────────────────────────────

def test_audit_skills_finds_10_core_skills():
    from omega_os.skills.improve_system.tools.audit_skills import audit
    result = audit()
    names = {e.name for e in result.entries}
    for skill in CORE_10_SKILLS:
        assert skill in names, f"audit_skills did not find core skill: {skill}"


def test_audit_skills_10_core_skills_all_pass():
    from omega_os.skills.improve_system.tools.audit_skills import audit
    result = audit()
    for entry in result.entries:
        if entry.name in CORE_10_SKILLS:
            assert entry.valid, (
                f"Core skill '{entry.name}' failed audit: {entry.all_issues()}"
            )


def test_audit_skills_no_safety_violations_in_core():
    from omega_os.skills.improve_system.tools.audit_skills import audit
    result = audit()
    for entry in result.entries:
        if entry.name in CORE_10_SKILLS:
            assert not entry.safety_violations, (
                f"Safety violation in core skill '{entry.name}': {entry.safety_violations}"
            )


def test_audit_skills_returns_structured_result():
    from omega_os.skills.improve_system.tools.audit_skills import audit, AuditResult
    result = audit()
    assert isinstance(result, AuditResult)
    assert result.total_skills > 0
    assert result.valid_count >= 10  # at least the 10 core skills


def test_audit_skills_to_dict():
    from omega_os.skills.improve_system.tools.audit_skills import audit
    result = audit()
    d = result.to_dict()
    assert "total_skills" in d
    assert "valid_count" in d
    assert "entries" in d
    assert isinstance(d["entries"], list)


# ── omega_skill_registry validate_skill_structure ────────────────────────────

@pytest.mark.parametrize("skill_name", CORE_10_SKILLS)
def test_validate_skill_structure_passes_for_core_skills(skill_name):
    from omega_skill_registry import validate_skill_structure
    result = validate_skill_structure(skill_name)
    assert result["valid"], (
        f"validate_skill_structure failed for '{skill_name}': {result['errors']}"
    )


def test_validate_skill_structure_fails_for_unknown_skill():
    from omega_skill_registry import validate_skill_structure
    result = validate_skill_structure("nonexistent_skill_xyz_abc")
    assert not result["valid"]
    assert result["errors"]
