"""
omega_persistence.py — Safe persistence layer for Omega OS.

Saves reports, research tasks, and system events without requiring Supabase.
When Supabase is configured it delegates to atlas_db; otherwise it uses a local
JSON fallback under omega_os/archives/runtime/.

Usage:
    from omega_persistence import save_report_metadata, get_recent_reports
    save_report_metadata({"query": "...", "intent": "COMPANY_RESEARCH", ...})
    reports = get_recent_reports(limit=10)
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Local fallback directory ───────────────────────────────────────────────────
_BASE_DIR     = Path(__file__).parent
_RUNTIME_DIR  = _BASE_DIR / "omega_os" / "archives" / "runtime"
_REPORTS_FILE = _RUNTIME_DIR / "reports.json"
_TASKS_FILE   = _RUNTIME_DIR / "research_tasks.json"
_EVENTS_FILE  = _RUNTIME_DIR / "omega_events.json"

_MAX_LOCAL_RECORDS = 500   # cap per file to prevent unbounded growth


# ── Supabase detection ────────────────────────────────────────────────────────

def is_supabase_configured() -> bool:
    """Return True when real Supabase credentials are present in the environment."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    placeholder_fragments = {"YOUR_", "your_", "example.com", "YOUR_PROJECT_ID"}
    if not url or not key:
        return False
    for fragment in placeholder_fragments:
        if fragment in url or fragment in key:
            return False
    return True


# ── Local JSON helpers ────────────────────────────────────────────────────────

def _ensure_runtime_dir() -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _load_json_list(path: Path) -> list[dict]:
    """Load a JSON list from disk, return [] on any failure."""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as exc:
        log.warning("omega_persistence: failed to load %s — %s", path.name, exc)
    return []


def _save_json_list(path: Path, records: list[dict]) -> None:
    """Write a JSON list to disk, capped at _MAX_LOCAL_RECORDS."""
    try:
        _ensure_runtime_dir()
        trimmed = records[-_MAX_LOCAL_RECORDS:]
        path.write_text(json.dumps(trimmed, indent=2, default=str), encoding="utf-8")
    except Exception as exc:
        log.warning("omega_persistence: failed to save %s — %s", path.name, exc)


def _append_record(path: Path, record: dict) -> None:
    records = _load_json_list(path)
    records.append(record)
    _save_json_list(path, records)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id() -> str:
    return str(uuid.uuid4())


# ── Public API ────────────────────────────────────────────────────────────────

def save_report_metadata(report: dict[str, Any]) -> dict[str, Any]:
    """
    Save report metadata.

    Accepted fields (all optional except query):
        query, intent, output_mode, company, ticker, session_id, user_id,
        quality, sec_filings_used, selected_skill, duration_ms, source

    Returns the saved record with id, saved_at, persistence_mode.
    """
    record: dict[str, Any] = {
        "id":              report.get("id") or _make_id(),
        "saved_at":        _now_iso(),
        "persistence_mode": "local_fallback",
        "query":           str(report.get("query", ""))[:500],
        "intent":          str(report.get("intent", "")),
        "output_mode":     str(report.get("output_mode", "")),
        "company":         report.get("company"),
        "ticker":          report.get("ticker"),
        "session_id":      report.get("session_id"),
        "user_id":         report.get("user_id"),
        "quality":         report.get("quality"),
        "sec_filings_used": bool(report.get("sec_filings_used", False)),
        "selected_skill":  report.get("selected_skill"),
        "duration_ms":     report.get("duration_ms"),
        "source":          report.get("source", "omega"),
    }

    if is_supabase_configured():
        try:
            from atlas_db import supabase as _sb
            if _sb:
                _sb.table("queries").insert({
                    "id":         record["id"],
                    "query":      record["query"],
                    "intent":     record["intent"],
                    "output_mode": record["output_mode"],
                    "created_at": record["saved_at"],
                }).execute()
                record["persistence_mode"] = "supabase"
                return record
        except Exception as exc:
            log.warning("omega_persistence: Supabase insert failed, falling back — %s", exc)

    _append_record(_REPORTS_FILE, record)
    return record


def save_research_task(task: dict[str, Any]) -> dict[str, Any]:
    """
    Queue a research task.

    Accepted fields:
        query (required), intent, company, ticker, priority (1-10),
        session_id, user_id, requested_by, notes

    Returns the saved record with id, status="queued", persistence_mode.
    """
    record: dict[str, Any] = {
        "id":              task.get("id") or _make_id(),
        "saved_at":        _now_iso(),
        "persistence_mode": "local_fallback",
        "status":          "queued",
        "query":           str(task.get("query", ""))[:500],
        "intent":          task.get("intent"),
        "company":         task.get("company"),
        "ticker":          task.get("ticker"),
        "priority":        int(task.get("priority", 5)),
        "session_id":      task.get("session_id"),
        "user_id":         task.get("user_id"),
        "requested_by":    task.get("requested_by"),
        "notes":           str(task.get("notes", ""))[:1000],
    }

    if is_supabase_configured():
        try:
            from atlas_db import supabase as _sb
            if _sb:
                _sb.table("research_tasks").insert(record).execute()
                record["persistence_mode"] = "supabase"
                return record
        except Exception as exc:
            log.warning("omega_persistence: Supabase insert failed, falling back — %s", exc)

    _append_record(_TASKS_FILE, record)
    return record


def save_omega_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Log a system event (audit, connection check, cadence run, error, etc.).

    Accepted fields:
        event_type (required), summary, severity ("info"|"warning"|"error"),
        source, metadata

    Returns the saved record.
    """
    record: dict[str, Any] = {
        "id":              event.get("id") or _make_id(),
        "saved_at":        _now_iso(),
        "persistence_mode": "local_fallback",
        "event_type":      str(event.get("event_type", "general")),
        "summary":         str(event.get("summary", ""))[:500],
        "severity":        event.get("severity", "info"),
        "source":          event.get("source", "omega"),
        "metadata":        event.get("metadata"),
    }

    _append_record(_EVENTS_FILE, record)
    return record


def get_recent_reports(limit: int = 10) -> list[dict[str, Any]]:
    """
    Return recent reports, newest first.
    Uses Supabase when configured, local JSON otherwise.
    """
    limit = max(1, min(limit, 100))

    if is_supabase_configured():
        try:
            from atlas_db import supabase as _sb
            if _sb:
                resp = (
                    _sb.table("queries")
                    .select("id,query,intent,output_mode,created_at")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                rows = resp.data or []
                for r in rows:
                    r["persistence_mode"] = "supabase"
                return rows
        except Exception as exc:
            log.warning("omega_persistence: Supabase query failed, falling back — %s", exc)

    records = _load_json_list(_REPORTS_FILE)
    return list(reversed(records))[:limit]


def get_research_queue(limit: int = 10) -> list[dict[str, Any]]:
    """
    Return queued research tasks, newest first (or by priority desc).
    Uses Supabase when configured, local JSON otherwise.
    """
    limit = max(1, min(limit, 100))

    if is_supabase_configured():
        try:
            from atlas_db import supabase as _sb
            if _sb:
                resp = (
                    _sb.table("research_tasks")
                    .select("*")
                    .eq("status", "queued")
                    .order("priority", desc=True)
                    .limit(limit)
                    .execute()
                )
                rows = resp.data or []
                for r in rows:
                    r["persistence_mode"] = "supabase"
                return rows
        except Exception as exc:
            log.warning("omega_persistence: Supabase query failed, falling back — %s", exc)

    records = _load_json_list(_TASKS_FILE)
    queued = [r for r in records if r.get("status") == "queued"]
    queued.sort(key=lambda r: (-(r.get("priority") or 5), r.get("saved_at", "")))
    return queued[:limit]


def get_persistence_status() -> dict[str, Any]:
    """
    Return a status snapshot of the persistence layer.

    Includes:
        persistence_mode: "supabase" | "local_fallback"
        supabase_configured: bool
        local_reports_count: int (from disk; 0 when using Supabase)
        local_tasks_count: int
        local_events_count: int
        runtime_dir: str (path to local fallback directory)
    """
    supabase_ok = is_supabase_configured()
    mode = "supabase" if supabase_ok else "local_fallback"

    local_reports = len(_load_json_list(_REPORTS_FILE)) if not supabase_ok else 0
    local_tasks   = len(_load_json_list(_TASKS_FILE))   if not supabase_ok else 0
    local_events  = len(_load_json_list(_EVENTS_FILE))  if not supabase_ok else 0

    return {
        "persistence_mode":     mode,
        "supabase_configured":  supabase_ok,
        "local_reports_count":  local_reports,
        "local_tasks_count":    local_tasks,
        "local_events_count":   local_events,
        "runtime_dir":          str(_RUNTIME_DIR),
    }
