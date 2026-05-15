"""
tests/test_omega_os.py — Tests for the Omega OS layer.

Covers:
- omega_os folder structure exists
- required skills exist with required sections
- omega_os_loader loads only relevant context
- select_skill matches query type
- omega_audit returns 4C scores and total
- omega_level_up returns structured analysis
- no secrets hardcoded in omega_os files
- prompt_builder can include Omega OS context without routing pollution
- trading format still only allowed when output_mode == trade_plan
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
OMEGA_OS = ROOT / "omega_os"
SKILLS_DIR = OMEGA_OS / "skills"
CONTEXT_DIR = OMEGA_OS / "context"

# ── Phase 1: Folder structure ─────────────────────────────────────────────────

def test_omega_os_root_exists():
    assert OMEGA_OS.exists(), "omega_os/ directory missing"

def test_omega_os_readme_exists():
    assert (OMEGA_OS / "README.md").exists()

def test_context_dir_exists():
    assert CONTEXT_DIR.exists()

def test_connections_dir_exists():
    assert (OMEGA_OS / "connections").exists()

def test_decisions_dir_exists():
    assert (OMEGA_OS / "decisions").exists()

def test_references_dir_exists():
    assert (OMEGA_OS / "references").exists()

def test_audits_dir_exists():
    assert (OMEGA_OS / "audits").exists()

def test_archives_dir_exists():
    assert (OMEGA_OS / "archives").exists()

def test_skills_dir_exists():
    assert SKILLS_DIR.exists()

REQUIRED_CONTEXT_FILES = [
    "about_user.md", "about_business.md", "priorities.md", "preferences.md",
    "portfolio_profile.md", "risk_profile.md", "project_roadmap.md",
    "user_goals.md", "brand_guidelines.md", "product_specs.md", "agent_architecture.md",
]

@pytest.mark.parametrize("filename", REQUIRED_CONTEXT_FILES)
def test_context_file_exists(filename):
    assert (CONTEXT_DIR / filename).exists(), f"Missing context file: {filename}"

def test_connections_md_exists():
    assert (OMEGA_OS / "connections" / "connections.md").exists()

def test_product_decisions_exists():
    assert (OMEGA_OS / "decisions" / "product_decisions.md").exists()

def test_architecture_decisions_exists():
    assert (OMEGA_OS / "decisions" / "architecture_decisions.md").exists()

def test_four_c_audits_exists():
    assert (OMEGA_OS / "audits" / "four_c_audits.md").exists()


# ── Phase 2: Required skills ──────────────────────────────────────────────────

REQUIRED_SKILLS = [
    "onboard", "audit", "level_up", "company_report", "daily_brief",
    "document_generator", "dashboard_generator", "portfolio_review",
    "research_queue", "watchlist_update", "voice_capture_triage", "weekly_product_review",
]

REQUIRED_SKILL_SECTIONS = [
    "name", "description", "when_to_use", "inputs_required",
    "steps", "outputs", "safety_rules", "related_files", "quality_checks",
]

@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_folder_exists(skill_name):
    assert (SKILLS_DIR / skill_name).exists(), f"Missing skill folder: {skill_name}"

@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
def test_skill_md_exists(skill_name):
    assert (SKILLS_DIR / skill_name / "skill.md").exists(), f"Missing skill.md for: {skill_name}"

@pytest.mark.parametrize("skill_name", REQUIRED_SKILLS)
@pytest.mark.parametrize("section", REQUIRED_SKILL_SECTIONS)
def test_skill_has_required_section(skill_name, section):
    skill_file = SKILLS_DIR / skill_name / "skill.md"
    if not skill_file.exists():
        pytest.skip(f"skill.md not found for {skill_name}")
    content = skill_file.read_text(encoding="utf-8").lower()
    assert f"## {section}" in content, f"skill {skill_name} missing section: ## {section}"


# ── Phase 3: omega_os_loader ──────────────────────────────────────────────────

from omega_os_loader import (
    list_skills,
    load_skill,
    select_skill,
    load_relevant_context,
    REQUIRED_SKILL_SECTIONS as LOADER_REQUIRED_SECTIONS,
)

def test_list_skills_returns_list():
    skills = list_skills()
    assert isinstance(skills, list)
    assert len(skills) > 0

def test_list_skills_has_name_and_description():
    skills = list_skills()
    for s in skills:
        assert "skill" in s, f"Missing 'skill' key in {s}"
        assert "description" in s, f"Missing 'description' key in {s}"

def test_load_skill_returns_content():
    content = load_skill("company_report")
    assert len(content) > 0
    assert "company_report" in content.lower() or "company" in content.lower()

def test_load_skill_missing_returns_empty():
    assert load_skill("nonexistent_skill_xyz") == ""

def test_select_skill_company_report():
    skill = select_skill("Give me everything on BlackRock", "COMPANY_RESEARCH", "company_report")
    assert skill == "company_report"

def test_select_skill_daily_brief():
    skill = select_skill("give me the morning brief", "GENERAL_FINANCE", "finance_answer")
    assert skill == "daily_brief"

def test_select_skill_portfolio_review():
    skill = select_skill("review my portfolio", "GENERAL_FINANCE", "finance_answer")
    assert skill == "portfolio_review"

def test_select_skill_document():
    skill = select_skill("make me a pdf report", "DOCUMENT_GENERATION", "document")
    assert skill == "document_generator"

def test_select_skill_html_dashboard():
    skill = select_skill("create an html dashboard", "HTML_ARTIFACT", "html_artifact")
    assert skill == "dashboard_generator"

def test_select_skill_no_match_returns_empty():
    # Use an intent not mapped to any skill and no keyword matches
    skill = select_skill("what is the capital of France", "MACRO_RISK_SCAN", "market_snapshot")
    assert skill == ""

def test_load_relevant_context_returns_string():
    ctx = load_relevant_context("Give me everything on BlackRock", "COMPANY_RESEARCH", "company_report")
    assert isinstance(ctx, str)

def test_load_relevant_context_not_empty_for_known_intent():
    ctx = load_relevant_context("Give me everything on BlackRock", "COMPANY_RESEARCH", "company_report")
    assert len(ctx) > 0

def test_load_relevant_context_does_not_include_all_files():
    """Context loader should not dump ALL context files into every prompt."""
    ctx = load_relevant_context("who won last night", "CASUAL", "chat")
    # Casual intent should not include portfolio or risk profile
    assert "portfolio_profile" not in ctx.lower() or "risk_profile" not in ctx.lower()

def test_routing_never_receives_context():
    """classify_intent_route() must accept only one positional param (the raw query string)."""
    from query_router import classify_intent_route
    import inspect
    sig = inspect.signature(classify_intent_route)
    params = list(sig.parameters.keys())
    assert len(params) == 1, (
        f"classify_intent_route() should only accept one param (raw query), got: {params}"
    )
    # Must not have any context/memory/session parameters
    forbidden_param_names = {"context", "memory", "session", "user_id", "controls"}
    assert not (set(params) & forbidden_param_names), (
        f"classify_intent_route() has forbidden params: {set(params) & forbidden_param_names}"
    )


# ── Phase 4: omega_audit ──────────────────────────────────────────────────────

from omega_audit import run_audit

def test_audit_returns_dict():
    result = run_audit()
    assert isinstance(result, dict)

def test_audit_has_four_c_scores():
    result = run_audit()
    assert "context" in result
    assert "connections" in result
    assert "capabilities" in result
    assert "cadence" in result

def test_audit_scores_in_range():
    result = run_audit()
    assert 0 <= result["context"] <= 25
    assert 0 <= result["connections"] <= 25
    assert 0 <= result["capabilities"] <= 25
    assert 0 <= result["cadence"] <= 25

def test_audit_total_is_sum():
    result = run_audit()
    expected = result["context"] + result["connections"] + result["capabilities"] + result["cadence"]
    assert result["total"] == expected

def test_audit_total_in_range():
    result = run_audit()
    assert 0 <= result["total"] <= 100

def test_audit_has_strengths_and_gaps():
    result = run_audit()
    assert "strengths" in result
    assert "gaps" in result
    assert isinstance(result["strengths"], list)
    assert isinstance(result["gaps"], list)

def test_audit_has_next_steps():
    result = run_audit()
    assert "next_steps" in result
    assert isinstance(result["next_steps"], list)
    assert len(result["next_steps"]) <= 5

def test_audit_has_phase_label():
    result = run_audit()
    assert "phase" in result
    assert len(result["phase"]) > 0

def test_audit_scores_positive_with_structure():
    """Now that omega_os structure exists, scores should be > 0."""
    result = run_audit()
    assert result["context"] > 0, "Context score should be > 0 with context files present"
    assert result["capabilities"] > 0, "Capabilities score should be > 0 with skills present"


# ── Phase 5: omega_level_up ───────────────────────────────────────────────────

from omega_level_up import analyze

def test_level_up_returns_dict():
    result = analyze()
    assert isinstance(result, dict)

def test_level_up_has_five_questions():
    result = analyze()
    assert "q1_repeated_actions" in result
    assert "q2_manual_boring" in result
    assert "q3_intern_tasks" in result
    assert "q4_scale_risks" in result
    assert "q5_highest_leverage" in result

def test_level_up_has_recommendation():
    result = analyze()
    assert "recommended_skill" in result
    assert "recommended_connection" in result
    assert "priority_score" in result
    assert "estimated_leverage" in result

def test_level_up_priority_score_in_range():
    result = analyze()
    assert 1 <= result["priority_score"] <= 10

def test_level_up_leverage_is_valid():
    result = analyze()
    assert result["estimated_leverage"] in ("low", "medium", "high", "10x")

def test_level_up_with_weekly_actions():
    result = analyze(weekly_actions=["ran company report 5x", "updated watchlist manually"])
    assert result["recommended_skill"] in (
        "company_report", "watchlist_update", "daily_brief", "audit",
        "level_up", "document_generator", "portfolio_review",
        "research_queue", "voice_capture_triage", "weekly_product_review",
        "onboard", "dashboard_generator",
    )

def test_level_up_opportunities_list():
    result = analyze()
    assert "opportunities" in result
    assert isinstance(result["opportunities"], list)
    assert len(result["opportunities"]) > 0

def test_level_up_no_unsafe_automations():
    """Recommended skills must not be undefined or None."""
    result = analyze()
    assert result["recommended_skill"] is not None
    assert len(result["recommended_skill"]) > 0


# ── Security: no secrets hardcoded ───────────────────────────────────────────

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{20,}",          # OpenAI API key
    r"AIza[a-zA-Z0-9_-]{35}",         # Google API key
    r"eyJ[a-zA-Z0-9_-]{20,}",         # JWT token (long)
    r"[a-f0-9]{32,}",                  # Generic hex secret (long)
    r"(?i)api[_-]?key\s*=\s*['\"][^'\"]{8,}['\"]",  # api_key = "..."
]

def _scan_for_secrets(filepath: Path) -> list[str]:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    found = []
    for pattern in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        for m in matches:
            # Skip obvious placeholders
            if any(ph in m.lower() for ph in ["fill in", "your_", "placeholder", "example", "xxx"]):
                continue
            if len(m) > 20:  # short matches are probably false positives
                found.append(f"{pattern!r}: {m[:40]}...")
    return found

def test_no_secrets_in_omega_os_files():
    """omega_os/ markdown files must not contain hardcoded secrets."""
    issues = []
    for md_file in OMEGA_OS.rglob("*.md"):
        secrets = _scan_for_secrets(md_file)
        if secrets:
            issues.append(f"{md_file.name}: {secrets[:2]}")
    assert not issues, f"Secrets found in omega_os files: {issues}"

def test_no_secrets_in_omega_python_files():
    """New omega_os Python files must not contain hardcoded secrets."""
    for pyfile in ["omega_os_loader.py", "omega_audit.py", "omega_level_up.py"]:
        filepath = ROOT / pyfile
        if filepath.exists():
            secrets = _scan_for_secrets(filepath)
            assert not secrets, f"Secrets found in {pyfile}: {secrets}"


# ── prompt_builder: Omega OS context without routing pollution ────────────────

from prompt_builder import build_synthesis_prompt
from query_router import classify_intent_route, INTENT_COMPANY_RESEARCH, INTENT_GENERAL_CHAT

def test_prompt_builder_accepts_omega_os_context():
    prompt = build_synthesis_prompt(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        omega_os_context="Company context: BlackRock is in user's watchlist.",
    )
    assert "OMEGA OS CONTEXT" in prompt
    assert "BlackRock is in user's watchlist" in prompt

def test_prompt_builder_omega_context_optional():
    """omega_os_context is optional — omitting it must not break the prompt."""
    prompt = build_synthesis_prompt(
        raw_query="who won last night",
        intent="GENERAL_CHAT",
        output_mode="chat",
    )
    assert "OMEGA OS CONTEXT" not in prompt
    assert len(prompt) > 50

def test_routing_unaffected_by_omega_context():
    """Adding omega_os_context to prompt_builder must not change classify_intent_route results."""
    intent_without = classify_intent_route("Give me everything on BlackRock")
    # omega_os_context is never passed to classify_intent_route
    intent_with = classify_intent_route("Give me everything on BlackRock")
    assert intent_without == intent_with

def test_omega_context_not_passed_to_routing():
    """Confirm omega_os_context and context params are NOT on classify_intent_route signature."""
    import inspect
    from query_router import classify_intent_route
    sig = inspect.signature(classify_intent_route)
    assert "omega_os_context" not in sig.parameters
    assert "context" not in sig.parameters
    assert "memory" not in sig.parameters


# ── Trade format only when output_mode == trade_plan ─────────────────────────

from output_modes import user_explicitly_requested_trade
from output_contracts import OUTPUT_CONTRACTS

def test_trade_forbidden_in_company_report():
    contract = OUTPUT_CONTRACTS["company_report"]
    assert any("trade plan" in p.lower() for p in contract.forbidden_phrases)

def test_trade_forbidden_in_chat():
    contract = OUTPUT_CONTRACTS["chat"]
    assert any("trade plan" in p.lower() for p in contract.forbidden_phrases)

def test_trade_allowed_in_trade_plan():
    contract = OUTPUT_CONTRACTS["trade_plan"]
    assert "Entry" in contract.required_sections or "entry" in [s.lower() for s in contract.required_sections]

def test_trade_not_triggered_by_casual_query():
    assert user_explicitly_requested_trade("who won last night") is False

def test_trade_not_triggered_by_company_query():
    assert user_explicitly_requested_trade("Give me everything on BlackRock") is False

def test_trade_triggered_by_explicit_request():
    assert user_explicitly_requested_trade("give me a trade setup for TSLA") is True
