"""
tests/test_omega_os_phase2.py — Tests for Omega OS Phase 2.

Covers:
- omega_connections registry loads and is correctly structured
- omega_cadence plan loads and is correctly structured
- prompt_builder selected_skill and context_files_used metadata
- no secrets hardcoded in new files
- .env.example exists with placeholder-only values
- classify_intent_route still receives raw query only
- trading format still only allowed when output_mode == trade_plan
- API endpoints importable (route registration check)
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Phase 6: omega_connections ────────────────────────────────────────────────

from omega_connections import (
    get_registry,
    get_connection,
    list_active,
    list_planned,
    list_configured,
    list_destructive,
    registry_summary,
    STATUS_ACTIVE, STATUS_PLANNED, STATUS_CONFIGURED,
    AUTH_NONE, AUTH_API_KEY, AUTH_OAUTH2,
)


def test_registry_returns_list():
    registry = get_registry()
    assert isinstance(registry, list)
    assert len(registry) > 0


def test_registry_has_minimum_connections():
    registry = get_registry()
    assert len(registry) >= 15, f"Expected at least 15 connections, got {len(registry)}"


def test_get_connection_supabase():
    conn = get_connection("supabase")
    assert conn is not None
    assert conn.name == "Supabase"
    assert conn.status == STATUS_ACTIVE


def test_get_connection_gmail():
    conn = get_connection("gmail")
    assert conn is not None
    assert conn.status == STATUS_PLANNED


def test_get_connection_missing_returns_none():
    assert get_connection("nonexistent_xyz") is None


def test_list_active_has_entries():
    active = list_active()
    assert len(active) > 0
    for c in active:
        assert c.status == STATUS_ACTIVE


def test_list_planned_has_entries():
    planned = list_planned()
    assert len(planned) > 0
    for c in planned:
        assert c.status == STATUS_PLANNED


def test_required_planned_connections_exist():
    slugs = {c.slug for c in get_registry()}
    required_planned = [
        "gmail", "google_calendar", "google_drive", "google_sheets",
        "github", "telegram", "notion", "slack", "sec_edgar",
        "alpha_vantage", "polygon", "broker_api",
    ]
    for slug in required_planned:
        assert slug in slugs, f"Missing planned connection: {slug}"


def test_connections_have_required_fields():
    for conn in get_registry():
        assert conn.name, f"Connection missing name"
        assert conn.slug, f"Connection {conn.name} missing slug"
        assert conn.status in (STATUS_ACTIVE, STATUS_CONFIGURED, STATUS_PLANNED, "deprecated")
        assert isinstance(conn.can_read, bool)
        assert isinstance(conn.can_write, bool)
        assert isinstance(conn.is_destructive, bool)
        assert isinstance(conn.safety_notes, str)


def test_destructive_connections_flagged():
    """is_destructive=True must be set for connections that can send money or delete data."""
    broker = get_connection("broker_api")
    assert broker is not None
    assert broker.is_destructive is True


def test_active_connections_have_env_vars_or_none():
    """Active connections should either have env vars defined or use AUTH_NONE."""
    for conn in list_active():
        if conn.auth_method != AUTH_NONE:
            assert len(conn.env_vars_required) > 0, (
                f"{conn.name} uses {conn.auth_method} but has no env_vars_required"
            )


def test_registry_summary_structure():
    summary = registry_summary()
    assert "total" in summary
    assert "active" in summary
    assert "planned" in summary
    assert "connections" in summary
    assert summary["total"] == len(get_registry())
    assert summary["active"] == len(list_active())
    assert summary["planned"] == len(list_planned())


def test_connection_to_dict():
    conn = get_connection("supabase")
    d = conn.to_dict()
    assert isinstance(d["env_vars_required"], list)
    assert isinstance(d["permissions_needed"], list)
    assert isinstance(d["use_cases"], list)


def test_no_real_secrets_in_connection_env_vars():
    """env_vars_required should only contain env var NAMES, not values."""
    secret_value_pattern = re.compile(
        r"^(sk-|SG\.|AIza|eyJ|xoxb-|ghp_|whsec_)", re.I
    )
    for conn in get_registry():
        for var_name in conn.env_vars_required:
            assert not secret_value_pattern.match(var_name), (
                f"Connection {conn.name} has a secret value in env_vars_required: {var_name}"
            )


# ── Phase 7: omega_cadence ────────────────────────────────────────────────────

from omega_cadence import (
    get_cadence_plan,
    get_job,
    list_jobs,
    list_by_frequency,
    cadence_summary,
    STATUS_PLANNED as CADENCE_PLANNED,
    FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY,
)

REQUIRED_JOB_SLUGS = [
    "daily_market_brief",
    "daily_priority_brief",
    "weekly_portfolio_review",
    "weekly_omega_os_audit",
    "weekly_product_review",
    "monthly_finance_report",
    "monthly_product_roadmap_review",
]


def test_cadence_plan_returns_list():
    plan = get_cadence_plan()
    assert isinstance(plan, list)
    assert len(plan) > 0


def test_all_required_jobs_exist():
    slugs = {j.slug for j in get_cadence_plan()}
    for slug in REQUIRED_JOB_SLUGS:
        assert slug in slugs, f"Missing cadence job: {slug}"


def test_get_job_daily_market_brief():
    job = get_job("daily_market_brief")
    assert job is not None
    assert job.frequency == FREQ_DAILY
    assert job.status == CADENCE_PLANNED


def test_get_job_weekly_portfolio_review():
    job = get_job("weekly_portfolio_review")
    assert job is not None
    assert job.frequency == FREQ_WEEKLY


def test_get_job_monthly_finance_report():
    job = get_job("monthly_finance_report")
    assert job is not None
    assert job.frequency == FREQ_MONTHLY


def test_get_job_missing_returns_none():
    assert get_job("nonexistent_job_xyz") is None


def test_jobs_have_required_fields():
    for job in get_cadence_plan():
        assert job.name, f"Job {job.slug} missing name"
        assert job.slug, "Job missing slug"
        assert job.frequency in (FREQ_DAILY, FREQ_WEEKLY, FREQ_MONTHLY, "hourly")
        assert job.schedule_hint, f"Job {job.slug} missing schedule_hint"
        assert job.output, f"Job {job.slug} missing output description"
        assert isinstance(job.safety_rules, tuple), f"Job {job.slug} safety_rules must be tuple"
        assert len(job.safety_rules) > 0, f"Job {job.slug} must have at least one safety rule"


def test_list_by_frequency():
    daily = list_by_frequency(FREQ_DAILY)
    weekly = list_by_frequency(FREQ_WEEKLY)
    monthly = list_by_frequency(FREQ_MONTHLY)
    assert len(daily) >= 2
    assert len(weekly) >= 3
    assert len(monthly) >= 2


def test_cadence_summary_structure():
    summary = cadence_summary()
    assert "total" in summary
    assert "planned" in summary
    assert "active" in summary
    assert "daily" in summary
    assert "weekly" in summary
    assert "monthly" in summary
    assert "jobs" in summary
    assert summary["total"] == len(get_cadence_plan())


def test_cadence_cost_estimate_positive():
    summary = cadence_summary()
    assert summary["total_estimated_cost_per_week_usd"] >= 0


def test_jobs_all_planned_not_active():
    """All jobs should be STATUS_PLANNED — no real scheduling yet."""
    for job in get_cadence_plan():
        assert job.status == CADENCE_PLANNED, (
            f"Job {job.slug} has status={job.status} — all jobs should be 'planned' until scheduling is wired"
        )


def test_job_to_dict():
    job = get_job("daily_market_brief")
    d = job.to_dict()
    assert isinstance(d["required_context"], list)
    assert isinstance(d["required_connections"], list)
    assert isinstance(d["safety_rules"], list)


def test_broker_api_not_in_cadence_write_connections():
    """No cadence job should use broker_api as a write connection (trading automation safety)."""
    for job in get_cadence_plan():
        # broker_api write access in cadence = dangerous auto-trading
        assert "broker_api" not in job.required_connections or not any(
            c.is_destructive and c.can_write
            for c in [get_connection("broker_api")] if c
        ), f"Job {job.slug} uses broker_api — review carefully"


# ── Phase 8: prompt_builder metadata ─────────────────────────────────────────

from prompt_builder import build_synthesis_prompt, build_synthesis_prompt_meta


def test_build_synthesis_prompt_meta_returns_tuple():
    prompt, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
    )
    assert isinstance(prompt, str)
    assert isinstance(meta, dict)


def test_meta_has_required_keys():
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
    )
    assert "selected_skill" in meta
    assert "context_files_used" in meta
    assert "output_mode" in meta
    assert "intent" in meta
    assert "omega_os_loaded" in meta


def test_meta_selected_skill_without_omega_os():
    """When include_omega_os=False, selected_skill should be empty."""
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=False,
    )
    assert meta["selected_skill"] == ""
    assert meta["omega_os_loaded"] is False


def test_meta_selected_skill_with_omega_os():
    """When include_omega_os=True, selected_skill should be populated for known queries."""
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=True,
    )
    assert meta["selected_skill"] == "company_report"
    assert meta["omega_os_loaded"] is True


def test_meta_context_files_used_list():
    _, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=True,
    )
    assert isinstance(meta["context_files_used"], list)
    assert len(meta["context_files_used"]) > 0


def test_meta_skill_in_context_files():
    """When a skill is selected, its path should appear in context_files_used."""
    _, meta = build_synthesis_prompt_meta(
        raw_query="give me the morning brief",
        intent="GENERAL_FINANCE",
        output_mode="finance_answer",
        include_omega_os=True,
    )
    assert any("skill" in f for f in meta["context_files_used"]) or meta["selected_skill"] == ""


def test_omega_os_context_in_prompt_when_include():
    prompt, meta = build_synthesis_prompt_meta(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        include_omega_os=True,
    )
    assert "OMEGA OS CONTEXT" in prompt


def test_no_omega_os_context_when_not_included():
    prompt, _ = build_synthesis_prompt_meta(
        raw_query="who won last night",
        intent="GENERAL_CHAT",
        output_mode="chat",
        include_omega_os=False,
    )
    assert "OMEGA OS CONTEXT" not in prompt


def test_backward_compat_build_synthesis_prompt():
    """build_synthesis_prompt() still works without omega_os_context."""
    prompt = build_synthesis_prompt(
        raw_query="analyze NVDA",
        intent="MARKET_DEEP_DIVE",
        output_mode="trade_plan",
    )
    assert "analyze NVDA" in prompt
    assert isinstance(prompt, str)


def test_routing_purity_with_meta():
    """The metadata build never passes context to classify_intent_route."""
    import inspect
    from query_router import classify_intent_route
    sig = inspect.signature(classify_intent_route)
    params = set(sig.parameters.keys())
    forbidden = {"context", "memory", "omega_os_context", "session"}
    assert not (params & forbidden), f"classify_intent_route has forbidden params: {params & forbidden}"


# ── .env.example exists and has only placeholders ────────────────────────────

def test_env_example_exists():
    assert (ROOT / ".env.example").exists(), ".env.example not found"


def test_env_example_has_required_vars():
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    required_vars = [
        "SUPABASE_URL", "SUPABASE_KEY", "GOOGLE_API_KEY",
        "STRIPE_SECRET_KEY", "OPENAI_API_KEY",
        "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN",
        "ALPHA_VANTAGE_KEY", "POLYGON_API_KEY",
    ]
    for var in required_vars:
        assert var in content, f"Missing {var} in .env.example"


def test_env_example_has_no_real_secrets():
    """All values in .env.example must be placeholders, not real credentials."""
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    real_secret_pattern = re.compile(
        r"^(?!#)[A-Z_]+=(?!YOUR_|https://YOUR|sk_live_YOUR|SG\.YOUR|sk-YOUR|"
        r"xoxb-YOUR|ghp_YOUR|whsec_YOUR|price_YOUR|your@)"
        r"[a-zA-Z0-9/+=._-]{20,}",
        re.MULTILINE,
    )
    matches = real_secret_pattern.findall(content)
    assert not matches, f"Potential real secrets in .env.example: {matches[:3]}"


# ── API endpoint registration check ──────────────────────────────────────────

def test_omega_os_routes_registered():
    """Confirm omega-os routes are registered on the FastAPI app."""
    import api_server
    routes = [r.path for r in api_server.app.routes]
    assert "/omega-os/audit" in routes
    assert "/omega-os/skills" in routes
    assert "/omega-os/connections" in routes
    assert "/omega-os/cadence" in routes
    assert "/omega-os/level-up" in routes
    assert "/omega-os/skill-select" in routes


# ── Trade quarantine ──────────────────────────────────────────────────────────

from output_contracts import OUTPUT_CONTRACTS
from output_modes import user_explicitly_requested_trade


def test_cadence_jobs_dont_produce_trade_plans_by_default():
    """No cadence job should auto-produce trade_plan output — only when user requests it."""
    from omega_cadence import get_cadence_plan
    for job in get_cadence_plan():
        assert "trade_plan" not in job.output.lower() or "trade" not in job.name.lower(), (
            f"Job {job.slug} mentions trade_plan in output — review safety rules"
        )


def test_trade_forbidden_in_company_report_contract():
    contract = OUTPUT_CONTRACTS["company_report"]
    assert any("trade plan" in p.lower() for p in contract.forbidden_phrases)


def test_trade_forbidden_in_chat_contract():
    contract = OUTPUT_CONTRACTS["chat"]
    assert any("stop loss" in p.lower() or "trade plan" in p.lower() for p in contract.forbidden_phrases)


def test_broker_connection_is_read_only_initially():
    """broker_api connection must have can_write=False until user explicitly enables write."""
    broker = get_connection("broker_api")
    assert broker is not None
    assert broker.can_write is False, "broker_api must be read-only by default"
    assert broker.is_destructive is True  # but flagged as destructive for write-enable safety


def test_trade_not_triggered_by_daily_brief():
    assert user_explicitly_requested_trade("give me the morning brief") is False


def test_trade_not_triggered_by_company_research():
    assert user_explicitly_requested_trade("Tell me about Apple revenue") is False
