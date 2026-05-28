"""Dashboard route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from api.auth import AuthContext
from ui.deps import nav_items, require_ui_auth
from ui.services.query_facade import ui_query_facade
from ui.templates_env import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
):
    state = await ui_query_facade.get_dashboard_state(auth=auth)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "state": state,
        },
    )
