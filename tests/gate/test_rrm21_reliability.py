"""RRM-2.1 — Intelligence Reliability Hardening gate."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api.auth import create_test_token
from api.main import app
from core.approval_service import create_immutable_proposal, prepare_approval_in_session
from core.health import agent_health_registry
from core.orchestrator import manual_orchestrator
from core.persistence import query_execution_spans, query_runtime_health, reset_in_memory_store
from core.runtime_session import MemoryConnection
from core.spans import span_manager
from core.telemetry import otel
from core.transaction import PersistRuntimePayload, _merge_pending_spans, persist_runtime_tx
from core.intelligence_store import get_health_snapshots, get_session_diagnostics
from httpx import ASGITransport, AsyncClient
from schemas.spans import SpanStatus, SpanType
from core.roles import UserRole


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_contextvar_span_isolation_under_concurrency():
    async def run_session(session_id: str) -> list[str]:
        span_manager.begin_session(session_id=session_id, correlation_id=session_id)
        span = span_manager.start(SpanType.TOOL_EXECUTION, metadata={"session": session_id})
        await asyncio.sleep(0.02)
        span_manager.end(span, status=SpanStatus.OK)
        return [s.session_id for s in span_manager.drain()]

    reset_in_memory_store()
    a_ids, b_ids = await asyncio.gather(run_session("iso-a"), run_session("iso-b"))
    assert a_ids == ["iso-a"]
    assert b_ids == ["iso-b"]


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_idempotent_memory_outbox_still_persists_spans():
    reset_in_memory_store()
    conn = MemoryConnection()
    sid, cid = "rrm21-idem", "rrm21-idem-corr"
    base = dict(
        correlation_id=cid,
        session_id=sid,
        event_type="founder.intent",
        event_payload={"message": "first"},
        business_key="founder.intent",
    )

    span_manager.begin_session(session_id=sid, correlation_id=cid)
    o = span_manager.start(SpanType.ORCHESTRATION)
    span_manager.end(o, status=SpanStatus.OK)
    r1 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
    assert r1.inserted is True

    span_manager.begin_session(session_id=sid, correlation_id=cid)
    t = span_manager.start(SpanType.TRANSITION)
    span_manager.end(t, status=SpanStatus.OK)
    r2 = await persist_runtime_tx(conn, PersistRuntimePayload(**base))
    assert r2.inserted is False

    spans = await query_execution_spans(sid, correlation_id=cid)
    types = {s.span_type for s in spans}
    assert SpanType.ORCHESTRATION in types
    assert SpanType.TRANSITION in types


@pytest.mark.rrm21
def test_merge_pending_spans_attaches_drained():
    span_manager.begin_session(session_id="merge", correlation_id="merge")
    span_manager.start(SpanType.ORCHESTRATION)
    payload = PersistRuntimePayload(
        correlation_id="merge",
        session_id="merge",
        event_type="probe",
        event_payload={},
    )
    _merge_pending_spans(payload)
    assert len(payload.execution_spans) == 1
    assert payload.execution_spans[0].span_type == SpanType.ORCHESTRATION


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_session_close_replay_confidence_baseline_default():
    reset_in_memory_store()
    session_id = "rrm21-rc"
    correlation_id = "rrm21-rc-corr"
    await manual_orchestrator.run_founder_request(
        "Analyze deployment anomaly",
        session_id=session_id,
        correlation_id=correlation_id,
    )
    rows = await query_runtime_health(session_id)
    assert rows
    assert rows[-1].replay_confidence == 1.0


@pytest.mark.rrm21
def test_single_health_snapshot_replace_on_repersist():
    reset_in_memory_store()
    from core.intelligence_persist import apply_intelligence_memory
    from core.runtime_health import runtime_health_engine

    sid, cid = "rrm21-health", "rrm21-health-corr"
    h1 = runtime_health_engine.compute(
        correlation_id=cid,
        session_id=sid,
        telemetry=[],
        spans=[],
        replay_confidence=1.0,
    )
    h2 = runtime_health_engine.compute(
        correlation_id=cid,
        session_id=sid,
        telemetry=[],
        spans=[],
        replay_confidence=0.2,
    )
    base = dict(
        correlation_id=cid,
        session_id=sid,
        event_type="health.probe",
        event_payload={},
        drain_spans=False,
    )
    apply_intelligence_memory(PersistRuntimePayload(**base, runtime_health=h1))
    apply_intelligence_memory(PersistRuntimePayload(**base, runtime_health=h2))
    assert len(get_health_snapshots(sid)) == 1
    assert get_health_snapshots(sid)[-1].replay_confidence == 0.2


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_degraded_escalation_emits_session_diagnostics():
    reset_in_memory_store()
    agent_health_registry.clear()
    with patch.object(
        agent_health_registry,
        "is_degraded",
        new=AsyncMock(return_value=True),
    ):
        session_id = "rrm21-degraded"
        correlation_id = "rrm21-degraded-corr"
        result = await manual_orchestrator.run_founder_request(
            "Need human help",
            session_id=session_id,
            correlation_id=correlation_id,
        )
    assert result.get("escalated") is True
    diag = get_session_diagnostics(session_id)
    assert diag is not None
    assert diag.session_id == session_id


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_approval_span_recorded():
    reset_in_memory_store()
    proposal = create_immutable_proposal(
        correlation_id="rrm21-approval",
        action="create_initiative",
        parameters={"reason": "test"},
        agent="ceo",
        side_effect_level="EXECUTE_SAFE",
        impact_summary="test approval span",
        proposed_by="founder",
        approval_level=1,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    await prepare_approval_in_session(proposal, "founder")
    spans = await query_execution_spans("rrm21-approval", correlation_id="rrm21-approval")
    assert any(s.span_type == SpanType.APPROVAL for s in spans)


@pytest.mark.rrm21
def test_prometheus_bridge_exports_otel_cognitive_metrics(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    monkeypatch.setattr(otel.settings, "otel_sdk_disabled", False)
    monkeypatch.setattr(otel.settings, "telemetry_enabled", True)
    otel.shutdown_telemetry()
    otel._initialized = False
    otel.init_telemetry()
    otel.record_cognitive_metrics(
        agent_id="ceo",
        session_id="prom",
        token_estimate=42,
        reasoning_latency_ms=10,
        retry_count=1,
    )
    body = otel.get_prometheus_metrics_text()
    assert "cognitive_tokens" in body
    otel.shutdown_telemetry()
    otel._initialized = False


@pytest.mark.rrm21
@pytest.mark.asyncio
async def test_diagnostics_available_after_degraded_close():
    reset_in_memory_store()
    agent_health_registry.clear()
    session_id = "rrm21-diag-deg"
    correlation_id = "rrm21-diag-deg-corr"
    with patch.object(
        agent_health_registry,
        "is_degraded",
        new=AsyncMock(return_value=True),
    ):
        await manual_orchestrator.run_founder_request(
            "escalate",
            session_id=session_id,
            correlation_id=correlation_id,
        )
    token = create_test_token(role=UserRole.ADMIN)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            f"/api/v1/sessions/{session_id}/diagnostics",
            params={"correlation_id": correlation_id},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id
