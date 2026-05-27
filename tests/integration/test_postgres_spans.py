"""Postgres integration — execution spans."""

import pytest

from core.orchestrator import manual_orchestrator
from core.persistence import query_execution_spans


@pytest.mark.postgres
@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_postgres_spans_persisted(postgres_available):
    session_id = "pg-spans-rrm2"
    correlation_id = "pg-spans-rrm2-corr"
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert "error" not in result
    from core.persistence import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        spans = await query_execution_spans(session_id, correlation_id=correlation_id, conn=conn)
    assert len(spans) >= 2
