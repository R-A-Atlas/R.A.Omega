"""
omega_agentic_os.py — Registry and loader for Agentic OS workers.

Provides safe, progressive-disclosure access to the five worker agents in
omega_agents/. Mirrors the progressive-disclosure pattern from omega_skill_registry.py.

Level 1: list_agentic_workers()         — name + description (always fast)
Level 2: load_worker_info(worker)       — information/ markdown files
Level 3: get_worker_status(worker)      — structure validation + availability
Level 4: run_worker_stub(worker)        — execute safe local stub

All functions degrade gracefully. No external APIs. No credentials required.
"""
from __future__ import annotations

import logging
import runpy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_ROOT = Path(__file__).parent
_AGENTS_DIR = _ROOT / "omega_agents"

_REQUIRED_INFO_FILES: tuple[str, ...] = (
    "instructions.md",
    "memory.md",
    "past_errors.md",
    "plan.md",
    "safety_rules.md",
)

# Canonical worker list with stable ordering
_WORKER_DESCRIPTIONS: dict[str, str] = {
    "daily_build_brief":    "Daily engineering summary from DONE files + git state",
    "visual_qa_agent":      "Visual QA checklist from UI file scan and manual test guide",
    "report_qa_agent":      "Deterministic QA checks on canonical sample outputs (BlackRock, TSLA, apple pie)",
    "growth_content_agent": "Content ideas and post drafts from project progress state",
    "supabase_health_agent": "Local DB and /health endpoint health check report",
}

_WORKER_SKILLS: dict[str, list[str]] = {
    "daily_build_brief":    ["improve_system"],
    "visual_qa_agent":      ["visual_qa"],
    "report_qa_agent":      ["company_report", "trade_plan", "general_chat", "source_verification", "improve_system"],
    "growth_content_agent": [],
    "supabase_health_agent": ["source_verification", "improve_system"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _worker_dir(worker_name: str) -> Path:
    return _AGENTS_DIR / worker_name


def _info_dir(worker_name: str) -> Path:
    return _worker_dir(worker_name) / "information"


def _impl_dir(worker_name: str) -> Path:
    return _worker_dir(worker_name) / "implementation"


def _find_stub(worker_name: str) -> Path | None:
    """Find the run_*.py stub in implementation/. Returns None if missing."""
    impl = _impl_dir(worker_name)
    if not impl.is_dir():
        return None
    stubs = sorted(impl.glob("run_*.py"))
    return stubs[0] if stubs else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Level 1 — fast listing
# ---------------------------------------------------------------------------

def list_agentic_workers() -> list[dict[str, Any]]:
    """
    Return name + description + available flag for every installed worker.

    Always returns exactly the 5 canonical workers; marks unavailable if the
    directory is missing.
    """
    result: list[dict[str, Any]] = []
    for name, description in _WORKER_DESCRIPTIONS.items():
        wdir = _worker_dir(name)
        available = wdir.is_dir() and _find_stub(name) is not None
        result.append({
            "name":        name,
            "description": description,
            "skills":      _WORKER_SKILLS.get(name, []),
            "available":   available,
        })
    return result


# ---------------------------------------------------------------------------
# Level 2 — worker information files
# ---------------------------------------------------------------------------

def load_worker_info(worker_name: str) -> dict[str, str]:
    """
    Load all information/ markdown files for a worker.

    Returns dict of {filename: content}. Missing files return empty strings.
    Unknown workers return empty dict.
    """
    info_dir = _info_dir(worker_name)
    if not info_dir.is_dir():
        return {}
    result: dict[str, str] = {}
    for fname in _REQUIRED_INFO_FILES:
        fpath = info_dir / fname
        if fpath.exists():
            try:
                result[fname] = fpath.read_text(encoding="utf-8")
            except Exception as exc:
                log.debug("load_worker_info: could not read %s — %s", fpath, exc)
                result[fname] = ""
        else:
            result[fname] = ""
    return result


# ---------------------------------------------------------------------------
# Level 3 — structure validation and status
# ---------------------------------------------------------------------------

def validate_worker_structure(worker_name: str) -> dict[str, Any]:
    """
    Validate that a worker has all required files.

    Returns {"valid": bool, "errors": list[str], "worker_name": str}.
    """
    errors: list[str] = []

    wdir = _worker_dir(worker_name)
    if not wdir.is_dir():
        return {"valid": False, "errors": [f"Worker directory not found: {worker_name}"], "worker_name": worker_name}

    info_dir = _info_dir(worker_name)
    if not info_dir.is_dir():
        errors.append("Missing information/ directory")
    else:
        for fname in _REQUIRED_INFO_FILES:
            if not (info_dir / fname).exists():
                errors.append(f"Missing information/{fname}")

    impl_dir = _impl_dir(worker_name)
    if not impl_dir.is_dir():
        errors.append("Missing implementation/ directory")
    else:
        stub = _find_stub(worker_name)
        if stub is None:
            errors.append("Missing implementation/run_*.py stub")

    return {
        "valid":       len(errors) == 0,
        "errors":      errors,
        "worker_name": worker_name,
    }


def get_worker_status(worker_name: str) -> dict[str, Any]:
    """
    Return availability and structure status for a worker.

    Returns a dict suitable for dashboard display. Degrades gracefully.
    """
    validation = validate_worker_structure(worker_name)
    stub = _find_stub(worker_name)

    return {
        "worker_name":  worker_name,
        "available":    validation["valid"],
        "valid":        validation["valid"],
        "errors":       validation["errors"],
        "description":  _WORKER_DESCRIPTIONS.get(worker_name, ""),
        "skills":       _WORKER_SKILLS.get(worker_name, []),
        "stub_path":    str(stub) if stub else None,
        "hosting":      "local",
        "hosting_status": "planned",
    }


# ---------------------------------------------------------------------------
# Level 4 — run safe local stub
# ---------------------------------------------------------------------------

def run_worker_stub(worker_name: str, write_output: bool = False) -> dict[str, Any]:
    """
    Import and execute the worker's safe local stub.

    The stub must expose run(write_output=False) -> Result with:
        .success (bool)
        .report  (str)
        .error   (str, optional)

    Returns a safe dict — never raises.
    """
    stub_path = _find_stub(worker_name)
    if stub_path is None:
        return {
            "success": False,
            "worker_name": worker_name,
            "report": "",
            "error": f"No stub found for worker: {worker_name!r}",
            "ran_at": _now_iso(),
        }

    try:
        ns = runpy.run_path(str(stub_path), run_name="__atlas_worker__")
        run_fn = ns.get("run")
        if run_fn is None or not callable(run_fn):
            raise ImportError(f"No callable run() in stub: {stub_path}")

        result = run_fn(write_output=write_output)

        return {
            "success":     getattr(result, "success", False),
            "worker_name": worker_name,
            "report":      getattr(result, "report", ""),
            "error":       getattr(result, "error", ""),
            "ran_at":      _now_iso(),
        }

    except Exception as exc:
        log.warning("run_worker_stub(%s): %s", worker_name, exc)
        return {
            "success":     False,
            "worker_name": worker_name,
            "report":      "",
            "error":       str(exc),
            "ran_at":      _now_iso(),
        }


# ---------------------------------------------------------------------------
# Memory / error append helpers
# ---------------------------------------------------------------------------

def append_worker_memory(worker_name: str, note: str) -> bool:
    """
    Append a timestamped note to the worker's memory.md.

    Returns True on success, False on failure. Never raises.
    """
    mem_path = _info_dir(worker_name) / "memory.md"
    if not mem_path.parent.is_dir():
        log.warning("append_worker_memory: information/ dir missing for %s", worker_name)
        return False
    try:
        entry = f"\n\n---\n\n**[{_now_iso()}]** {note.strip()}"
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return True
    except Exception as exc:
        log.warning("append_worker_memory(%s): %s", worker_name, exc)
        return False


def append_worker_error(worker_name: str, error: str) -> bool:
    """
    Append a timestamped error entry to the worker's past_errors.md.

    Returns True on success, False on failure. Never raises.
    """
    err_path = _info_dir(worker_name) / "past_errors.md"
    if not err_path.parent.is_dir():
        log.warning("append_worker_error: information/ dir missing for %s", worker_name)
        return False
    try:
        entry = f"\n\n---\n\n**[{_now_iso()}] ERROR:** {error.strip()}"
        with open(err_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return True
    except Exception as exc:
        log.warning("append_worker_error(%s): %s", worker_name, exc)
        return False


# ---------------------------------------------------------------------------
# Dashboard-level status aggregation
# ---------------------------------------------------------------------------

def get_agentic_os_status() -> dict[str, Any]:
    """
    Return safe aggregated metadata for dashboard consumption.

    All fields are always present — missing workers degrade to False/0/[].
    No external credentials required.
    """
    workers = list_agentic_workers()
    available = [w for w in workers if w["available"]]

    validations = {
        w["name"]: validate_worker_structure(w["name"])
        for w in workers
    }
    all_valid = all(v["valid"] for v in validations.values())

    suggested: list[str] = []
    if not all_valid:
        invalid = [n for n, v in validations.items() if not v["valid"]]
        suggested.append(f"Validate and fix worker structure for: {', '.join(invalid)}")
    if len(available) < len(workers):
        missing = [w["name"] for w in workers if not w["available"]]
        suggested.append(f"Complete implementation stubs for: {', '.join(missing)}")
    if not suggested:
        suggested.append("All workers healthy — schedule via Windows Task Scheduler or Modal Cloud")
        suggested.append("Run `python omega_agents/daily_build_brief/implementation/run_daily_build_brief.py` for today's brief")

    return {
        "agentic_workers_count":     len(workers),
        "agentic_workers_available": len(available),
        "always_on_hosting_status":  "planned",
        "workers":                   workers,
        "all_valid":                 all_valid,
        "suggested_agentic_actions": suggested[:5],
        "snapshot_at":               _now_iso(),
    }
