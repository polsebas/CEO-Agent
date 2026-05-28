"""UI FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth import AuthContext, decode_token, require_auth
from core.config import settings
from core.permissions import ROLE_PERMISSIONS

security = HTTPBearer(auto_error=False)
COOKIE_NAME = "ceo_token"


async def require_ui_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthContext:
    if settings.auth_disabled:
        from core.roles import UserRole

        from api.auth import _default_scopes

        return AuthContext(user_id="dev-user", role=UserRole.FOUNDER, scopes=_default_scopes(UserRole.FOUNDER))

    token = request.cookies.get(COOKIE_NAME)
    if not token and credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return decode_token(token)


def nav_items(auth: AuthContext) -> list[dict]:
    from core.permissions import Permission
    from core.rbac import role_has_permission

    items = []
    if role_has_permission(auth.role, Permission.SESSION_READ):
        items.append({"href": "/", "label": "Dashboard"})
        items.append({"href": "/sessions", "label": "Sessions"})
    if role_has_permission(auth.role, Permission.FOUNDER_REQUEST):
        items.append({"href": "/sessions/new", "label": "Execute"})
    if role_has_permission(auth.role, Permission.APPROVALS_READ):
        items.append({"href": "/approvals", "label": "Approvals"})
    return items
