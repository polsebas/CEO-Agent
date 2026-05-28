"""Persist RRM-3 adaptive layer entities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from core.intelligence_store import (
    append_adaptive_policy,
    append_context_priority_snapshot,
    append_governance_events,
    append_stability_events,
    upsert_tool_profile,
)
from core.runtime_session import MemoryConnection
from schemas.adaptive import AdaptivePolicySnapshot
from schemas.context import ContextPriorityScore
from schemas.governance_runtime import AdaptiveGovernanceEvent
from schemas.tools import ToolReliabilityProfile

from core.session_stability import SessionStabilityEvent


def _has_adaptive_data(payload) -> bool:
    return bool(
        payload.adaptive_policy_snapshot
        or payload.tool_reliability_updates
        or payload.context_priority_scores
        or payload.stability_events
        or payload.governance_events
    )


def apply_adaptive_memory(payload) -> None:
    if payload.adaptive_policy_snapshot:
        append_adaptive_policy(payload.adaptive_policy_snapshot)
    for profile in payload.tool_reliability_updates or []:
        upsert_tool_profile(profile)
    if payload.context_priority_scores:
        append_context_priority_snapshot(
            payload.session_id,
            payload.correlation_id,
            payload.context_priority_scores,
        )
    if payload.stability_events:
        append_stability_events(payload.stability_events)
    if payload.governance_events:
        append_governance_events(payload.governance_events)


async def persist_adaptive_postgres(conn: Any, payload) -> None:
    now = datetime.now(timezone.utc)
    if payload.adaptive_policy_snapshot:
        snap = payload.adaptive_policy_snapshot
        await conn.execute(
            """
            INSERT INTO adaptive_policies
            (session_id, correlation_id, signals_hash, policy_hash, data, created_at)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6)
            """,
            snap.session_id,
            snap.correlation_id,
            snap.signals_hash,
            snap.policy_hash,
            snap.model_dump_json(),
            snap.created_at,
        )
    for profile in payload.tool_reliability_updates or []:
        await conn.execute(
            """
            INSERT INTO tool_reliability_profiles (tool_name, data, updated_at)
            VALUES ($1,$2::jsonb,$3)
            ON CONFLICT (tool_name) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
            """,
            profile.tool_name,
            profile.model_dump_json(),
            profile.updated_at,
        )
    if payload.context_priority_scores:
        await conn.execute(
            """
            INSERT INTO context_priority_snapshots (session_id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            """,
            payload.session_id,
            payload.correlation_id,
            json.dumps([s.model_dump() for s in payload.context_priority_scores]),
            now,
        )
    for ev in payload.stability_events or []:
        await conn.execute(
            """
            INSERT INTO session_stability_events (session_id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            """,
            ev.session_id,
            ev.correlation_id,
            ev.model_dump_json(),
            ev.created_at,
        )
    for gev in payload.governance_events or []:
        await conn.execute(
            """
            INSERT INTO adaptive_governance_events (session_id, correlation_id, data, created_at)
            VALUES ($1,$2,$3::jsonb,$4)
            """,
            gev.session_id,
            gev.correlation_id,
            gev.model_dump_json(),
            gev.created_at,
        )


async def persist_adaptive(conn: Any, payload) -> None:
    if not _has_adaptive_data(payload):
        return
    if isinstance(conn, MemoryConnection):
        apply_adaptive_memory(payload)
    else:
        await persist_adaptive_postgres(conn, payload)
