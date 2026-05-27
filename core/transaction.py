"""Runtime transaction manager — persist on caller's connection only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.canonical import stable_hash
from core.persistence import (
    apply_memory_runtime_persist,
    get_memory_outbox_by_idempotency,
    get_world_state,
)
from core.runtime_session import MemoryConnection
from core.spans import drain_pending_spans
from schemas.cognition import CognitiveTelemetry, PromptLineage, StructuredRetryTrace
from schemas.decisions import DecisionRecord
from schemas.diagnostics import SessionDiagnostics
from schemas.effects import SideEffectRecord
from schemas.runtime import OutboxEvent
from schemas.runtime_health import RuntimeAnomaly, RuntimeHealth
from schemas.spans import ExecutionSpan
from schemas.world import WorldStateSnapshot


@dataclass
class RuntimeTransition:
    from_state: str
    to_state: str
    correlation_id: str
    session_id: str


@dataclass
class PersistRuntimePayload:
    correlation_id: str
    session_id: str
    event_type: str
    event_payload: dict
    causation_id: str | None = None
    decision: DecisionRecord | None = None
    side_effect: SideEffectRecord | None = None
    replay_snapshot: dict | None = None
    replay_step: int | None = None
    runtime_transition: RuntimeTransition | None = None
    retry_trace: StructuredRetryTrace | None = None
    business_key: str | None = None
    update_world: bool = False
    world_changed_entities: list[str] | None = None
    store_replay_baseline: bool = False
    execution_spans: list[ExecutionSpan] = field(default_factory=list)
    cognitive_telemetry: list[CognitiveTelemetry] = field(default_factory=list)
    runtime_health: RuntimeHealth | None = None
    prompt_lineage: list[PromptLineage] = field(default_factory=list)
    runtime_anomalies: list[RuntimeAnomaly] = field(default_factory=list)
    session_diagnostics: SessionDiagnostics | None = None
    drain_spans: bool = True


@dataclass
class PersistResult:
    event: OutboxEvent
    inserted: bool


def _idempotency_key(correlation_id: str, event_type: str, payload: dict, business_key: str | None) -> str:
    material = {
        "correlation_id": correlation_id,
        "event_type": event_type,
        "business_key": business_key or event_type,
        "payload": payload,
    }
    return stable_hash(material)


async def _fetch_outbox_by_idempotency(conn: Any, idempotency_key: str) -> OutboxEvent | None:
    row = await conn.fetchrow(
        "SELECT * FROM outbox_events WHERE idempotency_key = $1",
        idempotency_key,
    )
    if not row:
        return None
    from core.persistence import _row_to_outbox

    return _row_to_outbox(row)


def _merge_pending_spans(payload: PersistRuntimePayload) -> None:
    if not payload.drain_spans:
        return
    pending = drain_pending_spans()
    if pending:
        payload.execution_spans = list(payload.execution_spans) + pending


def _has_intelligence_data(payload: PersistRuntimePayload) -> bool:
    return bool(
        payload.execution_spans
        or payload.cognitive_telemetry
        or payload.runtime_health
        or payload.prompt_lineage
        or payload.runtime_anomalies
        or payload.session_diagnostics
    )


async def _persist_intelligence(conn: Any, payload: PersistRuntimePayload) -> None:
    if not _has_intelligence_data(payload):
        return
    from core.intelligence_persist import apply_intelligence_memory, persist_intelligence_postgres

    if isinstance(conn, MemoryConnection):
        apply_intelligence_memory(payload)
    else:
        await persist_intelligence_postgres(conn, payload)


async def _build_session_diagnostics_only(conn: Any, payload: PersistRuntimePayload) -> None:
    if payload.session_diagnostics is not None:
        return
    from core.session_diagnostics import build_session_diagnostics

    payload.session_diagnostics = await build_session_diagnostics(
        payload.session_id,
        payload.correlation_id,
        conn=conn,
    )


async def _persist_replay_baseline(conn: Any, payload: PersistRuntimePayload) -> None:
    from core.replay_validator import build_canonical_outcome
    from core.replay_version import ORCHESTRATOR_VERSION
    from schemas.replay import outcome_fingerprint

    outcome = await build_canonical_outcome(payload.session_id, payload.correlation_id, conn=conn)
    fp = outcome_fingerprint(outcome)

    if isinstance(conn, MemoryConnection):
        from core.replay_store import save_baseline_record_memory

        save_baseline_record_memory(
            payload.session_id,
            payload.correlation_id,
            fp,
            ORCHESTRATOR_VERSION,
        )
        return

    await conn.execute(
        """
        INSERT INTO replay_baselines
        (session_id, correlation_id, outcome_fingerprint, orchestrator_version, created_at)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (session_id) DO UPDATE SET
            outcome_fingerprint = EXCLUDED.outcome_fingerprint,
            orchestrator_version = EXCLUDED.orchestrator_version
        """,
        payload.session_id,
        payload.correlation_id,
        fp,
        ORCHESTRATOR_VERSION,
        datetime.now(timezone.utc),
    )


async def _complete_session_close(conn: Any, payload: PersistRuntimePayload) -> None:
    """Baseline + diagnostics materialization before final intelligence persist."""
    await _persist_replay_baseline(conn, payload)
    await _build_session_diagnostics_only(conn, payload)


async def persist_runtime_tx(conn: Any, payload: PersistRuntimePayload) -> PersistResult:
    """Persist on the active connection — no internal pool.acquire or locks."""
    world = get_world_state()
    idem = _idempotency_key(
        payload.correlation_id,
        payload.event_type,
        payload.event_payload,
        payload.business_key,
    )
    event = OutboxEvent(
        id=str(uuid4()),
        idempotency_key=idem,
        correlation_id=payload.correlation_id,
        causation_id=payload.causation_id,
        event_type=payload.event_type,
        payload=payload.event_payload,
        world_state_version=world.version,
        created_at=datetime.now(timezone.utc),
    )

    world_snap: WorldStateSnapshot | None = None
    if payload.update_world:
        new_state = world.model_copy(deep=True)
        new_state.version = world.version + 1
        world_snap = WorldStateSnapshot.from_state(new_state, payload.world_changed_entities)

    is_session_close = (
        payload.store_replay_baseline and payload.event_type == "session.completed"
    )

    if isinstance(conn, MemoryConnection):
        existing_mem = get_memory_outbox_by_idempotency(idem)
        if existing_mem:
            _merge_pending_spans(payload)
            if is_session_close:
                await _complete_session_close(conn, payload)
            await _persist_intelligence(conn, payload)
            return PersistResult(event=existing_mem, inserted=False)
        _merge_pending_spans(payload)
        if is_session_close:
            await _complete_session_close(conn, payload)
        apply_memory_runtime_persist(payload, event, world_snap)
        return PersistResult(event=event, inserted=True)

    existing = await _fetch_outbox_by_idempotency(conn, idem)
    if existing:
        _merge_pending_spans(payload)
        await _persist_intelligence(conn, payload)
        return PersistResult(event=existing, inserted=False)

    _merge_pending_spans(payload)

    if world_snap:
        await conn.execute(
            """
            INSERT INTO world_state_snapshots (version, timestamp, changed_entities, checksum, state)
            VALUES ($1, $2, $3::jsonb, $4, $5::jsonb)
            ON CONFLICT (version) DO UPDATE SET state = EXCLUDED.state
            """,
            world_snap.version,
            world_snap.timestamp,
            json.dumps(world_snap.changed_entities or []),
            world_snap.checksum,
            json.dumps(world_snap.state.model_dump(mode="json")),
        )
    if payload.decision:
        await conn.execute(
            """
            INSERT INTO decision_records (id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            ON CONFLICT (id) DO NOTHING
            """,
            payload.decision.id,
            payload.decision.correlation_id,
            payload.decision.model_dump_json(),
            payload.decision.created_at,
        )
    if payload.side_effect:
        await conn.execute(
            """
            INSERT INTO side_effect_records (id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            ON CONFLICT (id) DO NOTHING
            """,
            payload.side_effect.id,
            payload.side_effect.correlation_id,
            payload.side_effect.model_dump_json(),
            payload.side_effect.created_at,
        )
    await conn.execute(
        """
        INSERT INTO outbox_events
        (id, idempotency_key, correlation_id, causation_id, event_type, payload, world_state_version, processed, created_at)
        VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,FALSE,$8)
        """,
        event.id,
        event.idempotency_key,
        event.correlation_id,
        event.causation_id,
        event.event_type,
        json.dumps(event.payload),
        world_snap.version if world_snap else event.world_state_version,
        event.created_at,
    )
    if payload.replay_snapshot is not None and payload.replay_step is not None:
        await conn.execute(
            """
            INSERT INTO replay_snapshots (session_id, correlation_id, step, data)
            VALUES ($1,$2,$3,$4::jsonb)
            ON CONFLICT (session_id, step) DO UPDATE SET data = EXCLUDED.data
            """,
            payload.session_id,
            payload.correlation_id,
            payload.replay_step,
            json.dumps(payload.replay_snapshot),
        )
    if payload.retry_trace:
        await conn.execute(
            """
            INSERT INTO structured_retry_traces
            (correlation_id, session_id, agent_id, step_id, data, created_at)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6)
            ON CONFLICT (correlation_id, session_id, agent_id, step_id)
            DO UPDATE SET data = EXCLUDED.data
            """,
            payload.retry_trace.correlation_id,
            payload.retry_trace.session_id,
            payload.retry_trace.agent_id,
            payload.retry_trace.step_id,
            payload.retry_trace.model_dump_json(),
            payload.retry_trace.created_at,
        )
    if payload.runtime_transition:
        await conn.execute(
            """
            INSERT INTO runtime_transitions (correlation_id, session_id, from_state, to_state, created_at)
            VALUES ($1,$2,$3,$4,$5)
            """,
            payload.runtime_transition.correlation_id,
            payload.runtime_transition.session_id,
            payload.runtime_transition.from_state,
            payload.runtime_transition.to_state,
            datetime.now(timezone.utc),
        )

    if is_session_close:
        await _complete_session_close(conn, payload)

    await _persist_intelligence(conn, payload)

    return PersistResult(event=event, inserted=True)
