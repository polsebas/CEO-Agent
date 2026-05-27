"""User roles for RBAC."""

from enum import Enum


class UserRole(str, Enum):
    FOUNDER = "founder"
    ADMIN = "admin"
    OPERATOR = "operator"
    READONLY = "readonly"


ROLE_HIERARCHY = {
    UserRole.READONLY: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
    UserRole.FOUNDER: 3,
}
