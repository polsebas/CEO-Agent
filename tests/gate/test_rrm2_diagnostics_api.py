"""RRM-2E — diagnostics API gate."""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from api.auth import create_test_token
from api.main import app
from core.orchestrator import manual_orchestrator
from core.persistence import reset_in_memory_store
from core.roles import UserRole


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_diagnostics_endpoint_explainable():
    reset_in_memory_store()
    session_id = "rrm2-diag-api"
    correlation_id = "rrm2-diag-api-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    token = create_test_token(role=UserRole.ADMIN)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t0 = time.perf_counter()
        r = await client.get(
            f"/api/v1/sessions/{session_id}/diagnostics",
            params={"correlation_id": correlation_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == session_id
    assert body["span_summary"]["total"] >= 1
    assert elapsed_ms < 3000


@pytest.mark.rrm2
@pytest.mark.asyncio
async def test_metrics_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/metrics")
    assert r.status_code == 200
