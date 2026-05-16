"""
omega_dashboard.py — Aggregation layer for the R.A. Omega Command Center.

Provides two snapshots:
  build_command_center_snapshot() — system status, scores, queues, connections
  build_omega_brain_snapshot()    — context files, decisions, skills, memory

Both functions degrade gracefully if any subsystem is unavailable. No external
credentials required — subsystems return safe defaults when not configured.

Usage:
    from omega_dashboard import build_command_center_snapshot, build_omega_brain_snapshot
    payload = build_command_center_snapshot()
    brain   = build_omega_brain_snapshot()
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ROOT        = Path(__file__).parent
_OMEGA_OS    = _ROOT / "omega_os"
_CONTEXT_DIR = _OMEGA_OS / "context"
_DECISIONS_DIR = _OMEGA_OS / "decisions"
_AUDITS_FILE = _OMEGA_OS / "audits" / "four_c_audits.md"
_MEMORY_DIR  = _ROOT / "atlas_memory"


def _safe(fn, default=None):
    """Call fn(), return default on any exception."""
    try:
        return fn()
    except Exception as exc:
        log.debug("omega_dashboard: subsystem call failed — %s: %s", fn, exc)
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# Command Center Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

def _get_four_c_scores() -> dict[str, Any]:
    """Run the Four C audit and return scores + phase."""
    raw = _safe(lambda: __import__("omega_audit").run_audit(), {})
    if not raw:
        return {
            "context": 0, "connections": 0, "capabilities": 0, "cadence": 0,
            "total": 0, "phase": "unknown", "strengths": [], "gaps": [], "next_steps": [],
        }
    return {
        "context":      raw.get("context", 0),
        "connections":  raw.get("connections", 0),
        "capabilities": raw.get("capabilities", 0),
        "cadence":      raw.get("cadence", 0),
        "total":        raw.get("total", 0),
        "phase":        raw.get("phase", "unknown"),
        "strengths":    raw.get("strengths", [])[:5],
        "gaps":         raw.get("gaps", [])[:5],
        "next_steps":   raw.get("next_steps", [])[:3],
    }


def _get_connection_status() -> list[dict[str, Any]]:
    """Return active/configured/planned connection registry summary."""
    raw = _safe(lambda: __import__("omega_connections").get_registry(), [])
    if not raw:
        return []
    return [
        {
            "name":   c.name,
            "slug":   c.slug,
            "status": c.status,
            "can_write": c.can_write,
            "is_destructive": c.is_destructive,
        }
        for c in raw
    ]


def _get_cadence_status() -> list[dict[str, Any]]:
    """Return declared cadence jobs with their status."""
    raw = _safe(lambda: __import__("omega_cadence").get_cadence_plan(), [])
    if not raw:
        return []
    return [
        {
            "name":              j.name,
            "slug":              j.slug,
            "frequency":         j.frequency,
            "schedule_hint":     j.schedule_hint,
            "status":            j.status,
            "estimated_cost_usd": j.estimated_cost_usd,
        }
        for j in raw
    ]


def _get_recent_reports(limit: int = 5) -> list[dict[str, Any]]:
    """Return recent report metadata from persistence."""
    raw = _safe(lambda: __import__("omega_persistence").get_recent_reports(limit=limit), [])
    return raw or []


def _get_research_queue(limit: int = 5) -> list[dict[str, Any]]:
    """Return pending research tasks from persistence."""
    raw = _safe(lambda: __import__("omega_persistence").get_research_queue(limit=limit), [])
    return raw or []


def _get_skills_summary() -> list[dict[str, str]]:
    """Return available Omega OS skills (name + description)."""
    raw = _safe(lambda: __import__("omega_os_loader").list_skills(), [])
    return raw or []


def _get_capture_status() -> dict[str, Any]:
    """Return capture inbox counts and latest captures for dashboard."""
    status = _safe(lambda: __import__("omega_capture").get_capture_status(), {})
    latest = _safe(lambda: __import__("omega_capture").get_capture_inbox(limit=5), [])
    return {
        "capture_inbox_count": (status or {}).get("inbox_count", 0),
        "latest_captures":     latest or [],
        "capture_by_type":     (status or {}).get("by_type", {}),
        "capture_by_source":   (status or {}).get("by_source", {}),
    }


def _get_telegram_status() -> dict[str, Any]:
    """Return Telegram adapter + voice capture status. No credentials required."""
    raw = _safe(lambda: __import__("omega_telegram").get_telegram_status(), {})
    if not raw:
        return {
            "configured":        False,
            "status":            "not_configured",
            "voice_enabled":     False,
            "whisper_configured": False,
        }
    return {
        "configured":           raw.get("configured", False),
        "status":               raw.get("status", "not_configured"),
        "voice_enabled":        raw.get("voice_enabled", False),
        "whisper_configured":   raw.get("whisper_configured", False),
        "allowed_users_count":  raw.get("allowed_users_count", 0),
        "webhook_secret_set":   raw.get("webhook_secret_set", False),
    }


def _get_agentic_os_status() -> dict[str, Any]:
    """Return agentic OS worker metadata for dashboard."""
    raw = _safe(lambda: __import__("omega_agentic_os").get_agentic_os_status(), {})
    return raw or {
        "agentic_workers_count":     0,
        "agentic_workers_available": 0,
        "always_on_hosting_status":  "planned",
        "workers":                   [],
        "suggested_agentic_actions": [],
    }


def _get_google_workspace_status() -> dict[str, Any]:
    """Return Google Workspace configuration status."""
    raw = _safe(lambda: __import__("omega_google_workspace").get_google_workspace_status(), {})
    return raw or {"configured": False, "enabled": False, "message": "unavailable"}


def _get_persistence_status() -> dict[str, Any]:
    """Return persistence layer status."""
    raw = _safe(lambda: __import__("omega_persistence").get_persistence_status(), {})
    return raw or {"persistence_mode": "unknown", "supabase_configured": False}


def _get_sec_edgar_status() -> dict[str, Any]:
    """Return SEC EDGAR availability and integration status."""
    import os
    is_avail = _safe(lambda: __import__("omega_sec_edgar").is_available(), False)
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    return {
        "available":        bool(is_avail),
        "user_agent_set":   bool(ua),
        "status":           "active" if is_avail else ("configured" if ua else "not_configured"),
    }


def _build_suggested_next_actions(
    four_c: dict,
    connections: list[dict],
    cadence: list[dict],
    persistence: dict,
) -> list[str]:
    """Suggest 3-5 high-value next actions based on current system state."""
    actions: list[str] = []

    # Check persistence mode
    if persistence.get("persistence_mode") == "local_fallback":
        actions.append("Configure Supabase credentials to enable cloud persistence (SUPABASE_URL, SUPABASE_KEY)")

    # Check active connections
    active_slugs = {c["slug"] for c in connections if c["status"] == "active"}
    if "sec_edgar" not in active_slugs:
        actions.append("Set SEC_USER_AGENT in .env to activate SEC EDGAR filing integration")
    if "google_workspace" not in active_slugs:
        actions.append("Set GOOGLE_WORKSPACE_ENABLED=true to activate report export to Google Docs/Sheets")

    # Check cadence
    planned_jobs = [j for j in cadence if j["status"] == "planned"]
    if planned_jobs:
        actions.append(f"Schedule {len(planned_jobs)} planned cadence jobs (daily_market_brief, weekly_portfolio_review, ...)")

    # Check Four C gaps
    gaps = four_c.get("gaps", [])
    if gaps:
        actions.append(f"Address top context gap: {gaps[0]}")

    return actions[:5]


def _get_system_health(four_c: dict, persistence: dict) -> dict[str, Any]:
    """Return a quick health summary."""
    score = four_c.get("total", 0)
    if score >= 85:
        health = "excellent"
    elif score >= 70:
        health = "good"
    elif score >= 50:
        health = "needs_attention"
    else:
        health = "critical"

    return {
        "health":             health,
        "omega_os_score":     score,
        "persistence_mode":   persistence.get("persistence_mode", "unknown"),
        "supabase_active":    persistence.get("supabase_configured", False),
    }


def build_command_center_snapshot() -> dict[str, Any]:
    """
    Build a single aggregated Command Center payload.

    Calls multiple Omega OS subsystems, degrades gracefully on any failure.
    Returns a structured dict suitable for direct frontend consumption.

    All fields are always present — subsystem failures produce empty/default values.
    """
    four_c        = _get_four_c_scores()
    connections   = _get_connection_status()
    cadence       = _get_cadence_status()
    persistence   = _get_persistence_status()
    agentic_os    = _get_agentic_os_status()
    capture       = _get_capture_status()
    telegram      = _get_telegram_status()

    return {
        # Four C audit scores
        "omega_os_score":  four_c.get("total", 0),
        "four_c_scores":   {
            "context":      four_c.get("context", 0),
            "connections":  four_c.get("connections", 0),
            "capabilities": four_c.get("capabilities", 0),
            "cadence":      four_c.get("cadence", 0),
        },
        "phase_label":     four_c.get("phase", "unknown"),

        # Subsystem statuses
        "connection_status":       connections,
        "cadence_status":          cadence,
        "google_workspace_status": _get_google_workspace_status(),
        "persistence_status":      persistence,
        "sec_edgar_status":        _get_sec_edgar_status(),

        # Work queues
        "recent_reports":   _get_recent_reports(limit=5),
        "research_queue":   _get_research_queue(limit=5),

        # Skills registry
        "skills_summary":   _get_skills_summary(),

        # Capture inbox
        "capture_inbox_count":  capture.get("capture_inbox_count", 0),
        "latest_captures":      capture.get("latest_captures", []),
        "telegram_status":      telegram,
        "voice_capture_status": "enabled" if telegram.get("voice_enabled") else "disabled",

        # Agentic OS workers
        "agentic_workers_count":     agentic_os.get("agentic_workers_count", 0),
        "agentic_workers_available": agentic_os.get("agentic_workers_available", 0),
        "always_on_hosting_status":  agentic_os.get("always_on_hosting_status", "planned"),
        "agentic_os_status":         agentic_os,
        "suggested_agentic_actions": agentic_os.get("suggested_agentic_actions", []),

        # Guidance
        "suggested_next_actions": _build_suggested_next_actions(
            four_c, connections, cadence, persistence
        ),

        # System health roll-up
        "system_health": _get_system_health(four_c, persistence),

        # Metadata
        "snapshot_at": _now_iso(),
        "snapshot_type": "command_center",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Brain Snapshot
# ═══════════════════════════════════════════════════════════════════════════════

def _get_context_categories() -> list[dict[str, Any]]:
    """Return Omega OS context files grouped by category."""
    if not _CONTEXT_DIR.exists():
        return []
    files = []
    for f in sorted(_CONTEXT_DIR.iterdir()):
        if f.suffix == ".md":
            size = f.stat().st_size
            files.append({
                "filename":    f.name,
                "populated":   size > 50,
                "size_bytes":  size,
            })
    return files


def _get_decisions_summary() -> list[dict[str, str]]:
    """Return recent architecture decisions (last 10 lines of decisions file)."""
    decisions_file = _DECISIONS_DIR / "architecture_decisions.md"
    if not decisions_file.exists():
        return []
    try:
        lines = decisions_file.read_text(encoding="utf-8").strip().splitlines()
        # Return entries (lines starting with ##) with up to 5 entries
        entries: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in lines:
            if line.startswith("## "):
                if current:
                    entries.append(current)
                current = {"title": line.lstrip("# ").strip(), "summary": ""}
            elif current and line.strip() and not line.startswith("#"):
                current["summary"] = (current.get("summary", "") + " " + line.strip()).strip()[:200]
        if current:
            entries.append(current)
        return entries[-5:]
    except Exception:
        return []


def _get_audit_history_summary() -> list[dict[str, Any]]:
    """Return last 3 audit entries from four_c_audits.md."""
    if not _AUDITS_FILE.exists():
        return []
    try:
        text = _AUDITS_FILE.read_text(encoding="utf-8")
        # Split by audit entry headers (## )
        blocks = [b.strip() for b in text.split("## ") if b.strip()]
        entries: list[dict[str, Any]] = []
        for block in blocks[-3:]:
            lines = block.splitlines()
            title = lines[0].strip() if lines else "Audit"
            # Try to extract total score from content
            score = None
            for line in lines:
                if "total" in line.lower() and any(c.isdigit() for c in line):
                    import re
                    m = re.search(r"\d+", line)
                    if m:
                        score = int(m.group())
                        break
            entries.append({"title": title, "score": score})
        return entries
    except Exception:
        return []


def _get_skills_available() -> list[dict[str, str]]:
    """Return available skills with name and description."""
    return _get_skills_summary()


def _get_memory_files() -> list[dict[str, Any]]:
    """Return atlas_memory files summary (non-db files)."""
    memory_root = _ROOT / "C:\\Users\\crist\\.claude\\projects\\C--Users-crist-Projects-R-A-Omega\\memory"
    # Fall back to relative path
    memory_root_rel = Path.home() / ".claude" / "projects" / "C--Users-crist-Projects-R-A-Omega" / "memory"
    target = memory_root_rel if memory_root_rel.exists() else None

    files: list[dict[str, Any]] = []
    if target and target.exists():
        for f in sorted(target.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                mtype = "unknown"
                for line in content.splitlines():
                    if line.startswith("  type:"):
                        mtype = line.split("type:")[-1].strip()
                        break
                files.append({
                    "filename":  f.name,
                    "type":      mtype,
                    "size_bytes": f.stat().st_size,
                })
            except Exception:
                pass
    return files[:20]


def _get_recommended_questions() -> list[str]:
    """Return a static set of high-value questions for the current system state."""
    return [
        "What is the current macro regime and how does it affect my portfolio?",
        "Give me a full company intelligence report on BlackRock.",
        "What are the top 3 risks in my current watchlist?",
        "Run a daily brief — what happened in the market today?",
        "What are the best dividend stocks for the next 12 months?",
        "Analyze NVDA — current setup and key risk levels.",
        "What does the SEC filing history say about Apple's capital allocation?",
        "Generate a weekly portfolio review based on my current positions.",
    ]


def build_omega_brain_snapshot() -> dict[str, Any]:
    """
    Build a structured Brain snapshot describing Omega OS knowledge state.

    Returns context files, decisions, skill list, memory files, and recommended questions.
    All fields degrade gracefully — missing subsystems produce empty lists.
    """
    return {
        # Context knowledge base
        "context_categories":   _safe(_get_context_categories, []),

        # Architecture decisions log
        "decisions_summary":    _safe(_get_decisions_summary, []),

        # Audit history
        "audit_history_summary": _safe(_get_audit_history_summary, []),

        # Skills registry
        "skills_available":     _safe(_get_skills_available, []),

        # Persistent memory files
        "memory_files":         _safe(_get_memory_files, []),

        # Suggested questions for this system state
        "recommended_questions": _get_recommended_questions(),

        # Metadata
        "snapshot_at":   _now_iso(),
        "snapshot_type": "omega_brain",
    }
