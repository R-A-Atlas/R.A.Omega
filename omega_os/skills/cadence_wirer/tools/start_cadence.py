"""
start_cadence.py — Wires omega_cadence.py jobs to APScheduler.

Reads the cadence job registry and starts scheduled execution.
Only activates when OMEGA_CADENCE_ENABLED=true is set — safe to import
in api_server.py startup without side effects in development.

Jobs with existing tool scripts are wired to real runners.
Stub jobs log a "not yet implemented" notice until their tools are built.

Usage:
    # In development (check what would run, no scheduling)
    python omega_os/skills/cadence_wirer/tools/start_cadence.py --dry-run

    # In production (requires OMEGA_CADENCE_ENABLED=true)
    python omega_os/skills/cadence_wirer/tools/start_cadence.py

    # From api_server.py startup:
    from omega_os.skills.cadence_wirer.tools.start_cadence import start_cadence_if_enabled
    start_cadence_if_enabled()
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("omega.cadence")

# ── Cron schedules per slug (APScheduler cron kwargs) ─────────────────────────
# Times are ET (UTC-4 summer / UTC-5 winter — use UTC offsets at server level)

SCHEDULES: dict[str, dict] = {
    "daily_market_brief":          {"day_of_week": "mon-fri", "hour": 11, "minute": 0},   # 7 AM ET = 11 UTC
    "daily_priority_brief":        {"day_of_week": "mon-fri", "hour": 12, "minute": 30},  # 8:30 AM ET
    "weekly_portfolio_review":     {"day_of_week": "sun",     "hour": 22, "minute": 0},   # Sun 6 PM ET
    "weekly_omega_os_audit":       {"day_of_week": "mon",     "hour": 13, "minute": 0},   # Mon 9 AM ET
    "weekly_product_review":       {"day_of_week": "mon",     "hour": 14, "minute": 0},   # Mon 10 AM ET
    "monthly_finance_report":      {"day": 1,                 "hour": 12, "minute": 0},   # 1st of month 8 AM ET
    "monthly_product_roadmap_review": {"day": "last fri",     "hour": 19, "minute": 0},   # Last Fri 3 PM ET
}

# ── Implemented runners (slug → callable or script path) ──────────────────────

def _run_session_briefing() -> None:
    """daily_market_brief — uses session_briefing.py (implemented)."""
    script = ROOT / "omega_os" / "skills" / "dev_session_guard" / "tools" / "session_briefing.py"
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        logger.error("session_briefing failed: %s", result.stderr[:200])
    else:
        logger.info("daily_market_brief completed:\n%s", result.stdout[:500])


def _run_route_audit() -> None:
    """weekly_omega_os_audit — runs master audit (benchmark + readiness + route check)."""
    audit_script = ROOT / "omega_os" / "skills" / "audit_runner" / "tools" / "run_audit.py"
    result = subprocess.run(
        [sys.executable, str(audit_script), "--no-save"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    if result.returncode != 0:
        logger.error("weekly_omega_os_audit failed: %s", result.stderr[:300])
    else:
        logger.info("weekly_omega_os_audit completed:\n%s", result.stdout[:1000])


def _stub_runner(slug: str):
    """Returns a no-op runner for unimplemented cadence jobs."""
    def _run():
        logger.info("Cadence job '%s' is a stub — tool not yet built. Skipping.", slug)
    _run.__name__ = f"stub_{slug}"
    return _run


# ── Job runner map ────────────────────────────────────────────────────────────

RUNNERS: dict[str, callable] = {
    "daily_market_brief":           _run_session_briefing,
    "weekly_omega_os_audit":        _run_route_audit,
}


def _get_runner(slug: str) -> callable:
    return RUNNERS.get(slug, _stub_runner(slug))


# ── Dry run ───────────────────────────────────────────────────────────────────

def dry_run() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from omega_cadence import get_cadence_plan

    sep = "=" * 68
    print(sep)
    print("  R.A. OMEGA — CADENCE WIRER  [DRY RUN]")
    print(f"  OMEGA_CADENCE_ENABLED = {os.environ.get('OMEGA_CADENCE_ENABLED', '(not set)')}")
    print(sep)
    print(f"\n  {'SLUG':<36} {'SCHEDULE':<28} RUNNER")
    print(f"  {'-'*36} {'-'*28} ------")

    jobs = get_cadence_plan()
    for job in jobs:
        sched  = SCHEDULES.get(job.slug, {})
        sched_str = str(sched) if sched else "(no schedule defined)"
        runner = "REAL" if job.slug in RUNNERS else "STUB"
        print(f"  {job.slug:<36} {sched_str:<28} {runner}")

    print(f"\n  {len(jobs)} jobs declared,  {len(RUNNERS)} with real runners")
    print(f"  Set OMEGA_CADENCE_ENABLED=true to activate scheduling")
    print(sep)


# ── APScheduler wiring ────────────────────────────────────────────────────────

def start_cadence() -> None:
    """Wire all cadence jobs to APScheduler and start the scheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed — cadence not started. pip install apscheduler")
        return

    from omega_cadence import get_cadence_plan

    scheduler = BackgroundScheduler(timezone="UTC")
    jobs = get_cadence_plan()
    wired = 0

    for job in jobs:
        sched = SCHEDULES.get(job.slug)
        if not sched:
            logger.debug("No schedule defined for %s — skipping", job.slug)
            continue
        runner = _get_runner(job.slug)
        try:
            scheduler.add_job(
                runner,
                trigger="cron",
                id=job.slug,
                name=job.name,
                replace_existing=True,
                misfire_grace_time=300,
                **sched,
            )
            wired += 1
            logger.info("Wired cadence job: %s (%s)", job.slug, sched)
        except Exception as e:
            logger.error("Failed to wire %s: %s", job.slug, e)

    scheduler.start()
    logger.info("Omega cadence scheduler started — %d/%d jobs wired", wired, len(jobs))


def start_cadence_if_enabled() -> None:
    """Call from api_server.py startup. Only activates when env var is set."""
    enabled = os.environ.get("OMEGA_CADENCE_ENABLED", "").strip().lower()
    if enabled == "true":
        logger.info("OMEGA_CADENCE_ENABLED=true — starting cadence scheduler")
        start_cadence()
    else:
        logger.debug("OMEGA_CADENCE_ENABLED not set — cadence scheduler inactive (set to 'true' to enable)")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega cadence wirer")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without scheduling")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    enabled = os.environ.get("OMEGA_CADENCE_ENABLED", "").strip().lower()
    if enabled != "true":
        print("Set OMEGA_CADENCE_ENABLED=true to start the scheduler.")
        print("Run with --dry-run to preview the schedule.")
        sys.exit(0)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    start_cadence()
    print("Cadence scheduler running. Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Cadence scheduler stopped.")


if __name__ == "__main__":
    main()
