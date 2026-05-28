"""Session index for operational UI and API listing."""

from __future__ import annotations

from datetime import datetime, timezone

from core.persistence import get_events_by_correlation, get_runtime_transitions, query_session_diagnostics_row
from core.policy import policy_engine
from schemas.diagnostics import SessionDiagnostics
from schemas.session_summary import SessionListFilters, SessionSummary


async def _founder_message(correlation_id: str) -> str | None:
    events = await get_events_by_correlation(correlation_id)
    for event in events:
        if event.event_type == "founder.intent":
            msg = event.payload.get("message")
            return str(msg) if msg else None
    return None


async def _runtime_state(session_id: str) -> str:
    transitions = await get_runtime_transitions(session_id)
    if transitions:
        last = transitions[-1]
        return last.get("to_state") or last.get("to") or "unknown"
    return "unknown"


async def _pending_count_by_correlation() -> dict[str, int]:
    pending = await policy_engine.list_pending_approvals()
    counts: dict[str, int] = {}
    for approval in pending:
        cid = approval.correlation_id
        counts[cid] = counts.get(cid, 0) + 1
    return counts


def _summary_from_diagnostics(
    diag: SessionDiagnostics,
    *,
    founder_request: str | None,
    runtime_state: str,
    pending_approvals: int,
    updated_at: datetime | None = None,
) -> SessionSummary:
    health = diag.runtime_health
    health_status = health.health_band.value if health else "healthy"
    degraded = health.degraded_mode_active if health else False
    replay_confidence = health.replay_confidence if health else 1.0
    ts = updated_at
    if ts is None and health:
        ts = health.generated_at
    if ts is None:
        ts = datetime.now(timezone.utc)
    return SessionSummary(
        session_id=diag.session_id,
        correlation_id=diag.correlation_id,
        founder_request=founder_request,
        runtime_state=runtime_state,
        health_status=health_status,
        degraded=degraded,
        replay_confidence=replay_confidence,
        pending_approvals=pending_approvals,
        updated_at=ts,
    )


async def _load_all_diagnostics_rows() -> list[tuple[SessionDiagnostics, datetime | None]]:
    from core.config import settings
    from core.intelligence_store import list_all_session_diagnostics
    from core.runtime_session import MemoryConnection

    if settings.use_in_memory_store:
        rows = []
        for diag in list_all_session_diagnostics():
            rows.append((diag, diag.runtime_health.generated_at if diag.runtime_health else None))
        return rows

    from core.persistence import get_pool

    pool = await get_pool()
    if not pool:
        return []
    async with pool.acquire() as conn:
        db_rows = await conn.fetch(
            """
            SELECT session_id, correlation_id, data, created_at
            FROM session_diagnostics
            ORDER BY created_at DESC
            """
        )
        result = []
        for row in db_rows:
            from core.persistence import _json_data

            data = _json_data(row["data"])
            diag = SessionDiagnostics.model_validate(data)
            result.append((diag, row["created_at"]))
        return result


def _matches_filters(
    summary: SessionSummary,
    filters: SessionListFilters,
) -> bool:
    if filters.degraded_only and not summary.degraded:
        return False
    if filters.status and filters.status.lower() not in summary.runtime_state.lower():
        return False
    if filters.health and filters.health.lower() != summary.health_status.lower():
        return False
    if filters.has_pending_approvals is True and summary.pending_approvals == 0:
        return False
    if filters.has_pending_approvals is False and summary.pending_approvals > 0:
        return False
    if filters.search:
        q = filters.search.lower()
        haystack = " ".join(
            filter(
                None,
                [
                    summary.session_id,
                    summary.correlation_id,
                    summary.founder_request or "",
                    summary.runtime_state,
                ],
            )
        ).lower()
        if q not in haystack:
            return False
    return True


async def list_session_summaries(filters: SessionListFilters | None = None) -> list[SessionSummary]:
    filters = filters or SessionListFilters()
    pending_counts = await _pending_count_by_correlation()
    rows = await _load_all_diagnostics_rows()
    summaries: list[SessionSummary] = []

    for diag, created_at in rows:
        founder = await _founder_message(diag.correlation_id)
        runtime_state = await _runtime_state(diag.session_id)
        pending = pending_counts.get(diag.correlation_id, 0)
        summary = _summary_from_diagnostics(
            diag,
            founder_request=founder,
            runtime_state=runtime_state,
            pending_approvals=pending,
            updated_at=created_at,
        )
        if _matches_filters(summary, filters):
            summaries.append(summary)

    summaries.sort(key=lambda s: s.updated_at, reverse=True)
    start = filters.offset
    end = start + filters.limit
    return summaries[start:end]
