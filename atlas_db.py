"""
atlas_db.py — Supabase (PostgreSQL) helpers for multi-tenant ATLAS.

Environment:
    SUPABASE_URL  — Project URL (https://xxxx.supabase.co)
    SUPABASE_KEY  — Prefer service_role secret for FastAPI (server validates JWT,
                    then writes with full access). Anon key works only if RLS
                    policies allow per-user access matching auth.uid().

See schema.sql for tables: public.queries, public.chat_sessions, public.user_folders, public.positions, public.user_watchlist.
Auth users live in auth.users (Supabase-managed).

    ---------------------------------------------------------------------------
    -- PostgreSQL shape (also in schema.sql)
    ---------------------------------------------------------------------------
    public.queries
      id            UUID PRIMARY KEY  (client-supplied report id)
      user_id       UUID NOT NULL → auth.users(id)
      query_text    TEXT NOT NULL
      title         TEXT
      domain_tag    TEXT
      folder_name   TEXT
      session_id    UUID → chat_sessions(id) ON DELETE SET NULL
      result_json   JSONB NOT NULL
      created_at    TIMESTAMPTZ DEFAULT now()

    public.chat_sessions
      id, user_id → auth.users(id), title, archived_at, context_topic,
      updated_at, created_at

    public.user_folders
      user_id UUID REFERENCES auth.users(id)
      name    TEXT
      PRIMARY KEY (user_id, name)

    public.positions  (portfolio; CRUD via atlas_db + /positions)
      id, user_id, ticker, asset_type ('stock'|'option'),
      strike, option_type, expiry, avg_cost, quantity, created_at, updated_at
      Partial UNIQUE: (user_id,ticker) for stock; (user_id,ticker,strike,option_type) for option.

    public.user_watchlist
      user_id, ticker (PK composite)

    Legacy local auth.users note: There is no separate public.users table;
    tenant key is always auth.users.id from Supabase Auth.
    ---------------------------------------------------------------------------
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_QUERIES_TABLE = "queries"
_SESSIONS_TABLE = "chat_sessions"
_FOLDERS_TABLE = "user_folders"
_POSITIONS_TABLE = "positions"
_WATCHLIST_TABLE = "user_watchlist"
_RESEARCH_JOBS_TABLE = "research_jobs"
_USER_PREFS_TABLE = "user_preferences"
_MAX_REPORTS_PER_USER = 200

TEST_USER_LOCAL = "test_user_local"

# In-memory sessions when ATLAS_DISABLE_AUTH=test_user_local (no Supabase UUID)
_mock_chat_sessions: dict[str, list[dict[str, Any]]] = {}
_mock_user_preferences: dict[str, dict[str, Any]] = {}

_supabase_client: Any = None


def is_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL", "").strip() and os.environ.get("SUPABASE_KEY", "").strip())


def get_supabase_client():
    """
    Lazy singleton Supabase client. Returns None if env vars are missing.
    """
    global _supabase_client
    if not is_configured():
        return None
    if _supabase_client is None:
        try:
            from supabase import create_client

            url = os.environ["SUPABASE_URL"].strip()
            key = os.environ["SUPABASE_KEY"].strip()
            _supabase_client = create_client(url, key)
            log.info("Supabase client initialized")
        except Exception as e:
            log.error("Supabase init failed: %s", e)
            return None
    return _supabase_client


def supabase_schema_status() -> dict[str, Any]:
    """
    Read-only probes for Priority 0 migration objects (see schema.sql).
    Surfaced on GET /health when Supabase env vars are set.
    """
    status: dict[str, Any] = {
        "configured": is_configured(),
        "chat_sessions_reachable": None,
        "user_watchlist_reachable": None,
        "research_jobs_reachable": None,
        "user_preferences_reachable": None,
        "queries_has_session_id_column": None,
        "detail": None,
    }
    if not status["configured"]:
        return status
    client = get_supabase_client()
    if not client:
        status["detail"] = "supabase_client_unavailable"
        return status

    errs: list[str] = []

    try:
        client.table(_SESSIONS_TABLE).select("id").limit(1).execute()
        status["chat_sessions_reachable"] = True
    except Exception as e:
        status["chat_sessions_reachable"] = False
        errs.append(f"chat_sessions:{e!s}")

    try:
        client.table(_WATCHLIST_TABLE).select("user_id").limit(1).execute()
        status["user_watchlist_reachable"] = True
    except Exception as e:
        status["user_watchlist_reachable"] = False
        errs.append(f"user_watchlist:{e!s}")

    try:
        client.table(_QUERIES_TABLE).select("session_id").limit(1).execute()
        status["queries_has_session_id_column"] = True
    except Exception as e:
        status["queries_has_session_id_column"] = False
        errs.append(f"queries.session_id:{e!s}")

    try:
        client.table(_RESEARCH_JOBS_TABLE).select("id").limit(1).execute()
        status["research_jobs_reachable"] = True
    except Exception as e:
        status["research_jobs_reachable"] = False
        errs.append(f"research_jobs:{e!s}")

    try:
        client.table(_USER_PREFS_TABLE).select("user_id").limit(1).execute()
        status["user_preferences_reachable"] = True
    except Exception as e:
        status["user_preferences_reachable"] = False
        errs.append(f"user_preferences:{e!s}")

    if errs:
        status["detail"] = "; ".join(errs)[:800]
    return status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_uuidish(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _research_job_row_api(r: dict[str, Any]) -> dict[str, Any]:
    def ts(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, str):
            return val
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return {
        "job_id": str(r.get("id") or r.get("job_id") or ""),
        "user_id": str(r.get("user_id") or ""),
        "session_id": str(r.get("session_id")) if r.get("session_id") else None,
        "query": r.get("query") or "",
        "status": r.get("status") or "queued",
        "route_band": r.get("route_band") or "deep_research",
        "progress_pct": int(r.get("progress_pct") or 0),
        "current_stage": r.get("current_stage"),
        "current_message": r.get("current_message"),
        "search_count": int(r.get("search_count") or 0),
        "plan": r.get("plan_json") or r.get("plan") or [],
        "events": r.get("events_json") or r.get("events") or [],
        "sources": r.get("sources_json") or r.get("sources") or [],
        "artifacts": r.get("artifacts_json") or r.get("artifacts") or [],
        "route_decision": r.get("route_decision") or {},
        "cancel_requested": bool(r.get("cancel_requested")),
        "created_at": ts(r.get("created_at")),
        "updated_at": ts(r.get("updated_at")),
        "completed_at": ts(r.get("completed_at")),
    }


def _research_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": job.get("job_id") or job.get("id"),
        "user_id": job.get("user_id"),
        "query": job.get("query") or "",
        "status": job.get("status") or "queued",
        "route_band": job.get("route_band") or "deep_research",
        "progress_pct": max(0, min(100, int(job.get("progress_pct") or 0))),
        "current_stage": job.get("current_stage"),
        "current_message": job.get("current_message"),
        "search_count": int(job.get("search_count") or 0),
        "plan_json": job.get("plan") or [],
        "events_json": job.get("events") or [],
        "sources_json": job.get("sources") or [],
        "artifacts_json": job.get("artifacts") or [],
        "route_decision": job.get("route_decision") or {},
        "cancel_requested": bool(job.get("cancel_requested")),
        "updated_at": _now_iso(),
    }
    if job.get("session_id") and _is_uuidish(str(job.get("session_id"))):
        payload["session_id"] = str(job.get("session_id"))
    if job.get("completed_at"):
        payload["completed_at"] = job.get("completed_at")
    if job.get("created_at"):
        payload["created_at"] = job.get("created_at")
    return payload


_DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "display_name": "",
    "default_research_mode": "normal",
    "answer_style": "balanced",
    "risk_profile": "balanced",
    "market_focus": "US equities",
    "source_strictness": "balanced",
    "memory_enabled": True,
    "notifications_enabled": False,
    "accent_color": "blue",
    "subscription_tier": "free",
    "subscription_status": "active",
    "stripe_customer_id": "",
    "current_period_end": None,
    "extra_json": {},
}


def _clean_user_preferences(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(_DEFAULT_USER_PREFERENCES)
    if raw:
        out.update({k: v for k, v in raw.items() if k in out})
    out["display_name"] = str(out.get("display_name") or "").strip()[:120]
    if out.get("default_research_mode") not in {"normal", "web", "deep"}:
        out["default_research_mode"] = "normal"
    for key, max_len in {
        "answer_style": 40,
        "risk_profile": 40,
        "market_focus": 80,
        "source_strictness": 40,
        "accent_color": 40,
        "subscription_tier": 40,
        "subscription_status": 40,
        "stripe_customer_id": 120,
    }.items():
        out[key] = str(out.get(key) or _DEFAULT_USER_PREFERENCES[key]).strip()[:max_len]
    out["memory_enabled"] = bool(out.get("memory_enabled"))
    out["notifications_enabled"] = bool(out.get("notifications_enabled"))
    if not isinstance(out.get("extra_json"), dict):
        out["extra_json"] = {}
    return out


def _session_row_api(r: dict[str, Any]) -> dict[str, Any]:
    def ts(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, str):
            return val
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)

    return {
        "id": str(r.get("id", "")),
        "title": r.get("title"),
        "archived_at": ts(r.get("archived_at")),
        "context_topic": r.get("context_topic"),
        "updated_at": ts(r.get("updated_at")),
        "created_at": ts(r.get("created_at")),
    }


def create_chat_session(user_id: str, title: Optional[str] = None) -> dict[str, Any]:
    t = (title or "New chat").strip() or "New chat"
    if user_id == TEST_USER_LOCAL:
        sid = str(uuid.uuid4())
        now = _now_iso()
        row: dict[str, Any] = {
            "id": sid,
            "user_id": user_id,
            "title": t,
            "archived_at": None,
            "context_topic": None,
            "updated_at": now,
            "created_at": now,
        }
        _mock_chat_sessions.setdefault(user_id, []).insert(0, row)
        return _session_row_api(row)
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    resp = client.table(_SESSIONS_TABLE).insert({"user_id": user_id, "title": t}).execute()
    if not resp.data:
        raise RuntimeError("chat_sessions insert failed")
    return _session_row_api(resp.data[0])


def list_chat_sessions(user_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
    if user_id == TEST_USER_LOCAL:
        rows = list(_mock_chat_sessions.get(user_id, []))
        if not include_archived:
            rows = [r for r in rows if not r.get("archived_at")]
        return [_session_row_api(r) for r in rows]
    client = get_supabase_client()
    if not client:
        return []
    resp = (
        client.table(_SESSIONS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    rows = resp.data or []
    if not include_archived:
        rows = [r for r in rows if r.get("archived_at") in (None,)]
    return [_session_row_api(r) for r in rows]


def update_chat_session(
    user_id: str,
    session_id: str,
    *,
    title: Optional[str] = None,
    archived: Optional[bool] = None,
    context_topic: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if user_id == TEST_USER_LOCAL:
        for row in _mock_chat_sessions.get(user_id, []):
            if str(row.get("id")) != str(session_id):
                continue
            if title is not None:
                row["title"] = title.strip() or "New chat"
            if archived is True:
                row["archived_at"] = _now_iso()
            elif archived is False:
                row["archived_at"] = None
            if context_topic is not None:
                row["context_topic"] = context_topic.strip() or None
            row["updated_at"] = _now_iso()
            return _session_row_api(row)
        return None
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title.strip() or None
    if archived is True:
        updates["archived_at"] = datetime.now(timezone.utc).isoformat()
    elif archived is False:
        updates["archived_at"] = None
    if context_topic is not None:
        updates["context_topic"] = context_topic.strip() or None
    if not updates:
        row = (
            client.table(_SESSIONS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("id", session_id)
            .limit(1)
            .execute()
        )
        return _session_row_api(row.data[0]) if row.data else None
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.table(_SESSIONS_TABLE).update(updates).eq("user_id", user_id).eq("id", session_id).execute()
    row = (
        client.table(_SESSIONS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if row.data:
        return _session_row_api(row.data[0])
    return None


def touch_chat_session_topic(user_id: str, session_id: str, context_topic: str) -> None:
    ctx = (context_topic or "").strip()
    if not session_id or not ctx:
        return
    try:
        update_chat_session(user_id, session_id, context_topic=ctx[:500])
    except Exception as e:
        log.debug("[atlas_db] touch_chat_session_topic: %s", e)


def delete_chat_session(user_id: str, session_id: str) -> bool:
    if user_id == TEST_USER_LOCAL:
        lst = _mock_chat_sessions.get(user_id, [])
        for i, row in enumerate(lst):
            if str(row.get("id")) == str(session_id):
                lst.pop(i)
                return True
        return False
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    sel = (
        client.table(_SESSIONS_TABLE)
        .select("id")
        .eq("user_id", user_id)
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not sel.data:
        return False
    client.table(_SESSIONS_TABLE).delete().eq("user_id", user_id).eq("id", session_id).execute()
    return True


def get_user_preferences(user_id: str) -> dict[str, Any]:
    if user_id == TEST_USER_LOCAL or not _is_uuidish(user_id):
        stored = _mock_user_preferences.get(user_id)
        return {"user_id": user_id, **_clean_user_preferences(stored)}
    client = get_supabase_client()
    if not client:
        return {"user_id": user_id, **_clean_user_preferences(None)}
    resp = (
        client.table(_USER_PREFS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {"user_id": user_id, **_clean_user_preferences(None)}
    cleaned = _clean_user_preferences(rows[0])
    return {
        "user_id": user_id,
        **cleaned,
        "created_at": rows[0].get("created_at"),
        "updated_at": rows[0].get("updated_at"),
    }


def count_queries_today(user_id: str) -> int:
    """Count persisted query reports for the current UTC day."""
    if user_id == TEST_USER_LOCAL or not _is_uuidish(user_id):
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            1
            for row in _mock_query_reports.get(user_id, [])
            if str(row.get("created_at") or "").startswith(today)
        )
    client = get_supabase_client()
    if not client:
        return 0
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        resp = (
            client.table(_QUERIES_TABLE)
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        return int(getattr(resp, "count", None) or len(resp.data or []))
    except Exception as e:
        log.warning("[atlas_db] count_queries_today: %s", e)
        return 0


def update_user_preferences(user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    cleaned = _clean_user_preferences(updates)
    if user_id == TEST_USER_LOCAL or not _is_uuidish(user_id):
        existing = _mock_user_preferences.get(user_id, {})
        merged = _clean_user_preferences({**existing, **cleaned})
        merged["updated_at"] = _now_iso()
        _mock_user_preferences[user_id] = merged
        return {"user_id": user_id, **merged}
    client = get_supabase_client()
    if not client:
        return {"user_id": user_id, **cleaned}
    payload = {**cleaned, "user_id": user_id, "updated_at": _now_iso()}
    client.table(_USER_PREFS_TABLE).upsert(payload, on_conflict="user_id").execute()
    return get_user_preferences(user_id)


def insert_research_job(job: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Persist a research job to Supabase when tenant ids are real UUIDs."""
    user_id = str(job.get("user_id") or "")
    if not _is_uuidish(user_id):
        return None
    client = get_supabase_client()
    if not client:
        return None
    payload = _research_job_payload(job)
    client.table(_RESEARCH_JOBS_TABLE).upsert(payload, on_conflict="id").execute()
    return fetch_research_job(user_id, str(payload["id"]))


def fetch_research_job(user_id: str, job_id: str) -> Optional[dict[str, Any]]:
    if not (_is_uuidish(user_id) and job_id):
        return None
    client = get_supabase_client()
    if not client:
        return None
    resp = (
        client.table(_RESEARCH_JOBS_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _research_job_row_api(rows[0]) if rows else None


def update_research_job(
    user_id: str,
    job_id: str,
    updates: dict[str, Any],
) -> Optional[dict[str, Any]]:
    if not (_is_uuidish(user_id) and job_id):
        return None
    client = get_supabase_client()
    if not client:
        return None
    payload: dict[str, Any] = {"updated_at": _now_iso()}
    field_map = {
        "status": "status",
        "route_band": "route_band",
        "progress_pct": "progress_pct",
        "current_stage": "current_stage",
        "current_message": "current_message",
        "search_count": "search_count",
        "cancel_requested": "cancel_requested",
        "completed_at": "completed_at",
    }
    for src, dst in field_map.items():
        if src in updates:
            payload[dst] = updates[src]
    json_map = {
        "plan": "plan_json",
        "events": "events_json",
        "sources": "sources_json",
        "artifacts": "artifacts_json",
        "route_decision": "route_decision",
    }
    for src, dst in json_map.items():
        if src in updates:
            payload[dst] = updates[src]
    if "activity" in updates and isinstance(updates["activity"], dict):
        activity = updates["activity"]
        for src, dst in {
            "route_band": "route_band",
            "progress_pct": "progress_pct",
            "current_stage": "current_stage",
            "current_message": "current_message",
            "search_count": "search_count",
            "plan": "plan_json",
            "events": "events_json",
            "sources": "sources_json",
        }.items():
            if src in activity:
                payload[dst] = activity[src]
        if isinstance(activity.get("artifacts"), list) and activity.get("artifacts"):
            payload["artifacts_json"] = activity["artifacts"]
        if isinstance(activity.get("events"), list):
            existing = fetch_research_job(user_id, job_id)
            existing_events = list((existing or {}).get("events") or [])
            merged: list[dict[str, Any]] = []
            seen: set[str] = set()
            for event in [*existing_events, *list(activity.get("events") or [])]:
                if not isinstance(event, dict):
                    continue
                key = "|".join(str(event.get(k) or "") for k in ("type", "label", "detail", "loop", "ts"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(event)
            payload["events_json"] = merged[-80:]
    if "event" in updates and isinstance(updates["event"], dict):
        existing = fetch_research_job(user_id, job_id)
        if existing:
            payload["events_json"] = list(existing.get("events") or []) + [updates["event"]]
    if "progress_pct" in payload:
        payload["progress_pct"] = max(0, min(100, int(payload["progress_pct"] or 0)))
    client.table(_RESEARCH_JOBS_TABLE).update(payload).eq("user_id", user_id).eq("id", job_id).execute()
    return fetch_research_job(user_id, job_id)


def list_research_jobs(
    user_id: str,
    *,
    session_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not _is_uuidish(user_id):
        return []
    client = get_supabase_client()
    if not client:
        return []
    qb = client.table(_RESEARCH_JOBS_TABLE).select("*").eq("user_id", user_id)
    if session_id and _is_uuidish(session_id):
        qb = qb.eq("session_id", session_id)
    resp = qb.order("updated_at", desc=True).limit(max(1, min(200, int(limit)))).execute()
    return [_research_job_row_api(r) for r in (resp.data or [])]


def insert_research_query(
    user_id: str,
    report_id: str,
    query_text: str,
    result_json: dict[str, Any],
    domain_tag: Optional[str] = None,
    title: Optional[str] = None,
    folder_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    payload: dict[str, Any] = {
        "id": report_id,
        "user_id": user_id,
        "query_text": query_text,
        "result_json": result_json,
        "domain_tag": domain_tag,
        "title": title,
        "folder_name": folder_name,
    }
    if session_id:
        payload["session_id"] = session_id
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    client.table(_QUERIES_TABLE).insert(payload).execute()
    trim_queries_for_user(user_id, _MAX_REPORTS_PER_USER)


def trim_queries_for_user(user_id: str, keep: int = _MAX_REPORTS_PER_USER) -> None:
    """Delete oldest rows beyond `keep` for this user (by created_at desc)."""
    client = get_supabase_client()
    if not client:
        return
    try:
        resp = (
            client.table(_QUERIES_TABLE)
            .select("id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = resp.data or []
        if len(rows) <= keep:
            return
        for row in rows[keep:]:
            rid = row.get("id")
            if rid:
                client.table(_QUERIES_TABLE).delete().eq("id", rid).eq("user_id", user_id).execute()
    except Exception as e:
        log.warning("[atlas_db] trim_queries_for_user: %s", e)


def list_research_queries(
    user_id: str,
    limit: int = _MAX_REPORTS_PER_USER,
    session_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    client = get_supabase_client()
    if not client:
        return []
    qb = (
        client.table(_QUERIES_TABLE)
        .select("*")
        .eq("user_id", user_id)
    )
    if session_id:
        qb = qb.eq("session_id", session_id)
    resp = qb.order("created_at", desc=True).limit(limit).execute()
    return [_row_to_dashboard(r) for r in (resp.data or [])]


def delete_all_research_queries(user_id: str) -> None:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    client.table(_QUERIES_TABLE).delete().eq("user_id", user_id).execute()


def delete_research_query(user_id: str, report_id: str) -> bool:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    sel = (
        client.table(_QUERIES_TABLE)
        .select("id")
        .eq("user_id", user_id)
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if not (sel.data and len(sel.data)):
        return False
    client.table(_QUERIES_TABLE).delete().eq("user_id", user_id).eq("id", report_id).execute()
    return True


def list_folder_names_for_user(user_id: str) -> list[str]:
    client = get_supabase_client()
    if not client:
        return []
    names: set[str] = set()
    try:
        q = client.table(_QUERIES_TABLE).select("folder_name").eq("user_id", user_id).execute()
        for row in q.data or []:
            fn = row.get("folder_name")
            if fn is not None and isinstance(fn, str) and fn.strip():
                names.add(fn.strip())
    except Exception as e:
        log.warning("[atlas_db] list folders from queries: %s", e)
    try:
        f = (
            client.table(_FOLDERS_TABLE)
            .select("name")
            .eq("user_id", user_id)
            .execute()
        )
        for row in f.data or []:
            n = row.get("name")
            if isinstance(n, str) and n.strip():
                names.add(n.strip())
    except Exception as e:
        log.warning("[atlas_db] list folders from user_folders: %s", e)
    return sorted(names, key=str.lower)


def ensure_user_folder(user_id: str, name: str) -> list[str]:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    client.table(_FOLDERS_TABLE).upsert(
        {"user_id": user_id, "name": name},
        on_conflict="user_id,name",
    ).execute()
    return list_folder_names_for_user(user_id)


def fetch_research_query_row(user_id: str, report_id: str) -> Optional[dict[str, Any]]:
    """Return one raw queries row (incl. result_json) or None."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    resp = (
        client.table(_QUERIES_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def update_research_query_result_json(
    user_id: str, report_id: str, result_json: dict[str, Any]
) -> bool:
    """Replace result_json for a saved report. Returns False if row missing."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    sel = (
        client.table(_QUERIES_TABLE)
        .select("id")
        .eq("user_id", user_id)
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if not sel.data:
        return False
    client.table(_QUERIES_TABLE).update({"result_json": result_json}).eq(
        "user_id", user_id
    ).eq("id", report_id).execute()
    return True


def update_research_query(
    user_id: str,
    report_id: str,
    title: Optional[str] = None,
    folder_name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title.strip() or None
    if folder_name is not None:
        updates["folder_name"] = folder_name.strip() or None
    if not updates:
        row = (
            client.table(_QUERIES_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("id", report_id)
            .limit(1)
            .execute()
        )
        if row.data:
            return _row_to_dashboard(row.data[0])
        return None
    client.table(_QUERIES_TABLE).update(updates).eq("user_id", user_id).eq("id", report_id).execute()
    row = (
        client.table(_QUERIES_TABLE)
        .select("*")
        .eq("user_id", user_id)
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    if row.data:
        r0 = row.data[0]
        fn = updates.get("folder_name")
        if isinstance(fn, str) and fn.strip():
            try:
                ensure_user_folder(user_id, fn.strip())
            except Exception as e:
                log.warning("[atlas_db] ensure_user_folder after patch: %s", e)
        return _row_to_dashboard(r0)
    return None


def _row_to_dashboard(r: dict[str, Any]) -> dict[str, Any]:
    """Match atlas_dashboard_v4 localStorage /history shape."""
    ts = r.get("created_at")
    sid = r.get("session_id")
    return {
        "id": str(r.get("id", "")),
        "ts": ts if isinstance(ts, str) else (ts.isoformat() if ts is not None and hasattr(ts, "isoformat") else str(ts)),
        "query": r.get("query_text") or "",
        "title": r.get("title"),
        "domain_tag": r.get("domain_tag"),
        "folder_name": r.get("folder_name"),
        "session_id": str(sid) if sid else None,
        "result": r.get("result_json") if isinstance(r.get("result_json"), dict) else {},
    }


def _coerce_ts_iso(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _coerce_expiry_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val[:10] if len(val) >= 10 else val
    if hasattr(val, "isoformat"):
        return val.isoformat()[:10]
    return str(val)[:10]


def _row_to_api_stock(r: dict[str, Any]) -> dict[str, Any]:
    """Shape one DB row as positions_cache.json stock entry."""
    return {
        "ticker": r.get("ticker") or "",
        "shares": float(r.get("quantity") or 0),
        "avg_buy_price": r.get("avg_cost"),
        "current_price": None,
        "last_updated": _coerce_ts_iso(r.get("updated_at") or r.get("created_at")),
    }


def _row_to_api_option(r: dict[str, Any]) -> dict[str, Any]:
    """Shape one DB row as positions_cache.json option entry."""
    strike = r.get("strike")
    try:
        strike_f = float(strike) if strike is not None else None
    except (TypeError, ValueError):
        strike_f = None
    qty = r.get("quantity")
    try:
        contracts = int(float(qty)) if qty is not None else 0
    except (TypeError, ValueError):
        contracts = 0
    return {
        "ticker": r.get("ticker") or "",
        "option_type": str(r.get("option_type") or "").lower(),
        "strike": strike_f,
        "expiry": _coerce_expiry_str(r.get("expiry")),
        "contracts": contracts,
        "avg_premium": r.get("avg_cost"),
        "current_price": None,
        "last_updated": _coerce_ts_iso(r.get("updated_at") or r.get("created_at")),
    }


def fetch_positions_cache_shapes(user_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Return (stocks, options) lists in the same shape as legacy positions_cache.json / GET /positions.
    """
    client = get_supabase_client()
    if not client:
        return [], []
    try:
        resp = (
            client.table(_POSITIONS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as e:
        log.warning("[atlas_db] fetch positions: %s", e)
        return [], []
    stocks: list[dict[str, Any]] = []
    options: list[dict[str, Any]] = []
    for r in resp.data or []:
        if not isinstance(r, dict):
            continue
        at = str(r.get("asset_type") or "").lower()
        if at == "stock":
            stocks.append(_row_to_api_stock(r))
        elif at == "option":
            options.append(_row_to_api_option(r))
    return stocks, options


def replace_stock_position(
    user_id: str,
    ticker: str,
    shares: float,
    avg_buy_price: Optional[float],
) -> None:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    ticker = ticker.upper().strip()
    (
        client.table(_POSITIONS_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("ticker", ticker)
        .eq("asset_type", "stock")
        .execute()
    )
    payload = {
        "user_id": user_id,
        "ticker": ticker,
        "asset_type": "stock",
        "strike": None,
        "option_type": None,
        "expiry": None,
        "avg_cost": avg_buy_price,
        "quantity": shares,
    }
    client.table(_POSITIONS_TABLE).insert(payload).execute()


def replace_option_position(
    user_id: str,
    ticker: str,
    option_type: str,
    strike: float,
    expiry_yyyy_mm_dd: str,
    contracts: int,
    avg_premium: Optional[float],
) -> None:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    ticker = ticker.upper().strip()
    ot = option_type.lower().strip()
    (
        client.table(_POSITIONS_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("ticker", ticker)
        .eq("asset_type", "option")
        .eq("strike", strike)
        .eq("option_type", ot)
        .execute()
    )
    payload = {
        "user_id": user_id,
        "ticker": ticker,
        "asset_type": "option",
        "strike": strike,
        "option_type": ot,
        "expiry": expiry_yyyy_mm_dd[:10],
        "avg_cost": avg_premium,
        "quantity": float(contracts),
    }
    client.table(_POSITIONS_TABLE).insert(payload).execute()


def delete_positions_for_ticker(user_id: str, ticker: str) -> None:
    """Remove all stock and option rows for this ticker."""
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    ticker = ticker.upper().strip()
    client.table(_POSITIONS_TABLE).delete().eq("user_id", user_id).eq("ticker", ticker).execute()


def delete_option_leg(user_id: str, ticker: str, strike: float, option_type: str) -> None:
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    ticker = ticker.upper().strip()
    ot = option_type.lower().strip()
    (
        client.table(_POSITIONS_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("ticker", ticker)
        .eq("asset_type", "option")
        .eq("strike", strike)
        .eq("option_type", ot)
        .execute()
    )


def list_watchlist_tickers(user_id: str) -> list[str]:
    if user_id == TEST_USER_LOCAL:
        return []
    client = get_supabase_client()
    if not client:
        return []
    try:
        resp = (
            client.table(_WATCHLIST_TABLE)
            .select("ticker")
            .eq("user_id", user_id)
            .order("ticker")
            .execute()
        )
        out: list[str] = []
        for row in resp.data or []:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(str(row["ticker"]).upper().strip())
        return out
    except Exception as e:
        log.warning("[atlas_db] list_watchlist_tickers: %s", e)
        return []


def add_watchlist_ticker(user_id: str, ticker: str) -> None:
    if user_id == TEST_USER_LOCAL:
        return
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    t = ticker.upper().strip()
    if not t:
        return
    client.table(_WATCHLIST_TABLE).upsert(
        {"user_id": user_id, "ticker": t},
        on_conflict="user_id,ticker",
    ).execute()


def remove_watchlist_ticker(user_id: str, ticker: str) -> None:
    if user_id == TEST_USER_LOCAL:
        return
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase is not configured")
    t = ticker.upper().strip()
    (
        client.table(_WATCHLIST_TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("ticker", t)
        .execute()
    )
