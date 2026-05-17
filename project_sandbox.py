"""
project_sandbox.py — R.A. Omega Project Sandbox

Creates a lightweight named workspace folder for every complex query.
Each sandbox captures: query text, agent plan, raw API response, and
the final report — giving a full audit trail per analysis run.

Usage:
    from project_sandbox import create_sandbox, get_sandbox, list_sandboxes
    sb = create_sandbox(query="Analyze NVDA", user_id="abc123", plan=plan_dict)
    sb = attach_result(sb["sandbox_id"], result_dict)
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
SANDBOX_ROOT = BASE_DIR / "atlas_vault" / "03-Outputs" / "Sandboxes"
SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

_MAX_SANDBOXES_PER_USER = 50


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    """Turn a query into a short filesystem-safe slug."""
    clean = re.sub(r"[^a-z0-9 ]", "", text.lower())
    words = clean.split()[:5]
    return "-".join(words) if words else "query"


def _sandbox_dir(sandbox_id: str) -> Path:
    return SANDBOX_ROOT / sandbox_id


def _meta_path(sandbox_id: str) -> Path:
    return _sandbox_dir(sandbox_id) / "sandbox.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core API ──────────────────────────────────────────────────────────────────

def create_sandbox(
    query: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    intent: str = "GENERAL_FINANCE",
    research_mode: str = "normal",
    plan: Optional[dict] = None,
) -> dict:
    """
    Create a new sandbox workspace for a query.

    Returns the sandbox metadata dict (also written to disk).
    """
    sandbox_id = str(uuid.uuid4())[:8]
    slug = _slug(query)
    ts = _now_iso()
    date_prefix = ts[:10]  # YYYY-MM-DD

    meta = {
        "sandbox_id": sandbox_id,
        "name": f"{date_prefix}-{slug}",
        "query": query,
        "user_id": user_id,
        "session_id": session_id,
        "intent": intent,
        "research_mode": research_mode,
        "status": "running",
        "created_at": ts,
        "updated_at": ts,
        "plan": plan or {},
        "result_summary": None,
        "files": [],
    }

    sb_dir = _sandbox_dir(sandbox_id)
    sb_dir.mkdir(parents=True, exist_ok=True)

    # Write meta
    _meta_path(sandbox_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Write query file
    (sb_dir / "query.txt").write_text(query, encoding="utf-8")

    # Write plan if present
    if plan:
        (sb_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        meta["files"].append("plan.json")

    _prune_old_sandboxes(user_id)
    return meta


def attach_result(sandbox_id: str, result: dict) -> dict:
    """
    Attach the final API response to a sandbox.
    Writes result.json and a human-readable summary.md.
    Returns the updated sandbox metadata.
    """
    meta = get_sandbox(sandbox_id)
    if not meta:
        return {}

    sb_dir = _sandbox_dir(sandbox_id)
    ts = _now_iso()

    # Write full result
    (sb_dir / "result.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )

    # Build a short summary
    fr = result.get("final_report") or {}
    tldr = result.get("tldr") or fr.get("tldr") or fr.get("primary_recommendation") or ""
    exec_sum = fr.get("executive_summary") or fr.get("executive_brief") or ""
    intent = (result.get("parsed_query") or {}).get("intent_route", meta.get("intent", ""))
    output_mode = result.get("_output_mode", "")
    agent_count = (result.get("_pipeline_plan") or {}).get("agent_count", 0)

    summary_lines = [
        f"# {meta['name']}",
        f"**Query:** {meta['query']}",
        f"**Intent:** {intent}  |  **Mode:** {output_mode}  |  **Agents:** {agent_count}",
        f"**Created:** {meta['created_at'][:19]}Z",
        "",
        "## Bottom Line",
        tldr or "(no tldr)",
        "",
        "## Executive Summary",
        exec_sum[:800] if exec_sum else "(no executive summary)",
    ]

    (sb_dir / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    # Update meta
    meta.update({
        "status": "complete",
        "updated_at": ts,
        "result_summary": tldr[:200] if tldr else exec_sum[:200],
        "intent": intent or meta["intent"],
        "output_mode": output_mode,
        "agent_count": agent_count,
        "files": ["query.txt", "plan.json", "result.json", "summary.md"],
    })
    _meta_path(sandbox_id).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def get_sandbox(sandbox_id: str) -> Optional[dict]:
    """Return sandbox metadata dict, or None if not found."""
    p = _meta_path(sandbox_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_sandboxes(
    user_id: Optional[str] = None,
    limit: int = 20,
    session_id: Optional[str] = None,
) -> list[dict]:
    """
    Return sandboxes sorted by created_at descending.
    Filtered by user_id and/or session_id when provided.
    """
    results = []
    for sb_dir in SANDBOX_ROOT.iterdir():
        if not sb_dir.is_dir():
            continue
        meta_file = sb_dir / "sandbox.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if user_id and meta.get("user_id") != user_id:
            continue
        if session_id and meta.get("session_id") != session_id:
            continue
        results.append(meta)

    results.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return results[:limit]


def delete_sandbox(sandbox_id: str) -> bool:
    """Delete a sandbox folder. Returns True if deleted."""
    sb_dir = _sandbox_dir(sandbox_id)
    if not sb_dir.exists():
        return False
    import shutil
    shutil.rmtree(sb_dir)
    return True


# ── Pruning ───────────────────────────────────────────────────────────────────

def _prune_old_sandboxes(user_id: Optional[str]) -> None:
    """Keep at most _MAX_SANDBOXES_PER_USER per user; delete oldest first."""
    if not user_id:
        return
    user_sandboxes = list_sandboxes(user_id=user_id, limit=1000)
    excess = len(user_sandboxes) - _MAX_SANDBOXES_PER_USER
    if excess > 0:
        for old in user_sandboxes[-excess:]:
            delete_sandbox(old["sandbox_id"])
