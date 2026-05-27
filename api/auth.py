"""JWT authentication and RBAC for API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.config import settings
from core.permissions import ROLE_PERMISSIONS
from core.roles import ROLE_HIERARCHY, UserRole

__all__ = ["AuthContext", "UserRole", "require_auth", "require_role", "create_test_token", "decode_token"]


security = HTTPBearer(auto_error=False)


class AuthContext(BaseModel):
    user_id: str
    role: UserRole
    scopes: list[str] = []


def _default_scopes(role: UserRole) -> list[str]:
    return [p.value for p in ROLE_PERMISSIONS.get(role, set())]


def _encode_token(user_id: str, role: UserRole, expires_hours: int = 24, scopes: list[str] | None = None) -> str:
    from jose import jwt

    payload = {
        "sub": user_id,
        "role": role.value,
        "scopes": scopes if scopes is not None else _default_scopes(role),
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> AuthContext:
    from jose import jwt

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    role_str = payload.get("role", "readonly")
    try:
        role = UserRole(role_str)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role") from exc
    scopes = payload.get("scopes") or _default_scopes(role)
    return AuthContext(user_id=payload.get("sub", "unknown"), role=role, scopes=scopes)


async def require_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security)],
) -> AuthContext:
    if settings.auth_disabled:
        return AuthContext(user_id="dev-user", role=UserRole.FOUNDER, scopes=_default_scopes(UserRole.FOUNDER))
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return decode_token(credentials.credentials)


def require_role(min_role: UserRole):
    async def _checker(auth: Annotated[AuthContext, Depends(require_auth)]) -> AuthContext:
        if ROLE_HIERARCHY[auth.role] < ROLE_HIERARCHY[min_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return auth

    return _checker


def create_test_token(user_id: str = "test-founder", role: UserRole = UserRole.FOUNDER) -> str:
    """Helper for tests and local dev."""
    return _encode_token(user_id, role)
