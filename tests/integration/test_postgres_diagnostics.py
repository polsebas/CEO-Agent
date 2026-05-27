"""Postgres integration — session diagnostics."""

import pytest

from core.diagnostics import diagnostics_service
from core.orchestrator import manual_orchestrator


@pytest.mark.postgres
@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_postgres_session_diagnostics(postgres_available):
    session_id = "pg-diag-rrm2"
    correlation_id = "pg-diag-rrm2-corr"
    result = await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    assert "error" not in result
    from core.persistence import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        diag = await diagnostics_service.get_diagnostics(
            session_id, correlation_id, conn=conn
        )
    assert diag.span_summary.get("total", 0) >= 1
