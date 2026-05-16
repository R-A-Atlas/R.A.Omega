"""
omega_capture.py — Capture inbox for R.A. Omega.

Saves, classifies, and triages inbound captures from any source (Telegram,
voice, web, API). Persists through omega_persistence when available;
falls back to a local JSON file.

Usage:
    from omega_capture import save_capture, classify_capture, get_capture_inbox
    capture = save_capture("Bug: dashboard crashes on refresh", source="telegram")
    inbox   = get_capture_inbox(limit=10)
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

# ── Local fallback storage ────────────────────────────────────────────────────

_BASE_DIR      = Path(__file__).parent
_RUNTIME_DIR   = _BASE_DIR / "omega_os" / "archives" / "runtime"
_CAPTURES_FILE = _RUNTIME_DIR / "captures.json"

_MAX_LOCAL_CAPTURES = 500


# ── Classification ────────────────────────────────────────────────────────────

CAPTURE_TYPES = ("bug", "idea", "task", "research_request", "content_idea", "reminder", "unknown")

_BUG_KEYWORDS        = ("bug", "broken", "crash", "error", "fix", "not working", "fails", "exception", "500", "traceback")
_IDEA_KEYWORDS       = ("idea", "what if", "could we", "feature", "proposal", "suggest", "suggestion", "improvement")
_TASK_KEYWORDS       = ("todo", "to do", "do this", "implement", "add", "create", "build", "write", "make", "task")
_RESEARCH_KEYWORDS   = ("research", "analyze", "analyse", "look into", "investigate", "study", "report on", "deep dive", "find out")
_CONTENT_KEYWORDS    = ("post", "tweet", "write up", "blog", "content", "marketing", "share", "publish", "draft", "article")
_REMINDER_KEYWORDS   = ("remind", "reminder", "don't forget", "remember", "follow up", "check on", "revisit")


def classify_capture(raw_text: str, source: str = "telegram") -> str:
    """
    Classify a capture into one of the CAPTURE_TYPES.

    Uses keyword matching — deterministic, no LLM calls.
    Returns one of: bug, idea, task, research_request, content_idea, reminder, unknown.
    """
    if not raw_text or not isinstance(raw_text, str):
        return "unknown"

    lower = raw_text.lower()

    if any(kw in lower for kw in _BUG_KEYWORDS):
        return "bug"
    if any(kw in lower for kw in _RESEARCH_KEYWORDS):
        return "research_request"
    if any(kw in lower for kw in _REMINDER_KEYWORDS):
        return "reminder"
    if any(kw in lower for kw in _CONTENT_KEYWORDS):
        return "content_idea"
    if any(kw in lower for kw in _IDEA_KEYWORDS):
        return "idea"
    if any(kw in lower for kw in _TASK_KEYWORDS):
        return "task"
    return "unknown"


# ── Local JSON helpers ────────────────────────────────────────────────────────

def _ensure_runtime_dir() -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _load_captures() -> list[dict[str, Any]]:
    try:
        if _CAPTURES_FILE.exists():
            data = json.loads(_CAPTURES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as exc:
        log.warning("omega_capture: failed to load captures — %s", exc)
    return []


def _save_captures(records: list[dict[str, Any]]) -> None:
    try:
        _ensure_runtime_dir()
        trimmed = records[-_MAX_LOCAL_CAPTURES:]
        _CAPTURES_FILE.write_text(json.dumps(trimmed, indent=2, default=str), encoding="utf-8")
    except Exception as exc:
        log.warning("omega_capture: failed to save captures — %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id() -> str:
    return str(uuid.uuid4())


# ── Public API ────────────────────────────────────────────────────────────────

def save_capture(
    raw_text: str,
    source: str = "telegram",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Save an inbound capture to the inbox.

    Args:
        raw_text:  The raw text content of the capture.
        source:    Where it came from (telegram, voice, web, api, etc.)
        metadata:  Optional extra fields (user_id, message_id, file_id, etc.)

    Returns:
        Saved capture record with id, capture_type, status, saved_at.
    """
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    capture_type = classify_capture(raw_text, source)

    record: dict[str, Any] = {
        "id":           _make_id(),
        "saved_at":     _now_iso(),
        "source":       str(source)[:50],
        "raw_text":     raw_text[:2000],
        "capture_type": capture_type,
        "status":       "inbox",
        "triaged_at":   None,
        "metadata":     metadata or {},
    }

    # Try omega_persistence event log first (gracefully degrade if unavailable)
    try:
        from omega_persistence import save_omega_event as _save_event
        _save_event({
            "event_type": "capture_received",
            "summary":    f"[{capture_type}] from {source}: {raw_text[:120]}",
            "severity":   "info",
            "source":     "omega_capture",
            "metadata":   {"capture_id": record["id"], "capture_type": capture_type},
        })
    except Exception as exc:
        log.debug("omega_capture: event log unavailable — %s", exc)

    # Always persist to local captures file
    captures = _load_captures()
    captures.append(record)
    _save_captures(captures)

    log.info("omega_capture: saved [%s] from %s — id=%s", capture_type, source, record["id"])
    return record


def triage_capture(capture_id: str) -> dict[str, Any]:
    """
    Mark a capture as triaged (moved from inbox to triaged status).

    Args:
        capture_id:  UUID of the capture to triage.

    Returns:
        Updated capture record, or {"error": "..."} if not found.
    """
    captures = _load_captures()
    for record in captures:
        if record.get("id") == capture_id:
            record["status"] = "triaged"
            record["triaged_at"] = _now_iso()
            _save_captures(captures)
            return record
    return {"error": f"Capture not found: {capture_id}"}


def get_capture_inbox(limit: int = 20) -> list[dict[str, Any]]:
    """
    Return recent captures with status='inbox', newest first.

    Args:
        limit: Maximum number of captures to return (default 20, max 100).

    Returns:
        List of capture records.
    """
    limit = min(int(limit), 100)
    captures = _load_captures()
    inbox = [c for c in captures if c.get("status") == "inbox"]
    return list(reversed(inbox))[:limit]


def get_capture_status() -> dict[str, Any]:
    """
    Return capture inbox status for dashboard consumption.

    Returns:
        Dict with total, inbox_count, triaged_count, by_type, by_source.
    """
    captures = _load_captures()
    inbox     = [c for c in captures if c.get("status") == "inbox"]
    triaged   = [c for c in captures if c.get("status") == "triaged"]

    by_type: dict[str, int] = {}
    for c in inbox:
        ct = c.get("capture_type", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1

    by_source: dict[str, int] = {}
    for c in inbox:
        src = c.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    return {
        "total":          len(captures),
        "inbox_count":    len(inbox),
        "triaged_count":  len(triaged),
        "by_type":        by_type,
        "by_source":      by_source,
        "storage":        "local_json",
        "captures_file":  str(_CAPTURES_FILE),
    }
