"""RBAC FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.auth import AuthContext, require_auth
from core.permissions import APPROVAL_LEVEL_BY_ROLE, ROLE_PERMISSIONS
from core.permissions import Permission


def role_has_permission(role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def can_approve_level(role, required_level: int) -> bool:
    return APPROVAL_LEVEL_BY_ROLE.get(role, 0) >= required_level


def validate_scopes(role, scopes: list[str]) -> None:
    allowed = {p.value for p in ROLE_PERMISSIONS.get(role, set())}
    for scope in scopes:
        if scope not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope {scope} not allowed for role {role.value}",
            )


def require_permission(permission: Permission):
    async def _checker(auth: Annotated[AuthContext, Depends(require_auth)]) -> AuthContext:
        if auth.scopes:
            validate_scopes(auth.role, auth.scopes)
        if not role_has_permission(auth.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission.value}",
            )
        return auth

    return _checker
