"""
progress_state.py — Authoritative job progress state machine.
Prevents fake/frozen progress after the final answer appears.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional


class ProgressState(str, Enum):
    QUEUED             = "QUEUED"
    ROUTING            = "ROUTING"
    RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
    TOOL_CALLING       = "TOOL_CALLING"
    SYNTHESIZING       = "SYNTHESIZING"
    VALIDATING         = "VALIDATING"
    FINALIZING         = "FINALIZING"
    COMPLETE           = "COMPLETE"
    ERROR              = "ERROR"


TERMINAL_STATES: frozenset[ProgressState] = frozenset({
    ProgressState.COMPLETE,
    ProgressState.ERROR,
})


@dataclass
class JobProgress:
    job_id: str
    state: ProgressState = ProgressState.QUEUED
    message: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    _emit: Optional[Callable[[dict], None]] = field(default=None, repr=False, compare=False)

    def transition(
        self,
        state: ProgressState,
        message: str = "",
        error: Optional[str] = None,
    ) -> None:
        """Advance to a new state. No-op if already in a terminal state."""
        if self.state in TERMINAL_STATES:
            return
        self.state = state
        self.message = message
        self.error = error
        self.updated_at = datetime.now(timezone.utc)
        if self._emit is not None:
            try:
                self._emit(self.to_dict())
            except Exception:
                pass

    # Convenience alias matching old progress_state.py `.advance()` contract
    def advance(self, stage: str, pct: int = 0, detail: str = "") -> None:
        try:
            ps = ProgressState(stage)
        except ValueError:
            ps = ProgressState.SYNTHESIZING
        self.transition(ps, detail or f"{stage} ({pct}%)")

    @property
    def is_done(self) -> bool:
        return self.state in TERMINAL_STATES

    def to_dict(self) -> dict:
        return {
            "job_id":     self.job_id,
            "state":      self.state.value,
            "message":    self.message,
            "updated_at": self.updated_at.isoformat(),
            "error":      self.error,
        }
