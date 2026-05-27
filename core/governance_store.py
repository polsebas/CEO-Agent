"""Governance persistence — Postgres source of truth for approvals and audit."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.canonical import stable_hash
from core.runtime_session import MemoryConnection
from schemas.approvals import Approval, ApprovalStatus, ImmutableActionProposal


_in_memory_approvals: dict[str, Approval] = {}
_in_memory_audit: list[dict] = []


async def append_audit_event(
    conn: Any,
    *,
    event_type: str,
    actor: str,
    correlation_id: str,
    payload: dict,
) -> None:
    record = {
        "id": str(uuid4()),
        "event_type": event_type,
        "actor": actor,
        "correlation_id": correlation_id,
        "payload_hash": stable_hash(payload),
        "created_at": datetime.now(timezone.utc),
    }
    if isinstance(conn, MemoryConnection):
        _in_memory_audit.append(record)
        return
    await conn.execute(
        """
        INSERT INTO governance_audit_events (id, event_type, actor, correlation_id, payload_hash, created_at)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        record["id"],
        record["event_type"],
        record["actor"],
        record["correlation_id"],
        record["payload_hash"],
        record["created_at"],
    )


async def save_approval(conn: Any, approval: Approval) -> None:
    data = approval.model_dump(mode="json")
    if isinstance(conn, MemoryConnection):
        _in_memory_approvals[approval.id] = approval
        return
    action_hash = approval.binding.action_hash if approval.binding else ""
    await conn.execute(
        """
        INSERT INTO approvals (id, correlation_id, action_hash, data, status, created_at)
        VALUES ($1,$2,$3,$4::jsonb,$5,$6)
        ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, status = EXCLUDED.status
        """,
        approval.id,
        approval.correlation_id,
        action_hash,
        json.dumps(data),
        approval.status.value,
        datetime.now(timezone.utc),
    )


async def load_approval(conn: Any, approval_id: str) -> Approval | None:
    if isinstance(conn, MemoryConnection):
        return _in_memory_approvals.get(approval_id)
    row = await conn.fetchrow("SELECT data FROM approvals WHERE id = $1", approval_id)
    if not row:
        return None
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    return Approval.model_validate(data)


async def update_approval_status(
    conn: Any,
    approval_id: str,
    status: ApprovalStatus,
    *,
    approved_by: str | None = None,
) -> Approval | None:
    approval = await load_approval(conn, approval_id)
    if not approval:
        return None
    approval.status = status
    if approved_by:
        approval.approved_by = approved_by
        approval.approved_at = datetime.now(timezone.utc)
    await save_approval(conn, approval)
    return approval


async def list_approvals_by_correlation(conn: Any, correlation_id: str) -> list[Approval]:
    if isinstance(conn, MemoryConnection):
        return [a for a in _in_memory_approvals.values() if a.correlation_id == correlation_id]
    rows = await conn.fetch(
        "SELECT data FROM approvals WHERE correlation_id = $1 ORDER BY created_at ASC",
        correlation_id,
    )
    result = []
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        result.append(Approval.model_validate(data))
    return result


async def list_pending_approvals(conn: Any | None = None) -> list[Approval]:
    from core.config import settings

    if settings.use_in_memory_store or isinstance(conn, MemoryConnection):
        return [a for a in _in_memory_approvals.values() if a.status == ApprovalStatus.PENDING]
    if conn is None:
        from core.persistence import get_pool

        pool = await get_pool()
        if pool:
            async with pool.acquire() as c:
                return await list_pending_approvals(c)
        return []
    rows = await conn.fetch(
        "SELECT data FROM approvals WHERE status = $1 ORDER BY created_at ASC",
        ApprovalStatus.PENDING.value,
    )
    return [Approval.model_validate(json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]) for r in rows]


def reset_governance_memory() -> None:
    _in_memory_approvals.clear()
    _in_memory_audit.clear()
