"""Diagnostics API — read-only session introspection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.auth import AuthContext
from core.diagnostics import diagnostics_service
from core.permissions import Permission
from core.rbac import require_permission
from schemas.runtime import ReplayMode

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/sessions/{session_id}/health")
async def session_health(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    return await diagnostics_service.get_health(session_id)


@router.get("/sessions/{session_id}/spans")
async def session_spans(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
    correlation_id: str | None = Query(None),
):
    return await diagnostics_service.get_spans(session_id, correlation_id=correlation_id)


@router.get("/sessions/{session_id}/telemetry")
async def session_telemetry(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
    correlation_id: str | None = Query(None),
):
    return await diagnostics_service.get_telemetry(session_id, correlation_id=correlation_id)


@router.get("/sessions/{session_id}/context")
async def session_context(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
):
    return await diagnostics_service.get_context(session_id)


@router.get("/sessions/{session_id}/diagnostics")
async def session_diagnostics(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
    correlation_id: str = Query(...),
):
    diag = await diagnostics_service.get_diagnostics(session_id, correlation_id)
    return diag.model_dump()


@router.get("/replay/{session_id}/analysis")
async def replay_analysis(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.DIAGNOSTICS_READ))],
    correlation_id: str = Query(...),
    mode: ReplayMode = Query(ReplayMode.FROZEN),
):
    analytics = await diagnostics_service.get_replay_analysis(
        session_id, correlation_id, mode=mode
    )
    return analytics.model_dump()
