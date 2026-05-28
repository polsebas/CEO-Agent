"""Session stabilization — append events, evaluate at boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.cognition_loops import detect_delegation_loop, detect_retry_loop, detect_tool_cycle
from core.retry_storms import is_retry_storm, retry_density
from pydantic import BaseModel, Field


class SessionStabilityEvent(BaseModel):
    session_id: str
    correlation_id: str
    event_type: str
    severity: str = "medium"
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StabilityAssessment(BaseModel):
    stability_score: float = 1.0
    stability_pressure: float = 0.0
    events: list[SessionStabilityEvent] = Field(default_factory=list)
    policy_recompute_required: bool = False


class SessionStabilityService:
    def assess_at_boundary(
        self,
        *,
        session_id: str,
        correlation_id: str,
        telemetry: list,
        tool_names: list[str],
        delegations: list[str],
        retry_signatures: list[str] | None = None,
    ) -> StabilityAssessment:
        events: list[SessionStabilityEvent] = []
        pressure = 0.0
        retry_sigs = retry_signatures or []

        density = retry_density(telemetry)
        if is_retry_storm(density):
            pressure = max(pressure, density)
            events.append(
                SessionStabilityEvent(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    event_type="retry_storm",
                    severity="high",
                    metadata={"retry_density": density},
                )
            )

        if detect_delegation_loop(delegations):
            pressure = max(pressure, 0.7)
            events.append(
                SessionStabilityEvent(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    event_type="delegation_loop",
                    severity="high",
                    metadata={"delegations": delegations[-3:]},
                )
            )

        if detect_tool_cycle(tool_names):
            pressure = max(pressure, 0.6)
            events.append(
                SessionStabilityEvent(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    event_type="tool_cycle",
                    severity="medium",
                    metadata={"tools": tool_names[-8:]},
                )
            )

        if detect_retry_loop(retry_sigs):
            pressure = max(pressure, 0.65)
            events.append(
                SessionStabilityEvent(
                    session_id=session_id,
                    correlation_id=correlation_id,
                    event_type="retry_loop",
                    severity="high",
                )
            )

        score = max(0.0, 1.0 - pressure)
        return StabilityAssessment(
            stability_score=round(score, 4),
            stability_pressure=round(pressure, 4),
            events=events,
            policy_recompute_required=pressure >= 0.5,
        )


session_stability_service = SessionStabilityService()
