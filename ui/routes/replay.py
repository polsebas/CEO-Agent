"""Replay inspector UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from api.auth import AuthContext
from schemas.runtime import ReplayMode
from ui.deps import nav_items, require_ui_auth
from ui.services.human_labels import badge_class, icon_char
from ui.services.query_facade import ui_query_facade
from ui.templates_env import templates

router = APIRouter()


@router.get("/sessions/{session_id}/replay", response_class=HTMLResponse)
async def replay_view(
    request: Request,
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    correlation_id: str = Query(...),
    mode: ReplayMode = Query(ReplayMode.FROZEN),
):
    detail = await ui_query_facade.get_session_detail(session_id, correlation_id, auth=auth)
    replay = await ui_query_facade.get_replay_state(
        session_id, correlation_id, auth=auth, mode=mode
    )
    return templates.TemplateResponse(
        request,
        "replay.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "detail": detail,
            "replay": replay,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "mode": mode.value,
            "badge_class": badge_class,
            "icon_char": icon_char,
        },
    )
