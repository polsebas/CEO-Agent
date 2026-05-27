"""Executive Timeline — full causal chain for debugging."""

from __future__ import annotations

from datetime import datetime

from core.persistence import get_decisions_by_correlation, get_effects_by_correlation, get_events_by_correlation
from core.policy import policy_engine


class TimelineEntry:
    def __init__(
        self,
        timestamp: datetime,
        message: str,
        entry_type: str,
        metadata: dict | None = None,
        causation_id: str | None = None,
    ):
        self.timestamp = timestamp
        self.message = message
        self.entry_type = entry_type
        self.metadata = metadata or {}
        self.causation_id = causation_id


async def build_executive_timeline(correlation_id: str) -> list[dict]:
    entries: list[TimelineEntry] = []

    events = await get_events_by_correlation(correlation_id)
    for event in events:
        if event.event_type == "founder.intent":
            entries.append(
                TimelineEntry(
                    timestamp=event.created_at,
                    message=f"Founder intent: {event.payload.get('message', '')}",
                    entry_type="founder_intent",
                    metadata={"event_type": event.event_type},
                    causation_id=event.causation_id,
                )
            )
        elif event.event_type == "runtime.transition":
            entries.append(
                TimelineEntry(
                    timestamp=event.created_at,
                    message=f"Runtime {event.payload.get('from')} → {event.payload.get('to')}",
                    entry_type="runtime_transition",
                    metadata=event.payload,
                    causation_id=event.causation_id,
                )
            )
        else:
            entries.append(
                TimelineEntry(
                    timestamp=event.created_at,
                    message=f"{event.event_type}: {event.payload.get('summary', event.event_type)}",
                    entry_type="event",
                    metadata={"event_type": event.event_type},
                    causation_id=event.causation_id,
                )
            )

    decisions = await get_decisions_by_correlation(correlation_id)
    for decision in decisions:
        entries.append(
            TimelineEntry(
                timestamp=decision.created_at,
                message=f"Reasoning [{decision.agent}]: {decision.reasoning_summary}",
                entry_type="reasoning",
                metadata={
                    "agent": decision.agent,
                    "outcome": decision.outcome,
                    "tools_used": decision.tools_used,
                },
                causation_id=decision.causation_id,
            )
        )

    for approval in await policy_engine.list_pending_approvals():
        if approval.correlation_id == correlation_id:
            entries.append(
                TimelineEntry(
                    timestamp=approval.expires_at,
                    message=f"Approval pending: {approval.proposal.action}",
                    entry_type="approval",
                    metadata={"approval_id": approval.id, "status": approval.status.value},
                )
            )

    effects = await get_effects_by_correlation(correlation_id)
    for effect in effects:
        entries.append(
            TimelineEntry(
                timestamp=effect.created_at,
                message=f"Side effect {effect.mutation_status} on {', '.join(effect.systems_affected) or 'N/A'}",
                entry_type="side_effect",
                metadata={"status": effect.mutation_status, "action_id": effect.action_id},
                causation_id=effect.correlation_id,
            )
        )

    for event in events:
        if event.event_type == "session.completed":
            entries.append(
                TimelineEntry(
                    timestamp=event.created_at,
                    message=f"Outcome: {event.payload.get('summary', 'completed')}",
                    entry_type="outcome",
                    metadata=event.payload,
                    causation_id=event.causation_id,
                )
            )

    entries.sort(key=lambda e: e.timestamp)
    return [
        {
            "timestamp": e.timestamp.isoformat(),
            "message": e.message,
            "type": e.entry_type,
            "metadata": e.metadata,
            "causation_id": e.causation_id,
        }
        for e in entries
    ]
