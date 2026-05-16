"""Research job state for plan/progress/activity UX.

This keeps a local file-backed store for offline/dev reliability and mirrors to
Supabase `research_jobs` when configured with a real authenticated user id.
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
        _persist_remote(job)
        return deepcopy(job)


def get_job(job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if job and (not user_id or job.get("user_id") == user_id):
            return deepcopy(job)
    remote = _fetch_remote(user_id, str(job_id)) if user_id else None
    if remote:
        with _LOCK:
            _JOBS[str(job_id)] = remote
            _save()
        return deepcopy(remote)
    return None


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
    remote_updates: dict[str, Any] = {}
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            remote = _fetch_remote(user_id, str(job_id)) if user_id else None
            if not remote:
                return None
            _JOBS[str(job_id)] = remote
            job = _JOBS[str(job_id)]
        if user_id and job.get("user_id") != user_id:
            return None
        if status:
            job["status"] = status
            remote_updates["status"] = status
            if status in {"completed", "failed", "cancelled"}:
                job["completed_at"] = _now()
                remote_updates["completed_at"] = job["completed_at"]
        if progress_pct is not None:
            job["progress_pct"] = max(0, min(100, int(progress_pct)))
            remote_updates["progress_pct"] = job["progress_pct"]
        if current_stage is not None:
            job["current_stage"] = current_stage
            remote_updates["current_stage"] = current_stage
        if current_message is not None:
            job["current_message"] = current_message
            remote_updates["current_message"] = current_message
        if activity:
            remote_updates["activity"] = activity
            for key in ("route_band", "current_stage", "current_message", "search_count"):
                if key in activity:
                    job[key] = activity[key]
            if "progress_pct" in activity:
                job["progress_pct"] = max(0, min(100, int(activity["progress_pct"])))
            for key in ("plan", "sources"):
                if isinstance(activity.get(key), list):
                    job[key] = activity[key]
            if isinstance(activity.get("artifacts"), list) and activity.get("artifacts"):
                job["artifacts"] = activity["artifacts"]
            if isinstance(activity.get("events"), list):
                existing = list(job.get("events") or [])
                incoming = list(activity.get("events") or [])
                job["events"] = _merge_events(existing, incoming)
        if event:
            job.setdefault("events", []).append(event)
            remote_updates["event"] = event
        if artifacts is not None:
            job["artifacts"] = artifacts
            remote_updates["artifacts"] = artifacts
        job["updated_at"] = _now()
        _save()
        _update_remote(job, remote_updates)
        return deepcopy(job)


def cancel_job(job_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        if not job:
            remote = _fetch_remote(user_id, str(job_id)) if user_id else None
            if not remote:
                return None
            _JOBS[str(job_id)] = remote
            job = _JOBS[str(job_id)]
        if user_id and job.get("user_id") != user_id:
            return None
        job["cancel_requested"] = True
        updates: dict[str, Any] = {"cancel_requested": True}
        if job.get("status") in {"queued", "in_progress"}:
            job["status"] = "cancelled"
            job["current_stage"] = "Cancelled"
            job["current_message"] = "The research job was cancelled by the user."
            job["completed_at"] = _now()
            updates.update(
                {
                    "status": job["status"],
                    "current_stage": job["current_stage"],
                    "current_message": job["current_message"],
                    "completed_at": job["completed_at"],
                }
            )
        job["updated_at"] = _now()
        _save()
        _update_remote(job, updates)
        return deepcopy(job)


def activity_from_job(job: dict[str, Any]) -> dict[str, Any]:
    status = job.get("status")
    return {
        "job_id": job.get("job_id"),
        "status": status,
        "final_response_available": status in {"completed", "failed", "cancelled"},
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


def list_jobs(
    user_id: str,
    *,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with _LOCK:
        rows = [
            deepcopy(job)
            for job in _JOBS.values()
            if job.get("user_id") == user_id
            and (not session_id or str(job.get("session_id")) == str(session_id))
        ]
    rows.extend(_list_remote(user_id, session_id=session_id, limit=limit))
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        jid = str(row.get("job_id") or "")
        if jid:
            dedup[jid] = row
    return sorted(
        dedup.values(),
        key=lambda j: str(j.get("updated_at") or j.get("created_at") or ""),
        reverse=True,
    )[: max(1, min(200, int(limit)))]


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


def _merge_events(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in [*existing, *incoming]:
        if not isinstance(event, dict):
            continue
        key = "|".join(
            str(event.get(part) or "")
            for part in ("type", "label", "detail", "loop", "ts")
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)
    return merged[-80:]


def _persist_remote(job: dict[str, Any]) -> None:
    try:
        import atlas_db

        atlas_db.insert_research_job(job)
    except Exception:
        pass


def _fetch_remote(user_id: str | None, job_id: str) -> dict[str, Any] | None:
    if not user_id:
        return None
    try:
        import atlas_db

        return atlas_db.fetch_research_job(user_id, job_id)
    except Exception:
        return None


def _update_remote(job: dict[str, Any], updates: dict[str, Any]) -> None:
    if not updates:
        return
    try:
        import atlas_db

        atlas_db.update_research_job(str(job.get("user_id") or ""), str(job.get("job_id") or ""), updates)
    except Exception:
        pass


def _list_remote(
    user_id: str,
    *,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    try:
        import atlas_db

        return atlas_db.list_research_jobs(user_id, session_id=session_id, limit=limit)
    except Exception:
        return []
