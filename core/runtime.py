"""Runtime state machine with explicit transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from schemas.adaptive import AdaptivePolicy
from schemas.runtime import VALID_TRANSITIONS, RuntimeState


class InvalidStateTransition(Exception):
    def __init__(self, current: RuntimeState, target: RuntimeState) -> None:
        super().__init__(f"Invalid transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


@dataclass
class RuntimeStateMachine:
    correlation_id: str
    session_id: str
    state: RuntimeState = RuntimeState.IDLE
    history: list[tuple[RuntimeState, datetime]] = field(default_factory=list)
    stuck_counter: int = 0
    max_stuck_iterations: int = 5
    adaptive_policy: AdaptivePolicy | None = None
    policy_recompute_required: bool = False
    _session_tool_names: list[str] = field(default_factory=list)
    _session_delegations: list[str] = field(default_factory=list)
    _stability_event_keys: set[str] = field(default_factory=set)

    def transition(self, target: RuntimeState) -> RuntimeState:
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if target not in allowed and self.state != target:
            raise InvalidStateTransition(self.state, target)
        self.state = target
        self.history.append((target, datetime.now(timezone.utc)))
        return self.state

    def start(self) -> RuntimeState:
        return self.transition(RuntimeState.PERCEIVING)

    def detect_stuck(self, progressed: bool) -> RuntimeState | None:
        if progressed:
            self.stuck_counter = 0
            return None
        self.stuck_counter += 1
        if self.stuck_counter >= self.max_stuck_iterations:
            return self.transition(RuntimeState.REPLANNING)
        return None

    def fail(self, reason: str = "") -> RuntimeState:
        self.history.append((RuntimeState.FAILED, datetime.now(timezone.utc)))
        self.state = RuntimeState.FAILED
        return self.state

    def complete(self) -> RuntimeState:
        return self.transition(RuntimeState.COMPLETED)


def new_session_ids() -> tuple[str, str]:
    """Return (correlation_id, session_id)."""
    return str(uuid4()), str(uuid4())
