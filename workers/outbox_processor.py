"""Outbox processor — at-least-once with idempotency dedup."""

from __future__ import annotations

import asyncio

from core.health import agent_health_registry
from core.persistence import fetch_unprocessed_events, mark_event_processed


async def process_outbox_batch(limit: int = 50) -> int:
    events = await fetch_unprocessed_events(limit=limit)
    processed = 0
    for event in events:
        if not await mark_event_processed(event.idempotency_key):
            continue
        if event.event_type == "decision.recorded":
            agent = event.payload.get("agent", "unknown")
            agent_health_registry.record_run_sync(agent, success=True, latency_ms=0)
        processed += 1
    return processed


async def run_outbox_worker(interval_seconds: float = 5.0) -> None:
    while True:
        await process_outbox_batch()
        await asyncio.sleep(interval_seconds)
