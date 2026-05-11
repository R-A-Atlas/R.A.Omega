"""Local research job state for plan/progress/activity UX.

This is a file-backed scaffold for the product contract. It can later be moved
to Supabase `research_jobs` without changing the frontend shape.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
from typing import Any


_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}
_STORE_PATH: Path | None = None


def configure_store(path: Path) -> None:
    global _STORE_PATH
    _STORE_PATH = path
    path.parent.mkdir(parents=True, exist_ok=True)
    _load()


def create_job(
    *,
    user_id: str,
    query: str,
    route_decision: dict[str, Any],
    activity: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    now = _now()
    job_id = "research_" + uuid.uuid4().hex[:18]
    job = {
        "job_id": job_id,
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "status": "queued",
        "route_band": route_decision.get("route_band") or activity.get("route_band") or "deep_research",
        "progress_pct": int(activity.get("progress_pct") or 0),
        "current_stage": activity.get("current_stage") or "Queued",
        "current_message": activity.get("current_message") or "",
        "search_count": int(activity.get("search_count") or 0),
        "plan": list(activity.get("plan") or []),
        "events": list(activity.get("events") or []),
        "sources": list(activity.get("sources") or []),
        "artifacts": list(activity.get("artifacts") or []),
        "route_decision": dict(route_decision),
        "cancel_requested": False,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    with _LOCK:
        _JOBS[job_id] = job
        _save()
        return deepcopy(job)


def get_job(job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return None
        if user_id and job.get("user_id") != user_id:
            return None
        return deepcopy(job)


def update_job(
    job_id: str,
    *,
    user_id: str | None = None,
    status: str | None = None,
    progress_pct: int | None = None,
    current_stage: str | None = None,
    current_message: str | None = None,
    activity: dict[str, Any] | None = None,
    event: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return None
        if user_id and job.get("user_id") != user_id:
            return None
        if status:
            job["status"] = status
            if status in {"completed", "failed", "cancelled"}:
                job["completed_at"] = _now()
        if progress_pct is not None:
            job["progress_pct"] = max(0, min(100, int(progress_pct)))
        if current_stage is not None:
            job["current_stage"] = current_stage
        if current_message is not None:
            job["current_message"] = current_message
        if activity:
            for key in ("route_band", "current_stage", "current_message", "search_count"):
                if key in activity:
                    job[key] = activity[key]
            if "progress_pct" in activity:
                job["progress_pct"] = max(0, min(100, int(activity["progress_pct"])))
            for key in ("plan", "events", "sources", "artifacts"):
                if isinstance(activity.get(key), list):
                    job[key] = activity[key]
        if event:
            job.setdefault("events", []).append(event)
        if artifacts is not None:
            job["artifacts"] = artifacts
        job["updated_at"] = _now()
        _save()
        return deepcopy(job)


def cancel_job(job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            return None
        if user_id and job.get("user_id") != user_id:
            return None
        job["cancel_requested"] = True
        if job.get("status") in {"queued", "in_progress"}:
            job["status"] = "cancelled"
            job["current_stage"] = "Cancelled"
            job["current_message"] = "The research job was cancelled by the user."
            job["completed_at"] = _now()
        job["updated_at"] = _now()
        _save()
        return deepcopy(job)


def activity_from_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "route_band": job.get("route_band"),
        "progress_pct": job.get("progress_pct"),
        "current_stage": job.get("current_stage"),
        "current_message": job.get("current_message"),
        "search_count": job.get("search_count"),
        "query": job.get("query"),
        "plan": job.get("plan") or [],
        "events": job.get("events") or [],
        "sources": job.get("sources") or [],
        "artifacts": job.get("artifacts") or [],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> None:
    if _STORE_PATH is None or not _STORE_PATH.exists():
        return
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(raw, dict):
        _JOBS.clear()
        _JOBS.update({str(k): v for k, v in raw.items() if isinstance(v, dict)})


def _save() -> None:
    if _STORE_PATH is None:
        return
    try:
        _STORE_PATH.write_text(json.dumps(_JOBS, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass

