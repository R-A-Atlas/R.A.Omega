"""
omega_cadence.py — Cadence plan for the Omega OS layer.

Declares planned recurring jobs. Does NOT schedule real jobs — this is a declaration
registry only. Actual scheduling (APScheduler, CronCreate, cron) is a future step.

Each cadence job defines what it needs and what it produces so that when scheduling
is added, all dependencies are already documented.

Usage:
    from omega_cadence import get_cadence_plan, get_job, list_jobs
    plan = get_cadence_plan()
    job = get_job("daily_market_brief")
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ── Frequency constants ───────────────────────────────────────────────────────
FREQ_DAILY   = "daily"
FREQ_WEEKLY  = "weekly"
FREQ_MONTHLY = "monthly"
FREQ_HOURLY  = "hourly"

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_PLANNED   = "planned"    # declared but not yet scheduled
STATUS_ACTIVE    = "active"     # scheduled and running
STATUS_PAUSED    = "paused"     # was active, temporarily paused
STATUS_DISABLED  = "disabled"   # intentionally off


@dataclass(frozen=True)
class CadenceJob:
    name: str
    slug: str                              # snake_case identifier for lookups
    frequency: str                         # daily | weekly | monthly | hourly
    schedule_hint: str                     # human-readable timing (e.g. "7:00 AM ET Mon–Fri")
    status: str = STATUS_PLANNED
    required_context: tuple[str, ...] = field(default_factory=tuple)   # omega_os/context/ files needed
    required_connections: tuple[str, ...] = field(default_factory=tuple)  # connection slugs needed
    required_skills: tuple[str, ...] = field(default_factory=tuple)    # omega_os skill names needed
    output: str = ""                       # what the job produces
    output_destinations: tuple[str, ...] = field(default_factory=tuple)  # where output goes
    safety_rules: tuple[str, ...] = field(default_factory=tuple)
    estimated_cost_usd: float = 0.0        # estimated cost per run (Gemini API)
    estimated_duration_s: int = 60         # estimated wall-clock time in seconds

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["required_context"] = list(d["required_context"])
        d["required_connections"] = list(d["required_connections"])
        d["required_skills"] = list(d["required_skills"])
        d["output_destinations"] = list(d["output_destinations"])
        d["safety_rules"] = list(d["safety_rules"])
        return d


# ── Cadence job registry ──────────────────────────────────────────────────────

_CADENCE_PLAN: list[CadenceJob] = [

    CadenceJob(
        name="Daily Market Brief",
        slug="daily_market_brief",
        frequency=FREQ_DAILY,
        schedule_hint="7:00 AM ET Monday–Friday",
        status=STATUS_PLANNED,
        required_context=(
            "about_user.md",
            "portfolio_profile.md",
            "risk_profile.md",
            "preferences.md",
        ),
        required_connections=("supabase", "yfinance", "gemini"),
        required_skills=("daily_brief",),
        output="Morning market brief: regime, top movers, macro watch, watchlist RYG status, priority action",
        output_destinations=("app_response", "telegram", "gmail"),
        safety_rules=(
            "Never include trade recommendations without explicit user opt-in",
            "Label all market data with source and timestamp",
            "Do not run if market is closed (holidays + weekends) unless user opts in",
            "Delivery to Telegram/Gmail requires those connections to be active",
        ),
        estimated_cost_usd=0.05,
        estimated_duration_s=45,
    ),

    CadenceJob(
        name="Daily Priority Brief",
        slug="daily_priority_brief",
        frequency=FREQ_DAILY,
        schedule_hint="8:30 AM ET Monday–Friday (after market open)",
        status=STATUS_PLANNED,
        required_context=(
            "priorities.md",
            "user_goals.md",
            "project_roadmap.md",
            "preferences.md",
        ),
        required_connections=("supabase", "gemini"),
        required_skills=("daily_brief",),
        output="Daily priorities: top 3 tasks, blockers, decision needed today",
        output_destinations=("app_response", "telegram"),
        safety_rules=(
            "Priorities must come from priorities.md — do not invent tasks",
            "Do not include financial data in the priority brief (use daily_market_brief for that)",
            "Maximum 3 items — prioritize ruthlessly",
        ),
        estimated_cost_usd=0.02,
        estimated_duration_s=15,
    ),

    CadenceJob(
        name="Weekly Portfolio Review",
        slug="weekly_portfolio_review",
        frequency=FREQ_WEEKLY,
        schedule_hint="Sunday 6:00 PM ET",
        status=STATUS_PLANNED,
        required_context=(
            "portfolio_profile.md",
            "risk_profile.md",
            "about_user.md",
        ),
        required_connections=("supabase", "yfinance", "gemini"),
        required_skills=("portfolio_review",),
        output="Portfolio review: P&L summary, risk exposure, rebalancing needs, next week watchlist",
        output_destinations=("app_response", "atlas_vault/03-Outputs/", "google_sheets"),
        safety_rules=(
            "Never execute trades automatically — all recommendations require user confirmation",
            "Rebalancing suggestions must be labeled 'for review' not 'instructions'",
            "Flag positions approaching stop loss or max loss threshold prominently",
            "Do not run if positions data is stale (>24 hours without sync)",
        ),
        estimated_cost_usd=0.15,
        estimated_duration_s=120,
    ),

    CadenceJob(
        name="Weekly Omega OS Audit",
        slug="weekly_omega_os_audit",
        frequency=FREQ_WEEKLY,
        schedule_hint="Monday 9:00 AM ET",
        status=STATUS_PLANNED,
        required_context=(
            "project_roadmap.md",
            "priorities.md",
        ),
        required_connections=(),  # no external connections needed — reads local files
        required_skills=("audit",),
        output="Four C audit scores (0–100), strengths, gaps, next 5 implementation steps",
        output_destinations=("omega_os/audits/four_c_audits.md", "app_response"),
        safety_rules=(
            "Audit is read-only — do not modify omega_os files except four_c_audits.md",
            "Log score delta vs previous week",
            "Alert if score drops more than 5 points week-over-week",
        ),
        estimated_cost_usd=0.0,  # no LLM calls — pure file system inspection
        estimated_duration_s=5,
    ),

    CadenceJob(
        name="Weekly Product Review",
        slug="weekly_product_review",
        frequency=FREQ_WEEKLY,
        schedule_hint="Monday 10:00 AM ET",
        status=STATUS_PLANNED,
        required_context=(
            "project_roadmap.md",
            "priorities.md",
            "user_goals.md",
            "agent_architecture.md",
        ),
        required_connections=("supabase", "gemini"),
        required_skills=("weekly_product_review", "audit", "level_up"),
        output="Weekly product review: test count, Four C score, wins, blockers, next week priorities",
        output_destinations=("app_response", "atlas_vault/04-Projects/ATLAS/Notes/session_log.md"),
        safety_rules=(
            "Do not mark items as complete if tests are failing",
            "Do not edit deep_research.py, gemini_limiter.py, or atlas_memory.db",
            "Session log must be PASS only if all tests pass and server starts clean",
            "Do not push to production without completing visual QA step",
        ),
        estimated_cost_usd=0.10,
        estimated_duration_s=180,
    ),

    CadenceJob(
        name="Monthly Finance Report",
        slug="monthly_finance_report",
        frequency=FREQ_MONTHLY,
        schedule_hint="1st of month, 8:00 AM ET",
        status=STATUS_PLANNED,
        required_context=(
            "portfolio_profile.md",
            "risk_profile.md",
            "about_user.md",
            "user_goals.md",
        ),
        required_connections=("supabase", "yfinance", "gemini", "google_sheets"),
        required_skills=("portfolio_review", "document_generator"),
        output="Monthly finance report: sector performance, portfolio changes, key events, 30-day outlook",
        output_destinations=(
            "atlas_vault/03-Outputs/",
            "google_drive",
            "app_response",
        ),
        safety_rules=(
            "Label all data with source and as-of date",
            "Do not auto-send monthly report via email without user confirmation",
            "Do not include forward-looking recommendations labeled as predictions",
            "Archive previous month's report before generating the new one",
        ),
        estimated_cost_usd=0.50,
        estimated_duration_s=300,
    ),

    CadenceJob(
        name="Monthly Product Roadmap Review",
        slug="monthly_product_roadmap_review",
        frequency=FREQ_MONTHLY,
        schedule_hint="Last Friday of month, 3:00 PM ET",
        status=STATUS_PLANNED,
        required_context=(
            "project_roadmap.md",
            "priorities.md",
            "user_goals.md",
            "about_business.md",
            "agent_architecture.md",
        ),
        required_connections=("gemini",),
        required_skills=("weekly_product_review", "level_up"),
        output="Monthly roadmap review: phase completion, next month priorities, strategic direction, level-up recommendations",
        output_destinations=(
            "omega_os/context/project_roadmap.md",
            "omega_os/context/priorities.md",
            "app_response",
        ),
        safety_rules=(
            "Update project_roadmap.md with completed items — do not delete in-progress items",
            "Level-up recommendations must not include unsafe automations (trades, deletions)",
            "Strategic direction changes must be logged in omega_os/decisions/product_decisions.md",
        ),
        estimated_cost_usd=0.20,
        estimated_duration_s=120,
    ),
]


# ── Registry lookup functions ─────────────────────────────────────────────────

def get_cadence_plan() -> list[CadenceJob]:
    """Return all cadence jobs."""
    return list(_CADENCE_PLAN)


def get_job(slug: str) -> CadenceJob | None:
    """Look up a cadence job by its slug."""
    for job in _CADENCE_PLAN:
        if job.slug == slug:
            return job
    return None


def list_jobs(status: str | None = None) -> list[CadenceJob]:
    """Return all jobs, optionally filtered by status."""
    if status is None:
        return list(_CADENCE_PLAN)
    return [j for j in _CADENCE_PLAN if j.status == status]


def list_by_frequency(frequency: str) -> list[CadenceJob]:
    """Return jobs with a given frequency (daily | weekly | monthly)."""
    return [j for j in _CADENCE_PLAN if j.frequency == frequency]


def cadence_summary() -> dict:
    """Return a compact summary dict suitable for API responses."""
    return {
        "total": len(_CADENCE_PLAN),
        "planned": sum(1 for j in _CADENCE_PLAN if j.status == STATUS_PLANNED),
        "active": sum(1 for j in _CADENCE_PLAN if j.status == STATUS_ACTIVE),
        "daily": sum(1 for j in _CADENCE_PLAN if j.frequency == FREQ_DAILY),
        "weekly": sum(1 for j in _CADENCE_PLAN if j.frequency == FREQ_WEEKLY),
        "monthly": sum(1 for j in _CADENCE_PLAN if j.frequency == FREQ_MONTHLY),
        "total_estimated_cost_per_week_usd": round(
            sum(j.estimated_cost_usd * (7 if j.frequency == FREQ_DAILY
                                        else 1 if j.frequency == FREQ_WEEKLY
                                        else 0.25) for j in _CADENCE_PLAN),
            4,
        ),
        "jobs": [
            {
                "name": j.name,
                "slug": j.slug,
                "frequency": j.frequency,
                "schedule_hint": j.schedule_hint,
                "status": j.status,
                "estimated_cost_usd": j.estimated_cost_usd,
                "estimated_duration_s": j.estimated_duration_s,
            }
            for j in _CADENCE_PLAN
        ],
    }
