"""
gemini_limiter.py — Shared Gemini Rate Limiter
================================================
A single global lock that ensures NO TWO THREADS call Gemini
within MIN_INTERVAL seconds of each other.

Import and call wait_for_slot() before EVERY Gemini API call
in every file: screen_watcher, news_scanner, deep_research, etc.

Configure long-running calls: pass HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS)
when constructing google.genai.Client (see query_router, atlas_omega).

Usage:
    from gemini_limiter import wait_for_slot, record_call, get_stats
    
    wait_for_slot()  # blocks until safe
    response = model.generate_content(...)
    record_call("news_scanner", success=True)
"""
from __future__ import annotations
import threading
import time
import logging
from collections import deque
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
MIN_INTERVAL   = 12.0   # minimum seconds between ANY Gemini call, any thread
BURST_LIMIT    = 3      # max calls in any 60-second window before backing off
BURST_WINDOW   = 60.0   # seconds for burst window
BACKOFF_SECS   = 30.0   # extra wait after burst limit hit
# google.genai HttpOptions.timeout is in milliseconds. Batched JSON synthesis often
# exceeds ~60s client defaults; keep aligned with dashboard / reverse-proxy budget.
GEMINI_HTTP_TIMEOUT_MS = 300_000

# ── State ────────────────────────────────────────────────────────────────────
_lock        = threading.Lock()
_last_call   = 0.0
_call_log: deque = deque(maxlen=100)   # (timestamp, caller, success)
_burst_times: deque = deque(maxlen=BURST_LIMIT + 5)

# ── Public API ────────────────────────────────────────────────────────────────

def wait_for_slot(caller: str = "unknown") -> float:
    """
    Block the calling thread until it is safe to make a Gemini API call.
    Returns the number of seconds waited.
    """
    global _last_call

    with _lock:
        now = time.time()

        # Check burst limit
        recent = [t for t in _burst_times if now - t < BURST_WINDOW]
        if len(recent) >= BURST_LIMIT:
            burst_wait = BURST_WINDOW - (now - recent[0]) + BACKOFF_SECS
            if burst_wait > 0:
                log.warning(
                    "[gemini_limiter] Burst limit hit (%d calls in %ds) — "
                    "waiting %.0fs before %s",
                    len(recent), BURST_WINDOW, burst_wait, caller
                )
                # Release lock during sleep so other threads don't deadlock
                _lock.release()
                time.sleep(burst_wait)
                _lock.acquire()
                now = time.time()

        # Enforce minimum interval
        wait = MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            log.debug("[gemini_limiter] Rate limiting — waiting %.1fs for %s", wait, caller)
            _lock.release()
            time.sleep(wait)
            _lock.acquire()
            now = time.time()

        _last_call = now
        _burst_times.append(now)
        return max(0.0, wait)


def record_call(caller: str, success: bool, duration_s: float = 0.0):
    """Record the outcome of a Gemini call for stats tracking."""
    _call_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "caller": caller,
        "success": success,
        "duration_s": round(duration_s, 2),
    })


def get_stats() -> dict:
    """Return usage stats — useful for the dashboard."""
    calls = list(_call_log)
    total = len(calls)
    successes = sum(1 for c in calls if c["success"])
    return {
        "total_calls": total,
        "success_rate": round(successes / total * 100, 1) if total else 0,
        "last_call_ago_s": round(time.time() - _last_call, 1),
        "recent_callers": [c["caller"] for c in calls[-5:]],
        "min_interval_s": MIN_INTERVAL,
    }


def is_rate_limit_error(exc: BaseException) -> bool:
    """
    Detect Gemini / Google API quota or throughput limits (429, RESOURCE_EXHAUSTED).
    Works across google-genai exception types without importing them here.
    """
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "too many requests" in msg:
        return True
    if "quota" in msg and ("exceed" in msg or "exhaust" in msg):
        return True
    code = getattr(exc, "status_code", None)
    if code == 429:
        return True
    details = getattr(exc, "details", None) or getattr(exc, "response", None)
    if details is not None:
        d = str(details).lower()
        if "resource_exhausted" in d or "429" in d:
            return True
    args0 = getattr(exc, "args", None)
    if args0 and isinstance(args0, tuple) and args0:
        a0 = str(args0[0]).lower()
        if "429" in a0 or "resource_exhausted" in a0:
            return True
    return False
