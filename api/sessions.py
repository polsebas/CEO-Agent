"""Session listing API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.auth import AuthContext
from core.permissions import Permission
from core.rbac import require_permission
from core.session_list import list_session_summaries
from schemas.session_summary import SessionListFilters

router = APIRouter(prefix="/api/v1", tags=["sessions"])


@router.get("/sessions")
async def list_sessions(
    auth: Annotated[AuthContext, Depends(require_permission(Permission.SESSION_READ))],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    health: str | None = None,
    has_pending_approvals: bool | None = None,
    search: str | None = None,
    degraded_only: bool = False,
):
    filters = SessionListFilters(
        limit=limit,
        offset=offset,
        status=status,
        health=health,
        has_pending_approvals=has_pending_approvals,
        search=search,
        degraded_only=degraded_only,
    )
    rows = await list_session_summaries(filters)
    return [r.model_dump(mode="json") for r in rows]
