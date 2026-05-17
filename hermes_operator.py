"""
Hermes Operator — cadence runner, daily brief, safe auto-actions.

Named after the Greek messenger god: fast, reliable, always in motion.
Hermes wakes on a schedule, aggregates intelligence from all live modules,
and queues safe pre-approved actions for the operator to review.

Rules:
  - Zero LLM calls. Fully deterministic.
  - Read-only or append-only. No user data mutation.
  - All failures are swallowed and logged — never crash the server.
  - Thread-safe: one lock for cadence state mutations.

Persistence:  atlas_vault/04-Projects/Hermes/
  brief_<YYYYMMDD>.json   — daily briefs
  action_queue.json       — pending operator actions
  cadence_state.json      — last/next run timestamps per cadence
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
HERMES_DIR = BASE_DIR / "atlas_vault" / "04-Projects" / "Hermes"

_STATE_FILE = HERMES_DIR / "cadence_state.json"
_QUEUE_FILE = HERMES_DIR / "action_queue.json"
_MAX_QUEUE = 200

_lock = threading.Lock()
_stop_event = threading.Event()

# ── Safe Action Registry ──────────────────────────────────────────────────────

SAFE_ACTIONS = {
    "generate_brief":        "Generate and persist the daily Hermes intelligence brief",
    "snapshot_hub":          "Capture full intelligence hub snapshot to disk",
    "scan_division_playbooks": "Surface top playbook rules across all 8 divisions",
    "log_system_health":     "Write system health snapshot (data_cache freshness, counts)",
}

# ── Cadence Registry ──────────────────────────────────────────────────────────

CADENCES: dict[str, dict] = {
    "daily_brief": {
        "name":             "Daily Intelligence Brief",
        "description":      "Morning brief from hub signals + division highlights",
        "action":           "generate_brief",
        "interval_seconds": 86_400,
        "icon":             "📋",
    },
    "hub_snapshot": {
        "name":             "Hub Signal Snapshot",
        "description":      "Capture full hub snapshot every 4 hours",
        "action":           "snapshot_hub",
        "interval_seconds": 14_400,
        "icon":             "📡",
    },
    "system_health": {
        "name":             "System Health Check",
        "description":      "Log system health every hour",
        "action":           "log_system_health",
        "interval_seconds": 3_600,
        "icon":             "💚",
    },
    "division_scan": {
        "name":             "Division Playbook Scan",
        "description":      "Surface top rules from active division playbooks every 2 hours",
        "action":           "scan_division_playbooks",
        "interval_seconds": 7_200,
        "icon":             "🏛️",
    },
}

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class HermesAction:
    action_id: str
    action_type: str
    created_at: str
    payload: dict
    status: str = "pending"   # pending | dismissed | executed
    source: str = ""          # cadence id that triggered it

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HermesBrief:
    brief_id: str
    date: str                    # YYYY-MM-DD
    generated_at: str            # ISO timestamp
    regime: str                  # detected regime label
    top_signals: list            # up to 5 signals from hub brief
    division_highlights: list    # one highlight per active division
    system_health: dict          # data_cache freshness + counts
    pending_actions: int         # count of pending queue items
    summary: str                 # one-line human-readable summary

    def to_dict(self) -> dict:
        return asdict(self)


# ── Persistence helpers ───────────────────────────────────────────────────────

def _ensure_dir() -> None:
    HERMES_DIR.mkdir(parents=True, exist_ok=True)


def _load_cadence_state() -> dict:
    _ensure_dir()
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cadence_state(state: dict) -> None:
    _ensure_dir()
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_queue() -> list:
    _ensure_dir()
    if _QUEUE_FILE.exists():
        try:
            return json.loads(_QUEUE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_queue(queue: list) -> None:
    _ensure_dir()
    _QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")


# ── Action Queue ──────────────────────────────────────────────────────────────

def _enqueue_action(action_type: str, payload: dict, source: str = "") -> HermesAction:
    action = HermesAction(
        action_id=str(uuid.uuid4())[:8],
        action_type=action_type,
        created_at=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        source=source,
    )
    with _lock:
        queue = _load_queue()
        queue.append(action.to_dict())
        if len(queue) > _MAX_QUEUE:
            queue = queue[-_MAX_QUEUE:]
        _save_queue(queue)
    return action


def get_action_queue(status: Optional[str] = None) -> list[dict]:
    """Return the action queue, optionally filtered by status."""
    queue = _load_queue()
    if status:
        queue = [a for a in queue if a.get("status") == status]
    return queue


def dismiss_action(action_id: str) -> bool:
    """Mark an action as dismissed. Returns True if found."""
    with _lock:
        queue = _load_queue()
        for entry in queue:
            if entry.get("action_id") == action_id:
                entry["status"] = "dismissed"
                _save_queue(queue)
                return True
    return False


def execute_action(action_id: str) -> bool:
    """Mark an action as executed. Returns True if found."""
    with _lock:
        queue = _load_queue()
        for entry in queue:
            if entry.get("action_id") == action_id:
                entry["status"] = "executed"
                _save_queue(queue)
                return True
    return False


# ── Action Implementations ────────────────────────────────────────────────────

def _action_generate_brief(cadence_id: str) -> dict:
    """Build today's brief from hub + divisions + system health."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    brief_id = f"brief_{today.replace('-', '')}"

    # Hub signals
    top_signals: list = []
    regime = "UNKNOWN"
    try:
        from intelligence_hub import get_brief as hub_brief
        hub = hub_brief()
        top_signals = hub.get("top_signals", [])[:5]
        # Infer regime from signals
        bull = sum(1 for s in top_signals if s.get("direction") == "up")
        bear = sum(1 for s in top_signals if s.get("direction") == "down")
        if bull > bear:
            regime = "BULLISH"
        elif bear > bull:
            regime = "BEARISH"
        else:
            regime = "NEUTRAL"
    except Exception:
        log.debug("[hermes] hub brief unavailable", exc_info=True)

    # Division highlights
    division_highlights: list = []
    try:
        from division_sandbox import list_divisions
        for div in list_divisions():
            division_highlights.append({
                "id":          div["division_id"],
                "name":        div["name"],
                "icon":        div["icon"],
                "memory_count": div.get("memory_count", 0),
                "top_rule":    div.get("top_rule", ""),
            })
    except Exception:
        log.debug("[hermes] division list unavailable", exc_info=True)

    # System health
    sys_health = _collect_system_health()

    # Pending queue count
    pending = len([a for a in _load_queue() if a.get("status") == "pending"])

    top_names = ", ".join(s.get("name", "") for s in top_signals[:3]) or "no signals"
    summary = f"{today} · Regime: {regime} · Top signals: {top_names} · {pending} pending actions"

    brief = HermesBrief(
        brief_id=brief_id,
        date=today,
        generated_at=datetime.now(timezone.utc).isoformat(),
        regime=regime,
        top_signals=top_signals,
        division_highlights=division_highlights,
        system_health=sys_health,
        pending_actions=pending,
        summary=summary,
    )

    # Persist
    _ensure_dir()
    brief_path = HERMES_DIR / f"{brief_id}.json"
    brief_path.write_text(json.dumps(brief.to_dict(), indent=2), encoding="utf-8")
    log.info("[hermes] brief generated → %s", brief_path.name)

    return {"brief_id": brief_id, "summary": summary}


def _action_snapshot_hub(cadence_id: str) -> dict:
    """Save full hub snapshot to disk."""
    try:
        from intelligence_hub import get_snapshot
        snapshot = get_snapshot()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = HERMES_DIR / f"hub_snapshot_{ts}.json"
        _ensure_dir()
        out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        count = snapshot.get("total_signals", "?")
        log.info("[hermes] hub snapshot → %s (%s signals)", out.name, count)
        return {"file": out.name, "signal_count": count}
    except Exception as exc:
        log.debug("[hermes] hub snapshot failed: %s", exc)
        return {"error": str(exc)}


def _action_scan_division_playbooks(cadence_id: str) -> dict:
    """Collect top playbook rules from all divisions."""
    highlights: list = []
    try:
        from division_sandbox import DIVISIONS, get_playbook_context
        for div_id in DIVISIONS:
            ctx = get_playbook_context(
                intent=DIVISIONS[div_id]["intents"][0] if DIVISIONS[div_id].get("intents") else "",
                max_rules=1,
            )
            if ctx:
                highlights.append({"division": div_id, "rule": ctx.strip()})
    except Exception as exc:
        log.debug("[hermes] division scan failed: %s", exc)
    return {"highlights": highlights, "count": len(highlights)}


def _action_log_system_health(cadence_id: str) -> dict:
    health = _collect_system_health()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = HERMES_DIR / f"health_{ts}.json"
    _ensure_dir()
    out.write_text(json.dumps(health, indent=2), encoding="utf-8")
    log.info("[hermes] health logged → %s", out.name)
    return health


def _collect_system_health() -> dict:
    data_cache = BASE_DIR / "data_cache"
    cache_files = list(data_cache.glob("*_latest.json")) if data_cache.exists() else []
    now = time.time()
    stale = [f.name for f in cache_files if (now - f.stat().st_mtime) > 86400]

    div_dir = BASE_DIR / "atlas_vault" / "04-Projects" / "Divisions"
    div_count = len(list(div_dir.iterdir())) if div_dir.exists() else 0

    sandbox_dir = BASE_DIR / "atlas_vault" / "03-Outputs" / "Sandboxes"
    sandbox_count = len(list(sandbox_dir.iterdir())) if sandbox_dir.exists() else 0

    hermes_files = len(list(HERMES_DIR.glob("*.json"))) if HERMES_DIR.exists() else 0

    return {
        "cache_files":    len(cache_files),
        "stale_files":    len(stale),
        "stale_names":    stale[:5],
        "divisions_on_disk": div_count,
        "sandboxes":      sandbox_count,
        "hermes_files":   hermes_files,
        "checked_at":     datetime.now(timezone.utc).isoformat(),
    }


# ── Action Dispatcher ─────────────────────────────────────────────────────────

_ACTION_FNS = {
    "generate_brief":          _action_generate_brief,
    "snapshot_hub":            _action_snapshot_hub,
    "scan_division_playbooks": _action_scan_division_playbooks,
    "log_system_health":       _action_log_system_health,
}


def run_cadence(cadence_id: str) -> dict:
    """Execute a cadence immediately. Updates last_run timestamp."""
    if cadence_id not in CADENCES:
        return {"error": f"Unknown cadence '{cadence_id}'"}

    cfg = CADENCES[cadence_id]
    action = cfg["action"]
    fn = _ACTION_FNS.get(action)
    if not fn:
        return {"error": f"No handler for action '{action}'"}

    result: dict = {}
    try:
        result = fn(cadence_id)
    except Exception as exc:
        log.warning("[hermes] cadence '%s' action failed: %s", cadence_id, exc)
        result = {"error": str(exc)}

    now_iso = datetime.now(timezone.utc).isoformat()
    with _lock:
        state = _load_cadence_state()
        state[cadence_id] = {
            "last_run":  now_iso,
            "last_result": result,
        }
        _save_cadence_state(state)

    # Enqueue the result as a pending operator action
    _enqueue_action(
        action_type=action,
        payload=result,
        source=cadence_id,
    )

    return {"cadence_id": cadence_id, "action": action, "result": result}


# ── Cadence Status ────────────────────────────────────────────────────────────

def list_cadences() -> list[dict]:
    """Return all cadences with last_run / next_run / due status."""
    state = _load_cadence_state()
    now = time.time()
    out = []
    for cid, cfg in CADENCES.items():
        s = state.get(cid, {})
        last_run_iso = s.get("last_run")
        last_run_ts = 0.0
        if last_run_iso:
            try:
                last_run_ts = datetime.fromisoformat(last_run_iso).timestamp()
            except Exception:
                pass
        next_run_ts = last_run_ts + cfg["interval_seconds"] if last_run_ts else now
        due = now >= next_run_ts
        out.append({
            "cadence_id":        cid,
            "name":              cfg["name"],
            "description":       cfg["description"],
            "action":            cfg["action"],
            "interval_seconds":  cfg["interval_seconds"],
            "icon":              cfg["icon"],
            "last_run":          last_run_iso,
            "next_run":          datetime.fromtimestamp(next_run_ts, tz=timezone.utc).isoformat(),
            "due":               due,
            "last_result":       s.get("last_result"),
        })
    return out


# ── Brief Access ──────────────────────────────────────────────────────────────

def get_today_brief() -> Optional[dict]:
    """Return today's brief from disk, or None if not yet generated."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    brief_path = HERMES_DIR / f"brief_{today}.json"
    if brief_path.exists():
        try:
            return json.loads(brief_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def get_latest_brief() -> Optional[dict]:
    """Return the most recent brief (any date), or None."""
    _ensure_dir()
    briefs = sorted(HERMES_DIR.glob("brief_*.json"), reverse=True)
    for b in briefs:
        try:
            return json.loads(b.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


# ── Background Runner ─────────────────────────────────────────────────────────

def _tick() -> None:
    """Check all cadences and run any that are due."""
    state = _load_cadence_state()
    now = time.time()
    for cid, cfg in CADENCES.items():
        s = state.get(cid, {})
        last_run_iso = s.get("last_run")
        last_run_ts = 0.0
        if last_run_iso:
            try:
                last_run_ts = datetime.fromisoformat(last_run_iso).timestamp()
            except Exception:
                pass
        due = now >= (last_run_ts + cfg["interval_seconds"]) if last_run_ts else True
        if due:
            log.info("[hermes] running cadence: %s", cid)
            try:
                run_cadence(cid)
            except Exception:
                log.warning("[hermes] cadence '%s' raised unexpectedly", cid, exc_info=True)


def _runner_loop(interval: int = 60) -> None:
    """Background thread: tick every `interval` seconds until _stop_event is set."""
    log.info("[hermes] background runner started (tick every %ds)", interval)
    # Initial tick on startup so briefs exist immediately
    try:
        _tick()
    except Exception:
        log.warning("[hermes] initial tick failed", exc_info=True)
    while not _stop_event.wait(timeout=interval):
        try:
            _tick()
        except Exception:
            log.warning("[hermes] tick failed", exc_info=True)
    log.info("[hermes] background runner stopped")


def start_hermes(tick_interval: int = 60) -> threading.Thread:
    """Start the Hermes background runner. Call once at server startup."""
    _stop_event.clear()
    t = threading.Thread(
        target=_runner_loop,
        args=(tick_interval,),
        daemon=True,
        name="hermes-runner",
    )
    t.start()
    return t


def stop_hermes() -> None:
    """Signal the runner to stop cleanly."""
    _stop_event.set()
