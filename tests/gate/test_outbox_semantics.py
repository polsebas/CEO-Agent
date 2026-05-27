"""RRM-1.5-M5 — outbox handler semantics and FIFO ordering (in-memory)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from core.persistence import _in_memory_outbox, reset_in_memory_store
from schemas.runtime import OutboxEvent
from workers.outbox_processor import _handle_event, process_outbox_batch_memory


def _outbox_event(
    *,
    correlation_id: str,
    idempotency_key: str | None = None,
    created_at: datetime | None = None,
    event_type: str = "test.probe",
) -> OutboxEvent:
    return OutboxEvent(
        id=str(uuid4()),
        idempotency_key=idempotency_key or str(uuid4()),
        correlation_id=correlation_id,
        event_type=event_type,
        payload={"probe": True},
        world_state_version=0,
        processed=False,
        created_at=created_at or datetime.now(timezone.utc),
    )


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_outbox_handler_failure_leaves_row_unprocessed():
    reset_in_memory_store()
    event = _outbox_event(correlation_id="fail-corr")
    _in_memory_outbox.append(event)

    with patch("workers.outbox_processor._handle_event", return_value=False):
        processed = await process_outbox_batch_memory()

    assert processed == 0
    assert event.processed is False


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_outbox_two_workers_no_double_process():
    reset_in_memory_store()
    event = _outbox_event(correlation_id="double-corr")
    _in_memory_outbox.append(event)

    first = await process_outbox_batch_memory()
    second = await process_outbox_batch_memory()

    assert first == 1
    assert second == 0
    assert event.processed is True


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_outbox_fifo_by_correlation_then_created_at():
    reset_in_memory_store()
    base = datetime.now(timezone.utc)
    order: list[str] = []

    async def track(event: OutboxEvent) -> bool:
        order.append(event.correlation_id)
        return True

    events = [
        _outbox_event(
            correlation_id="corr-b",
            created_at=base,
        ),
        _outbox_event(
            correlation_id="corr-a",
            created_at=base + timedelta(seconds=10),
        ),
        _outbox_event(
            correlation_id="corr-a",
            created_at=base + timedelta(seconds=1),
        ),
    ]
    _in_memory_outbox.extend(events)

    with patch("workers.outbox_processor._handle_event", side_effect=track):
        await process_outbox_batch_memory(limit=10)

    assert order == ["corr-a", "corr-a", "corr-b"]


@pytest.mark.rrm15
@pytest.mark.asyncio
async def test_outbox_successful_handler_marks_processed():
    reset_in_memory_store()
    event = _outbox_event(correlation_id="ok-corr", event_type="decision.recorded")
    event.payload = {"agent": "ceo"}
    _in_memory_outbox.append(event)

    assert await _handle_event(event) is True
    assert await process_outbox_batch_memory() == 1
    assert event.processed is True
