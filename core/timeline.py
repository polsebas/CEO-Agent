"""Executive Timeline builder."""

from __future__ import annotations

from datetime import datetime

from core.persistence import get_decisions_by_correlation, get_effects_by_correlation, get_events_by_correlation


class TimelineEntry:
    def __init__(self, timestamp: datetime, message: str, entry_type: str, metadata: dict | None = None):
        self.timestamp = timestamp
        self.message = message
        self.entry_type = entry_type
        self.metadata = metadata or {}


async def build_executive_timeline(correlation_id: str) -> list[dict]:
    entries: list[TimelineEntry] = []

    events = await get_events_by_correlation(correlation_id)
    for event in events:
        entries.append(
            TimelineEntry(
                timestamp=event.created_at,
                message=f"{event.event_type}: {event.payload.get('summary', event.event_type)}",
                entry_type="event",
                metadata={"event_type": event.event_type},
            )
        )

    decisions = await get_decisions_by_correlation(correlation_id)
    for decision in decisions:
        entries.append(
            TimelineEntry(
                timestamp=decision.created_at,
                message=f"{decision.agent.upper()} — {decision.reasoning_summary}",
                entry_type="DecisionRecord",
                metadata={"agent": decision.agent, "outcome": decision.outcome},
            )
        )

    effects = await get_effects_by_correlation(correlation_id)
    for effect in effects:
        entries.append(
            TimelineEntry(
                timestamp=effect.created_at,
                message=f"Side effect {effect.mutation_status} on {', '.join(effect.systems_affected) or 'N/A'}",
                entry_type="SideEffectRecord",
                metadata={"status": effect.mutation_status},
            )
        )

    entries.sort(key=lambda e: e.timestamp)
    return [
        {
            "timestamp": e.timestamp.isoformat(),
            "message": e.message,
            "type": e.entry_type,
            "metadata": e.metadata,
        }
        for e in entries
    ]
