"""Session list, detail, timeline, founder request."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from api.auth import AuthContext
from core.orchestrator import manual_orchestrator
from core.permissions import Permission
from core.rbac import role_has_permission
from core.preprocessor import preprocessor
from schemas.session_summary import SessionListFilters
from ui.deps import nav_items, require_ui_auth
from ui.services.human_labels import badge_class, icon_char
from ui.services.query_facade import ui_query_facade
from ui.templates_env import templates

router = APIRouter()


@router.get("/sessions", response_class=HTMLResponse)
async def session_list(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    search: str | None = None,
    degraded_only: bool = False,
):
    filters = SessionListFilters(search=search, degraded_only=degraded_only, limit=100)
    sessions = await ui_query_facade.list_sessions(filters=filters, auth=auth)
    return templates.TemplateResponse(
        request,
        "sessions_list.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "sessions": sessions,
            "search": search or "",
            "degraded_only": degraded_only,
        },
    )


@router.get("/sessions/new", response_class=HTMLResponse)
async def founder_form(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
):
    if not role_has_permission(auth.role, Permission.FOUNDER_REQUEST):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "founder_form.html",
        {"request": request, "auth": auth, "nav_items": nav_items(auth)},
    )


@router.post("/ui/founder/request")
async def founder_submit(
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    message: Annotated[str, Form()],
    session_id: Annotated[str | None, Form()] = None,
    correlation_id: Annotated[str | None, Form()] = None,
):
    if not role_has_permission(auth.role, Permission.FOUNDER_REQUEST):
        return RedirectResponse("/", status_code=303)
    pre = preprocessor.process(message)
    preprocessor_hint = None
    result = await manual_orchestrator.run_founder_request(
        message,
        session_id=session_id or None,
        correlation_id=correlation_id or None,
        preprocessor_hint=preprocessor_hint,
    )
    sid = result.get("session_id", session_id or "unknown")
    cid = result.get("correlation_id", correlation_id or sid)
    return RedirectResponse(f"/sessions/{sid}?correlation_id={cid}", status_code=303)


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(
    request: Request,
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    correlation_id: str = Query(...),
    tab: str = "timeline",
):
    detail = await ui_query_facade.get_session_detail(session_id, correlation_id, auth=auth)
    timeline = await ui_query_facade.get_timeline_events(session_id, correlation_id, auth=auth)
    return templates.TemplateResponse(
        request,
        "session_detail.html",
        {
            "request": request,
            "auth": auth,
            "nav_items": nav_items(auth),
            "detail": detail,
            "timeline": timeline,
            "tab": tab,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "badge_class": badge_class,
            "icon_char": icon_char,
            "can_export": role_has_permission(auth.role, Permission.DIAGNOSTICS_READ),
        },
    )


@router.get("/sessions/{session_id}/timeline", response_class=HTMLResponse)
async def session_timeline_partial(
    request: Request,
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    correlation_id: str = Query(...),
):
    timeline = await ui_query_facade.get_timeline_events(session_id, correlation_id, auth=auth)
    return templates.TemplateResponse(
        request,
        "partials/timeline.html",
        {
            "request": request,
            "timeline": timeline,
            "session_id": session_id,
            "correlation_id": correlation_id,
        },
    )


@router.get("/sessions/{session_id}/export")
async def session_export(
    session_id: str,
    auth: Annotated[AuthContext, Depends(require_ui_auth)],
    correlation_id: str = Query(...),
):
    import json

    bundle = await ui_query_facade.build_session_bundle(session_id, correlation_id, auth=auth)
    content = json.dumps(bundle, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}-bundle.json"'},
    )
