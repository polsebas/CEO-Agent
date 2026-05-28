"""Diagnostics view UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from api.auth import AuthContext
from ui.deps import nav_items, require_ui_auth
from ui.services.human_labels import badge_class, icon_char
from ui.services.query_facade import ui_query_facade
from ui.templates_env import templates

router = APIRouter()


@router.get("/sessions/{session_id}/diagnostics", response_class=HTMLResponse)
async def diagnostics_view(
    request: Request,
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    correlation_id: str = Query(...),
):
    detail = await ui_query_facade.get_session_detail(session_id, correlation_id, auth=auth)
    data = await ui_query_facade.get_diagnostics_detail(session_id, correlation_id, auth=auth)
    return templates.TemplateResponse(
        request,
        "diagnostics.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "detail": detail,
            "data": data,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "badge_class": badge_class,
            "icon_char": icon_char,
        },
    )
